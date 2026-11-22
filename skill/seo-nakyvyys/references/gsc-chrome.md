# Search Console in Chrome

How to read and act in Google Search Console through the Claude in Chrome extension, as done on 2026-11-22. The UI was in Finnish; English labels are given where known. Labels and URLs can change: when a step fails, take a screenshot and read the page before guessing.

Contents: 1 Connect · 2 URL patterns · 3 Reading tables · 4 Indexing report · 5 URL inspection and indexing requests · 6 Sitemaps · 7 Verifying a property · 8 Limits

## 1. Connect

1. Load the tools in one ToolSearch call:
   `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__find,mcp__claude-in-chrome__browser_batch`
2. If no `claude-in-chrome` tool is found, the session is not connected. Tell the user to type `/chrome` in the chat and press Enter. It is a Claude Code command that only the user can run. On 2026-11-22 a typo (`/crome`) went through as plain text. If `/chrome` does not help: Chrome open, the Claude extension switched on (puzzle icon), then a new Claude Code session.
3. `tabs_context_mcp`, then `tabs_create_mcp` for your own tab. Do not navigate the user's open tabs.
4. Check the signed-in account: the page header names it (for example "Google-tili: <name> (...)"). On a sign-in page or the wrong account, stop and let the user sign in. Never type a password or accept terms for them.
5. Batch: one `browser_batch` with navigate, `computer` wait 3-4 s, and `get_page_text` or `javascript_tool` saves round trips.
6. The extension asks for permission per domain. `search.google.com` worked. A Vercel preview domain can be refused with "Navigation to this domain is not allowed" (one project's `<project>-*.vercel.app` previews on 2026-11-22, while two other projects' previews opened). Do not retry in a loop: ask the user to allow the domain, or rely on local checks and verify in production after the release.

## 2. URL patterns

Base `https://search.google.com/search-console`. `R` is the URL-encoded property:
- domain property: `sc-domain%3Aexample.fi`
- URL-prefix property: `https%3A%2F%2Fwww.example.fi%2F` (keep the trailing slash)

| Report | Path and query |
|---|---|
| All properties with their verification state | the base URL without `resource_id`, then open the property switcher (SKILL.md 1.1) |
| Overview, property switcher | `?resource_id=R` |
| Performance, last 3 months, all four metrics | `/performance/search-analytics?resource_id=R&num_of_months=3&metrics=CLICKS%2CIMPRESSIONS%2CCTR%2CPOSITION` |
| Performance, full history | same with `num_of_months=16` (16 is the maximum; a newer property starts later, for example a property added in June shows data from June on) |
| Last 28 days against the 28 before | `/performance/search-analytics?resource_id=R&num_of_days=28&metrics=CLICKS%2CIMPRESSIONS%2CCTR%2CPOSITION&compare_date=PREV` |
| Pages instead of queries | add `&breakdown=page` |
| Queries of one page | add `&page=!` + the URL-encoded full page URL, for example `&page=!https%3A%2F%2Fexample.fi%2Fhinnasto` |
| Indexing report | `/index?resource_id=R` |
| One indexing reason | click its row; the URL becomes `/index/drilldown?resource_id=R&item_key=...` |
| Sitemaps | `/sitemaps?resource_id=R` |
| URL inspection | the search box at the top of any property page (section 5) |

`metrics=` turns on CTR and position, which are off by default. `page=!` was the only page filter used on 2026-11-22 and it returned that page's queries; other filter prefixes are untested, so read the filter chip on the page to confirm what was applied. The direct URL `/inspect?resource_id=R&id=<url>` returned Google's 404 page on 2026-11-22: do not use it.

Data lag: on the evening of 2026-11-22 the data ran to 2026-11-20. Write the date range the page shows next to every number.

## 3. Reading tables

- `get_page_text` gives the four total cards and only the visible table page ("1–10/40" means 10 of 40 rows).
- Run `scripts/gsc_table.js` with `javascript_tool` (action `javascript_exec`, the file content as the script). It returns JSON with the totals, every row of every table (the DOM holds the rows hidden by paging) and parsed numbers when the columns are the four standard metrics. If the pager shows more rows than were read ("1–500/812"), set "Riviä sivua kohti" (rows per page) to 500 and page forward.
- Total cards are rounded (for example "Näyttökertoja yhteensä 9,80 t." = about 9 800). Rows are exact.
- Rows leave out anonymized queries, so query rows do not add up to the totals.
- In the comparison view each metric has two columns, `parsed` is null, and the raw rows are in order current, previous. A screenshot of the cards is the quickest way to read the totals.
- Read per-page queries (`page=!`) for every page with about 30 or more impressions, and for pages with impressions and no clicks. That is where the title and content fixes come from.

Record per site: date range, clicks, impressions, CTR, average position, pages in the index and not in it with reasons. `templates/audit-note.md` has the table.

## 4. Indexing report

The page shows "Lisätty hakemistoon" (indexed) and "Ei lisätty hakemistoon" (not indexed) with reasons. Click a reason to see its URLs. Seen on 2026-11-22 and harmless:

- "Uudelleenohjauksen sisältävä sivu" (Page with redirect): http, www or `.html` variants that redirect. One site had over a dozen.
- "Vaihtoehtoinen sivu, jossa on oikea ensisijainen tagi" (Alternate page with proper canonical tag): another site had a few.
- "Estetty toisen 4xx-ongelman vuoksi" (Blocked due to other 4xx issue) for an old variant such as `http://www.example.fi/`, last crawled months earlier.

Investigate when the URL list holds a page that should rank: a not-found reason for a live URL, a robots.txt block, a noindex exclusion, or "Havaittu, toistaiseksi ei indeksoitu" (Discovered, currently not indexed) for a page with content. Check the page with `scripts/verify_prod.sh` first.

## 5. URL inspection and indexing requests

Per URL, about 40 s:

1. Open the property: `?resource_id=R`.
2. Click the search box at the top ("Tarkasta mikä tahansa URL-osoite"; `find` "URL inspection search box"), type the full URL, press Enter.
3. Wait about 10 s for the result ("URL on Googlessa" or "URL ei ole Googlessa").
4. `find` the visible "Pyydä indeksointia" (Request indexing) button and click it. Google runs a live test, then shows a confirmation dialog. Close it (click its button or Escape).
5. Next URL: click the search box, `cmd+a`, type, Enter.

Request indexing only for URLs that answer 200, are indexable, point their canonical to themselves and changed in this release. Never for a noindex landing page, a draft, a redirect or a URL on another property. Google does not publish a fixed daily limit. On 2026-11-22, 10 requests across 4 properties went through without a quota message. If the dialog reports the quota is used up, stop and continue the next day; sitemaps and IndexNow are separate.

## 6. Sitemaps

`/sitemaps?resource_id=R`: the field "Anna sivustokartan URL-osoite", then "LÄHETÄ" (Submit). A domain property needs the full URL (`https://example.fi/sitemap.xml`); a URL-prefix property shows the prefix and takes the rest (`sitemap.xml`). The table shows the status ("Onnistui" = success), last read date and discovered pages. Resubmit after a release that adds pages, and right after a property is verified.

## 7. Verifying a property

A property marked "Ei vahvistettu" (not verified) shows no data. On its page, "Vahvista omistajuus" (Verify ownership) offers methods.

- HTML file (URL-prefix property): Google names a file `google<16 hex characters>.html` whose content is `google-site-verification: google<16 hex characters>.html`. The name belongs to the Google account: a second site of the same account got the same file the first site already served, so it was copied byte for byte. Put it in the site's `web_root`, release, check it answers 200 with `scripts/verify_prod.sh "<url> contains=google-site-verification"`, then click "Vahvista".
- Domain property: a DNS TXT record at the registrar. The user adds it; the skill never logs in to a registrar.

Once verified, the full 16 months of data appear at once. Submit the sitemap next, then read SKILL.md step 1 for the property right away: on 2026-11-22 its data gave a second round of fixes the same evening. A missing property, a client's account and a site without data: `references/new-site.md` section 3 and 4.

## 8. Limits

- Read reports freely. Write actions (indexing requests, sitemap submits, verification, "Vahvista korjaus" / Validate fix) happen only after the release they belong to and inside the user's permission for it.
- Never use Removals, user and owner management, settings, or the disavow tool.
- Never sign in, never change the Google account, never accept terms.
