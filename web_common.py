"""V8: jaettu web-pään logiikka (api/audit.py ja api/lead.py).

Anglés Marketingin sivusto on staattinen HTML, joten selain kutsuu näitä
funktioita suoraan — palvelinpuolen proxyä ei ole. Siksi CORS-rajaus,
SSRF-esto ja syötteen tarkistus tehdään täällä, ei kutsujassa.
"""
import ipaddress
import json
import os
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

DEFAULT_ORIGINS = (
    "https://anglesmarketing.fi",
    "https://www.anglesmarketing.fi",
)


def allowed_origins() -> Tuple[str, ...]:
    """Sallitut kutsujat. ALLOWED_ORIGINS-ympäristömuuttuja (pilkuin) korvaa
    oletukset — preview-deployta varten."""
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


def read_json(handler) -> dict:
    try:
        length = int(handler.headers.get("content-length") or 0)
        return json.loads(handler.rfile.read(length) or b"{}")
    except (ValueError, json.JSONDecodeError):
        return {}


def send_json(handler, code: int, payload: dict, origin: Optional[str] = None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(data)))
    if origin:
        handler.send_header("access-control-allow-origin", origin)
        handler.send_header("vary", "Origin")
    handler.end_headers()
    handler.wfile.write(data)


def send_preflight(handler):
    origin = cors_origin(handler.headers.get("origin", ""))
    handler.send_response(204 if origin else 403)
    if origin:
        handler.send_header("access-control-allow-origin", origin)
        handler.send_header("access-control-allow-methods", "POST, OPTIONS")
        handler.send_header("access-control-allow-headers", "content-type")
        handler.send_header("access-control-max-age", "86400")
        handler.send_header("vary", "Origin")
    handler.end_headers()
