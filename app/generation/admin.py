"""Administrator governance and tenant controls."""

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Click, DomainBlocklist, Link, User, UserRole
from app.security import get_current_user, require_admin

router = APIRouter(prefix="/api/admin", tags=["administration"])


def _admin_user(db: Session, request_user: User) -> User:
    return require_admin(request_user)


@router.get("/users")
def users(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _admin_user(db, current)
    rows = db.scalars(select(User).options()).all()
    output = []
    for user in rows:
        links = db.scalars(select(Link).where(Link.user_id == user.id).order_by(Link.created_at.desc())).all()
        output.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "is_suspended": user.is_suspended,
            "links": [{"id": link.id, "short_code": link.short_code, "long_url": link.long_url, "clicks": link.current_clicks, "is_active": link.is_active, "expires_at": link.expires_at.isoformat() if link.expires_at else None} for link in links],
        })
    return output


@router.post("/links/{link_id}/toggle")
def toggle_link(link_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _admin_user(db, current)
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found.")
    link.is_active = not link.is_active
    db.commit()
    return {"id": link.id, "is_active": link.is_active}


@router.patch("/links/{link_id}/disable")
def disable_link(link_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _admin_user(db, current)
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found.")
    link.is_active = False
    db.commit()
    return {"id": link.id, "is_active": False}


@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _admin_user(db, current)
    user = db.get(User, user_id)
    if not user or user.role == UserRole.ADMIN:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_suspended = not user.is_suspended
    db.commit()
    return {"id": user.id, "is_suspended": user.is_suspended}


@router.post("/blocklist")
def add_domain(domain: str = Form(...), db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _admin_user(db, current)
    normalized = domain.strip().lower().rstrip(".")
    if normalized.startswith("http://") or normalized.startswith("https://"):
        from urllib.parse import urlparse

        normalized = urlparse(normalized).hostname or ""
    if not normalized or "." not in normalized or any(part in normalized for part in ("/", " ", "@")):
        raise HTTPException(status_code=422, detail="Enter a root domain such as example.com.")
    existing = db.scalar(select(DomainBlocklist.id).where(DomainBlocklist.domain == normalized))
    if not existing:
        db.add(DomainBlocklist(domain=normalized, added_by=current.id))
        db.commit()
    return {"domain": normalized, "created": not bool(existing)}