import json
import os
import re
from typing import Optional

import env

KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge_base")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

ALLOWED_ACTIONS = {
    "REQUEST_PHOTOS",
    "APPROVE_REFUND_OR_REPLACEMENT",
    "REQUEST_DEFECT_EVIDENCE",
    "APPROVE_REPLACEMENT",
    "APPROVE_RETURN",
    "REJECT_OUTSIDE_WINDOW",
    "REJECT_OPENED_ITEM",
    "REJECT_FOOD_RETURN",
    "REPLACE_CORRECT_ITEM",
    "CANNOT_CANCEL_AFTER_DISPATCH",
    "CANCEL_AND_REFUND",
    "OPEN_SHIPPING_INVESTIGATION",
    "WAIT_AND_TRACK",
    "OFFER_REPLACEMENT_OR_REFUND",
    "NEEDS_MORE_INFORMATION",
}

_cached_policy_bloc: Optional[str] = None

def load_knowledge_base() -> str:
    """Load all policy docs into a single static block (CAG), cached in memory."""
    global _cached_policy_bloc
    if _cached_policy_bloc is not None:
        return _cached_policy_bloc
    blocks = []
    for fname in sorted(os.listdir(KNOWLEDGE_BASE_DIR)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(KNOWLEDGE_BASE_DIR, fname), encoding="utf-8") as f:
            blocks.append(f"[{fname}]\n{f.read().strip()}")
    _cached_policy_bloc = "\n\n".join(blocks)
    return _cached_policy_bloc

def make_decision(ticket: dict) -> dict:
    policy_bloc = load_knowledge_base()

    prompt = f"""You are an e-commerce support decision engine.
Analyze the support ticket using ONLY the provided policy documents.
Return a JSON object with exactly these fields:
{{"action": "<one allowed action>", "confidence": <0.0-1.0>, "reason": "<short justification>", "sources": ["<source file>", ...]}}

If the ticket lacks enough information to decide under the policies, use action "NEEDS_MORE_INFORMATION".
Do not invent policies that are not in the provided documents.

ALLOWED ACTIONS: {sorted(ALLOWED_ACTIONS)}

POLICY DOCUMENTS:
{policy_bloc}

TICKET:
message: {ticket['message']}
order_value_inr: {ticket.get('order_value_inr')}
days_since_delivery: {ticket.get('days_since_delivery')}
days_since_dispatch: {ticket.get('days_since_dispatch')}
product_type: {ticket.get('product_type')}
opened_status: {ticket.get('opened_status')}
order_status: {ticket.get('order_status')}

Return only the JSON, no commentary."""

    raw = _call_llm(prompt)
    parsed = _parse_response(raw)
    if parsed is None:
        return {
            "action": "NEEDS_MORE_INFORMATION",
            "confidence": 0.0,
            "reason": "Could not produce a valid structured decision from the LLM response.",
            "sources": [],
        }
    return parsed

def _call_llm(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )
    return response.text

def _parse_response(raw: str) -> Optional[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    action = data.get("action")
    if action not in ALLOWED_ACTIONS:
        return None
    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    sources = data.get("sources", [])
    if isinstance(sources, str):
        sources = [sources]
    return {
        "action": action,
        "confidence": confidence,
        "reason": str(data.get("reason", "")),
        "sources": [str(s) for s in sources],
    }