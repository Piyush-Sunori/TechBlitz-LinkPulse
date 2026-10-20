"""Pre-populates demo accounts and 100+ clicks for live review.

Usage (after `python reset_db.py`):
    python seed.py

Logins (password for all 3 users): Test@1234
Password of the locked link `secret1`: Link@123
"""

import hashlib
import random
from datetime import datetime, timedelta

from argon2 import PasswordHasher

from app.database import SessionLocal
from app.models import Campaign, Click, DomainBlocklist, Link, User, UserRole

random.seed(42)
ph = PasswordHasher()

USER_PASSWORD = "Test@1234"
LINK_PASSWORD = "Link@123"

# (browser, os, device_type, weight)
AGENTS = [
    ("Chrome", "Windows", "Desktop", 30),
    ("Chrome", "Android", "Mobile", 30),
    ("Safari", "iOS", "Mobile", 20),
    ("Firefox", "Windows", "Desktop", 6),
    ("Edge", "Windows", "Desktop", 6),
    ("Safari", "macOS", "Desktop", 5),
    ("Safari", "iOS", "Tablet", 3),
]
# (country, city, weight)
PLACES = [
    ("India", "Delhi", 20),
    ("India", "Mumbai", 14),
    ("India", "Dehradun", 8),
    ("India", "Haldwani", 4),
    ("USA", "New York", 8),
    ("UK", "London", 6),
    ("Germany", "Berlin", 4),
    ("Canada", "Toronto", 3),
]
# (referrer, weight)  None = direct visit
REFERRERS = [
    ("https://instagram.com", 30),
    ("https://twitter.com", 20),
    ("https://www.linkedin.com", 15),
    ("https://whatsapp.com", 15),
    (None, 20),
]


def pick(items):
    """Weighted random choice. Returns the tuple without its weight."""
    return random.choices(items, weights=[i[-1] for i in items])[0][:-1]


def visitor_hash(n: int) -> str:
    return hashlib.sha256(f"visitor-{n}".encode()).hexdigest()


def make_clicks(link_id: int, count: int, start: datetime, end: datetime, visitors: int = 40):
    seconds = int((end - start).total_seconds())
    rows = []
    for _ in range(count):
        browser, os_name, device = pick(AGENTS)
        country, city = pick(PLACES)
        (referrer,) = pick(REFERRERS)
        rows.append(
            Click(
                link_id=link_id,
                clicked_at=start + timedelta(seconds=random.randint(0, seconds)),
                browser=browser,
                os=os_name,
                device_type=device,
                country=country,
                city=city,
                referrer=referrer,
                visitor_hash=visitor_hash(random.randint(1, visitors)),
            )
        )
    return rows


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Database already has data. Run `python reset_db.py` first, then `python seed.py`.")
            return

        now = datetime.now()
        pw = ph.hash(USER_PASSWORD)

        # ---- users ----
        admin = User(username="admin", email="admin@linkpulse.com", password_hash=pw, role=UserRole.ADMIN)
        demo = User(username="demo_user", email="user@linkpulse.com", password_hash=pw, role=UserRole.USER)
        spam = User(username="spam_user", email="spam@linkpulse.com", password_hash=pw,
                    role=UserRole.USER, is_suspended=True)
        db.add_all([admin, demo, spam])
        db.flush()

        # ---- campaigns ----
        diwali = Campaign(name="Diwali Sale", user_id=demo.id)
        fest = Campaign(name="College Fest", user_id=demo.id)
        db.add_all([diwali, fest])
        db.flush()

        # ---- links (6 demo scenarios) ----
        specs = [
            # 1. normal link
            dict(short_code="diwali1", long_url="https://www.example.com/diwali-sale",
                 user_id=demo.id, campaign_id=diwali.id,
                 n=60, bots=9, start=now - timedelta(days=14), end=now),
            # 2. expiry in the future
            dict(short_code="fest2026", long_url="https://www.example.com/college-fest",
                 user_id=demo.id, campaign_id=fest.id, expires_at=now + timedelta(days=60),
                 n=30, bots=4, start=now - timedelta(days=14), end=now),
            # 3. already expired (HTTP 410)
            dict(short_code="oldoffer", long_url="https://www.example.com/old-offer",
                 user_id=demo.id, campaign_id=diwali.id, expires_at=now - timedelta(days=30),
                 n=12, bots=0, start=now - timedelta(days=60), end=now - timedelta(days=31)),
            # 4. click limit reached (HTTP 429)
            dict(short_code="limit3", long_url="https://www.example.com/limited",
                 user_id=demo.id, campaign_id=diwali.id, click_limit=3,
                 n=3, bots=0, start=now - timedelta(days=3), end=now),
            # 5. password protected
            dict(short_code="secret1", long_url="https://www.example.com/private",
                 user_id=demo.id, campaign_id=None, password_hash=ph.hash(LINK_PASSWORD),
                 n=5, bots=0, start=now - timedelta(days=5), end=now),
            # 6. disabled by admin (HTTP 403), owned by the suspended user
            dict(short_code="badlink", long_url="https://www.example.com/suspicious",
                 user_id=spam.id, campaign_id=None, is_active=False,
                 n=8, bots=0, start=now - timedelta(days=20), end=now - timedelta(days=10)),
        ]

        total_clicks = 0
        for spec in specs:
            n = spec.pop("n")
            bots = spec.pop("bots")
            start = spec.pop("start")
            end = spec.pop("end")
            link = Link(current_clicks=n, bot_clicks=bots, **spec)
            db.add(link)
            db.flush()
            db.add_all(make_clicks(link.id, n, start, end))
            total_clicks += n

        # ---- blocklist ----
        db.add_all([DomainBlocklist(domain=d, added_by=admin.id)
                    for d in ("phishing-scam.com", "free-money-now.xyz")])

        db.commit()
        print(f"Seeded: 3 users, 2 campaigns, {len(specs)} links, {total_clicks} clicks, 2 blocked domains.")
        print("Logins: admin / demo_user / spam_user  (password: Test@1234)")
    finally:
        db.close()


if __name__ == "__main__":
    main()