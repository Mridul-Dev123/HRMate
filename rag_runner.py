from rag.chunker import chunk_file
from rag.vectorstore import upsert_chunk
from rag.embbeding import get_embeddings


def main():
    text=chunk_file(filepath="rag/doc/policy.txt",chunk_size=1000,chunk_overlap=200)
    for i,chunk in enumerate(text):
        values=get_embeddings(chunk)
        upsert_chunk(id=f"chunk_{i}",values=values,text=chunk)
        print(f"Chunk {i} upserted")

if __name__ == "__main__":
    main()
        
        
        

