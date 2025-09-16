from openai import OpenAI
from dotenv import load_dotenv

import os

def get_openai_client():
    load_dotenv(override=True)
    api_key=os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def get_embeddings(text):
    client=get_openai_client()
    response = client.embeddings.create(
    input=text,
    model="text-embedding-3-large"
)
    # 3072
    return response.data[0].embedding

