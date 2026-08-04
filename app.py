"""V8: audit-api — WSGI-sovellus, joka tarjoaa SEO-testin ja lomakkeen reitit.

  POST /api/audit    — auditoi annetun sivuston ja palauttaa pisteet + löydökset
  POST /api/lead     — tallentaa liidin MailerLiteen (vaatii suostumuksen)
  POST /api/contact  — yhteydenottolomake: rivi kantaan + ilmoitus Kimille

Kutsutaan suoraan anglesmarketing.fi:n staattiselta sivustolta.
Tähän palveluun EI aseteta ANTHROPIC_API_KEYtä: auditointi ajaa puhtaana
sääntömoottorina, jolloin julkisen pään ajokohtainen kustannus on nolla.
"""
import json
import os
import re
from datetime import datetime, timezone

import requests

import db
import notify
import ratelimit
from aeo_seo_tool_v7 import AuditFetchError, grade, run_audit
from web_common import allowed_origins, cors_origin, validate_target

MAX_PAGES = 3
RESPONSE_KEYS = ("tool_version", "overall_score", "grade", "critical_alerts",
                 "top_findings", "pages", "recommendations", "site")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAILERLITE_URL = "https://connect.mailerlite.com/api/subscribers"


def _json_response(start_response, code, payload, origin=None, extra_headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [("content-type", "application/json; charset=utf-8"),
               ("content-length", str(len(body)))]
    if origin:
        headers += [("access-control-allow-origin", origin), ("vary", "Origin")]
    if extra_headers:
        headers += list(extra_headers)
    # Jokainen koodi jota jokin haara voi palauttaa on oltava tässä: puuttuva
    # avain nostaa KeyErrorin ja asiakas näkee 500:n oikean statuksen sijaan.
    status = {200: "200 OK", 202: "202 Accepted", 204: "204 No Content",
              400: "400 Bad Request", 401: "401 Unauthorized",
              403: "403 Forbidden", 404: "404 Not Found", 422: "422 Unprocessable Entity",
              429: "429 Too Many Requests",
              500: "500 Internal Server Error", 502: "502 Bad Gateway",
              503: "503 Service Unavailable"}[code]
    start_response(status, headers)
    return [body]


def _too_many(start_response, origin, retry_after, viesti):
    """429 suomeksi + Retry-After. Vastaus on välitön: rajaan osunut pyyntö ei
    ole ajanut auditointia eikä koskenut MailerLiteen."""
    return _json_response(start_response, 429, {"error": viesti},
                          origin, [("retry-after", str(retry_after))])


def _read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        return json.loads(environ["wsgi.input"].read(length) or b"{}")
    except (ValueError, KeyError, json.JSONDecodeError):
        return {}


def _preflight(start_response, origin):
    if not origin:
        start_response("403 Forbidden", [("content-length", "0")])
        return [b""]
    start_response("204 No Content", [
        ("access-control-allow-origin", origin),
        ("access-control-allow-methods", "POST, OPTIONS"),
        ("access-control-allow-headers", "content-type"),
        ("access-control-max-age", "86400"),
        ("vary", "Origin"),
        ("content-length", "0"),
    ])
    return [b""]


def _audit(environ, start_response, origin):
    body = _read_json(environ)
    # Honeypot: botille "onnistuminen" ilman että auditointi ajetaan
    if body.get("website"):
        return _json_response(start_response, 202, {"ok": True}, origin)

    # Rate limit vasta honeypotin jälkeen: botti ei saa kuluttaa oikeiden
    # kävijöiden kiintiötä, ja ennen run_auditia, koska juuri sen 2,4 sekuntia
    # tässä maksaa
    allowed, retry = ratelimit.check("audit", environ)
    if not allowed:
        return _too_many(start_response, origin, retry,
                         "Testejä on tehty liikaa — kokeile hetken kuluttua uudelleen")

    url = validate_target(str(body.get("url", "")))
    if not url:
        return _json_response(start_response, 400, {
            "error": "Osoite ei kelpaa — anna julkinen verkko-osoite, esim. yrityksesi.fi"
        }, origin)

    try:
        result = run_audit(url, max_pages=MAX_PAGES)
    except AuditFetchError as e:
        return _json_response(start_response, 422, {"error": str(e)}, origin)
    except Exception:
        return _json_response(start_response, 500, {
            "error": "Auditointi epäonnistui — yritä hetken kuluttua uudelleen"
        }, origin)
    return _json_response(start_response, 200,
                          {k: result[k] for k in RESPONSE_KEYS}, origin)


def _lead(environ, start_response, origin):
    body = _read_json(environ)
    # /api/lead:llä ei ole honeypottia (lomake ei lähetä sellaista kenttää),
    # joten raja on tässä ensimmäisenä
    allowed, retry = ratelimit.check("lead", environ)
    if not allowed:
        return _too_many(start_response, origin, retry,
                         "Liian monta lähetystä — kokeile hetken kuluttua uudelleen")

    email = str(body.get("email", "")).strip()
    if not EMAIL_RE.match(email):
        return _json_response(start_response, 400,
                              {"error": "Tarkista sähköpostiosoite"}, origin)
    if body.get("consent") is not True:
        return _json_response(start_response, 400,
                              {"error": "Raportin lähetys vaatii suostumuksen"}, origin)

    key = os.environ.get("MAILERLITE_API_KEY", "")
    group = os.environ.get("MAILERLITE_GROUP_ID", "")
    if not key or not group:
        return _json_response(start_response, 503,
                              {"error": "Lähetys ei ole juuri nyt käytössä"}, origin)

    # requests (ei urllib) — se käyttää certifin varmennepakettia, joten
    # TLS toimii myös koneilla joilla järjestelmän juurivarmenteet puuttuvat
    try:
        resp = requests.post(MAILERLITE_URL, timeout=15, headers={
            "authorization": f"Bearer {key}",
        }, json={
            "email": email,
            "groups": [group],
            "fields": {
                "audit_site_url": str(body.get("siteUrl", ""))[:255],
                # round, ei int: sivu näyttää pyöristetyn luvun, ja sähköpostissa
                # on oltava sama luku jonka asiakas näki (40.8 -> 41, ei 40)
                "audit_score": str(round(float(body.get("score") or 0))),
                # arvosana lasketaan samalla asteikolla kuin raporteissa, jotta
                # sähköpostissa ei lue kiinteää arvosanaa jokaiselle
                "audit_grade": grade(float(body.get("score") or 0)),
                "audit_source": str(body.get("source", ""))[:100],
            },
        })
        ok = resp.status_code in (200, 201)
    except requests.RequestException:
        ok = False
    if not ok:
        return _json_response(start_response, 502,
                              {"error": "Lähetys epäonnistui — yritä uudelleen"}, origin)
    return _json_response(start_response, 200, {"ok": True}, origin)


def _contact(environ, start_response, origin):
    """Yhteydenottolomake. Järjestys: honeypot -> raja -> tarkistus -> kanta
    -> ilmoitus. Kantainsertin epäonnistuminen EI kaada pyyntöä: maili lähtee
    silti ja vastaus on 200, koska liidi Kimin postilaatikossa voittaa 500:n
    asiakkaan selaimessa."""
    body = _read_json(environ)

    # Honeypot ennen kaikkea muuta: botille "onnistuminen" ilman riviä, ilman
    # mailia ja ilman että se kuluttaa oikeiden kävijöiden kiintiötä.
    # Kaksi nimeä, koska lomake kantoi aiemmin Netlifyn bot-field-konventiota.
    if body.get("website") or body.get("bot-field"):
        return _json_response(start_response, 202, {"ok": True}, origin)

    allowed, retry = ratelimit.check("contact", environ)
    if not allowed:
        return _too_many(start_response, origin, retry,
                         "Liian monta viestiä — kokeile hetken kuluttua uudelleen")

    nimi = str(body.get("nimi") or body.get("name") or "").strip()
    email = str(body.get("email") or "").strip()
    viesti = str(body.get("viesti") or body.get("message") or "").strip()
    ala = str(body.get("ala") or "").strip()
    paketti = str(body.get("paketti") or "").strip()

    if not 1 <= len(nimi) <= 120:
        return _json_response(start_response, 400, {"error": "Kerro nimesi"}, origin)
    if not EMAIL_RE.match(email):
        return _json_response(start_response, 400,
                              {"error": "Tarkista sähköpostiosoite"}, origin)
    if len(viesti) > 4000:
        return _json_response(start_response, 400,
                              {"error": "Viesti on liian pitkä — enintään 4000 merkkiä"},
                              origin)
    if len(ala) > 200 or len(paketti) > 200:
        return _json_response(start_response, 400,
                              {"error": "Ala tai paketti on liian pitkä"}, origin)

    utm = body.get("utm")
    lead = {
        "nimi": nimi,
        "email": email,
        "ala": ala or None,
        "paketti": paketti or None,
        "viesti": viesti or None,
        "source": str(body.get("source") or "yhteystiedot")[:100],
        "utm": utm if isinstance(utm, dict) else None,
        "ip_hash": ratelimit.ip_hash(ratelimit.client_ip(environ)),
        "user_agent": str(environ.get("HTTP_USER_AGENT", ""))[:255],
    }

    rows = db.insert("contact_leads", lead, returning=True)
    lead_id = None
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        lead_id = rows[0].get("id")

    status = notify.contact_lead(lead)
    if status == "ok" and lead_id:
        # ISO-aikaleima Pythonista, ei "now()"-merkkijonoa: PostgREST lähettää
        # arvon literaalina eikä SQL-funktiona
        db.patch("contact_leads", {"id": f"eq.{lead_id}"},
                 {"notified_at": datetime.now(timezone.utc).isoformat()})

    return _json_response(start_response, 200, {"ok": True}, origin)


def _health(start_response):
    """Kertoo onko palvelu konfiguroitu — ei koskaan arvoja, vain onko asetettu.
    Ilman tätä väärä tai puuttuva avain näkyy vain geneerisenä 503:na."""
    key = os.environ.get("MAILERLITE_API_KEY", "")
    group = os.environ.get("MAILERLITE_GROUP_ID", "")
    return _json_response(start_response, 200, {
        "audit": "ok",
        "mailerlite_key_set": bool(key),
        "mailerlite_key_len": len(key),
        "mailerlite_group_set": bool(group),
        "allowed_origins": len(allowed_origins()),
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY", "")),
    })


def app(environ, start_response):
    path = environ.get("PATH_INFO", "").rstrip("/")
    method = environ.get("REQUEST_METHOD", "GET")
    origin = cors_origin(environ.get("HTTP_ORIGIN", ""))

    if method == "GET" and path == "/api/health":
        return _health(start_response)
    if method == "OPTIONS":
        return _preflight(start_response, origin)
    routes = {"/api/audit": _audit, "/api/lead": _lead, "/api/contact": _contact}
    if path not in routes:
        return _json_response(start_response, 404, {"error": "not found"})
    if method != "POST":
        return _json_response(start_response, 404, {"error": "not found"})
    if not origin:
        return _json_response(start_response, 403, {"error": "forbidden"})

    return routes[path](environ, start_response, origin)
