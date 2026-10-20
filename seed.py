"""Create repeatable demo accounts, links, and click telemetry."""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Click, Link, User, UserRole
from app.security import hash_password

DEMO_USERS = [
    ("maya@example.com", "Maya Chen", "MayaPass123!", UserRole.USER),
    ("alex@example.com", "Alex Rivera", "AlexPass123!", UserRole.USER),
    ("admin@linkpulse.local", "Platform Admin", "AdminPass123!", UserRole.ADMIN),
]
DEMO_LINKS = [
    ("launch", "https://example.com/product-launch", "maya@example.com"),
    ("docs", "https://www.example.org/documentation", "maya@example.com"),
    ("field-notes", "https://example.net/field-notes", "alex@example.com"),
]


def seed_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        users = {}
        for email, username, password, role in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, username=username, password_hash=hash_password(password), role=role)
                db.add(user)
                db.flush()
            users[email] = user
        db.commit()

        for code, destination, owner_email in DEMO_LINKS:
            link = db.scalar(select(Link).where(Link.short_code == code))
            if link is None:
                link = Link(short_code=code, long_url=destination, user_id=users[owner_email].id)
                db.add(link)
                db.flush()
            if db.scalar(select(Click.id).where(Click.link_id == link.id).limit(1)) is None:
                for index in range(120):
                    clicked_at = datetime.utcnow() - timedelta(days=index % 7, hours=index % 24)
                    db.add(Click(
                        link_id=link.id,
                        clicked_at=clicked_at,
                        browser=("Chrome", "Safari", "Firefox")[index % 3],
                        os=("Windows", "iOS", "macOS", "Android")[index % 4],
                        device_type=("Desktop", "Mobile", "Tablet")[index % 3],
                        country=("US", "IN", "GB", "DE")[index % 4],
                        city=("New York", "Mumbai", "London", "Berlin")[index % 4],
                        referrer=("Direct", "https://search.example", "https://social.example")[index % 3],
                    ))
                link.current_clicks = 120
        db.commit()
    print("Seed complete. Demo sign-ins:")
    print("  User:  maya@example.com / MayaPass123!")
    print("  User:  alex@example.com / AlexPass123!")
    print("  Admin: admin@linkpulse.local / AdminPass123!")


if __name__ == "__main__":
    seed_database()