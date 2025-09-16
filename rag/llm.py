from openai import OpenAI
from dotenv import load_dotenv

import os

def get_openai_client():
    load_dotenv(override=True)
    api_key=os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def get_response(query,system_prompt):
    client=get_openai_client()
    response=client.responses.create(
        model="gpt-4.1",
        input=query,
        instructions=system_prompt)

    return response.output_text
