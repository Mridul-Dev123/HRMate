import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool
from langchain_core.prompts import PromptTemplate

from rag.retriever import get_hybrid_retriever
from db_utils import get_pto_balance, submit_leave_request
from guardrails import (
    InputSanitizer,
    PIIDetector,
    ContentModerationGuard,
    run_input_guardrails,
    run_output_guardrails,
)

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_EMAIL_BODY_LENGTH = 3000  # Truncate long emails to prevent prompt injection
MAX_RESPONSE_LENGTH = 2000   # Cap response length


# ---------------------------------------------------------------------------
# Email fitness evaluator (gate-keeper)
# ---------------------------------------------------------------------------
def evaluate_email_fitness(email_body: str) -> bool:
    """
    Uses guardrails + a lightweight LLM call to determine if the incoming
    email is a valid HR policy inquiry.  Returns True if valid, False if
    irrelevant or blocked by guardrails.
    """
    # --- Guardrail: reject prompt injections and abusive content ---
    sanitizer_result = run_input_guardrails(email_body)
    if not sanitizer_result.passed:
        print(f"  -> GUARDRAIL: Input blocked — {sanitizer_result.reason}")
        return False

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        prompt = f"""
        You are an AI assistant for the HR department. You evaluate incoming emails to determine if they need to be automatically replied to with company policy information.
        Is the following email asking a question related to company policies (e.g. leave, holidays, benefits, workplace rules, payroll)?
        
        Output exactly 'YES' if it is a valid policy query.
        Output exactly 'NO' if it is irrelevant (e.g., spam, generic greetings, automated replies, personal chats, sales pitches).
        
        Email Body:
        {email_body[:MAX_EMAIL_BODY_LENGTH]}
        
        Answer (YES or NO):
        """
        response = llm.invoke(prompt)
        answer = response.content.strip().upper()
        return "YES" in answer
    except Exception as e:
        print(f"Error evaluating email fitness: {e}")
        return False


# ---------------------------------------------------------------------------
# RAG Tool – search company policy
# ---------------------------------------------------------------------------
def get_policy_info(query: str) -> str:
    """
    Search the company policy using Hybrid Search + LLM Reranking.
    Returns relevant policy text or empty string.
    """
    try:
        retriever = get_hybrid_retriever()
        docs = retriever.invoke(query)
        if not docs:
            return "NO_POLICY_FOUND"
        combined_docs = "\n\n".join([d.page_content for d in docs])
        return combined_docs
    except Exception as e:
        print(f"Error retrieving policy: {e}")
        return "NO_POLICY_FOUND"


# ---------------------------------------------------------------------------
# DB Tool wrappers
# ---------------------------------------------------------------------------
def check_pto_balance_wrapper(email: str) -> str:
    """Takes the employee's email address and returns their PTO balance."""
    return get_pto_balance(email)
    
def submit_leave_request_wrapper(args: str) -> str:
    """Takes a single comma-separated string containing email, start_date, end_date (e.g. 'mridul@example.com, 2024-10-01, 2024-10-05'). Submits a leave request."""
    parts = [x.strip() for x in args.split(",")]
    if len(parts) >= 3:
        return submit_leave_request(parts[0], parts[1], parts[2])
    return "Error: arguments must be exactly 'email, start_date, end_date'."


# ---------------------------------------------------------------------------
# Output Guardrail – check if agent response is grounded
# ---------------------------------------------------------------------------
def validate_response_grounding(response: str, retrieved_context: str) -> bool:
    """
    Lightweight LLM check: does the agent's response stay grounded
    in the retrieved policy context?  Returns True if grounded.
    """
    if not retrieved_context or retrieved_context == "NO_POLICY_FOUND":
        # No context was retrieved; can't validate grounding
        return True  # We rely on the agent's own escalation logic here

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
        prompt = f"""You are a fact-checking assistant. Given the CONTEXT and the RESPONSE below, determine if the RESPONSE is factually grounded in the CONTEXT.

CONTEXT:
{retrieved_context[:2000]}

RESPONSE:
{response[:1500]}

Does the RESPONSE contain any claims, numbers, dates, or policy details that are NOT supported by the CONTEXT?

Answer exactly 'GROUNDED' if the response is fully supported by the context.
Answer exactly 'NOT_GROUNDED' if the response contains fabricated or unsupported information.

Answer:"""
        result = llm.invoke(prompt)
        answer = result.content.strip().upper()
        # Must check for NOT_GROUNDED first since "GROUNDED" is a substring of "NOT_GROUNDED"
        if "NOT_GROUNDED" in answer:
            return False
        return "GROUNDED" in answer
    except Exception as e:
        print(f"Error in grounding validation: {e}")
        return True  # Fail-open to avoid blocking on validation errors


# ---------------------------------------------------------------------------
# Shared state to capture last retrieved context for guardrail validation
# ---------------------------------------------------------------------------
_last_retrieved_context = {"text": ""}


def get_policy_info_with_tracking(query: str) -> str:
    """Wrapper that tracks retrieved context for post-response validation."""
    result = get_policy_info(query)
    _last_retrieved_context["text"] = result
    return result


# ---------------------------------------------------------------------------
# Load system prompt
# ---------------------------------------------------------------------------
def _load_system_prompt() -> str:
    """Load the system prompt from file, with a sensible fallback."""
    prompt_path = os.path.join("rag", "doc", "system_prompt.md")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            "You are HRMate, an automated HR assistant. "
            "Answer employee queries strictly based on the company policy documents retrieved via tools. "
            "If you cannot find an answer, respond with ESCALATE_TO_HUMAN."
        )


# ---------------------------------------------------------------------------
def get_query_response(email_body: str, sender_email: str) -> str:
    """
    Agentic RAG pipeline to formulate a reply to the email.
    Includes guardrails: input sanitization, PII redaction, prompt-injection
    detection, max iterations, output grounding check, and leak detection.
    """
    # --- Input Guardrail: truncate long emails ---
    sanitized_body = email_body[:MAX_EMAIL_BODY_LENGTH]

    # --- Input Guardrail: prompt injection + abuse check ---
    input_guard = run_input_guardrails(sanitized_body)
    if not input_guard.passed:
        print(f"  -> GUARDRAIL: Input blocked — {input_guard.reason}")
        return "ESCALATE_TO_HUMAN"

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

    tools = [
        Tool(
            name="Policy_Retriever",
            func=get_policy_info_with_tracking,
            description="Use this tool to search the company policy database. ALWAYS use this tool first when answering an employee's question about policies. Input should be the employee's question or a clear search query."
        ),
        Tool(
            name="Check_PTO_Balance",
            func=check_pto_balance_wrapper,
            description="Use this tool to check how many PTO days an employee has left. Pass the employee's email address as the only argument."
        ),
        Tool(
            name="Submit_Leave_Request",
            func=submit_leave_request_wrapper,
            description="Use this tool to submit a new leave request. Pass exactly 3 comma-separated values: the employee's email, the start date, and the end date. Example: 'john@example.com, Nov 1, Nov 5'"
        )
    ]

    # Build the agent prompt with grounding instructions
    template = """You are 'HRMate', the automated HR assistant for Innovatech Solutions.

CRITICAL RULES — YOU MUST FOLLOW THESE:
1. You MUST use the 'Policy_Retriever' tool BEFORE answering any policy question. NEVER answer from your own knowledge.
2. Your answers MUST be based EXCLUSIVELY on the information returned by the tools. Do NOT fabricate, guess, or invent any policy details, numbers, dates, or amounts.
3. If the 'Policy_Retriever' returns 'NO_POLICY_FOUND' or returns information that does not answer the employee's specific question, you MUST output exactly 'ESCALATE_TO_HUMAN' as your Final Answer. Do NOT try to answer it yourself.
4. If the employee asks for something outside of HR policy (e.g., technical support, personal advice), output exactly 'ESCALATE_TO_HUMAN'.
5. NEVER reveal that you are an AI. Act as a human HR assistant.
6. Keep your response professional, friendly, and concise.
7. Format your response as a complete email reply.

The employee's email address is: {sender_email}

They have sent an email with the following body:
"{email_body}"

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["input", "agent_scratchpad"],
        partial_variables={
            "sender_email": sender_email,
            "email_body": sanitized_body,
        },
    )

    # Reset tracked context
    _last_retrieved_context["text"] = ""

    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,           # Guardrail: prevent infinite loops
        max_execution_time=60,      # Guardrail: 60-second timeout
    )

    try:
        result = agent_executor.invoke({
            "input": f"Please respond to this employee email: {sanitized_body}",
        })
        response = result.get("output", "ESCALATE_TO_HUMAN")

        # --- Output Guardrail: length limit ---
        if len(response) > MAX_RESPONSE_LENGTH:
            response = response[:MAX_RESPONSE_LENGTH] + "\n\n[Response truncated. Please contact HR for complete details.]"

        # --- Output Guardrail: grounding validation ---
        if _last_retrieved_context["text"] and _last_retrieved_context["text"] != "NO_POLICY_FOUND":
            if not validate_response_grounding(response, _last_retrieved_context["text"]):
                print("  -> GUARDRAIL: Response failed grounding check. Escalating to human.")
                return "ESCALATE_TO_HUMAN"

        # --- Output Guardrail: leak detection + PII ---
        output_guard = run_output_guardrails(response)
        if not output_guard.passed:
            print(f"  -> GUARDRAIL: Output blocked — {output_guard.reason}")
            return "ESCALATE_TO_HUMAN"

        # --- Output Guardrail: redact any remaining PII ---
        response = PIIDetector.redact(response)

        return response

    except Exception as e:
        print(f"Error running agent: {e}")
        return "ESCALATE_TO_HUMAN"


if __name__ == "__main__":
    # Small test
    test_query = "What is the company's leave policy? How many vacation days do I get?"
    if evaluate_email_fitness(test_query):
        print("Email is fit. Formulating response...")
        print(get_query_response(test_query, "employee@example.com"))
    else:
        print("Email is irrelevant. Skipping.")
