"""User-scoped analytics aggregations for Chart.js."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Click, Link, User
from app.security import get_current_user
from app.tasks import bot_hits_filtered

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def analytics(
    link_id: int | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    links_query = select(Link)
    if user.role.value != "Admin":
        links_query = links_query.where(Link.user_id == user.id)
    if link_id is not None:
        links_query = links_query.where(Link.id == link_id)
    links = db.scalars(links_query).all()
    if link_id is not None and not links:
        raise HTTPException(status_code=404, detail="Link not found.")
    ids = [link.id for link in links]
    since = datetime.utcnow() - timedelta(days=days)
    if not ids:
        clicks = []
    else:
        clicks = db.scalars(select(Click).where(Click.link_id.in_(ids), Click.clicked_at >= since)).all()
    timeline = {}
    devices = {"Mobile": 0, "Desktop": 0, "Tablet": 0}
    countries = {}
    channels = {}
    for offset in range(days - 1, -1, -1):
        day = (datetime.utcnow() - timedelta(days=offset)).strftime("%Y-%m-%d")
        timeline[day] = 0
    for click in clicks:
        day = click.clicked_at.strftime("%Y-%m-%d")
        if day in timeline:
            timeline[day] += 1
        devices[click.device_type if click.device_type in devices else "Desktop"] += 1
        country = click.country or "Unknown"
        countries[country] = countries.get(country, 0) + 1
        referrer = (click.referrer or "Direct").strip()
        if referrer.startswith("http"):
            from urllib.parse import urlparse

            referrer = urlparse(referrer).hostname or "Other"
        channels[referrer] = channels.get(referrer, 0) + 1
    return {
        "total_clicks": sum(link.current_clicks for link in links),
        "unique_visitors": len({(click.link_id, click.city, click.country, click.referrer) for click in clicks}),
        "bot_hits_filtered": sum(bot_hits_filtered[link.id] for link in links),
        "active_links": sum(link.is_active for link in links),
        "expiring_links": sum(link.expires_at is not None and link.expires_at > datetime.utcnow() for link in links),
        "timeline": {"labels": list(timeline), "values": list(timeline.values())},
        "devices": {"labels": list(devices), "values": list(devices.values())},
        "geography": {"labels": [name for name, _ in sorted(countries.items(), key=lambda item: item[1], reverse=True)[:8]], "values": [count for _, count in sorted(countries.items(), key=lambda item: item[1], reverse=True)[:8]]},
        "channels": {"labels": list(channels), "values": list(channels.values())},
    }