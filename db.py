"""V8: ohut PostgREST-kääre Supabaseen.

Supabaseen puhutaan suoraan PostgRESTillä `requests`-kirjastolla, ei
`supabase-py`:llä: se raahaisi mukanaan httpx:n, postgrestin, gotruen,
storage3:n ja realtimen kolmea HTTP-kutsua varten ja kasvattaisi
kylmäkäynnistystä funktiossa jonka koko myyntiargumentti on 2 sekunnin budjetti.

Kaikki tämän moduulin funktiot palauttavat None virheessä eivätkä koskaan nosta
poikkeusta. Kantakatkos ei saa kaataa liidikonetta: liidi Kimin postilaatikossa
voittaa 500:n asiakkaan selaimessa.

Selain ei puhu Supabaselle koskaan. Service-role-avain elää vain Vercelin
ympäristömuuttujana; anon-avainta ei käytetä missään.
"""
import os
from typing import Any, Dict, List, Optional

import requests

# Lyhyet aikakatkaisut: kanta on liidipolun sivuvaikutus, ei sen ehto.
# (connect, read) sekunteina.
TIMEOUT = (2, 3)


def base_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _key() -> str:
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def configured() -> bool:
    """Onko kanta konfiguroitu lainkaan. Ilman tätä jokainen kutsu olisi
    turha HTTP-yritys ja aikakatkaisun verran hukkaa."""
    return bool(base_url() and _key())


def _headers(prefer: str = "") -> Dict[str, str]:
    key = _key()
    h = {
        "apikey": key,
        "authorization": f"Bearer {key}",
        "content-type": "application/json",
    }
    if prefer:
        h["prefer"] = prefer
    return h


def insert(table: str, row: Any, returning: bool = False) -> Optional[Any]:
    """Lisää rivin (tai rivilistan). Palauttaa listan luoduista riveistä kun
    returning=True, muuten True. None = ei onnistunut."""
    if not configured():
        return None
    prefer = "return=representation" if returning else "return=minimal"
    try:
        resp = requests.post(f"{base_url()}/rest/v1/{table}",
                             headers=_headers(prefer), json=row, timeout=TIMEOUT)
        if resp.status_code not in (200, 201, 204):
            return None
        if not returning:
            return True
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def patch(table: str, filters: Dict[str, str], values: Dict[str, Any],
          returning: bool = False) -> Optional[Any]:
    """Päivittää rivejä. filters on PostgREST-muotoa: {"id": "eq.<uuid>"}."""
    if not configured():
        return None
    prefer = "return=representation" if returning else "return=minimal"
    try:
        resp = requests.patch(f"{base_url()}/rest/v1/{table}",
                              headers=_headers(prefer), params=filters,
                              json=values, timeout=TIMEOUT)
        if resp.status_code not in (200, 204):
            return None
        return resp.json() if returning else True
    except (requests.RequestException, ValueError):
        return None


def select(table: str, params: Optional[Dict[str, str]] = None) -> Optional[List[Any]]:
    """Hakee rivejä. params on PostgREST-muotoa:
    {"select": "id,score", "id": "eq.<uuid>", "limit": "1"}."""
    if not configured():
        return None
    try:
        resp = requests.get(f"{base_url()}/rest/v1/{table}",
                            headers=_headers(), params=params or {}, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def rpc(fn: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Kutsuu tallennettua funktiota (esim. rate_hit)."""
    if not configured():
        return None
    try:
        resp = requests.post(f"{base_url()}/rest/v1/rpc/{fn}",
                             headers=_headers(), json=payload or {}, timeout=TIMEOUT)
        if resp.status_code not in (200, 201, 204):
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None
