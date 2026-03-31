import os
import re
import pickle
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Section-aware metadata extraction
# ---------------------------------------------------------------------------
SECTION_PATTERN = re.compile(
    r"^Section\s+(\d+):\s*(.+)", re.MULTILINE
)
SUBSECTION_PATTERN = re.compile(
    r"^(\d+\.\d+(?:\.\d+)?)\s+(.+)", re.MULTILINE
)


def _detect_section_metadata(text: str) -> dict:
    """
    Scans chunk text for section/subsection headers and returns
    metadata dict with section number and title.
    """
    metadata = {}

    # Check for top-level "Section X: Title"
    section_match = SECTION_PATTERN.search(text)
    if section_match:
        metadata["section_number"] = section_match.group(1)
        metadata["section_title"] = section_match.group(2).strip()

    # Check for subsection "X.Y Title" or "X.Y.Z Title"
    subsection_match = SUBSECTION_PATTERN.search(text)
    if subsection_match:
        metadata["subsection"] = subsection_match.group(1)
        metadata["subsection_title"] = subsection_match.group(2).strip()

    return metadata


def _strip_citations(text: str) -> str:
    """
    Remove the 'Works cited' section at the bottom of the policy document,
    since citations are not actual policy content.
    """
    marker = "Works cited"
    idx = text.find(marker)
    if idx != -1:
        return text[:idx].rstrip()
    return text


# ---------------------------------------------------------------------------
# Two-stage section-aware chunking
# ---------------------------------------------------------------------------
def chunk_policy_document(docs: list[Document]) -> list[Document]:
    """
    Two-stage chunking strategy optimised for structured HR policy documents:

    Stage 1: Split at section/subsection boundaries using custom separators.
             Uses a larger chunk_size (2000) to keep full subsections intact.
             No overlap at this stage — sections are self-contained.

    Stage 2: If any chunk is still too large (>2000 chars), sub-split it
             with a smaller size and overlap to maintain context continuity.

    Each chunk is tagged with section metadata for citation.
    """
    # Combine all loaded docs into a single string and strip citations
    full_text = "\n".join(d.page_content for d in docs)
    full_text = _strip_citations(full_text)

    # ── Stage 1: Section-aware split ──────────────────────────────────
    stage1_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\nSection ",     # Top-level section boundaries
            "\n\n\n",         # Triple newline (large gaps between subsections)
            "\n\n",           # Double newline (paragraph boundaries)
            "\n",             # Single newline (last resort)
        ],
        chunk_size=2000,
        chunk_overlap=0,      # No overlap — sections are self-contained
        keep_separator=True,
    )

    # Wrap in a Document so the splitter can work
    raw_doc = Document(page_content=full_text, metadata={"source": "policy.txt"})
    stage1_chunks = stage1_splitter.split_documents([raw_doc])

    # ── Stage 2: Sub-split any oversized chunks ───────────────────────
    stage2_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
    )

    final_chunks: list[Document] = []
    for chunk in stage1_chunks:
        if len(chunk.page_content) > 2000:
            sub_chunks = stage2_splitter.split_documents([chunk])
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)

    # ── Enrich with section metadata ──────────────────────────────────
    for chunk in final_chunks:
        meta = _detect_section_metadata(chunk.page_content)
        chunk.metadata.update(meta)

    return final_chunks


# ---------------------------------------------------------------------------
# Main indexing pipeline
# ---------------------------------------------------------------------------
def main():
    load_dotenv(override=True)

    print("Loading document...")
    filepath = "rag/doc/policy.txt"
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    loader = TextLoader(filepath, encoding="utf-8")
    docs = loader.load()

    # ── Chunk with section-aware strategy ─────────────────────────────
    print("Splitting document with section-aware strategy...")
    splits = chunk_policy_document(docs)
    print(f"Created {len(splits)} chunks.")

    # Print chunk summary for verification
    for i, chunk in enumerate(splits):
        sec = chunk.metadata.get("subsection") or chunk.metadata.get("section_number", "?")
        title = chunk.metadata.get("subsection_title") or chunk.metadata.get("section_title", "")
        print(f"  Chunk {i:>2}: Section {sec:<6} | {len(chunk.page_content):>5} chars | {title[:50]}")

    # ── Save BM25 Retriever ───────────────────────────────────────────
    print("\nCreating and saving BM25 retriever...")
    bm25_retriever = BM25Retriever.from_documents(splits)

    store_path = os.path.join("rag", "bm25_store.pkl")
    with open(store_path, "wb") as f:
        pickle.dump(bm25_retriever, f)
    print(f"BM25 store saved to {store_path}")

    # ── Save FAISS Vector Store ───────────────────────────────────────
    print("Creating and saving FAISS vector store...")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Missing GOOGLE_API_KEY in .env")
        return

    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    vector_store = FAISS.from_documents(splits, embeddings)
    faiss_path = os.path.join("rag", "faiss_index")
    vector_store.save_local(faiss_path)
    print(f"FAISS index saved to {faiss_path}")

    print(f"\n[DONE] Indexing complete! {len(splits)} chunks indexed into BM25 + FAISS.")


if __name__ == "__main__":
    main()
