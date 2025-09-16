from shlex import join
from pinecone.grpc import PineconeGRPC as Pinecone

import os
from dotenv import load_dotenv

def get_pinecone_client():
    load_dotenv(override=True)
    client=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return client

def upsert_chunk(id,values,text):
    client=get_pinecone_client()
    INDEX_HOST=os.getenv("PINECONE_INDEX_HOST")
    index = client.Index(host=INDEX_HOST)

    index.upsert(
    vectors=[
        {
        "id": id, 
        "values": values, 
        "metadata": {"text": text}
        }
    ]
    )

    return True


def query_vector(vector,top_k=10):
    client=get_pinecone_client()
    INDEX_HOST=os.getenv("PINECONE_INDEX_HOST")
    index = client.Index(host=INDEX_HOST)
    response = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
    )

    texts=[]
    for match in response.matches:
        texts.append(match.metadata["text"])
    return "\n".join(texts)



if __name__ == "__main__":
    client=get_pinecone_client()
    index_list = client.list_indexes()

    print(index_list)

