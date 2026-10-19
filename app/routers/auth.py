"""Registration, login, and logout routes."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import limiter
from app.database import get_db
from app.models import User, UserRole
from app.security import create_session_cookie, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register")
@limiter.limit("3/hour")
def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    username = username.strip()
    if len(password) < 10:
        return RedirectResponse("/login?error=Use+a+password+with+at+least+10+characters", status_code=303)
    if not email or len(email) > 255 or "@" not in email or not username or len(username) > 100:
        return RedirectResponse("/login?error=Enter+a+valid+email+and+display+name", status_code=303)
    if db.scalar(select(User.id).where((User.email == email) | (User.username == username))):
        return RedirectResponse("/login?error=That+email+or+display+name+is+already+registered", status_code=303)
    user = User(email=email, username=username, password_hash=hash_password(password), role=UserRole.USER)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/login?error=That+email+or+display+name+is+already+registered", status_code=303)
    response = RedirectResponse("/dashboard", status_code=303)
    create_session_cookie(response, user.id, user.role)
    return response


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("User"),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    requested_role = UserRole.ADMIN if role == "Admin" else UserRole.USER
    if not user or user.is_suspended or not verify_password(password, user.password_hash):
        return RedirectResponse("/login?error=Email+or+password+was+not+recognized", status_code=303)
    if user.role != requested_role:
        return RedirectResponse("/login?error=Choose+the+correct+account+role", status_code=303)
    response = RedirectResponse("/admin" if user.role == UserRole.ADMIN else "/dashboard", status_code=303)
    create_session_cookie(response, user.id, user.role)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("linkpulse_session", path="/")
    return response
