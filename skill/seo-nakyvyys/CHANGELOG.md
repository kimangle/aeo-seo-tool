# Changelog

One entry per version, newest first, in the form `## vX.Y.Z (YYYY-MM-DD)`. Site names, owners and workflow ids are left out; the private history is in `references/local/` when it exists.

## v0.3.0 (2026-11-22)

The skill moved into the public aeo-seo-tool repository (`skill/seo-nakyvyys`), so its files were split into a public and a private layer.

### Changed

- The examples in `references/heuristics.md`, `references/checklists.md`, `references/gsc-chrome.md`, `references/new-site.md`, the workflow template, the audit note template, the evals and the test fixtures use example domains (example.fi) and invented numbers, marked as examples. The techniques, URL patterns, thresholds and rules are unchanged.
- `references/learnings.md` keeps all 43 entries with the same numbers in a general form.
- `scripts/tests/run_tests.sh --online` reads its live URLs from the `tests` block of `config.local.json` or from the file named by `SEO_NAKYVYYS_ONLINE_SPECS`, and skips the online checks without them. The negative checks take the first bare URL and its host from that list.
- SKILL.md reads `references/local/sites.md`, `heuristics-examples.md` and `learnings-private.md` when they exist and works without them; step 7 says where a new real case and its general version go. The reminders file comes from the config `reminders_file`. The description names the near misses without other skills' names.
- The aeo-seo-tool is the repository the skill ships in; README Install links the folder into `~/.claude/skills`, after moving an existing plain folder out of the skills folder, and checks the link with `readlink`.
- SKILL.md 6.6 and README: `git worktree remove` deletes gitignored files, so a worktree's own `config.local.json` and `references/local/` are copied first.
- SKILL.md 4.3: caffeinate only on macOS. `run_tests.sh` creates its temp folder with a template that GNU `mktemp` accepts too. The example `reserved_ports` are 3000 and 5173.

### Added

- `references/local/` (gitignored): `sites.md`, `heuristics-examples.md`, `learnings-private.md`, `private-terms.txt`.
- `scripts/tests/leak_check.py`: fails when a term from `references/local/private-terms.txt` appears in a public file or file name, or when a private file is not ignored. Every line is also checked URL-decoded. `--commits <range>` adds the commit messages, the added file names and the added lines of the range anywhere in the repository; paths after `--` replace the current folder. `run_tests.sh` runs it when the terms file exists, with `--commits origin/main..HEAD` when that ref exists (`SEO_NAKYVYYS_LEAK_RANGE` sets another range or `none`).
- `config.example.json`: the `tests` block.

## v0.2.0 (2026-11-22)

Fixes from four reviews of v0.1.0 the same evening (coverage against the vault note and the three journals, skill quality, safety and rules, a dry run of new cases). Nothing here has run in a real workflow yet.

### Fixed

- `vercel curl` was used by one site's agents in all three workflows; learnings 11 claimed the opposite. The shared rules now forbid `vercel curl`, every Vercel MCP tool, bypass tokens and share links for every agent, and `check_workflow.sh` requires the rule.
- Review gate: reviewer verdicts were from before the fixer and nobody reviewed the fixer. The template has a fifth stage that re-reviews the fixer's HEAD with every lens that had findings, the fixer starts leftover blockers with "ESTÄVÄ:", and the result carries `verdicts_after_fix`, `reviewers_missing`, `release_ok` and `release_blockers`. A missing reviewer now blocks the release instead of looking clean.
- Legally required text (a privacy notice item for a new form) ships with its feature and is never reverted alone (SKILL.md 5.2, checklists 3, eval 4); the template tags it with `owner_info_tag`.
- A stale checkout of a CLI-deployed site was 33 commits behind. `also_update_branches` lists the base branch for such a site, and SKILL.md 5.6 fast-forwards a checkout only when that branch is checked out and clean (`fetch origin <base>:<branch>` when it is not), otherwise warns.
- Owner review: previews are behind Vercel login, so the owner sees drafts through the user (screenshots or page text from Chrome, a meeting, or the user's own share link). The skill never sends messages to owners or clients.
- New lenses `identtisyys`, `turva` and `tietosuoja` from the replacement-page run; an unknown lens stops the run. Checklists section 5 (forms and replacement pages) and the source-copy step in heuristics row 7.
- `check_workflow.sh` swallowed agent errors, passed a template without the Skill rule, and exited 0 on `{error: ...}`. It now collects every problem and fails on a missing rule (also Docker, pkill, --prod, origin/, vercel curl), `undefined`/`NaN` in a prompt, an error result, missing implementers or reviewers, no agent calls, overlapping or reserved ports and more than 8 tasks. The template validates required site fields itself.
- `verify_prod.sh`: `contains=` with spaces needs inner quotes (documented, examples fixed in heuristics and checklists); only 100-599 counts as a status code; a no-break space matches a space; the title is the first one outside inline SVG; robots `none` is noindex; a 404 page with "index" in robots warns; description limit 155 everywhere.
- `indexnow.sh` treats robots `none` as noindex, skips URLs whose canonical points elsewhere, and prints the kept list that also feeds the Google indexing requests.
- `vercel deploy` from an unlinked folder creates a new project: agents and the release copy only `.vercel/project.json` (no pulled env files) and check `projectName` against `vercel_project`.
- AUDIT now writes the baseline note and the daily line; every ranked item goes into the note, five are shown, IMPROVE asks which to do; a same-day note gets a new section instead of being overwritten; FOLLOW-UP uses the newest note that covers the site.
- Release: release branch and reverts in a new worktree, build again after a revert, a production FAIL is fixed only after showing the diff and asking, the release question names sitemap resubmits and verification.
- Durations corrected (36, about 40 and 23 minutes), heuristics row 4 title corrected.

### Added

- `references/new-site.md`: what to look up before asking, config fields from the repo, adding or sharing a property, no data yet, a site only on `*.vercel.app`, `deploy: other`, sites without a repo and the cost of `--fix-guide`.
- SKILL.md: step 1.1 property list, step 6.3 audit right after verification, 6.6 worktree cleanup, 6.7 next round offer, step 7 learnings, QUICK FIX mode, 7-day baseline reuse, per-round `k<N>` worktree folders, vault corrections from `open_questions`, caffeinate stop, no-Workflow fallback, `--output` for the HTML audit.
- Template: `app_dir`, `package_manager`, an install fallback for Vite, `deploy: other`, page-date rule for every agent, owner text defined (title, description, og, H1, schema text, llms.txt).
- Config: `aliases`, `owner_info_tag`, per-site `google_account`, `app_dir`, `package_manager`.
- Tests: negative mock runs (no Skill rule, empty sites, missing field with overlapping ports) and a local server for the `verify_prod.sh` and `indexnow.sh --dry-run` parsers. `evals/README.md` makes every eval run a dry run.
- Learnings 36-43.
- Checked after the fixes: `scripts/tests/run_tests.sh --online` 31 of 31 passed; `verify_prod.sh` on a live page PASS; `indexnow.sh --dry-run` kept 1 URL and sent nothing.

### Changed

- Eval 4 is a dry run that stops at the release question and lists commands; evals 7 and 8 (trigger-only) removed; trigger queries are 10 and 10 with near misses (a competitor's SEO, ChatGPT visibility, a blog post, Google Ads, a 3D page's meta tags, a review reply).
- Description: "titles and meta descriptions to win more clicks from Google", and not for sites without Search Console access or AI-assistant visibility (searchfit-seo) or Google Ads.
- Status line counts to the last step 7 (`Vaihe 3/7`).

## v0.1.0 (2026-11-22)

First version, written the same evening from the work it describes: a Search Console review of four sites, three workflows (44 agents), releases to all four sites, 10 indexing requests and IndexNow pings answered 202. Sources: the vault note of the run, the three workflow scripts and their journals.

### Added

- `SKILL.md`: steps 0 to 6 (connect and preflight, audit, diagnose and rank, plan in the vault, build with a workflow, release, notify and follow up), five modes (AUDIT, DIAGNOSE, IMPROVE, NOTIFY, FOLLOW-UP), stop points and hard rules.
- `references/gsc-chrome.md`: Search Console URL patterns (`performance/search-analytics` with `num_of_months`, `num_of_days`, `metrics`, `breakdown=page`, `page=!`, `compare_date=PREV`; `index`, `index/drilldown`, `sitemaps`), URL inspection through the search box (the direct `inspect?id=` URL gave 404), indexing requests, sitemap submits, HTML-file verification and the extension's per-domain permission.
- `references/heuristics.md`: priority order and a 15-row finding-to-fix table.
- `references/workflow-template.js`: parametrised workflow (sites from args, one worktree per agent, integrator per repo, technical and content reviewers, fixer), shared agent rules, per-stack build blocks (static, Next.js with `next build --webpack` for a symlinked node_modules, Vite), preview by git push or Vercel CLI, owner-approval commit tags, optional IndexNow key creation.
- `references/checklists.md`, `references/learnings.md` (35 entries), `templates/audit-note.md`.
- `scripts/verify_prod.sh`, `scripts/indexnow.sh` (`--dry-run`), `scripts/gsc_table.js`, `scripts/check_workflow.sh` (parse and mock run), `scripts/tests/run_tests.sh` (22 checks with `--online`, all passed on 2026-11-22; IndexNow only as a dry run).
- `config.example.json` and `config.local.json`, `evals/evals.json` (8 cases) and `evals/trigger-queries.json` (16 queries).
