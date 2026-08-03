"""V8: liidin talteenotto MailerLiteen SEO-testin sähköpostiportilta.

GDPR: tilaaja luodaan vain kun consent === true (checkbox ei ole esivalittu
sivulla). API-avain elää vain palvelimen ympäristössä, ei selaimessa.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web_common import cors_origin, read_json, send_json, send_preflight  # noqa: E402

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAILERLITE_URL = "https://connect.mailerlite.com/api/subscribers"


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_preflight(self)

    def do_POST(self):
        origin = cors_origin(self.headers.get("origin", ""))
        if not origin:
            send_json(self, 403, {"error": "forbidden"})
            return

        body = read_json(self)
        email = str(body.get("email", "")).strip()
        if not EMAIL_RE.match(email):
            send_json(self, 400, {"error": "Tarkista sähköpostiosoite"}, origin)
            return
        if body.get("consent") is not True:
            send_json(self, 400, {"error": "Raportin lähetys vaatii suostumuksen"}, origin)
            return

        key = os.environ.get("MAILERLITE_API_KEY", "")
        group = os.environ.get("MAILERLITE_GROUP_ID", "")
        if not key or not group:
            send_json(self, 503, {"error": "Lähetys ei ole juuri nyt käytössä"}, origin)
            return

        payload = json.dumps({
            "email": email,
            "groups": [group],
            "fields": {
                "audit_site_url": str(body.get("siteUrl", ""))[:255],
                "audit_score": str(int(float(body.get("score") or 0))),
                "audit_source": str(body.get("source", ""))[:100],
            },
        }).encode("utf-8")
        req = urllib.request.Request(MAILERLITE_URL, data=payload, method="POST", headers={
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = resp.status in (200, 201)
        except (urllib.error.URLError, OSError):
            ok = False
        if not ok:
            send_json(self, 502, {"error": "Lähetys epäonnistui — yritä uudelleen"}, origin)
            return
        send_json(self, 200, {"ok": True}, origin)
