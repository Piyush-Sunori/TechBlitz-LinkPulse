"""Background click telemetry ingestion."""

import logging
from collections import Counter

from user_agents import parse

from app.database import SessionLocal
from app.models import Click
from app.utils.geoip import lookup_ip

logger = logging.getLogger(__name__)
bot_hits_filtered: Counter[int] = Counter()


def is_bot(user_agent_string: str | None) -> bool:
    return bool(user_agent_string and parse(user_agent_string).is_bot)


def log_click_telemetry(
    link_id: int,
    ip_address: str | None,
    user_agent_str: str | None,
    referrer: str | None,
) -> None:
    """Parse and persist human click telemetry in a background worker session."""
    agent = parse(user_agent_str or "")
    if agent.is_bot:
        bot_hits_filtered[link_id] += 1
        return
    if agent.is_tablet:
        device_type = "Tablet"
    elif agent.is_mobile:
        device_type = "Mobile"
    else:
        device_type = "Desktop"
    country, city = lookup_ip(ip_address)
    db = SessionLocal()
    try:
        db.add(
            Click(
                link_id=link_id,
                browser=agent.browser.family or "Unknown",
                os=agent.os.family or "Unknown",
                device_type=device_type,
                country=country,
                city=city,
                referrer=(referrer or "")[:255] or "Direct",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist click telemetry for link %s", link_id)
    finally:
        db.close()