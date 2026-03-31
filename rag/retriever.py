import os
import pickle
from typing import List, Sequence, Optional

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# LCEL-based Document Filter (replaces deprecated LLMChainFilter)
# ---------------------------------------------------------------------------
class LLMDocumentFilter:
    """
    Uses an LLM to evaluate whether each retrieved document is relevant
    to the user's query.  Replaces the deprecated LLMChainFilter.
    """

    def __init__(self, llm=None):
        self.llm = llm or ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are a relevance evaluator. Given a user question and a "
                "document, determine if the document is relevant to the question.\n"
                "Answer ONLY 'YES' or 'NO'."
            )),
            ("human", (
                "Question: {question}\n\n"
                "Document:\n{document}\n\n"
                "Is this document relevant? (YES/NO):"
            )),
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    def filter_documents(
        self, documents: List[Document], query: str
    ) -> List[Document]:
        """
        Evaluate each document against *query* and keep only relevant ones.
        """
        relevant: List[Document] = []
        for doc in documents:
            try:
                answer = self.chain.invoke({
                    "question": query,
                    "document": doc.page_content[:1500],
                })
                if "YES" in answer.strip().upper():
                    relevant.append(doc)
            except Exception as e:
                print(f"Error filtering document: {e}")
                # Fail-open: keep the document if we can't evaluate it
                relevant.append(doc)
        return relevant

from pydantic import ConfigDict


# ---------------------------------------------------------------------------
# Custom Compression Retriever (wraps EnsembleRetriever + LLM filter)
# ---------------------------------------------------------------------------
class FilteredEnsembleRetriever(BaseRetriever):
    """
    A retriever that combines BM25 + FAISS via EnsembleRetriever,
    then filters results using an LLM-based relevance check.
    """

    ensemble_retriever: EnsembleRetriever
    llm_filter: Optional[LLMDocumentFilter] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        # Step 1: Retrieve from ensemble
        docs = self.ensemble_retriever.invoke(query)

        # Step 2: LLM-based filtering
        if self.llm_filter and docs:
            docs = self.llm_filter.filter_documents(docs, query)

        return docs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_hybrid_retriever() -> FilteredEnsembleRetriever:
    """
    Builds and returns a hybrid retriever:
      BM25 + FAISS ensemble  →  LLM relevance filter
    """
    load_dotenv(override=True)

    # 1. Load BM25 Retriever
    store_path = os.path.join("rag", "bm25_store.pkl")
    if not os.path.exists(store_path):
        raise FileNotFoundError(
            f"BM25 store missing at {store_path}. Please run rag_runner.py first."
        )

    with open(store_path, "rb") as f:
        bm25_retriever = pickle.load(f)

    # 2. Setup FAISS Vector Store Retriever
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env")

    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    faiss_path = os.path.join("rag", "faiss_index")

    if not os.path.exists(faiss_path):
        raise FileNotFoundError(
            f"FAISS index missing at {faiss_path}. Please run rag_runner.py first."
        )

    # allow_dangerous_deserialization=True is required for FAISS local loading.
    vector_store = FAISS.load_local(
        faiss_path, embeddings, allow_dangerous_deserialization=True
    )
    faiss_retriever = vector_store.as_retriever(search_kwargs={"k": 5})

    # 3. Combine into Ensemble Retriever
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.5, 0.5],
    )

    # 4. LLM-based relevance filter (replaces deprecated LLMChainFilter)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    llm_filter = LLMDocumentFilter(llm=llm)

    return FilteredEnsembleRetriever(
        ensemble_retriever=ensemble_retriever,
        llm_filter=llm_filter,
    )
