"""Link creation, listing, batch import, deletion, and QR generation."""

import csv
import io
import ipaddress
import secrets
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import limiter, settings
from app.database import get_db
from app.models import DomainBlocklist, Link, User
from app.schemas import LinkCreate, PasswordVerify
from app.security import create_unlock_cookie, get_current_user, hash_password, verify_password
from app.utils.qr import make_qr_png

router = APIRouter(prefix="/api/links", tags=["links"])


def validate_destination(value: str, db: Session) -> str:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise HTTPException(status_code=422, detail="Only complete HTTP and HTTPS URLs are allowed.")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise HTTPException(status_code=422, detail="Private and local destinations are not allowed.")
    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)}
        except (OSError, ValueError):
            addresses = set()
    if any(not address.is_global for address in addresses):
        raise HTTPException(status_code=422, detail="Private and local destinations are not allowed.")
    blocked = db.scalars(select(DomainBlocklist.domain)).all()
    if any(hostname == domain or hostname.endswith(f".{domain}") for domain in blocked):
        raise HTTPException(status_code=422, detail="This destination domain is blocked by an administrator.")
    return value


def _create_link(payload: LinkCreate, user: User, db: Session) -> Link:
    destination = validate_destination(payload.long_url, db)
    code = payload.custom_alias
    if code and db.scalar(select(Link.id).where(Link.short_code == code)):
        raise HTTPException(status_code=409, detail="That short alias is already in use.")
    if not code:
        for _ in range(8):
            candidate = secrets.token_urlsafe(6).replace(".", "")[:10]
            if not db.scalar(select(Link.id).where(Link.short_code == candidate)):
                code = candidate
                break
        if not code:
            raise HTTPException(status_code=503, detail="Could not reserve a short code. Please retry.")
    expires_at = payload.expires_at
    if expires_at and expires_at.tzinfo:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    if expires_at and expires_at <= datetime.utcnow():
        raise HTTPException(status_code=422, detail="Expiration must be in the future.")
    link = Link(
        short_code=code,
        long_url=destination,
        user_id=user.id,
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=expires_at,
        click_limit=payload.click_limit,
    )
    db.add(link)
    try:
        db.commit()
        db.refresh(link)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That short alias is already in use.") from None
    return link


def _link_payload(link: Link, request: Request) -> dict:
    base = str(request.base_url).rstrip("/") or settings.public_base_url
    return {
        "id": link.id,
        "short_code": link.short_code,
        "short_url": f"{base}/{link.short_code}",
        "long_url": link.long_url,
        "current_clicks": link.current_clicks,
        "click_limit": link.click_limit,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "is_active": link.is_active,
        "has_password": bool(link.password_hash),
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


@router.get("")
def list_links(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    links = db.scalars(select(Link).where(Link.user_id == user.id).order_by(Link.created_at.desc())).all()
    return [_link_payload(link, request) for link in links]


@router.post("")
@limiter.limit("30/minute")
def create_link(request: Request, payload: LinkCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = _create_link(payload, user, db)
    return JSONResponse(_link_payload(link, request), status_code=201)


@router.post("/bulk")
@limiter.limit("10/minute")
async def bulk_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv file.")
    content = await file.read(1_000_001)
    if len(content) > 1_000_000:
        raise HTTPException(status_code=413, detail="CSV files must be smaller than 1 MB.")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must use UTF-8 encoding.") from None
    if not reader.fieldnames or "long_url" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must contain a long_url column.")
    created, skipped = [], []
    for line_number, row in enumerate(reader, start=2):
        try:
            values = {key: (value or "").strip() for key, value in row.items() if key}
            expires = datetime.fromisoformat(values["expires_at"]) if values.get("expires_at") else None
            payload = LinkCreate(
                long_url=values.get("long_url", ""),
                custom_alias=values.get("custom_alias") or None,
                password=values.get("password") or None,
                expires_at=expires,
                click_limit=int(values["click_limit"]) if values.get("click_limit") else None,
            )
            created.append(_link_payload(_create_link(payload, user, db), request))
        except (ValueError, TypeError, HTTPException, IntegrityError) as error:
            db.rollback()
            reason = error.detail if isinstance(error, HTTPException) else str(error)
            skipped.append({"line": line_number, "reason": reason or "Invalid row"})
    return {"created": created, "skipped": skipped}


@router.get("/sample.csv")
def sample_csv():
    content = "long_url,custom_alias,password,expires_at,click_limit\nhttps://example.com/launch,launch,,2030-01-01T00:00:00,500\n"
    return Response(content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=linkpulse-sample.csv"})


@router.post("/{link_id}/verify-password")
@limiter.limit("10/minute")
def verify_link_password(
    link_id: int,
    request: Request,
    payload: PasswordVerify,
    response: Response,
    db: Session = Depends(get_db),
):
    link = db.get(Link, link_id)
    if not link or not link.password_hash:
        raise HTTPException(status_code=404, detail="Protected link not found.")
    if not verify_password(payload.password, link.password_hash):
        raise HTTPException(status_code=401, detail="That password did not match.")
    create_unlock_cookie(response, link.short_code)
    return {"unlocked": True, "short_code": link.short_code}


@router.get("/{link_id}/qr")
def download_qr(link_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = db.scalar(select(Link).options(joinedload(Link.owner)).where(Link.id == link_id))
    if not link or (link.user_id != user.id and user.role.value != "Admin"):
        raise HTTPException(status_code=404, detail="Link not found.")
    image = make_qr_png(f"{request.base_url} {link.short_code}".replace(" ", ""))
    return StreamingResponse(image, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{link.short_code}.png"'})


@router.delete("/{link_id}")
def delete_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = db.get(Link, link_id)
    if not link or (link.user_id != user.id and user.role.value != "Admin"):
        raise HTTPException(status_code=404, detail="Link not found.")
    db.delete(link)
    db.commit()
    return {"deleted": True}