from rag.llm import get_response
from rag.vectorstore import query_vector
from rag.embbeding import get_embeddings


import os



def get_query_response(query):
    
    vector=get_embeddings(query)
    text=query_vector(vector)
    
    filepath=os.path.join("rag", "doc", "system_prompt.md")
    with open(filepath, "r") as file:
        prompt = file.read()
    system_prompt=prompt

    Updated_query=f"<user_query>{query}</user_query>\n\n<policy_document>{text}</policy_document>"
    response=get_response(Updated_query,system_prompt)
    return response

if __name__ == "__main__":
    response=get_query_response("What is the leave policy of the company?")
    print(response)

