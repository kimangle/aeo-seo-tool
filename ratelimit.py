"""V8: rate limit — kustannuskatkaisija julkisille reiteille.

/api/audit on autentikoimaton crawl-endpoint joka kestää 2,0–2,4 s. Ilman
rajaa se on kenen tahansa käytettävissä rajattomasti, ja Vercel-sekunnit ovat
rahaa. Laskurit elävät Supabasessa (ks. sql/003_rate_hit.sql), koska Vercelin
Python on tilaton eikä muistissa oleva laskuri rajoita mitään.

FAIL-OPEN, tarkoituksella: jos kanta ei vastaa, pyyntö menee läpi. Julkinen
auditointi maksaa 0 € API-kuluina, eikä kantakatkos saa kaataa liidikonetta.
Globaali päiväkatto on se varmistus joka pysäyttää karkaavan tapauksen.

IP:tä ei tallenneta koskaan raakana: sha256(IP_HASH_SALT + ip).
"""
import hashlib
import os
from typing import Dict, List, Tuple

import db


def _limit(name: str, default: int) -> int:
    """Raja ympäristömuuttujasta, oletus jos puuttuu tai on roskaa."""
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def client_ip(environ: Dict[str, str]) -> str:
    """Kutsujan IP. Vercelin oma otsikko ensin — se on ainoa jota ei voi
    väärentää sovelluksesta käsin. X-Forwarded-For voi olla ketju, jonka
    ensimmäinen on alkuperäinen kutsuja."""
    vercel = (environ.get("HTTP_X_VERCEL_FORWARDED_FOR") or "").strip()
    if vercel:
        return vercel.split(",")[0].strip()
    fwd = (environ.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if fwd:
        return fwd.split(",")[0].strip()
    return (environ.get("REMOTE_ADDR") or "").strip()


def ip_hash(ip: str) -> str:
    """Pseudonymisointi. Suola ympäristömuuttujasta: ilman sitä hash olisi
    käännettävissä koko IPv4-avaruuden läpikäynnillä muutamassa minuutissa."""
    salt = os.environ.get("IP_HASH_SALT", "")
    return hashlib.sha256((salt + (ip or "")).encode("utf-8")).hexdigest()


def _rules(scope: str, h: str) -> List[Tuple[str, int, int]]:
    """(avain, raja, ikkuna sekunteina) — kaikki saman pyynnön rajat kerralla,
    jotta HTTPS-kierroksia on yksi eikä kolme."""
    if scope == "audit":
        return [
            (f"audit:ip:{h}", _limit("RL_AUDIT_PER_IP", 3), 600),
            (f"audit:ip24:{h}", _limit("RL_AUDIT_PER_IP_24H", 10), 86400),
            # Kustannuskatkaisija: koko palvelun päiväkatto.
            ("audit:global", _limit("RL_AUDIT_GLOBAL_24H", 300), 86400),
        ]
    if scope == "lead":
        return [(f"lead:ip:{h}", _limit("RL_LEAD_PER_IP", 5), 3600)]
    if scope == "contact":
        return [
            (f"contact:ip:{h}", _limit("RL_CONTACT_PER_IP", 3), 3600),
            ("contact:global", _limit("RL_CONTACT_GLOBAL_24H", 30), 86400),
        ]
    return []


def check(scope: str, environ: Dict[str, str]) -> Tuple[bool, int]:
    """Palauttaa (sallittu, retry_after_sekunteina).

    Kanta pois päältä tai nurin -> (True, 0). Tämä on fail-open eikä bugi."""
    rules = _rules(scope, ip_hash(client_ip(environ)))
    if not rules or not db.configured():
        return True, 0

    res = db.rpc("rate_hit", {
        "p_keys": [r[0] for r in rules],
        "p_limits": [r[1] for r in rules],
        "p_windows": [r[2] for r in rules],
    })
    if not isinstance(res, dict):
        return True, 0
    if res.get("allowed") is False:
        try:
            retry = int(res.get("retry_after") or 60)
        except (TypeError, ValueError):
            retry = 60
        return False, max(retry, 1)
    return True, 0
