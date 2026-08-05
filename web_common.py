"""V8: jaettu web-pään logiikka (app.py:n reitit).

Anglés Marketingin sivusto on staattinen HTML, joten selain kutsuu tätä
palvelinta suoraan — proxyä ei ole. Siksi CORS-rajaus, SSRF-esto ja syötteen
tarkistus tehdään täällä, ei kutsujassa.
"""
import ipaddress
import os
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

DEFAULT_ORIGINS = (
    "https://anglesmarketing.fi",
    "https://www.anglesmarketing.fi",
)


def allowed_origins() -> Tuple[str, ...]:
    """Sallitut kutsujat. ALLOWED_ORIGINS-ympäristömuuttuja (pilkuin) lisää
    oletusten päälle — demo- ja preview-osoitteita varten."""
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    extra = tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())
    return DEFAULT_ORIGINS + extra


def cors_origin(request_origin: str) -> Optional[str]:
    o = (request_origin or "").rstrip("/")
    return o if o in allowed_origins() else None


def _ip_is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_reserved or addr.is_multicast or addr.is_unspecified)


def validate_target(raw: str) -> Optional[str]:
    """SSRF-esto: palauttaa normalisoidun URLin tai None. Hylkää muut kuin
    http(s), sisäverkkonimet ja kaikki osoitteet jotka resolvoituvat
    privaattiin, loopbackiin tai link-localiin (esim. 169.254.169.254)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.lower().startswith(("http://", "https://")):
        raw = "https://" + raw
    u = urlparse(raw)
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    host = u.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return None
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None
    if not infos:
        return None
    for info in infos:
        if _ip_is_private(info[4][0]):
            return None
    return u.geturl()
