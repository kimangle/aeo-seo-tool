"""V8: audit-api — WSGI-sovellus, joka tarjoaa SEO-testin ja lomakkeen reitit.

  POST /api/audit    — auditoi annetun sivuston ja palauttaa pisteet + löydökset
  POST /api/lead     — tallentaa liidin MailerLiteen (vaatii suostumuksen)
  POST /api/contact  — yhteydenotto: tilaaja MailerLiteen + ilmoitus Kimille

Kutsutaan suoraan anglesmarketing.fi:n staattiselta sivustolta.
Tähän palveluun EI aseteta ANTHROPIC_API_KEYtä: auditointi ajaa puhtaana
sääntömoottorina, jolloin julkisen pään ajokohtainen kustannus on nolla.
"""
import json
import os
import re

import requests

import notify
from aeo_seo_tool_v7 import AuditFetchError, grade, run_audit
from web_common import allowed_origins, cors_origin, validate_target

MAX_PAGES = 3
RESPONSE_KEYS = ("tool_version", "overall_score", "grade", "critical_alerts",
                 "top_findings", "pages", "recommendations", "site")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAILERLITE_URL = "https://connect.mailerlite.com/api/subscribers"


def _json_response(start_response, code, payload, origin=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [("content-type", "application/json; charset=utf-8"),
               ("content-length", str(len(body)))]
    if origin:
        headers += [("access-control-allow-origin", origin), ("vary", "Origin")]
    status = {200: "200 OK", 202: "202 Accepted", 400: "400 Bad Request",
              403: "403 Forbidden", 404: "404 Not Found", 422: "422 Unprocessable Entity",
              500: "500 Internal Server Error", 502: "502 Bad Gateway",
              503: "503 Service Unavailable"}[code]
    start_response(status, headers)
    return [body]


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


def _contact_to_mailerlite(lead):
    """Tilaaja yhteydenottoryhmään. Oma ryhmänsä SEO-testin ryhmästä erillään:
    eri viesti, eri automaatio. Palauttaa True/False eikä koskaan nosta
    poikkeusta — kutsuja jatkaa ilmoitusmailiin myös epäonnistuessa."""
    key = os.environ.get("MAILERLITE_API_KEY", "")
    group = os.environ.get("MAILERLITE_CONTACT_GROUP_ID", "")
    if not key or not group:
        return False
    try:
        resp = requests.post(MAILERLITE_URL, timeout=15, headers={
            "authorization": f"Bearer {key}",
        }, json={
            "email": lead["email"],
            "groups": [group],
            "fields": {
                "contact_nimi": lead["nimi"][:120],
                "contact_ala": lead["ala"][:200],
                "contact_paketti": lead["paketti"][:200],
                # Katkaistu: koko viesti menee ilmoitusmailissa, ja MailerLiten
                # tekstikenttä on lyhyt — vapaata tekstiä ei lueta sieltä
                "contact_viesti": lead["viesti"][:255],
                "contact_source": lead["source"][:100],
            },
        })
        return resp.status_code in (200, 201)
    except requests.RequestException:
        return False


def _contact(environ, start_response, origin):
    """Yhteydenottolomake. Järjestys: honeypot -> tarkistus -> MailerLite ->
    ilmoitus. MailerLiten epäonnistuminen EI kaada pyyntöä: maili lähtee silti
    ja vastaus on 200, koska liidi Kimin postilaatikossa voittaa 500:n
    asiakkaan selaimessa. Vasta jos molemmat epäonnistuvat tulee 502, jotta
    lomake näyttää virhetilansa eikä valehtele onnistumisesta."""
    body = _read_json(environ)

    # Honeypot ennen kaikkea muuta: botille "onnistuminen" ilman MailerLite-
    # kutsua ja ilman mailia. Kaksi nimeä, koska lomake kantoi aiemmin
    # Netlifyn bot-field-konventiota.
    if body.get("website") or body.get("bot-field"):
        return _json_response(start_response, 202, {"ok": True}, origin)

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

    lead = {
        "nimi": nimi,
        "email": email,
        "ala": ala,
        "paketti": paketti,
        "viesti": viesti,
        "source": str(body.get("source") or "yhteystiedot")[:100],
    }

    subscribed = _contact_to_mailerlite(lead)
    # Ilmoitus yritetään aina, myös kun MailerLite kaatui: vapaa viesti on juuri
    # tämän mailin pointti, koska Kim ei lue viestikenttiä MailerLitesta
    notified = notify.contact_lead(lead) == "ok"
    if not subscribed and not notified:
        return _json_response(start_response, 502, {
            "error": "Viestin lähetys epäonnistui — yritä hetken kuluttua uudelleen"
        }, origin)
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
        "mailerlite_contact_group_set": bool(
            os.environ.get("MAILERLITE_CONTACT_GROUP_ID", "")),
        "notify_configured": bool(os.environ.get("RESEND_API_KEY", "")
                                  and os.environ.get("NOTIFY_EMAIL", "")),
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
