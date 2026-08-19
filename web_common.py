"""V8: jaettu web-pään logiikka (app.py:n reitit).

Anglés Marketingin sivusto on staattinen HTML, joten selain kutsuu tätä
palvelinta suoraan — proxyä ei ole. Siksi CORS-rajaus, SSRF-esto ja syötteen
tarkistus tehdään täällä, ei kutsujassa.
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


# ── V8: WSGI-vastaukset (jaettu app.py:n ja dev_console.py:n kesken) ─────────

STATUS = {200: "200 OK", 202: "202 Accepted", 204: "204 No Content",
          400: "400 Bad Request", 401: "401 Unauthorized", 403: "403 Forbidden",
          404: "404 Not Found", 422: "422 Unprocessable Entity",
          500: "500 Internal Server Error", 502: "502 Bad Gateway",
          503: "503 Service Unavailable"}


def json_response(start_response, code, payload, origin=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [("content-type", "application/json; charset=utf-8"),
               ("content-length", str(len(body)))]
    if origin:
        headers += [("access-control-allow-origin", origin), ("vary", "Origin")]
    start_response(STATUS[code], headers)
    return [body]


def html_response(start_response, code, html):
    """Konsolisivu. no-store ja noindex: tämä on sisäinen näkymä, jota ei
    tallenneta välimuistiin eikä indeksoida hakukoneisiin."""
    body = html.encode("utf-8")
    start_response(STATUS[code], [
        ("content-type", "text/html; charset=utf-8"),
        ("content-length", str(len(body))),
        ("cache-control", "no-store"),
        ("x-robots-tag", "noindex, nofollow"),
        ("referrer-policy", "no-referrer"),
    ])
    return [body]


def read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        return json.loads(environ["wsgi.input"].read(length) or b"{}")
    except (ValueError, KeyError, json.JSONDecodeError):
        return {}
