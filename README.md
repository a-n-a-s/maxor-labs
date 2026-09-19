# Support Ticket Decision Assistant

AI-powered support-ticket decision assistant built with **FastAPI**, **Streamlit**, **JWT auth**, **SQLite**, and the **Gemini API** using Cache-Augmented Generation (CAG) over policy documents.

A user registers and logs in, receives a JWT, submits a support ticket, and receives an evidence-backed recommendation (`action`, `confidence`, `reason`, `sources`). Tickets and decisions persist in SQLite.

## Features

- **JWT authentication** — bcrypt password hashing, bearer-token authorization, per-user data isolation
- **Structured AI decisions** — Gemini returns validated JSON (`action`, `confidence`, `reason`, `sources`); returns `NEEDS_MORE_INFORMATION` when the ticket lacks enough detail
- **CAG over policy documents** — all 6 policy docs (~613 tokens) are fed directly into the prompt; retrieval step is unnecessary at this corpus size
- **Streamlit frontend** — login/register, new decision, history
- **Tests** — 17 pytest tests including the Alice/Bob authorization case
- **Evaluation runner** — grades decisions against supplied test cases

## Project structure

```
intern-project/
├── backend/
│   ├── api.py          # FastAPI routes
│   ├── auth.py         # bcrypt + JWT
│   ├── database.py     # SQLite schema
│   ├── decision.py     # CAG prompt + Gemini call + output validation
│   ├── env.py          # .env loading
│   └── retrieval.py    # (unused) local RAG implementation
├── frontend/
│   └── streamlit_app.py
├── knowledge_base/     # 6 policy documents
├── data/
│   ├── tickets.csv             # historical synthetic tickets
│   └── sample_test_cases.json  # 5 official evaluation cases
├── tests/              # pytest suite
├── evaluate.py         # evaluation runner
└── requirements.txt
```

## Setup

1. **Clone / download** the repository.

2. **Create a virtual environment** (recommended):
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure secrets** — copy `.env.example` to `.env` and fill in values:
   ```
   GEMINI_API_KEY=your-gemini-api-key     # from https://aistudio.google.com/u/0/api-keys
   JWT_SECRET=generate-a-random-long-string-at-least-32-chars
   ```
   `.env` can live at the project root or in `backend/`; it is loaded automatically and never committed.

## Run

**Terminal 1 — backend** (from the project root):
```powershell
uvicorn --app-dir backend api:app --reload
```
API: http://localhost:8000 · Interactive docs: http://localhost:8000/docs

**Terminal 2 — frontend**:
```powershell
streamlit run frontend/streamlit_app.py
```
UI: http://localhost:8501

Start the backend first.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/register` | Create a user account |
| POST | `/login` | Verify credentials, return `access_token` |
| GET | `/me` | Return the authenticated user |
| POST | `/tickets` | Submit a ticket, generate + persist an AI decision |
| GET | `/tickets` | List the authenticated user's tickets |
| GET | `/tickets/{id}` | Return one ticket and its decision (own tickets only) |

Protected endpoints require `Authorization: Bearer <JWT>`.

## Tests

```powershell
python -m pytest
```
Includes the required authorization test: Alice's token cannot retrieve Bob's ticket.

## Evaluation

Run the AI against the 5 supplied test cases (calls the real Gemini API):

```powershell
python evaluate.py
```

Optionally evaluate all 214 historical tickets:

```powershell
python evaluate.py --cases data/tickets.csv
```

Example output:

```
5 test cases
Correct: 4
Incorrect: 1
Accuracy: 80%
```

## Q&A / technical decisions

- **Why CAG instead of RAG?** The entire knowledge base is ~2,961 chars (~613 tokens). Retrieval (embeddings + vector search) would add complexity with zero accuracy benefit at this scale, and the spec explicitly permits CAG when it does not bloat the prompt context. A full RAG pipeline remains in `backend/retrieval.py` for reference.
- **Why not?.** Considered but rejected: LangChain/LlamaIndex, FAISS/Chroma, hosted vector DBs, password storage without hashing.
- **Model**: `gemini-3-flash-preview` by default; override with the `GEMINI_MODEL` env var. `gemini-2.0-flash` was shut down by Google in June 2026 and must not be used.