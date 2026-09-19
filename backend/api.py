from typing import Optional
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr

from auth import create_access_token, hash_password, verify_password, get_current_user
from database import get_connection, init_db

from decision import make_decision

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Support Ticket Decision API", lifespan=lifespan)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TicketRequest(BaseModel):
    message: str
    order_value_inr: Optional[float] = None
    days_since_delivery: Optional[int] = None
    days_since_dispatch: Optional[int] = None
    product_type: Optional[str] = None
    opened_status: Optional[str] = None
    order_status: Optional[str] = None

@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    conn = get_connection()
    exists = conn.execute("SELECT id FROM users WHERE email = ?", (body.email,)).fetchone()
    if exists:
        conn.close()
        raise HTTPException(status_code=409, detail="Email already registered")
    password_hash = hash_password(body.password)
    cur = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (body.email, password_hash),
    )
    conn.commit()
    conn.close()
    return {
        "id": cur.lastrowid,
        "email": body.email,
    }

@app.post("/login")
def login(body: LoginRequest):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?", (body.email,)
    ).fetchone()
    conn.close()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "access_token": create_access_token(row["id"]),
        "token_type": "bearer",
        "user": {"id": row["id"], "email": row["email"]},
    }

@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user

@app.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketRequest, user: dict = Depends(get_current_user)):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    decision = make_decision(body.model_dump())

    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO tickets
           (user_id, message, order_value_inr, days_since_delivery,
            days_since_dispatch, product_type, opened_status, order_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user["id"],
            message,
            body.order_value_inr,
            body.days_since_delivery,
            body.days_since_dispatch,
            body.product_type,
            body.opened_status,
            body.order_status,
        ),
    )
    ticket_id = cur.lastrowid

    conn.execute(
        """INSERT INTO decisions (ticket_id, action, reason, confidence, sources)
           VALUES (?, ?, ?, ?, ?)""",
        (
            ticket_id,
            decision["action"],
            decision["reason"],
            decision["confidence"],
            ",".join(decision["sources"]),
        ),
    )
    conn.commit()
    conn.close()

    return _serialize_ticket(_fetch_ticket(ticket_id, user["id"]))

def _fetch_ticket(ticket_id, user_id):
    conn = get_connection()
    ticket = conn.execute(
        """SELECT t.id, t.message, t.order_value_inr, t.days_since_delivery,
                  t.days_since_dispatch, t.product_type, t.opened_status, t.order_status,
                  t.created_at, d.action, d.reason, d.confidence, d.sources, d.created_at AS decision_created_at
           FROM tickets t
           LEFT JOIN decisions d ON d.ticket_id = t.id
           WHERE t.id = ? AND t.user_id = ?""",
        (ticket_id, user_id),
    ).fetchone()
    conn.close()
    return ticket

def _serialize_ticket(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "message": row["message"],
        "created_at": row["created_at"],
        "details": {
            "order_value_inr": row["order_value_inr"],
            "days_since_delivery": row["days_since_delivery"],
            "days_since_dispatch": row["days_since_dispatch"],
            "product_type": row["product_type"],
            "opened_status": row["opened_status"],
            "order_status": row["order_status"],
        },
        "decision": (
            {
                "action": row["action"],
                "reason": row["reason"],
                "confidence": row["confidence"],
                "sources": [s for s in (row["sources"] or "").split(",") if s],
                "created_at": row["decision_created_at"],
            }
            if row["action"]
            else None
        ),
    }

@app.get("/tickets")
def list_tickets(user: dict = Depends(get_current_user)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, message, created_at FROM tickets WHERE user_id = ? ORDER BY id DESC",
        (user["id"],),
    ).fetchall()
    conn.close()
    return {"tickets": [dict(r) for r in rows]}

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, user: dict = Depends(get_current_user)):
    ticket = _fetch_ticket(ticket_id, user["id"])
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _serialize_ticket(ticket)