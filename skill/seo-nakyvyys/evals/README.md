# Evals

Behaviour cases in `evals.json` and trigger tests in `trigger-queries.json`. `config.local.json` points at the user's real repos, Search Console properties and vault, so an eval run must never touch them.

## Every run is a dry run

- Copy the skill to a temporary folder and give it a `config.local.json` whose `vault_dir`, `worktree_root` and every `repo` point into a new folder under `/tmp` (mock repos made with `git init`, a bare `origin` next to each, one commit on `main`).
- No Chrome and no Search Console: the grader checks the plan, the URLs the run would open and the order of steps. A run that tries to load Chrome tools stops there and says what it would read.
- No `git push` to any remote that is not a mock, no `vercel deploy`, no Workflow tool start (the run stops at the agent-count question, which is the expected stop), no Search Console write action, no IndexNow POST. `scripts/indexnow.sh` only with `--dry-run`; `scripts/verify_prod.sh` may run against live sites because it only sends GET requests.
- Where the skill would release, it stops at the release question and lists the exact commands it would run. Expectations about releases check that list.

## Format

`evals.json` is the older single-file format: skill-creator reads it but new tests go in case folders, `evals/<case-name>/prompt.md`, `case.yaml` and graders, as skill-creator's `references/schemas.md` describes. Trigger tests (does the skill load or not) stay in `trigger-queries.json`, not in behaviour cases.
