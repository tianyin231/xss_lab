from __future__ import annotations

import secrets
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from server.models import User


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


def issue_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.auth_token = token
    return token


def extract_bearer_token(header_value: str | None) -> str:
    raw = str(header_value or "").strip()
    if not raw:
        return ""
    prefix = "bearer "
    if raw.lower().startswith(prefix):
        return raw[len(prefix):].strip()
    return raw


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
