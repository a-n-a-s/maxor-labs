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

Run the AI against the 5 supplied test cases (calls the real Gemini API — `--delay` spaces requests to stay within free-tier rate limits):

```powershell
python evaluate.py
```

Optionally evaluate all 214 historical tickets:

```powershell
python evaluate.py --cases data/tickets.csv
```

### Result (5/5 correct, verified live)

```
5 test cases
Correct: 5
Incorrect: 0
Accuracy: 100%
[PASS] S01: got=REQUEST_PHOTOS (100%) expected=REQUEST_PHOTOS
[PASS] S02: got=APPROVE_RETURN (100%) expected=APPROVE_RETURN
[PASS] S03: got=OPEN_SHIPPING_INVESTIGATION (100%) expected=OPEN_SHIPPING_INVESTIGATION
[PASS] S04: got=REPLACE_CORRECT_ITEM (100%) expected=REPLACE_CORRECT_ITEM
[PASS] S05: got=NEEDS_MORE_INFORMATION (100%) expected=NEEDS_MORE_INFORMATION
```

## RAG vs CAG — and why we chose CAG

**The requirement (spec section 7):** load policy docs → split into chunks → create embeddings → store locally → embed the incoming ticket → retrieve the most relevant chunks → pass retrieved context to the LLM. The spec's hint then adds: *"you might also use CAG instead of overengineering with RAG, only if it doesn't bloat the prompt context needlessly."*

### CAG, in one line
Cache-Augmented Generation skips the retrieval pipeline and puts the **entire knowledge base into the prompt** on every request.

### Why we picked CAG for this project

**1. The corpus is tiny — 613 tokens total.**
The 6 policy files are 2,961 characters ≈ **613 tokens** (measured with a real tokenizer, not guessed). That is ~0.5% of a small context window. There is nothing to "retrieve from": the whole KB already fits comfortably in the prompt.

**2. RAG adds real risk, not just complexity.**
Retrieval introduces a new failure mode: if search returns the *wrong* chunks, the LLM never sees the applicable rule and invents an answer. For a 6-document knowledge base, that risk far outweighs the pipeline's benefits.

**3. The cost difference is negligible (and we verified it).**
Priced on `gemini-3-flash-preview` before deciding:

| | RAG (top-4 chunks) | CAG (all 6 docs) |
|---|---|---|
| Input tokens / request | ~1,060 | ~1,300 |
| Cost / request | ~$0.00098 | ~$0.0011 |

A **~$0.00012/request** delta — noise at this scale. Cost was never the deciding factor; reliability and simplicity were.

**4. CAG is not a trap at scale here.**
The prompt is a fixed static prefix (policies + instructions) with only the ticket varying, so Gemini context caching would discount the bulk of the input cost if request volume grew — the extra cost shrinks, not grows.

**5. The spec permits it explicitly.**
The "only if it doesn't bloat the prompt context needlessly" condition is satisfied: 613 tokens is the opposite of bloat.

**6. The RAG path isn't lost.**
`backend/retrieval.py` still contains the full local pipeline (header-based chunking, hashed word embeddings, NumPy cosine-similarity KNN over a SQLite `chunks` table). If the knowledge base ever outgrows the context window, swapping back is localized to `decision.load_knowledge_base()`. The current pipeline is:

```
ticket + all policy docs → Gemini (forced JSON) → validate action/confidence/sources → persist
```