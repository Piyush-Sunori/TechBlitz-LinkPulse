"""Password hashing, signed cookies, CSRF tokens, and access checks."""

import base64
import hashlib
import hmac
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, UserRole

password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return password_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def _sign(value: str) -> str:
    digest = hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _signed_value(payload: str) -> str:
    return f"{payload}.{_sign(payload)}"


def _verify_signed(value: str) -> str | None:
    try:
        payload, signature = value.rsplit(".", 1)
    except ValueError:
        return None
    return payload if hmac.compare_digest(signature, _sign(payload)) else None


def create_session_cookie(response: Response, user_id: int, role: UserRole | str) -> None:
    payload = f"{user_id}:{getattr(role, 'value', role)}:{int(time.time()) + settings.session_max_age}"
    response.set_cookie(
        settings.session_cookie,
        _signed_value(payload),
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def create_csrf_token() -> str:
    return _signed_value(secrets.token_urlsafe(32))


def valid_csrf_token(token: str | None) -> bool:
    return bool(token and _verify_signed(token))


def create_unlock_cookie(response: Response, short_code: str) -> None:
    expiry = int(time.time()) + 3600
    response.set_cookie(
        f"linkpulse_unlock_{short_code}",
        _signed_value(f"{short_code}:{expiry}"),
        max_age=3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=f"/{short_code}",
    )


def has_link_unlock(request: Request, short_code: str) -> bool:
    payload = _verify_signed(request.cookies.get(f"linkpulse_unlock_{short_code}", ""))
    if not payload:
        return False
    try:
        code, expiry = payload.rsplit(":", 1)
        return code == short_code and int(expiry) > int(time.time())
    except (ValueError, TypeError):
        return False


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    payload = _verify_signed(request.cookies.get(settings.session_cookie, ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    try:
        user_id, _role, expiry = payload.split(":", 2)
        if int(expiry) <= int(time.time()):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.") from None
    user = db.get(User, int(user_id))
    if not user or user.is_suspended:
        raise HTTPException(status_code=401, detail="This account is unavailable.")
    return user


def require_admin(user: User) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user
