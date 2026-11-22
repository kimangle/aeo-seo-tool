#!/usr/bin/env bash
# indexnow.sh - tell IndexNow (Bing, Yandex, Seznam, Naver and others; not Google) which URLs changed.
#
# Usage:
#   scripts/indexnow.sh [--dry-run] --site DOMAIN [URL ...] [-f urls.txt]
#   scripts/indexnow.sh [--dry-run] --host HOST --key KEY [--key-location URL] URL ...
#
#   --site DOMAIN   read host and indexnow_key from config.local.json (sites[].domain)
#   --config FILE   another config file (default: ../config.local.json, or $SEO_NAKYVYYS_CONFIG)
#   --dry-run       do every read-only check, print the JSON body, send nothing
#   -f FILE         URLs one per line (# comments and blank lines skipped)
#
# Before any POST it checks, and stops on failure:
#   1. every URL is on HOST (IndexNow answers 422 otherwise)                       exit 2
#   2. https://HOST/KEY.txt answers 200 and its body is exactly the key          exit 3
#   3. each URL answers 200, has no noindex (robots "none" counts as noindex) and no
#      canonical pointing to another URL; others are skipped with a note      exit 4 if none left
# Then it POSTs to https://api.indexnow.org/indexnow and prints the HTTP code.
# The "kept" list it prints is also the list for Google indexing requests (SKILL.md 6.2).
# 200 = OK, 202 = accepted (key check pending). Anything else exits 5.
# With --site and no URLs it exits 64: a ping needs an explicit list of changed URLs.

set -euo pipefail

if [ "$#" -eq 0 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
  exit 64
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SEO_NAKYVYYS_DEFAULT_CONFIG="${SEO_NAKYVYYS_CONFIG:-$SCRIPT_DIR/../config.local.json}"

exec python3 -I - "$@" <<'PY'
import json, os, re, subprocess, sys, tempfile
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, quote, urljoin

ENDPOINT = "https://api.indexnow.org/indexnow"
UA = "seo-nakyvyys-indexnow/0.1 (+curl)"
MEANING = {200: "OK, URLs submitted", 202: "accepted, key validation pending",
           400: "bad request (invalid format)", 403: "forbidden (key not valid or key file not found)",
           422: "unprocessable (URLs not on this host, or key does not match the schema)",
           429: "too many requests (possible spam)"}

args = sys.argv[1:]
dry = False
site = host = key = key_loc = None
config = os.environ.get("SEO_NAKYVYYS_DEFAULT_CONFIG")
urls = []
i = 0
try:
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry = True; i += 1
        elif a == "--site":
            site = args[i + 1]; i += 2
        elif a == "--host":
            host = args[i + 1]; i += 2
        elif a == "--key":
            key = args[i + 1]; i += 2
        elif a == "--key-location":
            key_loc = args[i + 1]; i += 2
        elif a == "--config":
            config = args[i + 1]; i += 2
        elif a == "-f":
            with open(args[i + 1], encoding="utf-8") as fh:
                urls += [l.strip() for l in fh if l.strip() and not l.strip().startswith("#")]
            i += 2
        elif a.startswith("-"):
            print(f"unknown option {a}", file=sys.stderr); sys.exit(64)
        else:
            urls.append(a); i += 1
except IndexError:
    print("an option is missing its value", file=sys.stderr); sys.exit(64)

if site:
    try:
        cfg = json.load(open(config, encoding="utf-8"))
    except Exception as e:
        print(f"cannot read config {config}: {e}", file=sys.stderr); sys.exit(64)
    match = [s for s in cfg.get("sites", []) if isinstance(s, dict) and site in (s.get("domain"), s.get("host"))]
    if not match:
        print(f"site {site} is not in {config}", file=sys.stderr); sys.exit(64)
    s = match[0]
    host = host or s.get("host") or s.get("domain")
    key = key or s.get("indexnow_key")
    if not key:
        print(f"{site} has no indexnow_key in the config: create the key file first (SKILL.md step 6)", file=sys.stderr)
        sys.exit(64)

if not host or not key:
    print("need --site, or --host and --key", file=sys.stderr); sys.exit(64)
if not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
    print("key must be 8-128 characters of a-z, A-Z, 0-9 and -", file=sys.stderr); sys.exit(64)
if not urls:
    print("no URLs given: list the changed URLs explicitly", file=sys.stderr); sys.exit(64)
key_loc = key_loc or f"https://{host}/{key}.txt"


def enc(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path, safe="/%:@!$&'()*+,;=-._~"),
                       quote(p.query, safe="=&%:@!$'()*+,;/?-._~"), ""))


def get(url):
    with tempfile.TemporaryDirectory(prefix="indexnow_") as td:
        h, b = os.path.join(td, "h"), os.path.join(td, "b")
        r = subprocess.run(["curl", "-sS", "--max-time", "20", "-A", UA, "-D", h, "-o", b,
                            "-w", "%{http_code}\n%{content_type}", enc(url)], capture_output=True, text=True)
        if r.returncode != 0:
            return 0, "", {}, r.stderr.strip()
        code, ctype = (r.stdout.split("\n") + [""])[:2]
        headers = {}
        for line in open(h, encoding="latin-1"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        return int(code or 0), ctype, headers, open(b, "rb").read().decode("utf-8", "replace")


def norm(url):
    p = urlsplit(enc(url))
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((p.scheme.lower(), (p.netloc or "").lower(), path, p.query, ""))


class Robots(HTMLParser):
    def __init__(self):
        super().__init__(); self.values = []; self.canonical = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("name", "").lower() in ("robots", "googlebot", "bingbot"):
            self.values.append(a.get("content", "").lower())
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split() and self.canonical is None:
            self.canonical = a.get("href", "")


# 1. every URL on the host
off = [u for u in urls if urlsplit(u).hostname != host]
if off:
    print(f"FAIL: these URLs are not on {host}: {off}", file=sys.stderr); sys.exit(2)

# 2. key file live
code, ctype, _, body = get(key_loc)
if code != 200 or body.strip() != key:
    print(f"FAIL: key file {key_loc} answered {code}" + ("" if code != 200 else " with other content")
          + ". Release the key file first; do not ping before it answers 200.", file=sys.stderr)
    sys.exit(3)
print(f"key file OK: {key_loc} (200, {ctype or 'no content-type'})")

# 3. only indexable 200 pages
keep = []
for u in dict.fromkeys(urls):
    c, ct, hd, bd = get(u)
    values = [hd.get("x-robots-tag", "").lower()]
    canonical = None
    if "html" in (ct or "").lower():
        p = Robots(); p.feed(bd); values += p.values; canonical = p.canonical
    toks = {t.strip() for v in values for t in v.split(",") if t.strip()}
    if c != 200:
        print(f"skip {u}: status {c}")
    elif "noindex" in toks or "none" in toks:
        print(f"skip {u}: noindex")
    elif canonical and norm(urljoin(enc(u), canonical)) != norm(u):
        print(f"skip {u}: canonical points to {canonical}")
    else:
        keep.append(u)
if not keep:
    print("FAIL: no indexable URL left to submit", file=sys.stderr); sys.exit(4)
print(f"kept {len(keep)} indexable, self-canonical URL(s); use the same list for Google indexing requests")

payload = {"host": host, "key": key, "keyLocation": key_loc, "urlList": keep}
print(json.dumps(payload, ensure_ascii=False, indent=1))
if dry:
    print(f"DRY RUN: would POST {len(keep)} URL(s) to {ENDPOINT}. Nothing was sent.")
    sys.exit(0)

r = subprocess.run(["curl", "-sS", "--max-time", "30", "-o", "/dev/null", "-w", "%{http_code}", "-X", "POST", ENDPOINT,
                    "-H", "Content-Type: application/json; charset=utf-8", "--data-binary", json.dumps(payload)],
                   capture_output=True, text=True)
code = int(r.stdout or 0)
print(f"{host}: HTTP {code} {MEANING.get(code, '')}".rstrip())
sys.exit(0 if code in (200, 202) else 5)
PY
