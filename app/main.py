"""FastAPI entry point and server-rendered LinkPulse pages."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import BASE_DIR, limiter, settings
from app.database import Base, engine, get_db
from app.models import Click, DomainBlocklist, Link, User, UserRole
from app.routers import admin, analytics, auth, links, redirect
from app.security import create_csrf_token, get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("LinkPulse database schema is ready.")
    except SQLAlchemyError as error:
        logger.warning("Database unavailable; configure MySQL before using data-backed pages: %s", error)
    yield


app = FastAPI(title="LinkPulse", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.middleware("http")
async def security_and_csrf_middleware(request: Request, call_next):
    request.state.csrf_token = create_csrf_token()
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token = request.headers.get("x-csrf-token")
        if not token and request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
            raw_body = await request.body()
            body = raw_body.decode("utf-8", errors="replace")
            token = parse_qs(body).get("csrf_token", [None])[0]

            async def replay_body():
                return {"type": "http.request", "body": raw_body, "more_body": False}

            request._receive = replay_body
        from app.security import valid_csrf_token

        if not valid_csrf_token(token):
            from fastapi.responses import JSONResponse

            response = JSONResponse({"detail": "Invalid or missing CSRF token."}, status_code=403)
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com https://fonts.googleapis.com; font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _page_context(request: Request, **values):
    return {"request": request, "csrf_token": request.state.csrf_token, **values}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", _page_context(request))


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", _page_context(request, error=request.query_params.get("error")))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    if user.role == UserRole.ADMIN:
        return RedirectResponse("/admin", status_code=303)
    user_links = db.scalars(select(Link).where(Link.user_id == user.id).order_by(Link.created_at.desc())).all()
    return templates.TemplateResponse("dashboard.html", _page_context(request, user=user, links=user_links, now=datetime.utcnow()))


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    user_links = db.scalars(select(Link).where(Link.user_id == user.id).order_by(Link.created_at.desc())).all()
    return templates.TemplateResponse("analytics.html", _page_context(request, user=user, links=user_links))


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    if user.role != UserRole.ADMIN:
        return RedirectResponse("/dashboard", status_code=303)
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    all_links = db.scalars(select(Link).join(User).options()).all()
    totals = {
        "users": len(users),
        "links": len(all_links),
        "domains": db.scalar(select(func.count(DomainBlocklist.id))) or 0,
        "clicks": db.scalar(select(func.coalesce(func.sum(Link.current_clicks), 0))) or 0,
    }
    return templates.TemplateResponse("admin.html", _page_context(request, user=user, users=users, links=all_links, totals=totals, domains=db.scalars(select(DomainBlocklist).order_by(DomainBlocklist.domain)).all()))


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)
    return {"status": "ok", "database": "connected", "service": settings.app_name}


app.include_router(auth.router)
app.include_router(links.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(redirect.router)