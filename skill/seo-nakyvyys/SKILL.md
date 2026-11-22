---
name: seo-nakyvyys
description: >-
  Improve a site's visibility in Google end to end: read Search Console in the
  user's Chrome, rank the fixes, plan in the notes vault, build them with
  worktree agents (titles, schema, redirects, hreflang, guides, verification
  files), release only on the user's yes, then request indexing, resubmit
  sitemaps, ping IndexNow and follow up at 2 and 4 weeks. Own and client sites
  in the user's Search Console. Use it whenever the user asks how a site does
  in Google, why a page does not show up, wants more clicks or better rankings,
  or mentions Search Console, indexing, sitemaps, IndexNow, or titles and meta
  descriptions to win more clicks from Google, even without saying SEO.
  Finnish cues: kato search console, miten sivuilla menee googlessa,
  hakukoneoptimointi, miksi ei näy googlessa, paranna hakunäkyvyyttä, pyydä
  indeksointia. Not for a site without Search Console access (a
  competitor), visibility in AI assistants (searchfit-seo), Google Ads, social
  media posts, 3D websites or video production.
compatibility: >-
  Claude Code with the Claude in Chrome extension connected (/chrome) and the
  site owner's Google account signed in; the Workflow tool for multi-agent
  runs; git, gh, curl, python3 3.8+, Node 18+; Vercel CLI through npx
  (vercel@63.1.2) for sites deployed from the command line. Optional: the
  aeo-seo-tool in the same repository (aeo_seo_tool_v7.py) for an HTML audit.
metadata:
  version: "0.3.0"
---

# seo-nakyvyys

One cycle: read Search Console, rank the fixes, plan in the vault, build them in worktrees with agents, release with the user's yes, tell Google and IndexNow, follow up after 2 and 4 weeks, keep what was learned. Written from the 2026-11-22 run on four sites (README).

- Talk in the user's language. Skill files stay in English.
- Open every reply during a run with a status line, the step number of the headings below out of the last step 7 (`Vaihe 3/7 · Suunnitelma`), and end it with the one next action.
- Paths are relative to this folder. Settings come from `config.local.json` (keys explained in `config.example.json`); `<vault>` is its `vault_dir`. Expand `~` to the absolute home path in every command and in the workflow args.
- Read a reference only when a step names it.
- Private layer, optional and gitignored: `references/local/`. If `references/local/sites.md` exists, read it in step 0. When a step names `references/heuristics.md` or `references/learnings.md`, also read `references/local/heuristics-examples.md` or `references/local/learnings-private.md` if it exists. Without them the generic examples are enough.
- No Workflow tool in this session: run the template's stages one agent at a time with the same prompts.

## Modes

| Mode | Pick it when the user | Steps |
|---|---|---|
| AUDIT | wants to see how the sites are doing ("kato search console", "miten mun sivuilla menee") | 0, 1, 2, then 3.1 and 3.2 (note and daily line), then stop with the ranked list |
| DIAGNOSE | asks why one page or site does not show up ("miksi X ei näy googlessa") | 0, then section "Diagnose one URL" |
| IMPROVE | wants things fixed ("paranna näkyvyyttä", "tee kaikki järjestyksessä", a yes after AUDIT) | 0 to 7, with the choice in step 2 |
| QUICK FIX | wants one title, description or redirect changed on one page to win clicks | 0, the page's queries (1.4), then 3.4, 5, 6 and 7 for that page |
| NOTIFY | only wants Google and IndexNow told about pages released elsewhere | `verify_prod.sh` on the URLs, then 6 |
| FOLLOW-UP | is at a reminder date or asks what the changes did | 0, 1 against the baseline note, then 2 |

IMPROVE right after an AUDIT, or with a baseline note under 7 days old that covers the site, reuses that note: say its date and skip step 1.

A site missing from the config, a property missing or unverified in Search Console, or a site with no data yet: follow `references/new-site.md` first. A site without a repo (Lovable, Wix, WordPress, `deploy: manual`) gets steps 0 to 3 and a fix list the owner applies (`references/new-site.md` section 6); no workflow.

## 0. Connect and preflight

1. Chrome: follow `references/gsc-chrome.md` section 1. No Chrome tools after one ToolSearch means the user types `/chrome` and presses Enter; only the user can run it. Work in your own new tab.
2. The Search Console header must show the account in `google_account` (or the site's own `google_account`). A sign-in page or another account: stop, the user signs in.
3. Run `date` (every time and date you write comes from it), `df -h /` (stop below `min_free_disk_gb`), and `gh auth status`. For a `vercel-cli` site also `npx -y vercel@63.1.2 whoami`: it must be the user's own account and the scope in the config, never a client's or an employer's team.
4. Read the newest baseline note that covers each site (`<vault>/search-console-*.md`; one note can hold several sites and rounds), `<vault>/<reminders_file>` and each site's `vault_notes`. When a note and reality disagree, trust what you see, fix the note and say so.

## 1. Audit

Per site, with `references/gsc-chrome.md` sections 2 to 4:

1. Properties, once for all sites: open Search Console without `resource_id` and read the property switcher: every property with its verification state, against the config's `gsc_property` and `other_gsc_properties`. A missing or unverified property is row 1 of the decision table (`references/new-site.md` section 3).
2. Performance for 3 months and for 16 months: totals, then every query row and every page row with `scripts/gsc_table.js`.
3. The last 28 days against the 28 before (`compare_date=PREV`).
4. Per-page queries (`page=!<url>`) for every page with about 30 or more impressions or with impressions and no clicks.
5. The indexing report, with each not-indexed reason opened.
6. The sitemaps page: status and last read date.
7. Live state: `scripts/verify_prod.sh` on the home page and the pages from item 4.
8. Copies elsewhere: curl old hosts the vault mentions (a `*.lovable.app` or old preview domain) and the project's own `https://<vercel_project>.vercel.app/`. A copy that answers 200 without a canonical to the real domain or noindex competes with the real page.
9. Optional HTML audit: `python3 <aeo_seo_tool>/aeo_seo_tool_v7.py --url https://<domain> --max-pages 10 --no-open --output <scratchpad>/aeo` (never the default `./reports`, which can land in the vault or a repo). Never add `--fix` or `--fix-guide` here: with `ANTHROPIC_API_KEY` set they call the Claude API, which costs money.

Write each number with the date range Search Console shows ("data ulottuu 20.11. asti").

## 2. Diagnose and rank

Read `references/heuristics.md`. Match each finding to a row of its decision table and rank by its priority order: blockers, page-1 CTR, brand position, question queries at 15 to 40, new content for far terms. For each item note the site, page, evidence (query, impressions, position, range), fix, whose OK it needs and a rough agent-minute cost.

Every ranked item goes into the note's Ehdotukset (3.1); the reply shows at most five, numbered, best first, and asks which to do. The rest wait in the note for a later round. "Tee kaikki järjestyksessä" means all of them in rank order. AUDIT writes 3.1 and 3.2 and stops. IMPROVE waits for the answer too, unless the user already said "tee kaikki".

## 3. Plan in the vault

1. Write `<vault>/search-console-YYYY-MM-DD.md` from `templates/audit-note.md`: Luvut, Havainnot, Ehdotukset (every ranked item). If today's note exists, append a section `## <sivustot> klo HH.MM` instead of overwriting it. Add the user's decision in their exact words with the time.
2. Add 2 to 5 lines to the day's daily note.
3. Estimate before building: agents, minutes and how heavy. On 2026-11-22 four sites took 21 agents and 36 minutes, a replacement page with a form and a video took 8 agents and about 40 minutes (video encoding, `npm ci`), and a second round took 15 agents and 23 minutes; the re-review adds one agent per lens that had findings. Over 30 minutes or about 10 agents, ask first.
4. A one-file fix under 20 minutes is done directly or with one agent, without a reviewer chain. Then the main session reads the whole diff and runs `references/checklists.md` section 1 on a local build: that is its review, and the release question names it ("tarkastettu: diff luettu, paikallinen build").

## 4. Build with a workflow

1. Copy `references/workflow-template.js` to the scratchpad and fill `args` from the config and the approved plan, with absolute paths:
   - one site entry per repo, one task per independent change (at most 8 per site), each task prompt with its evidence (queries, impressions, positions, date range), files to read, what not to touch, and any owner approval the vault records;
   - `wt_root`: `worktree_root` with `{mmdd}` plus `/k<N>`, the round of the day (`ls` the day folder; k1 first). Check `git -C <repo> branch -a --list '<name>*'` and add `-k<N>` to a branch name that exists;
   - each site its own block of 10 ports from `port_base`, no block containing one of `reserved_ports`; pass `reserved_ports` too;
   - `create_indexnow_key: true` for a site whose `indexnow_key` is empty;
   - lenses `tekninen` and `sisalto`; for a replacement page or a form add `identtisyys`, `turva` and `tietosuoja` (`references/checklists.md` section 5).
2. `scripts/check_workflow.sh <copy> --mock <args.json>` must pass. It fails on a missing shared rule, a missing site field, `undefined` in a prompt, overlapping or reserved ports, more than 8 tasks, an unknown lens or an agent error. `PRINT_LABEL=<label>` shows any prompt in full.
3. Tell the user the agent count and time in one line, plus "kysy tilannetta viestillä, älä paina stopia". Start the Workflow tool only after their yes. Keep the machine awake. On macOS: `pgrep -fl caffeinate`, and if none runs, `nohup caffeinate -ims >/dev/null 2>&1 & disown` and note its PID (the charger should stay plugged in); elsewhere use the system's own setting or skip it.
4. While it runs, never SendMessage its agents (a message starts a second copy in the same worktree). Wait for the result.
5. Read every site's result. A site can be released only when `release_ok` is true: every lens reviewed, each lens's last verdict go with no blocking issue (`verdicts_after_fix` where the fixer ran), and no `not_fixed` line starting with "ESTÄVÄ:". Otherwise report `release_blockers` and offer a fix round. A blocker the user removed outside the code (an environment variable added) is named in the release question.
6. `open_questions` that correct the vault (a branch already merged, a commit never released, an approval already given): fix the note now (note, line, reason) and tell the user in one line.
7. Look at the previews in Chrome where the extension allows the domain (`references/learnings.md` 11 and 12). Append the branch table to the vault note. If you started caffeinate, stop it now: `ps -o command= -p <PID>` must show caffeinate, then `kill <PID>`.

The template carries the rules every agent gets: no Skill tool, no Chrome, no SendMessage, no `vercel curl` or Vercel MCP tools, own worktree from `origin/<base>`, no push to the base branch, no production deploy, no IndexNow, no secrets, no Docker, no pkill or killall, stop only own PIDs, commit often, no invented facts, no AI slop, page dates only for changed text, owner text in separate tagged commits.

## 5. Release (only after the user's yes)

1. Show per site: branch at HEAD, preview, what changes on the live site, how it was reviewed and whose OK is still missing. Ask once: "Julkaisenko nämä N sivustoa ja teenkö sen jälkeen indeksointipyynnöt, sivukarttojen uudelleenlähetyksen[, X:n omistajuuden vahvistuksen] ja IndexNow-pingit?" The yes covers those Search Console actions for these URLs and nothing else.
2. Create `release/<site>-<date>` and any reverts in a new worktree under the round's `wt_root` from `origin/<base>`, never in the user's checkout. Revert commits that wait for another person's OK (tagged `owner_ok_tag`) unless that person approved in writing. Legally required text that a released feature needs (a privacy notice item for a new form, tagged `owner_info_tag`) ships with the feature and is never reverted alone; tell the user it goes out "[X:n tiedoksi]" and add a reminder line for the owner. If the user wants the owner's OK first, hold the feature back too. After a revert, build and check again. Branches that depend on each other go out together on the release branch.
3. Go through `references/checklists.md` section 3.
4. `git-auto`: `git fetch origin && git merge-base --is-ancestor origin/<base> <sha> && git push origin <sha>:<base>`. If it is not a fast-forward, merge in a worktree, run the checks again, then push.
5. `vercel-cli`: the same push, then from a clean worktree at that commit: `mkdir -p .vercel && cp <repo>/.vercel/project.json .vercel/` (only that file: `.vercel` can hold pulled env files) and check that its `projectName` is `vercel_project`. No file: `npx -y vercel@63.1.2 project ls --scope <vercel_scope>` must list the project, then `vercel link --yes --project <vercel_project> --scope <vercel_scope>`; never deploy from an unlinked folder (it creates a new project). Then `npx -y vercel@63.1.2 deploy --prod --yes --scope <vercel_scope>`; wait for Ready. `other` (hosting outside Vercel): push the branch and give the user the release steps from the repo's README; check production after they release.
6. The user's checkout, for each of `also_update_branches` (a `vercel-cli` site lists its base branch: a `vercel deploy --prod` from a stale checkout rolls production back): if `git -C <repo> branch --show-current` is that branch and `git -C <repo> status --porcelain` is empty, `git -C <repo> merge --ff-only origin/<base>`; if the branch is not checked out, `git -C <repo> fetch origin <base>:<branch>` (fast-forward only, the working tree stays as it is); otherwise change nothing and write in the reply and the vault note the command plus "älä aja vercel deploy --prod vanhasta checkoutista".
7. Production check: `scripts/verify_prod.sh -f <list>` with the changed pages, redirects, noindex pages, the 404 page and key files (`references/checklists.md` section 4). A FAIL: fix it in a new worktree, show the user the diff and the `verify_prod.sh` output, ask, then push (never force). If the site is broken, offer to revert to the previous sha and do it only on the user's yes.
8. Write the release (old and new sha per site, the user's words, check results) into the vault note.

## 6. Notify search engines and follow up

1. IndexNow (Bing, Yandex, Seznam, Naver; Google does not use it). A site without `indexnow_key`: the workflow created `<web_root>/<key>.txt`; after the release add the key to the config. Then `scripts/indexnow.sh --site <domain> <changed URLs>`: it checks the key file answers 200 with the key, skips non-200, noindex and canonical-elsewhere URLs, prints the kept list, then posts; 200 or 202 is OK. `--dry-run` shows the request without sending it.
2. Google: URL inspection and "Pyydä indeksointia" for the URLs `indexnow.sh` kept (changed, 200, indexable, self-canonical; without a key, those `verify_prod.sh` shows that way). `references/gsc-chrome.md` section 5, about 40 s each. Never for noindex pages, drafts or redirects.
3. Sitemap: resubmit when pages were added or the property was just verified (section 6 there). A property that was waiting for its verification file: click "Vahvista" (section 7), then read step 1 for it at once (an older site shows 16 months immediately), add the findings to Ehdotukset and offer them as the next round.
4. Follow-up: add one line to the "Aktiiviset" section of `<vault>/<reminders_file>` with the dates 14 and 28 days ahead, the sites and the baseline note, plus anything still waiting for someone (an owner's OK, a login).
5. Vault: append the indexing requests, sitemap submits and IndexNow codes to the note; a daily note line.
6. Clean up the round: `git -C <repo> worktree remove <path>` for each released worktree (`--force` only when `git -C <path> status --porcelain` shows nothing but the node_modules symlink or build output), `git -C <repo> branch -d <branch>` for merged local branches. `worktree remove` deletes gitignored files without a warning, so first copy a `config.local.json` or `references/local/` that exists only in that worktree. Anything that needs `rm -rf`: print the command for the user.
7. Offer the Ehdotukset items still open as the next round, with an estimate, and ask.

FOLLOW-UP compares the same period lengths as the baseline (28 days against the previous 28, and 3 months), per changed page and per targeted query: clicks, impressions, CTR, position. Say what is too early to judge: data lags about 2 days, title changes show in 2 to 4 weeks, new pages in 3 to 6 months. Write the comparison as a new dated note (the next baseline, linked to the old one; same-day rule of 3.1) and note the check on the reminder line; the line moves to "Hoidetut" only when the user says it is done.

## 7. Learnings

After every run beyond AUDIT: new pitfalls go into `references/learnings.md` (end of a section, with the date), new finding-to-fix cases into the `references/heuristics.md` table, and each change gets a `CHANGELOG.md` entry and a version bump in the metadata above. A change to SKILL.md itself is shown to the user as a diff and written only after their yes.

The skill folder can live in a public repository. Tracked files carry only the technique with example domains (example.fi) and invented numbers marked as examples. The real case (site, owner, queries, Search Console numbers, commit shas, workflow ids, preview URLs, keys, local paths) goes into `references/local/learnings-private.md` or `references/local/heuristics-examples.md` under the same number, and machine settings into `config.local.json`. Before a commit, run `scripts/tests/run_tests.sh`: with `references/local/private-terms.txt` present it fails on any listed term in the public files.

## Diagnose one URL

1. `scripts/verify_prod.sh <url>`: status, robots, canonical, title.
2. URL inspection in Search Console: is it in Google, which canonical Google chose, last crawl.
3. Its queries (`page=!<url>`, 16 months): no impressions means Google does not show it at all (index, crawl, competition); impressions without clicks means the title and description do not win the click; a deep position means the content does not answer the query yet.
4. Answer in three lines: the cause, the fix from `references/heuristics.md`, the cost. Offer QUICK FIX or IMPROVE for it.

## Stop and ask

- Before every production release. On a `git-auto` site a merge to the base branch is a release.
- Before a workflow over 30 minutes or about 10 agents.
- Anything in an outside account beyond reading Search Console: Lovable, Vercel settings and environment variables, the newsletter service, DNS, Google Business Profile, Search Console properties and users. The user signs in and enters secrets.
- Text on someone else's site (`owner_ok_needed`): the title, meta description, og and twitter texts, H1, visible text, schema text fields, FAQ and llms.txt lines are the owner's text unless the config `notes` or the vault record their OK for that change. New or changed owner text waits in tagged commits or a noindex draft branch. The owner sees a draft through the user: the main session opens the preview in the user's Chrome and saves screenshots or the page text (`get_page_text`) for the user to pass on, or the user meets the owner, or the user decides to make a share link in their own Vercel account. Write the chosen way in the vault note.
- A promise about the business (English service, reports, guarantees, prices) that the site and the vault do not already make.

## Never

- Type passwords, API keys or tokens, sign in, or add or read environment variable values.
- Publish without the user's yes in this session, force push, or release a site whose `release_ok` is false, or a 3.4 fix whose diff the main session did not read.
- Start Docker, use `pkill` or `killall`, or stop processes by name or port range. Stop only PIDs you started; check `ps -o command= -p <PID>` first.
- `rm -rf`: print the command for the user.
- Use `vercel curl` (it can create a "Protection Bypass for Automation" secret), the Vercel MCP's web fetch, share-link, protection or environment tools, bypass tokens or share links to open a protected preview.
- Ping IndexNow before the key file answers 200 in production, or request indexing for a noindex page, a draft, a redirect or a page whose canonical points elsewhere.
- Use another person's or company's Vercel or GitHub account for the user's sites.
- Let an agent call the Skill tool or send messages to anyone.
- Send email, chat or any other message to a site owner, client or anyone else: draft the text for the user to send.

## File map

| Path | What it holds |
|---|---|
| `config.example.json`, `config.local.json` | Every setting with its meaning; this machine's sites (gitignored) |
| `references/local/` | Optional and gitignored: `sites.md`, `heuristics-examples.md`, `learnings-private.md` with real cases, `private-terms.txt` for the leak check |
| `references/gsc-chrome.md` | Chrome connection, Search Console URL patterns, tables, indexing report, URL inspection, sitemaps, verification |
| `references/new-site.md` | A site not in the config: fields from the repo, the property, no data yet, not live yet, hosting outside Vercel, sites without a repo |
| `references/heuristics.md` | Priority order and the finding-to-fix table with example cases |
| `references/workflow-template.js` | Parametrised Workflow script: implementers, integrator, reviewers, fixer, re-review, `release_ok` |
| `references/checklists.md` | Technical and content checks, release checks, the production URL list, forms and replacement pages |
| `references/learnings.md` | Pitfalls from the first run and their fixes |
| `templates/audit-note.md` | The vault note, from numbers to follow-up |
| `scripts/gsc_table.js` | Browser snippet: all table rows and totals of a Search Console page as JSON |
| `scripts/verify_prod.sh` | curl checks: status, title, robots, canonical, hreflang, JSON-LD, redirects, Range, contains |
| `scripts/indexnow.sh` | Key file check, indexable self-canonical URL filter and the IndexNow POST; `--dry-run` |
| `scripts/check_workflow.sh` | Parse and mock-run a Workflow script before starting it |
| `scripts/tests/run_tests.sh` | Offline tests with a local server and the leak check; `--online` adds read-only checks against the live URLs in `config.local.json` |
| `evals/README.md`, `evals/evals.json`, `evals/trigger-queries.json` | Dry-run rules, behaviour cases and trigger queries |
| `README.md`, `CHANGELOG.md` | Install and use; version history |
