#!/usr/bin/env bash
# run_tests.sh - tests for the seo-nakyvyys skill.
#
#   scripts/tests/run_tests.sh            offline: syntax, JSON, the workflow mock run and its
#                                         negative cases, gsc_table.js, verify_prod.sh and
#                                         indexnow.sh --dry-run against a local server on 127.0.0.1,
#                                         and the leak check when references/local/private-terms.txt
#                                         exists (in a git checkout with origin/main it also checks
#                                         the commit messages and added lines of origin/main..HEAD;
#                                         set SEO_NAKYVYYS_LEAK_RANGE to another range, or to "none")
#   scripts/tests/run_tests.sh --online   also read-only checks against your live sites:
#                                         verify_prod.sh and indexnow.sh --dry-run on the URLs in
#                                         the "tests" block of config.local.json, or on the specs
#                                         file named by SEO_NAKYVYYS_ONLINE_SPECS. Without either,
#                                         the online checks are skipped.
#
# Nothing is posted anywhere: indexnow.sh always runs with --dry-run. The local server is
# python3 -m http.server on a free port; the script stops only that PID. The fixtures are
# invented pages. Exit 0 when every check passed.

set -uo pipefail
cd "$(dirname "$0")/../.."
pass=0; fail=0
tmpd="$(mktemp -d "${TMPDIR:-/tmp}/seo-nakyvyys-test.XXXXXX")"
logf="$tmpd/log"
ok()  { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; }
run() { local name="$1"; shift; if "$@" >"$logf" 2>&1; then ok "$name"; else bad "$name"; sed 's/^/     /' "$logf" | tail -20; fi; }

for s in scripts/*.sh scripts/tests/*.sh; do run "bash -n $s" bash -n "$s"; done
run "node --check scripts/gsc_table.js" node --check scripts/gsc_table.js
run "python3 compiles scripts/tests/leak_check.py" python3 -I -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' scripts/tests/leak_check.py
for j in config.example.json evals/evals.json evals/trigger-queries.json scripts/tests/mock-args.json; do
  run "valid JSON $j" python3 -m json.tool "$j"
done
[ -f config.local.json ] && run "valid JSON config.local.json" python3 -m json.tool config.local.json
run "workflow template parses and mock-runs" scripts/check_workflow.sh references/workflow-template.js --mock scripts/tests/mock-args.json
grep -v 'Do not call the Skill tool' references/workflow-template.js > "$tmpd/no-skill-rule.js"
run "check_workflow.sh fails when the Skill rule is missing" bash -c '! scripts/check_workflow.sh "$1" --mock scripts/tests/mock-args.json >/dev/null 2>&1' _ "$tmpd/no-skill-rule.js"
echo '{"date":"2026-11-22","wt_root":"/tmp/wt-seo-test/k1","sites":[]}' > "$tmpd/empty-args.json"
run "check_workflow.sh fails on empty sites" bash -c '! scripts/check_workflow.sh references/workflow-template.js --mock "$1" >/dev/null 2>&1' _ "$tmpd/empty-args.json"
python3 -I -c '
import json,sys
a=json.load(open(sys.argv[1])); del a["sites"][0]["github_repo"]; a["sites"][1]["port"]=a["sites"][0]["port"]+5
json.dump(a,open(sys.argv[2],"w"))' scripts/tests/mock-args.json "$tmpd/bad-args.json"
run "check_workflow.sh fails on a missing field and overlapping ports" bash -c '! scripts/check_workflow.sh references/workflow-template.js --mock "$1" >/dev/null 2>&1' _ "$tmpd/bad-args.json"
run "gsc_table.js on a fake Search Console DOM" node scripts/tests/test_gsc_table.mjs
run "SKILL.md under 250 lines" test "$(wc -l < SKILL.md)" -lt 250
run "SKILL.md description at most 1024 characters" python3 -I -c '
import re,sys
s=open("SKILL.md").read()
d=" ".join(re.search(r"description: >-\n((?:  .*\n)+)", s).group(1).split())
sys.exit(0 if len(d) <= 1024 else 1)'
run "every reference named in SKILL.md exists (the optional references/local/ aside)" python3 -I -c '
import re,os,sys
s=open("SKILL.md").read()
paths=set(re.findall(r"`((?:references|scripts|templates|evals)/[A-Za-z0-9_./-]+)`", s))
missing=[p for p in paths if not os.path.exists(p) and not p.startswith("references/local/")]
print("missing:", missing) if missing else None
sys.exit(1 if missing else 0)'
run "indexnow.sh refuses to run without URLs" bash -c '! scripts/indexnow.sh --dry-run --host example.com --key 0123456789abcdef >/dev/null 2>&1'
run "verify_prod.sh usage exit 64" bash -c 'scripts/verify_prod.sh >/dev/null 2>&1; [ $? -eq 64 ]'

# Local server for parser tests (own PID only).
port="$(python3 -I -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
python3 -m http.server "$port" --bind 127.0.0.1 --directory scripts/tests/fixtures >/dev/null 2>&1 &
srv=$!
if python3 -I -c '
import socket,sys,time
for _ in range(50):
    try:
        socket.create_connection(("127.0.0.1",int(sys.argv[1])),0.2).close(); sys.exit(0)
    except OSError: time.sleep(0.1)
sys.exit(1)' "$port"; then
  L="http://127.0.0.1:$port"
  run "verify_prod.sh reads the head title, not an inline SVG title" bash -c 'scripts/verify_prod.sh "$1/svg-title.html" | grep -q "title(13) \"Oikea otsikko\""' _ "$L"
  run "verify_prod.sh treats robots none as noindex" scripts/verify_prod.sh "$L/robots-none.html noindex"
  run "verify_prod.sh contains= with quoted spaces matches a no-break space" scripts/verify_prod.sh "$L/price.txt contains='1 000 €'"
  run "verify_prod.sh rejects an unquoted contains= with spaces" bash -c 'out=$(scripts/verify_prod.sh "$1/price.txt contains=1 000 €" 2>&1); [ $? -eq 1 ] && grep -q "unknown expectation .000." <<<"$out"' _ "$L"
  run "verify_prod.sh 404 expectation" scripts/verify_prod.sh "$L/olematon.html 404"
  run "indexnow.sh --dry-run skips robots none and a foreign canonical" bash -c '
    out=$(scripts/indexnow.sh --dry-run --host 127.0.0.1 --key 0123456789abcdef --key-location "$1/0123456789abcdef.txt" \
      "$1/svg-title.html" "$1/robots-none.html" "$1/canon-elsewhere.html" 2>&1) || exit 1
    grep -q "skip $1/robots-none.html: noindex" <<<"$out" && grep -q "skip $1/canon-elsewhere.html: canonical points to" <<<"$out" \
      && grep -q "kept 1 indexable" <<<"$out" && grep -q "DRY RUN" <<<"$out"' _ "$L"
else
  bad "local test server did not start on port $port"
fi
if ps -o command= -p "$srv" 2>/dev/null | grep -q "http.server $port"; then kill "$srv"; wait "$srv" 2>/dev/null; fi

# Public layer: no private term in the files git would publish (skip without a terms file).
if [ -f references/local/private-terms.txt ]; then
  range="${SEO_NAKYVYYS_LEAK_RANGE:-origin/main..HEAD}"
  if [ "$range" != "none" ] && git rev-parse --verify -q "${range%%..*}" >/dev/null 2>&1; then
    run "no private term in the public files, nor in the commits and added lines of $range" python3 -I scripts/tests/leak_check.py --commits "$range"
  else
    run "no private term in the public files (references/local/private-terms.txt)" python3 -I scripts/tests/leak_check.py
  fi
else
  echo "skip leak check: no references/local/private-terms.txt"
fi

if [ "${1:-}" = "--online" ]; then
  specs="$tmpd/online-specs.txt"
  : > "$specs"
  if [ -n "${SEO_NAKYVYYS_ONLINE_SPECS:-}" ]; then
    if [ -f "$SEO_NAKYVYYS_ONLINE_SPECS" ]; then cp "$SEO_NAKYVYYS_ONLINE_SPECS" "$specs"; else bad "SEO_NAKYVYYS_ONLINE_SPECS is not a file: $SEO_NAKYVYYS_ONLINE_SPECS"; fi
  elif [ -f config.local.json ]; then
    python3 -I -c '
import json,sys
t=json.load(open(sys.argv[1],encoding="utf-8")).get("tests") or {}
open(sys.argv[2],"w",encoding="utf-8").write("".join(s+"\n" for s in t.get("online_specs") or []))' config.local.json "$specs"
  fi
  if grep -qvE '^[[:space:]]*(#|$)' "$specs" 2>/dev/null; then
    run "verify_prod.sh on live pages" scripts/verify_prod.sh -f "$specs"
    first="$(grep -vE '^[[:space:]]*(#|$)' "$specs" | awk 'NF==1 {print $1; exit}')"
    if [ -n "$first" ]; then
      run "verify_prod.sh catches a wrong expectation" bash -c '! scripts/verify_prod.sh "$1 noindex" >/dev/null 2>&1' _ "$first"
      host="$(python3 -I -c 'import sys,urllib.parse as u; print(u.urlsplit(sys.argv[1]).hostname or "")' "$first")"
      run "indexnow.sh stops on a key file that is not live" bash -c 'scripts/indexnow.sh --dry-run --host "$1" --key 0123456789abcdef0123456789abcdef "https://$1/" >/dev/null 2>&1; [ $? -eq 3 ]' _ "$host"
    else
      echo "skip negative online checks: no spec is a bare URL"
    fi
  else
    echo "skip online page checks: no tests.online_specs in config.local.json and no SEO_NAKYVYYS_ONLINE_SPECS file"
  fi
  inxf="$tmpd/indexnow.txt"
  : > "$inxf"
  if [ -f config.local.json ]; then
    python3 -I -c '
import json,sys
i=(json.load(open(sys.argv[1],encoding="utf-8")).get("tests") or {}).get("indexnow") or {}
if i.get("site") and i.get("urls"):
    open(sys.argv[2],"w",encoding="utf-8").write("\n".join([i["site"], i.get("noindex_url") or "-"] + list(i["urls"])) + "\n")' config.local.json "$inxf"
  fi
  if [ -s "$inxf" ]; then
    isite="$(sed -n 1p "$inxf")"
    inoindex="$(sed -n 2p "$inxf")"
    iurls=()
    while IFS= read -r u; do [ -n "$u" ] && iurls+=("$u"); done < <(sed -n '3,$p' "$inxf")
    run "indexnow.sh --dry-run (no POST)" scripts/indexnow.sh --dry-run --site "$isite" "${iurls[@]}"
    if [ "$inoindex" != "-" ]; then
      run "indexnow.sh skips a noindex page" bash -c 'site="$1"; nx="$2"; shift 2; scripts/indexnow.sh --dry-run --site "$site" "$nx" "$@" | grep -qF "skip $nx: noindex"' _ "$isite" "$inoindex" "${iurls[@]}"
    fi
  else
    echo "skip online IndexNow checks: no tests.indexnow in config.local.json"
  fi
fi

rm -f "${tmpd:?}/log" "${tmpd:?}/no-skill-rule.js" "${tmpd:?}/empty-args.json" "${tmpd:?}/bad-args.json" "${tmpd:?}/online-specs.txt" "${tmpd:?}/indexnow.txt"
rmdir "${tmpd:?}" 2>/dev/null || true
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
