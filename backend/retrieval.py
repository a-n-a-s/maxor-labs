import os
import re

import numpy as np
from database import get_connection

EMBEDDING_DIM = 768

def _numpy_embed(text: str) -> np.ndarray:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    vec = np.zeros(EMBEDDING_DIM)
    for token in tokens:
        seed = int.from_bytes(token.encode()[:8], "little")
        rng = np.random.RandomState(seed)
        vec += rng.uniform(-0.1, 0.1, EMBEDDING_DIM)
    return vec

def hash_vector(vec: np.ndarray) -> str:
    return vec.astype(np.float32).tobytes().hex()

def init_knowledge_base() -> None:
    conn = get_connection()
    conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
    )
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
    ).fetchone()
    if exists:
        count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if count > 0:
            return
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding BLOB NOT NULL
        )
    """)
    files = [f for f in os.listdir("knowledge_base") if f.endswith(".md")]
    for fname in files:
        with open(os.path.join("knowledge_base", fname), encoding="utf-8") as f:
            text = f.read()
        chunks = split_document(text, source=fname)
        for title, chunk in chunks:
            vec = _numpy_embed(chunk)
            cursor.execute(
                "INSERT INTO chunks (source, title, chunk_text, embedding) VALUES (?, ?, ?, ?)",
                (fname, title, chunk, hash_vector(vec)),
            )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Ingested {count} chunks from {len(files)} documents")
    conn.close()

def split_document(text: str, source: str, chunk_size: int = 300) -> list[tuple[str, str]]:
    blocks = re.split(r"\n(?=#+)", text.strip())
    chunks = []
    for block in blocks:
        lines = block.strip().splitlines()
        title = lines[0].lstrip("#").strip() if lines else source
        body = " ".join(line.strip() for line in lines[1:]).strip()
        if not body:
            continue
        if len(body) <= chunk_size:
            chunks.append((title, f"{title}: {body}"))
        else:
            for i in range(0, len(body), chunk_size):
                chunks.append((title, f"{title}: {body[i:i+chunk_size]}"))
    return chunks

def retrieve(query: str, k: int = 3) -> list[dict]:
    init_knowledge_base()
    query_vec = _numpy_embed(query)
    conn = get_connection()
    rows = conn.execute("SELECT id, source, title, chunk_text, embedding FROM chunks").fetchall()
    conn.close()
    scored = []
    for row in rows:
        vec = np.frombuffer(bytes.fromhex(row["embedding"]), dtype=np.float32)
        sim = float(np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-9))
        scored.append((sim, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"source": r["source"], "title": r["title"], "text": r["chunk_text"], "score": round(s, 4)}
        for s, r in scored[:k]
    ]