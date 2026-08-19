"""V8: kehittäjäkonsoli — Kimin oma näkymä asiakkaisiin ja liideihin.

  GET  /dev                — konsolisivu (HTML, ei dataa ilman tunnusta)
  GET  /api/dev/clients    — asiakkaat ja liidit JSONina
  POST /api/dev/audit      — ajaa auditin yhdelle asiakkaalle konsolista

Tunnistautuminen: DEV_TOKEN-ympäristömuuttuja. Selain lähettää sen
x-dev-token-otsakkeessa; ilman sitä data-reitit vastaavat 401. Jos DEV_TOKEN
puuttuu, konsoli on kokonaan pois päältä (503) — tyhjä tunnus ei koskaan avaa
näkymää vahingossa.

Asiakastiedot luetaan MailerLitesta, joka on tämän palvelun ainoa tietovarasto:
SEO-testin liidit (MAILERLITE_GROUP_ID) ja yhteydenotot
(MAILERLITE_CONTACT_GROUP_ID) yhdistetään sähköpostin perusteella yhdeksi
asiakasriviksi. Konsoli ei kirjoita MailerLiteen mitään.
"""
import hmac
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from aeo_seo_tool_v7 import AuditFetchError, run_audit
from web_common import html_response, json_response, read_json, validate_target

MAILERLITE_GROUPS_URL = "https://connect.mailerlite.com/api/groups"
PAGE_LIMIT = 100          # MailerLiten sivukoko
MAX_PAGES = 20            # katto: 2000 tilaajaa riittää konsolinäkymään
AUDIT_MAX_PAGES = 3       # sama kuin julkisessa SEO-testissä


# ── Tunnistautuminen ────────────────────────────────────────────────────────

def _expected_token() -> str:
    return os.environ.get("DEV_TOKEN", "")


def _token_from(environ) -> str:
    return (environ.get("HTTP_X_DEV_TOKEN") or "").strip()


def _authorized(environ) -> Tuple[bool, Optional[int]]:
    """Palauttaa (ok, virhekoodi). 503 = konsolia ei ole konfiguroitu,
    401 = väärä tai puuttuva tunnus."""
    expected = _expected_token()
    if not expected:
        return False, 503
    given = _token_from(environ)
    if not given or not hmac.compare_digest(given, expected):
        return False, 401
    return True, None


# ── MailerLite-haku ─────────────────────────────────────────────────────────

def _fetch_group(key: str, group_id: str) -> List[Dict[str, Any]]:
    """Hakee ryhmän tilaajat sivutettuna. Verkkovirhe ei kaada konsolia:
    palautetaan se mitä ehdittiin saada."""
    out: List[Dict[str, Any]] = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"limit": PAGE_LIMIT}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(f"{MAILERLITE_GROUPS_URL}/{group_id}/subscribers",
                                timeout=15, params=params,
                                headers={"authorization": f"Bearer {key}",
                                         "accept": "application/json"})
            if resp.status_code != 200:
                break
            payload = resp.json()
        except (requests.RequestException, ValueError):
            break
        out += payload.get("data") or []
        cursor = (payload.get("meta") or {}).get("next_cursor")
        if not cursor:
            break
    return out


def _ts(raw: Any) -> str:
    """MailerLite palauttaa ajat muodossa 'YYYY-MM-DD HH:MM:SS' (UTC).
    Normalisoidaan ISO-muotoon; kelvoton arvo katoaa tyhjänä."""
    s = str(raw or "").strip()
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(
            tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ""


def _pyorista(x: float) -> int:
    """Puolikkaat ylöspäin, ei Pythonin pankkiiripyöristystä: konsolissa on
    näyttävä sama luku kuin asiakkaan raportissa (64,5 -> 65, ei 64)."""
    return math.floor(x + 0.5)


def _num(raw: Any) -> Optional[int]:
    try:
        return _pyorista(float(str(raw).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _blank_client(email: str) -> Dict[str, Any]:
    return {"email": email, "nimi": "", "sivusto": "", "score": None, "grade": "",
            "ala": "", "paketti": "", "viesti": "", "lahteet": [], "tyypit": [],
            "status": "", "eka": "", "viim": ""}


def _merge(client: Dict[str, Any], sub: Dict[str, Any], tyyppi: str) -> None:
    """Yhdistää yhden MailerLite-tilaajan asiakasriviin. Uudempi tieto voittaa
    vain jos se ei ole tyhjä — yhteydenotossa ei ole audit-pisteitä eikä
    SEO-testin liidissä nimeä, joten rivit täydentävät toisiaan."""
    fields = sub.get("fields") or {}

    def take(avain: str, *lahteet: str) -> None:
        for f in lahteet:
            arvo = str(fields.get(f) or "").strip()
            if arvo:
                client[avain] = arvo
                return

    take("nimi", "contact_nimi", "name")
    take("sivusto", "audit_site_url")
    take("grade", "audit_grade")
    take("ala", "contact_ala")
    take("paketti", "contact_paketti")
    take("viesti", "contact_viesti")

    score = _num(fields.get("audit_score"))
    if score is not None and client["score"] is None:
        client["score"] = score

    lahde = str(fields.get("contact_source") or fields.get("audit_source") or "").strip()
    if lahde and lahde not in client["lahteet"]:
        client["lahteet"].append(lahde)
    if tyyppi not in client["tyypit"]:
        client["tyypit"].append(tyyppi)

    # Tilaksi jää vähiten mairitteleva: peruutus yhdessäkin ryhmässä näkyy
    tila = str(sub.get("status") or "").strip()
    if tila and (not client["status"] or tila != "active"):
        client["status"] = tila

    luotu = _ts(sub.get("subscribed_at") or sub.get("created_at"))
    muokattu = _ts(sub.get("updated_at")) or luotu
    if luotu and (not client["eka"] or luotu < client["eka"]):
        client["eka"] = luotu
    if muokattu and muokattu > client["viim"]:
        client["viim"] = muokattu


def collect_clients() -> Dict[str, Any]:
    """Kokoaa asiakasnäkymän. Palauttaa aina rakenteen — puuttuva konfiguraatio
    kerrotaan lahteet-kentässä, jotta konsoli näyttää syyn tyhjälle listalle."""
    key = os.environ.get("MAILERLITE_API_KEY", "")
    audit_group = os.environ.get("MAILERLITE_GROUP_ID", "")
    contact_group = os.environ.get("MAILERLITE_CONTACT_GROUP_ID", "")

    lahteet = {"mailerlite_avain": bool(key),
               "seo_testi_ryhma": bool(audit_group),
               "yhteydenotto_ryhma": bool(contact_group)}

    clients: Dict[str, Dict[str, Any]] = {}
    if key:
        for group_id, tyyppi in ((audit_group, "seo-testi"),
                                 (contact_group, "yhteydenotto")):
            if not group_id:
                continue
            for sub in _fetch_group(key, group_id):
                email = str(sub.get("email") or "").strip().lower()
                if not email:
                    continue
                _merge(clients.setdefault(email, _blank_client(email)), sub, tyyppi)

    rivit = sorted(clients.values(), key=lambda c: c["viim"] or c["eka"], reverse=True)
    return {"clients": rivit, "stats": _stats(rivit), "lahteet": lahteet}


def _stats(rivit: List[Dict[str, Any]]) -> Dict[str, Any]:
    raja = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pisteet = [c["score"] for c in rivit if c["score"] is not None]
    return {
        "asiakkaita": len(rivit),
        "yhteydenottoja": sum(1 for c in rivit if "yhteydenotto" in c["tyypit"]),
        "uusia_7pv": sum(1 for c in rivit if (c["eka"] or "") >= raja),
        "keskipisteet": _pyorista(sum(pisteet) / len(pisteet)) if pisteet else None,
    }


# ── Reitit ──────────────────────────────────────────────────────────────────

def page(start_response):
    return html_response(start_response, 200, PAGE)


def clients(environ, start_response):
    ok, code = _authorized(environ)
    if not ok:
        return json_response(start_response, code, {
            "error": ("Konsoli ei ole käytössä — aseta DEV_TOKEN"
                      if code == 503 else "Väärä tunnus")})
    return json_response(start_response, 200, collect_clients())


def audit(environ, start_response):
    """Auditoi asiakkaan sivuston konsolista. Sama moottori kuin julkisessa
    SEO-testissä, mutta ilman CORS-rajausta: tämä on saman origin'in sisäinen
    kutsu, jonka tunnus suojaa."""
    ok, code = _authorized(environ)
    if not ok:
        return json_response(start_response, code, {
            "error": ("Konsoli ei ole käytössä — aseta DEV_TOKEN"
                      if code == 503 else "Väärä tunnus")})

    url = validate_target(str(read_json(environ).get("url", "")))
    if not url:
        return json_response(start_response, 400, {"error": "Osoite ei kelpaa"})
    try:
        result = run_audit(url, max_pages=AUDIT_MAX_PAGES)
    except AuditFetchError as e:
        return json_response(start_response, 422, {"error": str(e)})
    except Exception:
        return json_response(start_response, 500, {"error": "Auditointi epäonnistui"})
    return json_response(start_response, 200, {
        "url": url,
        "overall_score": result["overall_score"],
        "grade": result["grade"],
        "critical_alerts": result["critical_alerts"],
        "top_findings": result["top_findings"],
        "pages": len(result["pages"]),
    })


# ── Konsolisivu ─────────────────────────────────────────────────────────────
# Staattinen sivu: data haetaan selaimesta /api/dev/clients-reitiltä tunnuksella,
# joten HTML:ssä ei ole koskaan asiakastietoja eikä avaimia.
PAGE = r'''<!doctype html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<link rel="icon" href="data:,">
<title>Anglés · kehittäjäkonsoli</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;
  background:#0f172a;color:#e2e8f0;font-size:14px;min-height:100vh}
a{color:#89CFF0}
.wrap{max-width:1180px;margin:0 auto;padding:26px 20px 60px}
header{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding-bottom:20px;border-bottom:1px solid #1e293b;margin-bottom:24px}
header h1{font-size:1.15rem;font-weight:700;letter-spacing:-.01em}
header .dot{width:9px;height:9px;border-radius:99px;background:#89CFF0}
header .spacer{flex:1}
button{font-family:inherit;font-size:.8rem;font-weight:700;border-radius:8px;
  border:1px solid #334155;background:#1e293b;color:#e2e8f0;padding:8px 14px;cursor:pointer}
button:hover{background:#243050}
button.primary{background:#89CFF0;border-color:#89CFF0;color:#0f172a}
button.primary:hover{background:#6dbfe8}
button:disabled{opacity:.5;cursor:default}
input{font-family:inherit;font-size:.85rem;background:#0f172a;border:1px solid #334155;
  color:#e2e8f0;border-radius:8px;padding:10px 12px;width:100%}
input:focus{outline:none;border-color:#89CFF0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:22px}
.tile{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:18px 20px}
.tile .k{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;color:#64748b;font-weight:700}
.tile .v{font-size:1.9rem;font-weight:700;margin-top:6px;letter-spacing:-.02em}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
.toolbar input{flex:1;min-width:220px}
.chip{font-size:.75rem;font-weight:700;padding:7px 13px;border-radius:99px;
  border:1px solid #334155;background:#1e293b;color:#94a3b8;cursor:pointer}
.chip.on{background:#89CFF020;border-color:#89CFF0;color:#89CFF0}
table{width:100%;border-collapse:collapse;background:#1e293b;border:1px solid #334155;
  border-radius:12px;overflow:hidden}
th{background:#0f172a;padding:11px 14px;text-align:left;font-size:.68rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.07em;color:#64748b;border-bottom:1px solid #334155}
td{padding:13px 14px;border-bottom:1px solid #1a2744;vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr{cursor:pointer}
tbody tr:hover td{background:#243050}
.nimi{font-weight:700}
.mail{font-size:.76rem;color:#64748b;font-family:ui-monospace,Menlo,monospace}
.badge{display:inline-block;font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:99px;
  border:1px solid #334155;color:#94a3b8}
.badge.g{background:#052e16;border-color:#22c55e;color:#4ade80}
.badge.y{background:#451a03;border-color:#f59e0b;color:#fbbf24}
.badge.r{background:#450a0a;border-color:#ef4444;color:#f87171}
.badge.b{background:#89CFF015;border-color:#89CFF0;color:#89CFF0}
.muted{color:#64748b}
.note{background:#451a03;border:1px solid #f59e0b;color:#fbbf24;border-radius:10px;
  padding:12px 16px;margin-bottom:18px;font-size:.82rem}
.err{background:#450a0a;border:1px solid #ef4444;color:#f87171;border-radius:10px;
  padding:12px 16px;margin-bottom:18px;font-size:.82rem}
.empty{padding:44px;text-align:center;color:#64748b}
#login{max-width:400px;margin:16vh auto;background:#1e293b;border:1px solid #334155;
  border-radius:16px;padding:30px}
#login h2{font-size:1.05rem;margin-bottom:8px}
#login p{color:#64748b;font-size:.82rem;margin-bottom:18px;line-height:1.5}
#login button{width:100%;margin-top:12px}
.overlay{position:fixed;inset:0;background:#020617cc;display:flex;justify-content:flex-end;z-index:9}
.panel{width:min(520px,100%);height:100%;overflow-y:auto;background:#0f172a;
  border-left:1px solid #334155;padding:26px}
.panel h2{font-size:1.1rem;margin-bottom:4px}
.panel .mail{margin-bottom:20px;display:block}
.row{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #1a2744;font-size:.85rem}
.row .k{width:120px;flex:none;color:#64748b;font-size:.75rem;text-transform:uppercase;
  letter-spacing:.05em;font-weight:700;padding-top:2px}
.row .v{flex:1;word-break:break-word}
.viesti{white-space:pre-wrap;line-height:1.6;background:#1e293b;border:1px solid #334155;
  border-radius:10px;padding:14px;margin-top:14px;font-size:.85rem}
.actions{display:flex;gap:10px;margin:22px 0 8px}
.result{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin-top:14px}
.result ul{margin:10px 0 0 18px;color:#cbd5e1;font-size:.82rem;line-height:1.6}
footer{margin-top:34px;color:#334155;font-size:.7rem;text-align:center}
</style>
</head>
<body>

<div id="login" hidden>
  <h2>Kehittäjäkonsoli</h2>
  <p>Anna konsolin tunnus (DEV_TOKEN). Tunnus tallentuu vain tähän selaimeen.</p>
  <input id="token" type="password" placeholder="DEV_TOKEN" autocomplete="off">
  <div id="loginerr" class="err" style="margin-top:12px" hidden></div>
  <button class="primary" id="loginbtn">Kirjaudu</button>
</div>

<div class="wrap" id="app" hidden>
  <header>
    <span class="dot"></span>
    <h1>Anglés · kehittäjäkonsoli</h1>
    <span class="spacer"></span>
    <span class="muted" id="updated"></span>
    <button id="refresh">Päivitä</button>
    <button id="logout">Kirjaudu ulos</button>
  </header>

  <div id="config" class="note" hidden></div>
  <div id="error" class="err" hidden></div>

  <div class="tiles">
    <div class="tile"><div class="k">Asiakkaita</div><div class="v" id="t-clients">–</div></div>
    <div class="tile"><div class="k">Yhteydenottoja</div><div class="v" id="t-contacts">–</div></div>
    <div class="tile"><div class="k">Uusia 7 pv</div><div class="v" id="t-new">–</div></div>
    <div class="tile"><div class="k">Keskipisteet</div><div class="v" id="t-score">–</div></div>
  </div>

  <div class="toolbar">
    <input id="search" placeholder="Hae nimellä, sähköpostilla tai sivustolla…">
    <span class="chip on" data-f="kaikki">Kaikki</span>
    <span class="chip" data-f="yhteydenotto">Yhteydenotot</span>
    <span class="chip" data-f="seo-testi">SEO-testi</span>
  </div>

  <table>
    <thead><tr>
      <th>Asiakas</th><th>Sivusto</th><th>Pisteet</th><th>Tyyppi</th><th>Viimeksi</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="empty" id="empty" hidden>Ei asiakkaita näillä ehdoilla.</div>

  <footer>Tiedot MailerLitesta · konsoli ei kirjoita mitään takaisin</footer>
</div>

<script>
const $ = (id) => document.getElementById(id);
let TOKEN = localStorage.getItem('devToken') || '';
let DATA = { clients: [], stats: {}, lahteet: {} };
let FILTER = 'kaikki';

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function pvm(iso) {
  if (!iso) return '–';
  const d = new Date(iso);
  if (isNaN(d)) return '–';
  return d.toLocaleDateString('fi-FI') + ' ' +
    d.toLocaleTimeString('fi-FI', {hour: '2-digit', minute: '2-digit'});
}

function scoreClass(n) {
  if (n == null) return '';
  return n >= 75 ? 'g' : (n >= 50 ? 'y' : 'r');
}

async function api(path, opts) {
  const o = Object.assign({headers: {}}, opts || {});
  o.headers['x-dev-token'] = TOKEN;
  if (o.body) o.headers['content-type'] = 'application/json';
  const r = await fetch(path, o);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.error || 'Virhe'), {code: r.status});
  return data;
}

function showLogin(msg) {
  $('app').hidden = true;
  $('login').hidden = false;
  if (msg) { $('loginerr').textContent = msg; $('loginerr').hidden = false; }
  $('token').focus();
}

async function load() {
  try {
    DATA = await api('/api/dev/clients');
  } catch (e) {
    if (e.code === 401) { localStorage.removeItem('devToken'); TOKEN = ''; showLogin(e.message); return; }
    $('login').hidden = true; $('app').hidden = false;
    $('error').textContent = e.message; $('error').hidden = false;
    return;
  }
  $('login').hidden = true;
  $('app').hidden = false;
  $('error').hidden = true;
  $('updated').textContent = 'päivitetty ' + new Date().toLocaleTimeString('fi-FI');

  const s = DATA.stats || {};
  $('t-clients').textContent = s.asiakkaita ?? '–';
  $('t-contacts').textContent = s.yhteydenottoja ?? '–';
  $('t-new').textContent = s.uusia_7pv ?? '–';
  $('t-score').textContent = s.keskipisteet == null ? '–' : s.keskipisteet;

  const l = DATA.lahteet || {};
  const puuttuu = [];
  if (!l.mailerlite_avain) puuttuu.push('MAILERLITE_API_KEY');
  if (!l.seo_testi_ryhma) puuttuu.push('MAILERLITE_GROUP_ID');
  if (!l.yhteydenotto_ryhma) puuttuu.push('MAILERLITE_CONTACT_GROUP_ID');
  $('config').hidden = puuttuu.length === 0;
  $('config').textContent = 'Puuttuva asetus: ' + puuttuu.join(', ') +
    ' — osa asiakkaista ei näy ennen kuin tämä on asetettu.';

  render();
}

function suodata() {
  const q = $('search').value.trim().toLowerCase();
  return (DATA.clients || []).filter(c => {
    if (FILTER !== 'kaikki' && !(c.tyypit || []).includes(FILTER)) return false;
    if (!q) return true;
    return [c.nimi, c.email, c.sivusto, c.ala, c.paketti]
      .some(v => String(v || '').toLowerCase().includes(q));
  });
}

function render() {
  const rivit = suodata();
  $('empty').hidden = rivit.length > 0;
  $('rows').innerHTML = rivit.map((c, i) => {
    const sc = c.score == null ? '<span class="muted">–</span>'
      : '<span class="badge ' + scoreClass(c.score) + '">' + c.score +
        (c.grade ? ' · ' + esc(c.grade) : '') + '</span>';
    const tyypit = (c.tyypit || []).map(t =>
      '<span class="badge' + (t === 'yhteydenotto' ? ' b' : '') + '">' + esc(t) + '</span>').join(' ');
    const peruttu = c.status && c.status !== 'active'
      ? ' <span class="badge r">' + esc(c.status) + '</span>' : '';
    return '<tr data-i="' + i + '">' +
      '<td><div class="nimi">' + esc(c.nimi || '(ei nimeä)') + peruttu +
        '</div><span class="mail">' + esc(c.email) + '</span></td>' +
      '<td>' + (c.sivusto ? '<span class="mail">' + esc(c.sivusto) + '</span>'
                          : '<span class="muted">–</span>') + '</td>' +
      '<td>' + sc + '</td><td>' + tyypit + '</td>' +
      '<td class="muted">' + pvm(c.viim || c.eka) + '</td></tr>';
  }).join('');
  $('rows').querySelectorAll('tr').forEach(tr =>
    tr.onclick = () => avaa(rivit[+tr.dataset.i]));
}

function rivi(k, v) {
  if (!v) return '';
  return '<div class="row"><div class="k">' + k + '</div><div class="v">' + esc(v) + '</div></div>';
}

function avaa(c) {
  const wrap = document.createElement('div');
  wrap.className = 'overlay';
  const url = /^https?:\/\//i.test(c.sivusto || '') ? c.sivusto : '';
  const site = url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(url) + '</a>'
    : esc(c.sivusto || '');
  wrap.innerHTML = '<div class="panel">' +
    '<button id="close" style="float:right">Sulje</button>' +
    '<h2>' + esc(c.nimi || c.email) + '</h2>' +
    '<span class="mail"><a href="mailto:' + esc(c.email) + '">' + esc(c.email) + '</a></span>' +
    (site ? '<div class="row"><div class="k">Sivusto</div><div class="v">' + site + '</div></div>' : '') +
    rivi('Pisteet', c.score == null ? '' : c.score + (c.grade ? ' · ' + c.grade : '')) +
    rivi('Ala', c.ala) + rivi('Paketti', c.paketti) +
    rivi('Tyyppi', (c.tyypit || []).join(', ')) +
    rivi('Lähde', (c.lahteet || []).join(', ')) +
    rivi('Tila', c.status) +
    rivi('Ensimmäinen', pvm(c.eka)) + rivi('Viimeksi', pvm(c.viim)) +
    (c.viesti ? '<div class="viesti">' + esc(c.viesti) + '</div>' : '') +
    '<div class="actions">' +
      (url ? '<button class="primary" id="run">Aja audit</button>' : '') +
      '<button id="mail">Vastaa sähköpostilla</button>' +
    '</div><div id="out"></div></div>';
  document.body.appendChild(wrap);

  const sulje = () => wrap.remove();
  wrap.onclick = (e) => { if (e.target === wrap) sulje(); };
  wrap.querySelector('#close').onclick = sulje;
  wrap.querySelector('#mail').onclick = () => {
    location.href = 'mailto:' + encodeURIComponent(c.email) + '?subject=' +
      encodeURIComponent('Anglés Marketing — ' + (c.sivusto || 'SEO-testisi'));
  };
  const run = wrap.querySelector('#run');
  if (run) run.onclick = async () => {
    run.disabled = true;
    run.textContent = 'Auditoidaan…';
    const out = wrap.querySelector('#out');
    try {
      const r = await api('/api/dev/audit', {method: 'POST', body: JSON.stringify({url: url})});
      // top_findings on lista {name, message, status} — sama rakenne kuin
      // julkisessa SEO-testissä; critical_alerts on pelkkiä tekstejä
      const loydokset = (r.top_findings || []).map(f => typeof f === 'string' ? '<li>' + esc(f) + '</li>'
        : '<li><b>' + esc(f.name || '') + '</b>' + (f.message ? ' — ' + esc(f.message) : '') + '</li>').join('');
      const halytykset = (r.critical_alerts || []).map(a =>
        '<div class="err" style="margin:10px 0 0">' + esc(a) + '</div>').join('');
      const pisteet = Math.round(r.overall_score);
      out.innerHTML = '<div class="result"><span class="badge ' + scoreClass(pisteet) + '">' +
        pisteet + ' / 100 · ' + esc(r.grade) + '</span> <span class="muted">' + r.pages +
        ' sivua auditoitu</span>' + halytykset +
        (loydokset ? '<ul>' + loydokset + '</ul>' : '') + '</div>';
    } catch (e) {
      out.innerHTML = '<div class="err">' + esc(e.message) + '</div>';
    }
    run.disabled = false;
    run.textContent = 'Aja audit uudelleen';
  };
}

$('loginbtn').onclick = () => {
  TOKEN = $('token').value.trim();
  if (!TOKEN) return;
  localStorage.setItem('devToken', TOKEN);
  $('loginerr').hidden = true;
  load();
};
$('token').onkeydown = (e) => { if (e.key === 'Enter') $('loginbtn').click(); };
$('logout').onclick = () => { localStorage.removeItem('devToken'); TOKEN = ''; showLogin(''); };
$('refresh').onclick = load;
$('search').oninput = render;
document.querySelectorAll('.chip').forEach(ch => ch.onclick = () => {
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
  ch.classList.add('on');
  FILTER = ch.dataset.f;
  render();
});

if (TOKEN) load(); else showLogin('');
</script>
</body>
</html>
'''
