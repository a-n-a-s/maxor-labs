import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import env
from database import get_connection

JWT_SECRET = os.getenv("JWT_SECRET", "hardwordhardwordhardwordhardword")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

security = HTTPBearer()

_BCRYPT_ROUNDS = 12

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()

def verify_password(password: str, stored: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored.encode())
    except ValueError:
        return False

def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    user_id = decode_access_token(credentials.credentials)
    conn = get_connection()
    row = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return dict(row)