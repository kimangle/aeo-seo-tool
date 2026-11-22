# A new site, a missing property, or no data yet

For a site that is not in `config.local.json`, a Search Console property that is missing or unverified, a site without data, a site that is not live yet, hosting outside Vercel and sites without a repo. Read the section the case needs. The skill never signs in, adds properties, touches DNS or enters secrets: the user does those.

Contents: 1 Find what is known · 2 Config fields from the repo · 3 The property · 4 No data yet · 5 Not live yet · 6 Hosting outside Vercel, no repo

## 1. Find what is known before asking

```bash
grep -ril '<name>' <vault> --include='*.md' | head -20
gh repo list --limit 100 | grep -i '<name>'
ls ~ | grep -i '<name>'
```

Match the user's word for the site (a nickname, a short form of the domain) against `aliases` in the config too. Read the site's context note. A site with no context note in the vault: say so and offer to write one (`<vault>/<site>/context.md`: what it is, owner, domain, repo, how it deploys, whose OK text needs). Ask the user in one message only for what the vault, GitHub and the repo do not tell.

## 2. Config fields from the repo

| Field | Where it comes from |
|---|---|
| `github_repo` | `git -C <repo> remote get-url origin` |
| `base_branch` | `git -C <repo> symbolic-ref --short refs/remotes/origin/HEAD`, without `origin/` |
| `stack` | `package.json` with `next` → `next`; with `vite` → `vite`; no package.json and plain HTML → `static`; anything else → `other` |
| `package_manager` | `package-lock.json` npm, `pnpm-lock.yaml` pnpm, `yarn.lock` yarn, `bun.lock` or `bun.lockb` bun |
| `app_dir` | The folder of the package.json the site builds from: `.`, or for example `apps/web` in a monorepo |
| `web_root` | Next.js and Vite: `<app_dir>/public`; static: the folder the host serves (Vercel Root Directory, the folder with `index.html`) |
| `deploy` | `.vercel/project.json` or `vercel.json` means Vercel. `gh api repos/<github_repo>/deployments --jq '.[0:3][] \| {environment, creator: .creator.login}'` with `vercel[bot]` means the git integration: `git-auto`. A Vercel project without git deployments: `vercel-cli` (confirm with the user). `netlify.toml`, a Pages workflow in `.github/workflows/` or a `gh-pages` branch: `other`. A site builder without a repo: `manual` |
| `vercel_project`, `vercel_scope` | `projectName` in `.vercel/project.json`; the scope whose `npx -y vercel@63.1.2 project ls --scope <scope>` lists it, and it must be the user's own |
| `host`, `sitemap` | `curl -sI https://<domain>/` (a Location to www means the www host); the `Sitemap:` line of `/robots.txt` |
| `prod_build_env` | The repo's README or `next.config.*` (for example a variable such as `SITE_ENV=production` that switches robots to production) |
| `indexnow_key` | Empty: the workflow creates the key file (`create_indexnow_key: true`) |
| `gsc_property`, `google_account` | Section 3 |
| `owner`, `owner_ok_needed`, `owner_ok_tag`, `owner_info_tag`, `coauthor_line` | The vault, otherwise the user |

`scripts/check_workflow.sh --mock` refuses a site entry without the fields the template needs, so a gap shows before any agent starts.

## 3. The Search Console property

1. Open `https://search.google.com/search-console` without `resource_id` and read the property switcher: every property and its state ("Ei vahvistettu" = not verified).
2. Missing: the user adds it ("Lisää kiinteistö") while signed in as `google_account`. A domain property (`sc-domain:<domain>`) covers http, https, www and subdomains and needs a DNS TXT record at the registrar, which the user adds. Without DNS access: a URL-prefix property for the canonical host (`https://www.<domain>/`, trailing slash) verified with Google's HTML file: put the file in `web_root` as a one-file change (SKILL.md 3.4), release it, check it with `scripts/verify_prod.sh "<url> contains=google-site-verification"`, then click "Vahvista" (`references/gsc-chrome.md` section 7).
3. The property belongs to another Google account (a client's): the owner adds the user's `google_account` in the property's Settings → Users and permissions as a Full user (the Finnish labels are not recorded yet; read the page). A restricted user cannot request indexing. Write that account in the site's `google_account` if it differs from the global one.

## 4. No data yet

Right after verification, read SKILL.md step 1 at once: an older site shows its 16 months immediately (on 2026-11-22 a client site's data gave a second round of fixes the same evening). When the reports stay empty (a new site):

- run `scripts/verify_prod.sh` on the home page and the main pages, and the optional HTML audit of SKILL.md 1.9;
- fix only verification and technical blockers: noindex or robots blocks on pages that should rank, missing canonical, missing or broken sitemap, 404s on linked pages;
- submit the sitemap;
- add a reminder line about 7 days ahead for the first real audit.

## 5. Not live yet, or only on *.vercel.app

- A site whose production is only `<project>.vercel.app`, or that is noindex on purpose before launch: say so, and leave the property, sitemap, indexing requests and IndexNow until the domain is live. Fix only what would block the launch.
- After launch, the `*.vercel.app` address should redirect to the domain or carry a canonical to it; SKILL.md 1.8 checks this.

## 6. Hosting outside Vercel, and sites without a repo

- `deploy: other` (Netlify, GitHub Pages, own server): agents check a local build and push the branch; there is no preview URL. The user releases by the repo's README; the main session checks production afterwards with `scripts/verify_prod.sh`.
- `deploy: manual` (Lovable, Wix, WordPress without a repo): no workflow. The main session writes a fix list the owner applies in the site builder. `aeo_seo_tool_v7.py --url https://<domain> --fix-guide --output <scratchpad>/aeo` builds a package with copy-paste snippets, but with `ANTHROPIC_API_KEY` set it calls the Claude API: tell the user it costs money and that the AI writes text for the client, and run it only after their yes. Every text in the package waits for the owner's OK.
