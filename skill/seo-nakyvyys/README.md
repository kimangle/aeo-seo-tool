# seo-nakyvyys

A Claude Code skill that improves a website's visibility in Google in one cycle: it reads Google Search Console in your own Chrome, ranks what to fix, writes the plan into your notes vault, has agents build the fixes in git worktrees, releases only when you say yes, then requests indexing, resubmits sitemaps, pings IndexNow and reminds you to check the numbers after 2 and 4 weeks.

It was written from one evening's work on 2026-11-22: four sites, three workflows with 44 agents, 10 indexing requests and four IndexNow pings. The references keep what that evening taught, with example domains (example.fi) and invented numbers in place of the real sites. Your own sites and cases stay in two gitignored places, `config.local.json` and `references/local/` (see "Public and private files").

## Status: v0.3.0 (2026-11-22), draft

- Every step ran once by hand or in a workflow on 2026-11-22. The skill itself, as written here, has not run end to end yet. v0.2.0 fixed what four reviewers found in v0.1.0 the same evening; v0.3.0 split the files into a public and a private layer (CHANGELOG).
- `scripts/tests/run_tests.sh` runs offline checks, including a local server with invented pages for the `verify_prod.sh` and `indexnow.sh --dry-run` parsers. `--online` adds read-only checks against the live URLs you list in `config.local.json`; without them it skips those checks. On 2026-11-22 the online run passed 31 of 31 checks against the author's sites (macOS, Python 3, Node 24, curl). `indexnow.sh` was only tested with `--dry-run`; its POST is the same request the run sent by hand, which returned 202 for all four sites.
- The workflow template's re-review stage and `release_ok` are tested only with the mock run of `check_workflow.sh`; no real workflow has used them yet.
- `scripts/gsc_table.js` is tested on a fake DOM shaped like a Search Console page. Search Console can change its markup; when the output is empty, read one table with `get_page_text` and fix the selectors.
- The evals in `evals/` are written and have not been run. Every eval run is a dry run (`evals/README.md`).

## Install

The skill lives in the `skill/seo-nakyvyys` folder of the aeo-seo-tool repository. Link it into Claude Code's skills folder, so a `git pull` updates it. If `~/.claude/skills/seo-nakyvyys` already exists as a plain folder, move it outside the skills folder first (`mv ~/.claude/skills/seo-nakyvyys ~/seo-nakyvyys-old`): otherwise `ln -s` puts the link inside the old folder without an error, and Claude Code keeps loading the old copy.

```bash
ln -s <repo>/skill/seo-nakyvyys ~/.claude/skills/seo-nakyvyys
readlink ~/.claude/skills/seo-nakyvyys     # must print <repo>/skill/seo-nakyvyys
cd <repo>/skill/seo-nakyvyys
cp config.example.json config.local.json   # fill in your vault, worktree folder and sites
mkdir -p references/local                  # optional: your own cases, learnings and leak terms
scripts/tests/run_tests.sh                 # offline checks
scripts/tests/run_tests.sh --online        # plus read-only checks on the URLs in config.local.json
```

Each key in `config.example.json` is explained in the file. `config.local.json` holds no secrets: IndexNow keys and Search Console verification file names are public, because the sites serve them from their root.

## Public and private files

The repository is public, so the skill keeps two layers.

| Layer | Files | What goes there |
|---|---|---|
| Public, tracked | `SKILL.md`, `README.md`, `CHANGELOG.md`, `config.example.json`, `references/*.md`, `references/workflow-template.js`, `scripts/`, `templates/`, `evals/` | Steps, rules, URL patterns, heuristics and learnings in a general form. Examples use example.fi and invented numbers, marked as examples |
| Private, gitignored | `config.local.json`, `references/local/` | Your sites, owners and accounts; real cases and their Search Console numbers; the full learnings |

The skill works without `references/local/`. When it exists, SKILL.md reads these files from it:

| File | Read with | Holds |
|---|---|---|
| `sites.md` | step 0 | Accounts, owners and whose OK text needs, special pages, your production URL list |
| `heuristics-examples.md` | `references/heuristics.md` | Your real case for each row of the decision table, same row numbers |
| `learnings-private.md` | `references/learnings.md` | The full learnings with names and numbers, same entry numbers |
| `private-terms.txt` | `scripts/tests/run_tests.sh` | One term or `re:` regex per line: client and family names, domains, account ids, keys, local paths. The tests fail if any of them shows up in a public file |

When a run teaches something new, write the real case in the private file and the general version, with invented numbers, in the public one (SKILL.md step 7).

`git worktree remove` deletes gitignored files without a warning. If `config.local.json` or `references/local/` exists only in a worktree, copy both to the main checkout before you remove it.

## Requirements

| Tool | For |
|---|---|
| Claude Code with the Claude in Chrome extension | Reading Search Console and the indexing requests. Type `/chrome` to connect. The Google account that owns the properties must be signed in |
| Workflow tool | Multi-agent builds (step 4). Without it, the same template is a checklist for one agent at a time |
| git, gh (GitHub CLI) | Worktrees, pushes, finding Vercel previews through GitHub statuses |
| curl, python3 3.8+ | `verify_prod.sh`, `indexnow.sh`, the leak check (standard library only) |
| Node 18+ | `check_workflow.sh`, the `gsc_table.js` test, Next.js and Vite builds |
| Vercel CLI via `npx -y vercel@63.1.2` | Sites that deploy only with `vercel deploy --prod` |
| aeo-seo-tool (optional) | An HTML audit of the live site, see below |

## Use

Say it in your own words. Examples that start each mode:

| You say | Mode | What happens |
|---|---|---|
| "kato miten mun search consolessa menee" | AUDIT | Reads every property, writes the baseline note with every ranked fix, shows at most five and asks which to do |
| "miksi tää sivu ei näy googlessa" + a URL | DIAGNOSE | Live check, URL inspection and the page's own queries; cause, fix and cost in three lines |
| "paranna näkyvyyttä kaikilla sivuilla" | IMPROVE | Audit, your choice of fixes, plan in the vault, estimate, then a workflow after your yes (with a re-review of the fixer's work); release after a second yes; indexing, IndexNow, reminder, cleanup, learnings |
| "vaihda hinnasto-sivun title, näyttöjä tulee mut ei klikkejä" | QUICK FIX | The page's queries, one change without a workflow, the diff read by the main session, release and indexing after your yes |
| "pyydä indeksointi näille" | NOTIFY | Production check, then Google and IndexNow for the URLs that are indexable |
| "miten ne muutokset vaikutti" | FOLLOW-UP | Same periods as the baseline, per changed page and query, honest about what is too early |

The skill stops and asks before every production release, before any workflow over about 30 minutes, before anything in an outside account (Lovable, Vercel settings and environment variables, DNS, the newsletter service, Search Console properties), and before text on someone else's site goes live. It never signs in, handles secrets, creates share links or sends messages to site owners; it drafts the message for you. A site that is not in the config yet: `references/new-site.md`.

## The scripts on their own

```bash
# Production check: status, title, robots, canonical, hreflang, JSON-LD, redirects, Range, contains
scripts/verify_prod.sh https://example.fi/en "https://example.fi/opas noindex" \
  "https://www.example.fi/vanha-blogi -> https://www.example.fi/blogi"

# A contains= text with spaces gets its own quotes inside the spec
scripts/verify_prod.sh "https://example.fi/llms.txt contains='1 200 €'"

# IndexNow: checks the key file, skips noindex and canonical-elsewhere pages; --dry-run sends nothing
scripts/indexnow.sh --dry-run --site example.fi https://example.fi/en

# Check a filled-in workflow before starting it; print one agent's prompt
PRINT_LABEL=yhdistys:example scripts/check_workflow.sh /path/to/run.js --mock /path/to/args.json

# Leak check on its own: terms from references/local/private-terms.txt against the public files;
# --commits also checks the commit messages and the lines a range adds anywhere in the repository
python3 -I scripts/tests/leak_check.py --commits origin/main..HEAD
```

`scripts/gsc_table.js` runs in the browser: paste it into the Claude in Chrome `javascript_tool` on a Search Console report page.

## aeo-seo-tool

The audit tool in the root of this repository (`aeo_seo_tool_v7.py`) checks the HTML side that Search Console does not show: titles, descriptions, heading structure, JSON-LD, Open Graph, robots.txt, sitemap.xml, llms.txt and whether AI crawlers may read the site. Set `aeo_seo_tool` in `config.local.json` to the repository root. The skill uses it in three places:

- Step 1, optional: `python3 aeo_seo_tool_v7.py --url https://<domain> --max-pages 10 --no-open --output <scratchpad>/aeo` for an audit without an API key. Always pass `--output`: the default `./reports` writes into the current folder, which can be the vault or a repo.
- Sites without a repo (Lovable, Wix, WordPress): `--fix-guide` builds a fix package with copy-paste snippets the owner applies in their site builder. It includes `--fix`: with `ANTHROPIC_API_KEY` set it calls the Claude API, which costs money and has AI write the client's text. The skill tells you this and runs it only after your yes; the texts wait for the owner's OK.
- Follow-up for a client: `--compare <old audit JSON>` writes a before-and-after report.

Search Console says what Google shows and what people click; the tool says what is wrong in the HTML. The skill ranks fixes from Search Console first and uses the tool to find the technical faults behind them.

## Files

| Path | What it holds |
|---|---|
| `SKILL.md` | The cycle, modes, stop points and rules |
| `config.example.json`, `config.local.json` | Settings with explanations; this machine's sites (gitignored) |
| `references/gsc-chrome.md` | Search Console in Chrome: URL patterns, tables, inspection, sitemaps, verification |
| `references/new-site.md` | A site not in the config, a missing property, no data yet, hosting outside Vercel, sites without a repo |
| `references/heuristics.md` | Priority order and the finding-to-fix table with invented example cases |
| `references/workflow-template.js` | Parametrised workflow: implementers, integrator, reviewers, fixer, re-review, `release_ok` |
| `references/checklists.md` | Technical, content, release and production checks; forms and replacement pages |
| `references/learnings.md` | Pitfalls from the first run and their fixes, in a general form |
| `references/local/` | Gitignored private layer (see above) |
| `templates/audit-note.md` | The vault note format |
| `scripts/` | `verify_prod.sh`, `indexnow.sh`, `gsc_table.js`, `check_workflow.sh`, tests, invented fixtures and the leak check |
| `evals/` | Dry-run rules, six behaviour cases and 20 trigger queries (10 near misses) |
