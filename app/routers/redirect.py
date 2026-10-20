"""Public short-code resolution and password-gated redirects."""

from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.config import BASE_DIR, limiter
from app.database import get_db
from app.models import DomainBlocklist, Link, User
from app.security import create_unlock_cookie, has_link_unlock, verify_password
from app.tasks import log_click_telemetry
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
router = APIRouter(tags=["redirect"])


def _blocked_domain(db: Session, url: str) -> bool:
    from urllib.parse import urlparse

    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in db.scalars(select(DomainBlocklist.domain)).all())


def _intercept(request: Request, template: str, status: int, link: Link | None = None, **context):
    return templates.TemplateResponse(template, {"request": request, "link": link, **context}, status_code=status)


@router.get("/{short_code}")
def resolve_short_link(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    link = db.scalar(select(Link).where(Link.short_code == short_code))
    if not link:
        return _intercept(request, "intercepts/410_expired.html", 404, message="This short link does not exist.")
    owner = db.get(User, link.user_id)
    if not link.is_active or (owner and owner.is_suspended) or _blocked_domain(db, link.long_url):
        return _intercept(request, "intercepts/403_suspended.html", 403, link)
    if link.expires_at and link.expires_at <= datetime.utcnow():
        return _intercept(request, "intercepts/410_expired.html", 410, link)
    if link.click_limit is not None and link.current_clicks >= link.click_limit:
        return _intercept(request, "intercepts/429_capped.html", 429, link)
    if link.password_hash and not has_link_unlock(request, short_code):
        return _intercept(request, "intercepts/password.html", 200, link, csrf_token=request.state.csrf_token, error=None)

    now = datetime.utcnow()
    conditions = [Link.id == link.id, Link.is_active.is_(True), or_(Link.expires_at.is_(None), Link.expires_at > now)]
    if link.click_limit is not None:
        conditions.append(Link.current_clicks < link.click_limit)
    changed = db.execute(update(Link).where(*conditions).values(current_clicks=Link.current_clicks + 1))
    db.commit()
    if changed.rowcount != 1:
        db.expire_all()
        current = db.get(Link, link.id)
        if not current or not current.is_active:
            return _intercept(request, "intercepts/403_suspended.html", 403, current)
        if current.expires_at and current.expires_at <= datetime.utcnow():
            return _intercept(request, "intercepts/410_expired.html", 410, current)
        return _intercept(request, "intercepts/429_capped.html", 429, current)

    client_ip = request.client.host if request.client else None
    background_tasks.add_task(
        log_click_telemetry,
        link.id,
        client_ip,
        request.headers.get("user-agent", ""),
        request.headers.get("referer"),
    )
    return RedirectResponse(link.long_url, status_code=302)


@router.post("/{short_code}/unlock")
@limiter.limit("10/minute")
def unlock_link(
    short_code: str,
    request: Request,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    link = db.scalar(select(Link).where(Link.short_code == short_code))
    if not link or not link.password_hash or not verify_password(password, link.password_hash):
        return _intercept(request, "intercepts/password.html", 401, link, csrf_token=request.state.csrf_token, error="That password did not match.")
    response = RedirectResponse(f"/{short_code}", status_code=303)
    create_unlock_cookie(response, short_code)
    return response