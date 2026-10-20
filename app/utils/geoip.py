"""Offline GeoLite2 lookup wrapper; returns empty values when the database is absent."""

from functools import lru_cache

import geoip2.database
import geoip2.errors

from app.config import settings


@lru_cache(maxsize=1)
def _reader() -> geoip2.database.Reader | None:
    if not settings.geoip_database.is_file():
        return None
    try:
        return geoip2.database.Reader(str(settings.geoip_database))
    except (OSError, ValueError):
        return None


def lookup_ip(ip_address: str | None) -> tuple[str | None, str | None]:
    if not ip_address or ip_address in {"127.0.0.1", "::1"}:
        return None, None
    reader = _reader()
    if reader is None:
        return None, None
    try:
        result = reader.city(ip_address)
        return result.country.iso_code, result.city.name
    except (geoip2.errors.AddressNotFoundError, ValueError):
        return None, None
