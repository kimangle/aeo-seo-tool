"""V8: Vercel Python -funktio — auditoi URL:n run_auditilla ja palauttaa JSONin.

Kutsutaan vain lisamyyntia-siten /api/audit-proxyn kautta, joka tekee
URL-validoinnin, SSRF-eston ja rate limitin. Tämä pää vaatii jaetun
salaisuuden (AUDIT_INTERNAL_KEY) x-internal-key-headerissa.

Tähän projektiin EI aseteta ANTHROPIC_API_KEYtä — auditointi ajaa puhtaana
sääntömoottorina, jolloin julkisen pään ajokohtainen kustannus on nolla.
"""
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeo_seo_tool_v7 import AuditFetchError, run_audit  # noqa: E402

MAX_PAGES = 3
RESPONSE_KEYS = ("tool_version", "overall_score", "grade", "critical_alerts",
                 "top_findings", "pages", "recommendations", "site")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        secret = os.environ.get("AUDIT_INTERNAL_KEY", "")
        given = self.headers.get("x-internal-key", "")
        if not secret or not hmac.compare_digest(given, secret):
            self._send(401, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("content-length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            url = str(body.get("url", "")).strip()
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "Virheellinen pyyntö"})
            return
        if not url.startswith(("http://", "https://")):
            self._send(400, {"error": "Osoitteen pitää alkaa http:// tai https://"})
            return

        try:
            result = run_audit(url, max_pages=MAX_PAGES)
        except AuditFetchError as e:
            self._send(422, {"error": str(e)})
            return
        except Exception:
            self._send(500, {"error": "Auditointi epäonnistui — yritä hetken kuluttua uudelleen"})
            return
        self._send(200, {k: result[k] for k in RESPONSE_KEYS})

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
