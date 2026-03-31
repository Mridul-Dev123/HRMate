import os
import pickle
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

def main():
    load_dotenv(override=True)
    
    print("Loading document...")
    filepath = "rag/doc/policy.txt"
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    loader = TextLoader(filepath, encoding="utf-8")
    docs = loader.load()
    
    print("Splitting document...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    print(f"Created {len(splits)} chunks.")
    
    print("Creating and saving BM25 retriever...")
    bm25_retriever = BM25Retriever.from_documents(splits)
    
    store_path = os.path.join("rag", "bm25_store.pkl")
    with open(store_path, "wb") as f:
        pickle.dump(bm25_retriever, f)
    print(f"BM25 store saved to {store_path}")
    
    print("Creating and saving FAISS vector store...")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Missing GOOGLE_API_KEY in .env")
        return

    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    vector_store = FAISS.from_documents(splits, embeddings)
    faiss_path = os.path.join("rag", "faiss_index")
    vector_store.save_local(faiss_path)
    print(f"FAISS index saved to {faiss_path}")

if __name__ == "__main__":
    main()
