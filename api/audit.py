"""V8: Vercel Python -funktio — auditoi URL:n run_auditilla ja palauttaa JSONin.

Kutsutaan suoraan anglesmarketing.fi:n staattiselta seo-testi-sivulta, joten
CORS-rajaus ja SSRF-esto tehdään täällä (web_common).

Tähän projektiin EI aseteta ANTHROPIC_API_KEYtä — auditointi ajaa puhtaana
sääntömoottorina, jolloin julkisen pään ajokohtainen kustannus on nolla.
"""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeo_seo_tool_v7 import AuditFetchError, run_audit  # noqa: E402
from web_common import (  # noqa: E402
    cors_origin, read_json, send_json, send_preflight, validate_target,
)

MAX_PAGES = 3
RESPONSE_KEYS = ("tool_version", "overall_score", "grade", "critical_alerts",
                 "top_findings", "pages", "recommendations", "site")


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_preflight(self)

    def do_POST(self):
        origin = cors_origin(self.headers.get("origin", ""))
        if not origin:
            send_json(self, 403, {"error": "forbidden"})
            return

        body = read_json(self)
        # Honeypot: botille "onnistuminen" ilman että auditointi ajetaan
        if body.get("website"):
            send_json(self, 202, {"ok": True}, origin)
            return

        url = validate_target(str(body.get("url", "")))
        if not url:
            send_json(self, 400, {
                "error": "Osoite ei kelpaa — anna julkinen verkko-osoite, esim. yrityksesi.fi"
            }, origin)
            return

        try:
            result = run_audit(url, max_pages=MAX_PAGES)
        except AuditFetchError as e:
            send_json(self, 422, {"error": str(e)}, origin)
            return
        except Exception:
            send_json(self, 500, {
                "error": "Auditointi epäonnistui — yritä hetken kuluttua uudelleen"
            }, origin)
            return
        send_json(self, 200, {k: result[k] for k in RESPONSE_KEYS}, origin)
