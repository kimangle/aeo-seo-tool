# Learnings

Pitfalls from the first run (2026-11-22: four sites, three workflows, 44 agents) and what solved them, plus what the review of the skill draft found the same evening (36-43). Sources: the agents' summaries, open questions and not-fixed lists in the three workflow journals, and the vault note of the run. Site names, owners, commit shas and numbers are left out here; when `references/local/learnings-private.md` exists, it holds the full entries under the same numbers. Add new entries at the end of a section with the next free number and the date: the generic version here, the real one in the private file.

## Git, worktrees and builds

1. **Local base branch behind origin.** One site's checkout sat on a feature branch and its local `main` was behind. The plan said the branch had six unmerged commits; they had been in `origin/main` for three months. Fix: branch from `origin/<base>` after `git fetch`, and check claims with `git merge-base --is-ancestor`. Correct the vault note when it is wrong.
2. **Turbopack and a symlinked node_modules.** `npm run build` failed in a worktree: "Symlink [project]/node_modules is invalid, it points out of the filesystem root". `npx next build --webpack` with the same config passed. Vercel's own build is unaffected.
3. **No node_modules in the main checkout** (a Next.js site). Implementers could not build; one read TypeScript only, two borrowed another worktree's node_modules read-only for `tsc`. Only the integrator ran `npm ci` (a few hundred MB in its worktree). Keep it to one `npm ci` per repo when the disk is short of space.
4. **Adjacent lines in llms.txt.** Two parallel branches edited lines 14 and 15 of the same llms.txt, which git reports as a conflict. Implementers now leave shared list files (sitemap.xml, llms.txt) to the integrator, who keeps both lines.
5. **A fix that never shipped.** A price fix in llms.txt existed only on a feature branch; the vault plan said "published" and the live llms.txt was wrong for weeks. A reviewer caught it and the commit was cherry-picked. Before a release, compare live facts (prices, titles) with the source of truth, and use `git branch -a --contains <sha>` when a note claims something shipped.
6. **Dependent branches.** A link from an article to a new landing page would have answered 404 if its branch had shipped before the page. Both went out together on `release/<site>-<date>`.
7. **Owner-approval commits.** Changes waiting for the site owner were separate commits tagged with the site's `owner_ok_tag`. One footer link was reverted before the release without touching anything else. The home page title turned out to be approved already a month earlier: check the vault before asking again.
8. **A build script publishes every page.** On a Vite multi-page site `scripts/prerender.mjs` writes `dist/sitemap.xml` and `dist/llms.txt` from every page that has a data file and an HTML shell. A draft merged to main is in the sitemap at once, so drafts stay on their own branch.
9. **Commit attribution on a client repo.** Some repos want commits without attribution lines, and the run added them anyway. The config has `coauthor_line` per site.
10. **The agent cannot run `rm -rf`.** Scratch copies (about 100 MB) stayed in the scratchpad. Print the cleanup command for the user instead of working around the block.
36. **A stale checkout of a CLI-deployed site** (2026-11-22). After the releases, the user's checkout of a site that only deploys with `vercel deploy --prod` sat on main 33 commits behind origin/main, with a clean tree. A deploy from that checkout would have taken the SEO changes, a new landing page, privacy items and the IndexNow key out of production. `also_update_branches` now lists main for such a site, and SKILL.md 5.6 fast-forwards the checkout or warns.
37. **A second round on the same day** (2026-11-22). Round 1's worktrees were still in `~/wt-seo-<mmdd>`, so round 2 used a `k2` subfolder; the folder grew to 1.6 GB and one site repo to 11 worktrees. Each round now gets its own `k<N>` folder, branch names get `-k<N>` on a clash, and SKILL.md 6.6 removes released worktrees.

## Previews and the browser

11. **Vercel previews are behind login, and `vercel curl` got used anyway.** Every preview answered curl with 302 to `vercel.com/sso-api`. The agents on the git-auto sites refused `vercel curl` (it can create a "Protection Bypass for Automation" secret, a settings change), but the agents of the CLI-deployed site used it in all three workflows (integrator, reviewer and fixer, and mp4 Range tests). The ban then sat only in the git-auto preview text. Since v0.2.0 the shared rules forbid `vercel curl`, every Vercel MCP tool, bypass tokens and share links for every agent. After such a slip the user checks once in Vercel: the project → Settings → Deployment Protection, whether a bypass secret appeared. Check previews in the user's Chrome, or check the same commit locally and verify in production after the release.
12. **The Chrome extension refused one preview domain**: "Navigation to this domain is not allowed" for one project's `<project>-*.vercel.app` previews, while two other projects' previews opened. The integrator and fixer had tested that site locally, and production was checked after the release.
13. **`/crome` is not `/chrome`.** A typo sent the command as plain text and no Chrome tools loaded. Ask for `/chrome` exactly.
38. **Owners cannot open previews** (2026-11-22). The client site owners have no Vercel login, so a preview link is no use to them, and the skill forbids share links and bypass. A draft article still waited for its owner's OK. The way now: the user shows the draft (screenshots or page text from Chrome, or a meeting), or decides to create a share link in their own account.

## Search Console

14. **The direct inspection URL gives 404.** `/search-console/inspect?resource_id=...&id=...` returned Google's 404 page. Use the search box at the top of the property.
15. **get_page_text shows ten rows.** The DOM holds all of them (dozens of queries on one site); `scripts/gsc_table.js` reads them.
16. **Rounded totals.** A card such as "Näyttökertoja yhteensä 9,80 t." is rounded; the rows are exact.
17. **Unverified property = no data.** A client site's property had been added but not verified. After the HTML file shipped and "Vahvista" was clicked, 16 months of data appeared at once.
18. **Data lag of about two days.** Read on 2026-11-22, data ran to 2026-11-20.
39. **A newly verified property is a new audit** (2026-11-22). Right after a client site was verified, its 16 months showed the brand name outside the top 10 and 404s on two old URLs that still had clicks. That became round 2 the same evening (308 redirects, brand first in the title). SKILL.md 6.3 now reads step 1 at once after "Vahvista".

## Content

19. **Invented first-person claims.** A guide claimed every video the owner makes has at least one filmed shot, and that unlicensed music never goes into a video. Both contradicted the work itself: ads in the site's own gallery had no filmed shot, and the vault's notes describe a different music practice. They became advice without "I". Agents may write advice; claims about how the owner works need the owner.
20. **Promises in a translated page.** A translated page promised a service in that language that nobody had confirmed; the promise was narrowed to what is delivered. A "most popular" badge without data behind it was renamed.
21. **FAQ against the delivery notes.** An FAQ answer contradicted the owner's delivery notes and was aligned with them.
22. **Review incentives.** A guide says Google forbids rewarding reviews. A delivery note mentioned a client's prize draw, so it was checked: it was not tied to reviews.
23. **Privacy text must match the code.** A form route did more with personal data than the privacy notice said. The route was narrowed to what the notice describes, and the notice got its own item for that form.
24. **Cannibalisation inside one site.** A draft article aimed at a query a sibling article already owns; it was retargeted to a nearby query (heuristics row 12).
25. **Title length against the query.** The fixer chose a 64-character title for a question page to keep a query word; `verify_prod.sh` warns above 60. The 60 limit is a rule of thumb (Google cuts by pixel width); the user decides when a query word needs the room.
26. **Structured data without visible text.** A tool page's FAQPage had questions that were not on the page. Either show them or drop them from the schema.
40. **Page dates moved for a byline** (2026-11-22). An agent marked an article "päivitetty <date>" and moved `dateModified` and `lastmod` although only the byline changed; the reviewers flagged it against Google's guidance and the fixer put back the old date. When a second branch joined the release branch, the privacy page date in the site's per-page date file had to be updated by hand: git does not show that as a conflict.

## Media and forms

27. **A long webinar video.** A webinar video of about half an hour, 1440p and tens of megabytes, was re-encoded with ffmpeg to 720p H.264 with AAC mono and `+faststart`, which roughly halved it, and production answers a Range request with 206. A long keyframe interval can make seeking slow on a phone, and the file now sits in git history; the alternative (Vercel Blob) needs the user's OK.
28. **A missing API key in production.** `vercel env ls` (names only) showed no API key for the newsletter service. The route fell back to emailing the lead; the user added the key. Agents never add or read secret values.
29. **Logins belong to the user.** Unpublishing the old site-builder page needed the owner's login, so it waited. The replacement page was already live, so nothing broke in the meantime.
30. **Old share-image script.** A share-image script rendered images with only the light background after a layout change moved the logo into its own canvas. Look at every generated image with the Read tool before committing it.
41. **A replacement page needs its own lenses** (2026-11-22). In the replacement-page workflow the lenses identity, technical-security and privacy-language found four blockers: two kinds of numbering the old page did not show, a privacy notice that did not match the route, and the newsletter API key missing in Production. The template now has the lenses `identtisyys`, `turva` and `tietosuoja`, and an unknown lens name stops the run instead of silently becoming `tekninen`.
42. **Legal text goes out with the feature** (2026-11-22). The landing page's privacy notice items went live without the owner's OK, tagged with the site's `owner_info_tag`, because a form that collects personal data cannot be live without them; the owner got a reminder line. Reverting every commit that waits for an OK would have shipped the form without its notice.

## Release and notifications

31. **Fast-forward release.** `git fetch origin && git merge-base --is-ancestor origin/main <sha> && git push origin <sha>:main` released three sites safely; anything else stops for a merge in a worktree and a new check.
32. **IndexNow order.** The key files were in branches; the pings waited until all four `https://<host>/<key>.txt` answered 200 in production (a loop of curl checks every 10 s), then each POST returned 202.
33. **Search Console write actions after the release only.** Ten indexing requests and one sitemap submit, all after `verify_prod` passed; no request for the noindex landing page.
34. **Redirects with non-ASCII paths.** A path like `/meistä` needed both the `ä` and the `%C3%A4` form in `next.config.ts`. Lower-case `%c3%a4` could not be tested before the release because of the preview login; production answered 308 for the forms browsers send.
35. **Two-hop apex redirect.** `http://example.fi/` went to `https://example.fi/` and then to www. It comes from the Vercel domain settings, not the code, and is minor.
43. **Verdicts were from before the fix** (2026-11-22). The first template never reviewed the fixer's commits, so verdicts stayed "korjattavaa" after a fix and a blocker could sit in `not_fixed` as free text. The template now re-reviews the fixer's HEAD with every lens that had findings, asks the fixer to start leftover blockers with "ESTÄVÄ:", and returns `release_ok` with the reasons.
