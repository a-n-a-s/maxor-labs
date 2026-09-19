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

**1. Why CAG instead of RAG?**
The entire knowledge base is six markdown files: **2,961 characters ≈ 613 tokens** (verified with a real tokenizer, not an estimate). That is 0.5% of one small LLM context window. Embedding the docs, building a vector store, and running retrieval would add moving parts — and a retrieval-accuracy risk (LLM never sees the right rule if search misses) — with zero benefit at this scale. The spec's own hint permits CAG "only if it doesn't bloat the prompt context needlessly"; ~613 extra tokens per request is negligible. I also priced both approaches before deciding: at `gemini-3-flash-preview` rates, RAG ≈ $0.00098/request vs CAG ≈ $0.0011/request — a $0.00012 difference. Cost was genuinely not the deciding factor; simplicity and reliability were. A full local RAG pipeline (chunking + hashed embeddings + NumPy cosine KNN) remains in `backend/retrieval.py` for reference and future use if the corpus grows.

**2. Why CAG's prompt structure is worth the token cost**
The prompt is a fixed prefix (policies + instructions) with only the ticket varying, so with Gemini's context caching the static prefix would read at a steep discount at scale — meaning CAG's extra input cost shrinks, not grows, with volume.

**3. Why bcrypt for password hashing?**
Passwords must never be stored as plaintext or reversible hashes. bcrypt is a deliberately slow, salted, adaptive hash — brute-force resistant (12 rounds ≈ 4-5 orders of magnitude cost factor), handles salting automatically, and needs no extra dependencies beyond `bcrypt`. I initially used PBKDF2-HMAC-SHA256 (also crypto-sound) and switched after review; both are fine, bcrypt was chosen for simplicity and industry familiarity.

**4. Why JWT with PyJWT, HS256, and a `sub` claim?**
JWT gives stateless authentication — the server stores no session; the token is self-verifying via HMAC-SHA256 of `header.payload` with `JWT_SECRET`. Any tampering invalidates the signature, and `exp` is checked automatically on decode. `sub` (subject) carries the user id; expiry is `JWT_EXPIRE_MINUTES` (default 60). HS256 is the right symmetric choice for a single-service app — asymmetric RS256 adds key management for no benefit here. The secret must be ≥32 random bytes (PyJWT warns below that); the code fails closed: forged/expired tokens → 401.

**5. How are authentication and authorization separated?**
Authentication (who are you?) happens in `auth.get_current_user`: `HTTPBearer()` extracts the token, `decode_access_token` verifies the signature + expiry and returns the user id, then the DB row is fetched. This is wired into routes via FastAPI dependency injection (`Depends(get_current_user)`), so handlers can't forget auth. Authorization (can you touch *this* resource?) is enforced per-query in `api.py`: every ticket lookup filters `WHERE user_id = ?`, so a valid Alice token still gets 404 on Bob's ticket. This is exactly the split the spec tests.

**6. Why SQLite with raw `sqlite3`, not SQLAlchemy or Postgres?**
The schema is three small tables. SQLAlchemy would add an ORM layer to justify; Postgres adds a server to run. SQLite is a zero-ops embedded database that satisfies the assignment (and is in the spec's required list). Raw `sqlite3` keeps the code transparent. One design note: a fresh connection is opened per operation (row factory + `PRAGMA foreign_keys = ON`) because SQLite connections are not thread-safe and FastAPI serves requests concurrently.

**7. Why no LangChain / LlamaIndex / FAISS / Chroma / hosted vector DB?**
All overkill for 6 policy documents. LangChain/LlamaIndex would wrap a single prompt in abstractions; FAISS/Chroma and Pinecone are for corpora that don't fit in context. The spec lists them as optional; the engineering-judgment rubric favors the smallest thing that works. Reintroducing them later (if the knowledge base grows) is easy because the CAG/RAG swap is localized to `decision.py`.

**8. Why `gemini-3-flash-preview`, and why the model is configurable?**
`gemini-2.0-flash` (initially referenced) was **shut down by Google on June 1, 2026** — the code would 500 on every ticket. Current Flash-class models (`gemini-3-flash-preview`) give the best speed/cost for this structured, low-complexity task. The model is read from `GEMINI_MODEL` (default set in `.env.example`) so it can be changed without code edits. The Gemini call also uses `response_mime_type="application/json"` to force structured output, which is then still parsed and validated by `_parse_response` — never trusted blindly.

**9. Why is the LLM response validated instead of used as-is?**
The model can return an off-list action, a confidence outside 0-1, or malformed JSON. `_parse_response` whitelists actions against `ALLOWED_ACTIONS`, clamps confidence, coerces `sources` to a list, and falls back to `NEEDS_MORE_INFORMATION` when parsing fails — so the API always stores a well-formed decision and never invents an answer on thin information (spec section 8).

**10. Why do unit tests mock the LLM?**
Tests must be fast, free, and deterministic. The tests monkeypatch `api.make_decision` with a fixed result, so pytest verifies our code (routes, DB, auth, authorization) without spending API tokens or depending on model output. Real-model accuracy is verified separately by `evaluate.py`, which calls Gemini against the official test cases.

**11. Why is `data/decisions.db` gitignored but schema committed?**
The database is runtime state (users, tickets, decisions you create while testing). Committing it would bake in test data and stale credentials. The schema lives in code (`database.py` creates tables idempotently on startup), so any clone rebuilds a clean DB automatically. Same principle as `.env` versus `.env.example`.

**12. Why does the frontend not need CORS handling on the backend?**
Streamlit makes its HTTP calls **server-side** with Python's `requests` (not from the browser), so browser same-origin policy never applies — CORS is moot. (An early review flagged this as a possible issue; it was verified and dismissed.)