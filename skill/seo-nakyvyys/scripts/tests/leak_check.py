"""leak_check.py - fail when a private term appears in the public files of this skill.

Usage (from the skill folder):
  python3 -I scripts/tests/leak_check.py [TERMS_FILE] [--commits RANGE] [-- PATH ...]

TERMS_FILE defaults to references/local/private-terms.txt next to this script's skill folder
(gitignored): one term per line, matched case-insensitively as a substring; a line starting
with "re:" is a Python regular expression; blank lines and lines starting with # are skipped.
Every line is also checked after URL decoding (%C3%A4 = ä).

Public files are the ones git would publish: tracked plus untracked-but-not-ignored files
under PATH (default: the current folder). Outside a git checkout it walks PATH and leaves out
config.local.json, *.local.json, .env files and references/local/. File names are checked too.

--commits RANGE (for example origin/main..HEAD) also checks, anywhere in the repository, the
commit messages in RANGE, the names of files the range adds and the lines it adds outside the
files already checked above (the repository root README, .gitignore and so on).

From the repository root the root files can be checked as well:
  python3 -I skill/seo-nakyvyys/scripts/tests/leak_check.py -- skill README.md

Exit 0 = clean, 1 = a term was found, 2 = no terms file (nothing to check), 3 = git could
not read RANGE.
"""
import os
import re
import subprocess
import sys
from urllib.parse import unquote

here = os.path.dirname(os.path.abspath(__file__))
default_terms = os.path.normpath(os.path.join(here, "..", "..", "references", "local", "private-terms.txt"))

args = sys.argv[1:]
paths = []
if "--" in args:
    i = args.index("--")
    paths = args[i + 1:]
    args = args[:i]
commit_range = None
if "--commits" in args:
    j = args.index("--commits")
    if j + 1 >= len(args):
        print("--commits needs a range, for example origin/main..HEAD")
        sys.exit(3)
    commit_range = args[j + 1]
    del args[j:j + 2]
terms_file = args[0] if args else default_terms
paths = paths or ["."]

if not os.path.isfile(terms_file):
    print(f"no terms file {terms_file}: nothing to check")
    sys.exit(2)

patterns = []
for raw in open(terms_file, encoding="utf-8"):
    line = raw.rstrip("\n")
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    if line.startswith("re:"):
        patterns.append((line, re.compile(line[3:], re.IGNORECASE)))
    else:
        patterns.append((line, re.compile(re.escape(line.strip()), re.IGNORECASE)))


def matches(text):
    """Labels of the terms found in text or in its URL-decoded form."""
    decoded = unquote(text)
    return [label for label, rx in patterns if rx.search(text) or (decoded != text and rx.search(decoded))]


def git(*cmd):
    return subprocess.run(["git", "-c", "core.quotePath=false", *cmd], capture_output=True, check=True).stdout.decode("utf-8", "replace")


def is_private(norm):
    return "/references/local/" in "/" + norm or norm.endswith(".local.json")


def public_files():
    try:
        out = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *paths)
        files = [f for f in out.split("\0") if f]
        return [f for f in files if os.path.isfile(f)], True
    except (OSError, subprocess.CalledProcessError):
        pass
    files = []
    for top in paths:
        if os.path.isfile(top):
            files.append(os.path.normpath(top))
            continue
        for d, dirs, names in os.walk(top):
            rel = os.path.relpath(d, ".").replace(os.sep, "/")
            if "/references/local" in "/" + rel or "/.git" in "/" + rel:
                dirs[:] = []
                continue
            for n in names:
                if n == "config.local.json" or n.endswith(".local.json") or n.startswith(".env"):
                    continue
                files.append(os.path.normpath(os.path.join(rel, n)))
    return files, False


hits = []
files, in_git = public_files()
for f in sorted(files):
    norm = f.replace(os.sep, "/")
    if is_private(norm):
        hits.append((f, 0, "(private file is not ignored)", ""))
        continue
    for label in matches(norm):
        hits.append((f, 0, label, "file name"))
    try:
        text = open(f, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        continue
    for n, line in enumerate(text.splitlines(), 1):
        for label in matches(line):
            hits.append((f, n, label, line.strip()[:120]))

if commit_range:
    if not in_git:
        print("--commits needs a git checkout")
        sys.exit(3)
    try:
        prefix = git("rev-parse", "--show-prefix").strip()
        log = git("log", "--format=%H%x1f%B%x1e", commit_range)
        names = git("diff", "--name-only", "--diff-filter=AR", "-z", commit_range)
        diff = git("diff", "--no-color", "--no-ext-diff", "--unified=0", commit_range)
    except (OSError, subprocess.CalledProcessError) as e:
        err = getattr(e, "stderr", b"") or b""
        print(f"git could not read {commit_range}: {err.decode('utf-8', 'replace').strip() or e}")
        sys.exit(3)
    checked = {prefix + f.replace(os.sep, "/") for f in files}
    for entry in log.split("\x1e"):
        if "\x1f" not in entry:
            continue
        sha, body = entry.strip("\n").split("\x1f", 1)
        for n, line in enumerate(body.splitlines(), 1):
            for label in matches(line):
                hits.append((f"commit {sha[:12]} message", n, label, line.strip()[:120]))
    for name in (x for x in names.split("\0") if x and x not in checked):
        for label in matches(name):
            hits.append((f"{name} (file added in the range)", 0, label, "file name"))
    current, in_hunk = None, False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current, in_hunk = None, False
            continue
        if not in_hunk:
            if line.startswith("+++ "):
                p = line[4:]
                if len(p) > 1 and p[0] == '"' and p[-1] == '"':
                    p = p[1:-1]
                current = p[2:] if p.startswith("b/") else None
            elif line.startswith("@@"):
                in_hunk = True
            continue
        if current is None or current in checked or not line.startswith("+"):
            continue
        for label in matches(line[1:]):
            hits.append((f"{current} (line added in the range)", 0, label, line[1:].strip()[:120]))

for f, n, label, line in hits:
    print(f"LEAK {f}:{n} [{label}] {line}")
scope = f" and in {commit_range}" if commit_range else ""
print(f"{len(hits)} private term hit(s) in public files{scope}")
sys.exit(1 if hits else 0)
