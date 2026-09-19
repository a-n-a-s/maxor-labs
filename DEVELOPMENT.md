# DEVELOPMENT.md

Documentation of how AI coding agents were used in this project, per the assignment deliverable.

## Summary

Development was performed with the assistance of an AI coding agent (**opencode**). The agent wrote most of the initial code, and the human developer reviewed, directed, and validated every change. This file records how the agent was used and how its output was verified.

## How the agent was used

| Stage | What the agent did | Human verification |
|---|---|---|
| Database schema | Designed the SQLite schema (`database.py`) from the spec's table definitions, added ticket-metadata columns (order value, days, product type, opened/order status) needed by the policy logic | Reviewed schema against spec §6; confirmed FKs + `ON DELETE CASCADE`; kept `ticket_id UNIQUE` for 1:1 ticket→decision |
| Auth | Implemented bcrypt hashing + JWT issuance/validation (register/login/me) | Reviewed; explicitly required switching from PBKDF2 to bcrypt; set `bcrypt` rounds; with PyJWT the dev default secret was lengthened to satisfy the ≥32-byte HS256 check |
| API routes | Generated all 6 FastAPI endpoints with Pydantic models and DI-based auth via `Depends(get_current_user)` | Tested every endpoint with pytest; the code returned correct 201/401/404/409/422 statuses |
| RAG → CAG call | The agent flagged Google's deprecation of `gemini-2.0-flash`, proposed CAG over RAG per the spec hint, and counted the corpus tokens before deciding | I asked the agent to **count tokens and costs first** before any switch; the full knowledge base is ~613 tokens, so CAG was adopted. Dead RAG code (`retrieval.py`) was intentionally kept for reference |
| Frontend | Wrote the Streamlit app (login/register, new decision, history) | Manual review; simplified a redundant null-check block |
| Tests | Wrote 17 pytest tests incl. the required Alice/Bob authorization test; mocked the LLM so tests never call the paid Gemini API | Reviewed test design; ran the suite (17 passing); confirmed the mock targets `api.make_decision` so real API calls are never made during unit tests |
| Eval runner | Built `evaluate.py` reading `sample_test_cases.json` and reporting accuracy per spec §9 | Tested the non-Gemini parts (case loading, ticket building, report formatting) without spending API tokens |
| .env/dotenv | Wired `python-dotenv`; debugged a real failure where uvicorn (run from project root) could not find `.env` stored in `backend/` by making env-loading path-based instead of CWD-based | Reproduced the reported `GEMINI_API_KEY environment variable is not set` error, then verified the fix loads the key from the project root CWD |

## Principles followed

1. **The agent never had the company's API key.** The candidate used their own Gemini key, stored in a gitignored `.env`.
2. **Every agent-written piece of code was validated by the human.** At minimum: compile check, pytest run, or targeted review. No code was trusted blindly.
3. **Cost-sensitive steps were deferred, not guessed.** The RAG→CAG decision was made only after counting corpus tokens and estimating per-request costs; the evaluation runner was built but intentionally not run, since it spends API tokens.
4. **Secrets hygiene was enforced end-to-end.** `.env` is gitignored; only `.env.example` is committed; the report/exit includes checks that no keys are present in committed files.
5. **The agent's output was challenged where wrong**: e.g. the initial claim that Streamlit→FastAPI needed CORS was corrected after review (Streamlit makes server-side HTTP calls, so CORS is moot); the token-count estimate was replaced by a real tokenizer count.
6. **Simplicity over architecture.** No LangChain, no vector DBs, no multi-container setup — matching the assignment's stated scope.

## Files the agent produced or materially changed

- `backend/database.py`, `backend/auth.py`, `backend/api.py`, `backend/decision.py`, `backend/env.py`
- `frontend/streamlit_app.py`
- `tests/` (conftest, helpers, test_auth, test_tickets, test_authorization)
- `evaluate.py`, `requirements.txt`, `.env.example`, `.gitignore`, `pytest.ini`, `README.md`, this file

## Verification commands used

```powershell
python -m pytest          # unit tests — no API calls
python evaluate.py        # evaluation runner — REQUIRES GEMINI_API_KEY (spends tokens) — run only when intended
uvicorn --app-dir backend api:app --reload   # backend
streamlit run frontend/streamlit_app.py      # frontend
```