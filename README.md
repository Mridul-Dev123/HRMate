# 🤝 HRMate

> An AI-powered, agentic HR assistant that automatically answers employee email queries using company policy documents — powered by RAG (Retrieval-Augmented Generation), Google Gemini, and a multi-layered guardrail system.

---

## 📖 How It Works

HRMate watches an email inbox for new messages from employees. When one arrives, it:

1. **Validates** the email through input guardrails (prompt injection detection, content moderation).
2. **Evaluates** whether the email is a genuine HR query using an LLM fitness check.
3. **Retrieves** the most relevant policy sections using **Hybrid Search** (BM25 + FAISS) with **LLM-based reranking**.
4. **Generates** a professional, policy-grounded email reply using Gemini via a ReAct agent.
5. **Validates** the response through output guardrails (grounding check, PII redaction, leak detection).
6. **Sends** the reply automatically back to the employee via SMTP, or **escalates** to human HR if needed.

```
Employee Email
      │
      ▼
  Input Guardrails ──► LLM Fitness Check ──► ReAct Agent
  (injection, abuse)                              │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              Policy_Retriever  Check_PTO   Submit_Leave
                              (BM25 + FAISS     Balance     Request
                               + LLM Rerank)
                                    │
                                    ▼
                            Output Guardrails
                         (grounding, PII, leaks)
                                    │
                              ┌─────┴─────┐
                              ▼           ▼
                        Auto-Reply    Escalate to
                        via SMTP      Human HR
```

---

## 🗂️ Project Structure

```
HRMate/
├── main.py              # Core email polling loop — reads inbox & sends AI replies
├── llm_runner.py         # Agentic RAG pipeline: ReAct agent with tools & guardrails
├── guardrails.py         # Input/output guardrail classes (injection, PII, moderation, leaks)
├── db_utils.py           # SQLite helpers: analytics logging, PTO balance, leave requests
├── rag_runner.py         # One-time script to chunk & index the policy document
├── requirements.txt      # Python dependencies
├── rag/
│   ├── retriever.py      # Hybrid retriever: BM25 + FAISS ensemble → LLM relevance filter
│   └── doc/
│       ├── policy.txt           # Company HR policy document
│       └── system_prompt.md     # Prompt template that governs the AI's behaviour
└── tests/
    ├── conftest.py        # Shared pytest fixtures (temp DB, monkeypatching)
    ├── test_db_utils.py   # Unit tests for database utilities
    ├── test_guardrails.py # Unit tests for all guardrail classes
    └── test_llm_runner.py # Unit tests for LLM pipeline (mocked, no API calls)
```

---

## 🛡️ Guardrails

HRMate implements a **multi-layered guardrail system** to ensure safe, accurate, and professional responses:

### Input Guardrails
| Guardrail | Description |
|-----------|-------------|
| **InputSanitizer** | Detects prompt injection attempts (jailbreaks, "ignore instructions", XSS, DAN) |
| **ContentModerationGuard** | Flags abusive or threatening language |
| **Email Truncation** | Caps input at 3,000 characters to prevent prompt stuffing |

### Output Guardrails
| Guardrail | Description |
|-----------|-------------|
| **Grounding Validation** | LLM check to ensure the response is factually grounded in retrieved policy |
| **ResponseValidator** | Detects leaked API keys, system prompts, or raw agent traces |
| **PIIDetector** | Detects and redacts SSNs, credit cards, phone numbers from responses |
| **Length Limit** | Caps response at 2,000 characters |

### Agent Guardrails
| Guardrail | Description |
|-----------|-------------|
| **Max Iterations** | Agent limited to 5 reasoning steps to prevent infinite loops |
| **Execution Timeout** | 60-second hard timeout on agent execution |
| **Escalation** | Automatic escalation to human HR when confidence is low |

---

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/HRMate.git
cd HRMate
```

### 2. Create & activate virtual environment

```bash
python -m venv myenv

# Windows
myenv\Scripts\activate

# macOS/Linux
source myenv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
# Email credentials
EMAIL_USER=your-email@example.com
EMAIL_PASS=your-app-password

# IMAP & SMTP servers (example: Gmail)
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com

# Google Gemini
GOOGLE_API_KEY=your-google-api-key
```

> **Gmail users**: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password, and enable IMAP in Gmail settings.

### 5. Add your HR policy document

Place your company's policy as plain text at `rag/doc/policy.txt`.

### 6. Index the policy document

Run this **once** (or whenever the policy changes):

```bash
python rag_runner.py
```

This chunks the document, generates embeddings via Google's `text-embedding-004` model, and creates both a BM25 index and a FAISS vector store locally.

### 7. Start the auto-reply bot

```bash
python main.py
```

The bot will poll the inbox every 2 seconds and automatically reply to any unread emails.
Press `Ctrl+C` to stop.

---

## 🧪 Testing

HRMate includes a comprehensive test suite with **63 tests** covering all modules. Tests use mocks — no real API calls or email connections needed.

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_guardrails.py -v
python -m pytest tests/test_db_utils.py -v
python -m pytest tests/test_llm_runner.py -v
```

### Test Coverage

| Module | Tests | What's Covered |
|--------|-------|----------------|
| `test_db_utils.py` | 11 | Table creation, seed idempotency, logging, PTO balance, leave requests |
| `test_guardrails.py` | 35 | Prompt injection (9 patterns), PII detection/redaction, content moderation, response validation, composite runners |
| `test_llm_runner.py` | 17 | Email fitness eval, policy retrieval, grounding validation, tool wrappers, end-to-end agent pipeline |

---

## 🧠 AI Behaviour

The assistant is guided by the system prompt in `rag/doc/system_prompt.md`:

- **Strictly policy-based**: All answers are drawn exclusively from the retrieved policy chunks — no hallucination.
- **Anti-hallucination rules**: Never fabricates numbers, dates, amounts, or policy details. References section numbers when quoting policy.
- **Professional & friendly**: Replies are warm, concise, and ready to send as-is.
- **Graceful fallback**: If the policy doesn't cover a query, the bot escalates to human HR rather than guessing.
- **Agentic tools**: The agent can check PTO balances and submit leave requests via database tools.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| LLM | Google Gemini 2.0 Flash |
| Embeddings | Google `text-embedding-004` |
| Vector Database | FAISS (local) |
| Keyword Search | BM25 (via `rank_bm25`) |
| Retrieval Strategy | Hybrid Ensemble (BM25 + FAISS) → LLM Reranking |
| Agent Framework | LangChain (ReAct agent) |
| Database | SQLite (analytics, PTO, leave requests) |
| Email (Read) | Python `imaplib` |
| Email (Send) | Python `smtplib` |
| Guardrails | Custom regex-based + LLM-based validation |
| Testing | pytest (63 tests, fully mocked) |
| Config | `python-dotenv` |

---

## 📝 Notes

- The polling interval is set to **2 seconds** (`POLL_INTERVAL_SECONDS` in `main.py`). Adjust as needed.
- The chunker uses a **1,000-character chunk size** with **200-character overlap** for good context coverage.
- The hybrid retriever returns the **top 5** results per retriever, combined via Reciprocal Rank Fusion.
- The bot only processes **UNSEEN** emails, so already-read messages are skipped.
- All guardrails are **fail-open** on validation errors (to avoid blocking legitimate queries) but **fail-closed** on detected threats (prompt injection, abuse).