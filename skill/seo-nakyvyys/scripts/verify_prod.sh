#!/usr/bin/env bash
# verify_prod.sh - check live URLs with curl after a release (or before one, for a baseline).
#
# Usage:
#   scripts/verify_prod.sh [--timeout S] URL_SPEC ...
#   scripts/verify_prod.sh [--timeout S] -f specs.txt
#
# One URL_SPEC is a URL followed by optional expectations. In a file, one spec per
# line; blank lines and lines starting with # are skipped. On the command line, quote
# each spec that has more than one word. A contains= text with spaces needs its own
# quotes inside the spec, shell-style:
#   scripts/verify_prod.sh "https://site.fi/llms.txt contains='1 000 €'"
#   (in a -f file: https://site.fi/llms.txt contains='1 000 €')
# contains= treats a no-break space (U+00A0, U+202F) on the page as a normal space.
#
#   https://site.fi/page                      200, indexable (default)
#   https://site.fi/landing noindex           200 with robots noindex (meta or X-Robots-Tag)
#   https://site.fi/missing 404               status 404 (any code 100-599)
#   https://site.fi/old -> https://site.fi/new   301 or 308 to the target, final hop count shown
#   https://site.fi/video.mp4 range           a Range request answers 206
#   https://site.fi/<key>.txt contains=<key>  body contains the text (file check: no page checks)
#
# For every HTML page with status 200 it prints title (length; the first <title> outside
# an inline <svg>), meta description length (warns above 155), robots ("none" counts as
# noindex), canonical (self or not), hreflang codes, H1 count and JSON-LD parse result, and
# checks hreflang return links between the pages in the same run. A 404 page that carries
# "index" in any robots value gets a warning.
#
# Exit 0 when nothing failed (warnings allowed), 1 when any check failed, 64 on usage error.
# Read-only: only GET requests (HEAD-free, so servers that treat HEAD differently do not fool it).

set -euo pipefail

if [ "$#" -eq 0 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
  exit 64
fi

exec python3 -I - "$@" <<'PY'
import json, shlex, subprocess, sys, tempfile, os
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, quote, urljoin

UA = "seo-nakyvyys-verify/0.1 (+curl)"
args = sys.argv[1:]
timeout = "20"
specs = []
i = 0
while i < len(args):
    a = args[i]
    if a == "--timeout":
        timeout = args[i + 1]; i += 2; continue
    if a == "-f":
        path = args[i + 1]; i += 2
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    specs.append(line)
        continue
    specs.append(a); i += 1

if not specs:
    print("usage: verify_prod.sh [--timeout S] URL_SPEC ... | -f specs.txt", file=sys.stderr)
    sys.exit(64)


def enc(url):
    """Percent-encode non-ASCII characters (for example a path with ä) the way browsers send them."""
    p = urlsplit(url)
    path = quote(p.path, safe="/%:@!$&'()*+,;=-._~")
    query = quote(p.query, safe="=&%:@!$'()*+,;/?-._~")
    return urlunsplit((p.scheme, p.netloc.encode("idna").decode("ascii") if p.netloc else p.netloc, path, query, ""))


def norm(url):
    p = urlsplit(enc(url))
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))


def curl(url, extra=None, follow=False):
    with tempfile.TemporaryDirectory(prefix="verify_prod_") as td:
        hdr, body = os.path.join(td, "h"), os.path.join(td, "b")
        cmd = ["curl", "-sS", "--max-time", timeout, "-A", UA, "-D", hdr, "-o", body,
               "-w", "%{http_code}\n%{redirect_url}\n%{content_type}\n%{num_redirects}\n%{url_effective}"]
        if follow:
            cmd.append("-L")
        for h in extra or []:
            cmd += ["-H", h]
        cmd.append(enc(url))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return {"error": r.stderr.strip() or f"curl exit {r.returncode}"}
        code, redirect, ctype, nred, eff = (r.stdout.split("\n") + [""] * 5)[:5]
        headers = {}
        if os.path.exists(hdr):
            for line in open(hdr, encoding="latin-1"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
        data = open(body, "rb").read() if os.path.exists(body) else b""
        return {"code": int(code or 0), "redirect": redirect, "ctype": ctype, "headers": headers,
                "body": data, "num_redirects": int(nred or 0), "effective": eff}


NBSP = {"\u00a0": " ", "\u202f": " "}


def spaces(text):
    return text.translate(str.maketrans(NBSP))


def robots_tokens(values):
    return {t.strip() for v in values for t in v.lower().split(",") if t.strip()}


def is_noindex(values):
    toks = robots_tokens(values)
    return "noindex" in toks or "none" in toks


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.in_title, self.title_done, self.svg = "", False, False, 0
        self.robots, self.canonical = [], None
        self.description, self.hreflang, self.h1, self.ld, self.in_ld, self.buf = None, {}, 0, [], False, ""

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "svg":
            self.svg += 1
        elif tag == "title" and not self.svg and not self.title_done:
            self.in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            if name in ("robots", "googlebot"):
                self.robots.append(a.get("content", "").lower())
            elif name == "description":
                self.description = a.get("content", "")
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel:
                self.canonical = a.get("href")
            if "alternate" in rel and a.get("hreflang"):
                self.hreflang[a["hreflang"].lower()] = a.get("href", "")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.in_ld, self.buf = True, ""

    def handle_endtag(self, tag):
        if tag == "svg" and self.svg:
            self.svg -= 1
        elif tag == "title" and self.in_title:
            self.in_title, self.title_done = False, True
        elif tag == "script" and self.in_ld:
            self.ld.append(self.buf)
            self.in_ld = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_ld:
            self.buf += data


fails = warns = 0
pages = {}


def out(level, url, msg):
    global fails, warns
    if level == "FAIL":
        fails += 1
    elif level == "WARN":
        warns += 1
    print(f"{level:4} {url} | {msg}")


for spec in specs:
    try:
        toks = shlex.split(spec)
    except ValueError:
        toks = spec.split()
    url, rest = toks[0], toks[1:]
    expect_code, noindex_expected, target, want_range, contains = 200, False, None, False, []
    j = 0
    while j < len(rest):
        t = rest[j]
        if t == "->":
            target = rest[j + 1]; j += 2; continue
        if t == "noindex":
            noindex_expected = True
        elif t == "range":
            want_range = True
        elif t.startswith("contains="):
            contains.append(t[len("contains="):])
        elif t.isdigit() and len(t) == 3 and 100 <= int(t) <= 599:
            expect_code = int(t)
        else:
            out("FAIL", url, f"unknown expectation '{t}'")
        j += 1

    if target:
        r = curl(url)
        if "error" in r:
            out("FAIL", url, r["error"]); continue
        loc = r["headers"].get("location", "")
        got = urljoin(enc(url), loc) if loc else ""
        f = curl(url, follow=True)
        hops = f.get("num_redirects", 0)
        final = f.get("effective", "")
        msg = f"{r['code']} -> {got or '(no Location)'} | final {f.get('code')} {final} ({hops} hop{'s' if hops != 1 else ''})"
        if r["code"] not in (301, 302, 307, 308):
            out("FAIL", url, f"expected a redirect, got {r['code']}")
        elif norm(got) != norm(target) and norm(final) != norm(target):
            out("FAIL", url, f"redirects elsewhere: {msg}")
        elif r["code"] in (302, 307):
            out("WARN", url, f"temporary redirect, use 301/308: {msg}")
        elif hops > 1:
            out("WARN", url, f"more than one hop: {msg}")
        elif f.get("code") != 200:
            out("FAIL", url, f"target does not answer 200: {msg}")
        else:
            out("PASS", url, msg)
        continue

    if want_range:
        r = curl(url, extra=["Range: bytes=0-1023"])
        if "error" in r:
            out("FAIL", url, r["error"]); continue
        lvl = "PASS" if r["code"] == 206 else "FAIL"
        out(lvl, url, f"Range request -> {r['code']} ({r['ctype'] or 'no content-type'}, {r['headers'].get('content-range', 'no content-range')})")
        continue

    r = curl(url)
    if "error" in r:
        out("FAIL", url, r["error"]); continue
    code = r["code"]
    if code != expect_code:
        extra = f" -> {r['headers'].get('location')}" if r["headers"].get("location") else ""
        out("FAIL", url, f"status {code}{extra}, expected {expect_code}")
        continue
    body_text = r["body"].decode("utf-8", errors="replace")
    missing = [c for c in contains if spaces(c) not in spaces(body_text)]
    xrobots = r["headers"].get("x-robots-tag", "").lower()
    # A page gets the SEO checks; a file (key, verification file, feed) only status and contains=.
    is_html = "html" in (r["ctype"] or "").lower() and "<html" in body_text[:5000].lower() and not contains

    if code != 200 or not is_html:
        parts = [f"{code}", r["ctype"] or "no content-type", f"{len(r['body'])} bytes"]
        if xrobots:
            parts.append(f"x-robots-tag: {xrobots}")
        if code == 404 and is_html:
            p = Page(); p.feed(body_text)
            toks = robots_tokens(p.robots)
            if "index" in toks or (p.robots and not is_noindex(p.robots)):
                out("WARN", url, "404 page robots should be only noindex: " + "; ".join(p.robots)); continue
        if missing:
            out("FAIL", url, " | ".join(parts) + f" | missing text: {missing}")
        else:
            out("PASS", url, " | ".join(parts) + (" | contains OK" if contains else ""))
        continue

    p = Page()
    p.feed(body_text)
    robots = "; ".join(p.robots + ([f"x-robots-tag {xrobots}"] if xrobots else [])) or "(none)"
    noindex = is_noindex(p.robots + ([xrobots] if xrobots else []))
    problems = []
    level = "PASS"
    title = " ".join(p.title.split())
    if not title:
        problems.append("no <title>"); level = "FAIL"
    elif len(title) > 60:
        problems.append(f"title {len(title)} chars (>60)"); level = "WARN"
    if p.description is None:
        problems.append("no meta description")
        level = "WARN" if level == "PASS" else level
    elif len(p.description) > 155:
        problems.append(f"description {len(p.description)} chars (>155)")
        level = "WARN" if level == "PASS" else level
    if noindex and not noindex_expected:
        problems.append("noindex on a page that should be indexable"); level = "FAIL"
    if noindex_expected and not noindex:
        problems.append("expected noindex, page is indexable"); level = "FAIL"
    canon = "(none)"
    if p.canonical:
        canon = "self" if norm(urljoin(enc(url), p.canonical)) == norm(url) else p.canonical
        if canon != "self" and not noindex:
            problems.append(f"canonical points elsewhere: {p.canonical}")
            level = "WARN" if level == "PASS" else level
    elif not noindex:
        problems.append("no canonical")
        level = "WARN" if level == "PASS" else level
    ld_ok, ld_bad = 0, 0
    for block in p.ld:
        try:
            json.loads(block); ld_ok += 1
        except Exception:
            ld_bad += 1
    if ld_bad:
        problems.append(f"{ld_bad} JSON-LD block(s) do not parse"); level = "FAIL"
    if p.h1 != 1:
        problems.append(f"{p.h1} H1 elements")
        level = "WARN" if level == "PASS" else level
    if missing:
        problems.append(f"missing text: {missing}"); level = "FAIL"
    pages[norm(url)] = p.hreflang
    hl = ",".join(sorted(p.hreflang)) or "-"
    msg = (f"200 | title({len(title)}) \"{title[:70]}\" | desc {len(p.description or '')} | robots: {robots} | "
           f"canonical: {canon} | hreflang: {hl} | JSON-LD: {ld_ok} ok | H1: {p.h1}")
    if problems:
        msg += " | " + "; ".join(problems)
    out(level, url, msg)

# hreflang return links between pages checked in this run
for src, alts in pages.items():
    for code, href in alts.items():
        dst = norm(href)
        if dst in pages and dst != src:
            back = [norm(h) for h in pages[dst].values()]
            if src not in back:
                out("WARN", src, f"hreflang {code} -> {href} has no return link to this page")

print(f"\n{len(specs)} checked, {fails} failed, {warns} warnings")
sys.exit(1 if fails else 0)
PY
