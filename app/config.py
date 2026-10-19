"""Environment-backed application settings."""

import os
from pathlib import Path

from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    app_name = "LinkPulse"
    database_url = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://linkpulse:linkpulse@127.0.0.1:3306/linkpulse?charset=utf8mb4",
    )
    secret_key = os.getenv("SECRET_KEY", "change-this-development-secret-before-deploying")
    public_base_url = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    geoip_database = Path(os.getenv("GEOIP_DATABASE", str(BASE_DIR / "data" / "GeoLite2-City.mmdb")))
    session_cookie = "linkpulse_session"
    session_max_age = 86400


settings = Settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[])