# 🤝 HRMate

> An AI-powered HR assistant that automatically answers employee email queries using company policy documents — powered by RAG (Retrieval-Augmented Generation), OpenAI, and Pinecone.

---

## 📖 How It Works

HRMate watches an email inbox for new messages from employees. When one arrives, it:

1. **Embeds** the query using OpenAI's `text-embedding-3-large` model.
2. **Retrieves** the most relevant sections from the company policy document stored in a Pinecone vector database.
3. **Generates** a professional, policy-grounded email reply using GPT-4.1.
4. **Sends** the reply automatically back to the employee via SMTP.

```
Employee Email
      │
      ▼
  IMAP Poll  ──► Embed Query ──► Pinecone Vector Search ──► Relevant Policy Chunks
                                                                       │
                                                                       ▼
                                                                GPT-4.1 Response
                                                                       │
                                                                       ▼
                                                             Auto-Reply via SMTP
```

---

## 🗂️ Project Structure

```
HRMate/
├── main.py            # Core email polling loop — reads inbox & sends AI replies
├── llm_runner.py      # Orchestrates RAG: embed → retrieve → generate
├── rag_runner.py      # One-time script to chunk & index the policy document
├── requirements.txt   # Python dependencies
└── rag/
    ├── chunker.py     # Splits the policy document into overlapping chunks
    ├── embbeding.py   # Generates OpenAI embeddings for text
    ├── llm.py         # Calls GPT-4.1 to generate responses
    ├── vectorstore.py # Upserts/queries vectors in Pinecone
    └── doc/
        ├── policy.txt         # Your company's HR policy document
        └── system_prompt.md   # Prompt template that governs the AI's behaviour
```

---

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/HRMate.git
cd HRMate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
# Email credentials
EMAIL_USER=your-email@example.com
EMAIL_PASS=your-app-password

# IMAP & SMTP servers (example: Gmail)
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com

# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_HOST=https://your-index-host.pinecone.io
```

> **Gmail users**: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password, and enable IMAP in Gmail settings.

### 4. Add your HR policy document

Place your company's policy as plain text at `rag/doc/policy.txt`.

### 5. Index the policy document into Pinecone

Run this **once** (or whenever the policy changes):

```bash
python rag_runner.py
```

This chunks the document, generates embeddings, and upserts them into your Pinecone index.

> **Note**: Your Pinecone index must be configured for 3072-dimensional vectors to match the `text-embedding-3-large` model output.

### 6. Start the auto-reply bot

```bash
python main.py
```

The bot will poll the inbox every 2 seconds and automatically reply to any unread emails.  
Press `Ctrl+C` to stop.

---

## 🧠 AI Behaviour

The assistant is guided by the system prompt in `rag/doc/system_prompt.md`:

- **Strictly policy-based**: All answers are drawn exclusively from the retrieved policy chunks — no hallucination.
- **Professional & friendly**: Replies are warm, concise, and ready to send as-is.
- **Graceful fallback**: If the policy doesn't cover a query, the bot tells the employee to contact HR directly rather than guessing.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | OpenAI GPT-4.1 |
| Embeddings | OpenAI `text-embedding-3-large` |
| Vector Database | Pinecone (gRPC) |
| Email (Read) | Python `imaplib` |
| Email (Send) | Python `smtplib` |
| Config | `python-dotenv` |

---

## 📝 Notes

- The polling interval is set to **2 seconds** (`POLL_INTERVAL_SECONDS` in `main.py`). Adjust as needed.
- The chunker uses a **1000-character chunk size** with **200-character overlap** for good context coverage.
- The vector query retrieves the **top 10** most relevant policy chunks per email.
- The bot only processes **UNSEEN** emails, so already-read messages are skipped.