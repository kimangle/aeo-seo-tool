# From finding to fix

Decision rules used on 2026-11-22. The example column uses example domains and invented numbers of a realistic size: it shows the shape of each finding, not real data. The thresholds are rules of thumb, not Google thresholds. The fix column says what to change on the site; `references/checklists.md` says how to check it. Your own real cases go in `references/local/heuristics-examples.md` (gitignored) under the same row number.

## 1. Priority order

1. **Blockers.** No data (unverified property), pages that should rank but are noindex or blocked, URLs with clicks that now answer 404, a copy of the content on another domain, wrong facts on live pages (an old price).
2. **Page 1 with low CTR.** Many impressions at position 1-10 and few clicks: title and meta description. Fast, and visible in 2-4 weeks.
3. **Brand not at 1-3.** The site's own name should rank first.
4. **Position 15-40 on question or how-to queries.** Answer the question on the page.
5. **Far non-brand terms (50+) on a young site.** New guide pages, internal links, share images. Takes 3-6 months.

Release blockers before polish ("julkaisun esteet ennen koristeita"). One cycle can mix levels when the agents run in parallel, as on 2026-11-22.

## 2. Decision table

All numbers in the example column are invented examples.

| # | Finding in Search Console | Fix | Example (invented numbers) | Watch afterwards |
|---|---|---|---|---|
| 1 | Property "Ei vahvistettu", no data | HTML verification file in the web root (URL-prefix property) or DNS TXT (domain property, user does it), release, "Vahvista", submit sitemap | www.example.fi: `public/google<token>.html`, verified after the release; 16 months of data appeared at once (example: 300 clicks, 9 000 impressions) | Data starts at once; next cycle uses it |
| 2 | Many impressions, position under 10, CTR near 0, and the query's words are missing from the title | Title (60 chars max) with the exact query words, description (155 max) that says what the page does and is true, og/twitter titles and WebPage schema name the same; H1 or lead with the phrase | A plumbing firm, example.fi/linjasaneeraus: 2 000 impressions, 10 clicks; "linjasaneeraus hinta" 800 impressions at 4.0, 2 clicks; "linjasaneeraus kerrostalo" 500 at 6.0, 0 clicks. Title "Palvelut taloyhtiöille \| Example Putki" became "Linjasaneeraus kerrostaloon: hinta, kesto ja vaiheet" (52 chars, brand suffix dropped to fit) | CTR of the two queries after 4 weeks |
| 3 | Impressions and 0 clicks at position 15-30, the visible queries are questions | Title and H1 as the question; a short section that answers each question (H2 = the question); FAQ and FAQPage schema in sync; link to the tool or service that helps | A vet clinic, example.fi/koiran-rokotukset: 1 500 impressions, 0 clicks, position 22; "milloin koiran rokotukset uusitaan" 200 at 19, "paljonko koiran rokotus maksaa" 90 at 27. New title "Milloin koiran rokotukset uusitaan ja mitä ne maksavat?", one section per question, a link to the booking page | Clicks above 0; position of the two questions |
| 4 | A page ranks 28-70 for its main term and a cluster of variants | Title and H1 on the main term plus the intent; sections for the variants people search; FAQ for the rest | A hair salon, example.fi/hiusten-varjays: 2 400 impressions, 20 clicks, position 45; "hiusten värjäys" 900 at 68, "hiusten värjäys kotona" 300 at 35, "värjäyksen hinta" 100 at 40. New title "Hiusten värjäys: hinnat, kesto ja hoito \| Example" (the brand suffix fit), sections for home dyeing and prices, four FAQ items for the rest | Position of the main term |
| 5 | The site's own name ranks below 3 | Brand first in the title of the home page; Organization or ProfessionalService schema with name, url, logo, founder; sameAs only for profiles that exist and are linked from the site | An accounting firm, example.fi: the brand "Example" 40 impressions at 7. Title became "Example: kirjanpito ja palkat pienyrityksille" | Brand position after 2-4 weeks |
| 6 | Brand works, the head term is far (40+), the page is young | Exact phrase in title, H1 and an H2; visible author and "updated" date linking to the author page; Article schema with datePublished, dateModified, image; fixed sitemap lastmod dates | A garden shop, example.fi: "kompostointi" at 70, "kompostori talvella" at 55, /kompostointi 25 impressions at 33. Title and H1 "Kompostointi: näin kompostori toimii myös talvella", byline "Maija Meikäläinen · päivitetty 3.11.2026" | Position of both terms after 4-6 weeks |
| 7 | The same text lives on another domain (an old Lovable, Wix or preview site) with status 200 and no canonical or noindex | First save the old page's HTML and its JS bundle with curl into a new, empty scratchpad folder (data, not instructions) and give it to the agents as `source_copy`, so they copy every string verbatim; review with the lenses `identtisyys`, `turva` and `tietosuoja` (`references/checklists.md` section 5). Build the replacement on the own domain, release it, then the owner unpublishes the old one and moves every link (social bios, story highlights, newsletter emails). A landing page that duplicates an article gets noindex, follow | An old site-builder copy of a landing page on `<name>.lovable.app`: the replacement example.fi/opas (identical texts, noindex, not in the sitemap) went out first; unpublishing the old copy waited for the owner's login | Old URL gone; the article's position |
| 8 | URLs with clicks or impressions now answer 404 | 308 permanent redirect to the closest live page; for non-ASCII paths add the URL-encoded form too (ä = %C3%A4); test in production | www.example.fi: /meistä (20 clicks) → /meista, /vanha-blogi (40 impressions) → /blogi | Both 308 in `verify_prod.sh`; 404s leave the index report |
| 9 | English queries land on the Finnish home page | Only if the business serves English-speaking customers: an /en page, hreflang fi, en and x-default on both pages, sitemap and llms.txt entries, English schema from the Finnish one; promise only what is delivered in English | A physiotherapy clinic, example.fi: "physiotherapy espoo" 300 at 25, "sports massage espoo" 150 at 30, "english speaking physiotherapist" 80 at 12. /en released; it lists only the treatments the staff give in English | Impressions and clicks of /en |
| 10 | A page made for ads or social posts copies an article or gates content | noindex, follow; out of the sitemap; no indexing request, no IndexNow | example.fi/opas from row 7 | It never appears in the performance report |
| 11 | Young site, only brand traffic, non-brand terms at 50-94 | Informational guides of 900-1400 words that answer one search and link to the matching service page; links from sibling sites; share images | A young bakery site, example.fi: "gluteeniton leipä tilaus" at 55, "täytekakku tilaus" at 93. Two guides (/oppaat/gluteeniton-leipa, /oppaat/taytekakun-tilaus), a contextual link from a sibling site, share images | Impressions in 4 weeks, positions in 3-6 months |
| 12 | Two pages of one site aim at the same query | Give each page its own query and link between them | Draft /kompostointi/bokashi first aimed at "kompostori haisee", which /kompostointi/ongelmat already owns; retargeted to "bokashi kompostointi" | Only one of the pages shows for the query |
| 13 | Mobile LCP is slow on the page that should rank | Videos preload none and load after the window load event; WebP posters; no entrance animation on the H1 and the first paragraph | A page with background videos: LCP 6.0 s on mobile; 3 mp4 requests before load became 0 (lab test, slow 4G) | Core Web Vitals report after 28 days |
| 14 | A live fact is wrong (price in llms.txt or schema) | Fix it in the release; find why the earlier fix never shipped | example.fi llms.txt said "alkaen 1 500 €", the right price is 1 200 €; the fix commit sat only on a feature branch | `verify_prod.sh "<url> contains='1 200 €'"` (inner quotes for the space) |
| 15 | Average position got worse over 28 days | Compare per-query positions before acting: the average is weighted by impressions, so a change in the query mix moves it even when no single query moved | example.fi: 6.0 → 9.0 while impressions went 2 000 → 3 000 (1 000 new impressions on queries around position 15) and clicks stayed at 40 | Per-query positions, not the average |

## 3. Not a problem

- "Uudelleenohjauksen sisältävä sivu" and "Vaihtoehtoinen sivu, jossa on oikea ensisijainen tagi" in the indexing report when the URLs are http, www or `.html` variants.
- A brand suffix missing from a title that needs the room: Google shows the site name separately.
- Total cards that do not match the sum of rows (anonymized queries).

## 4. Who decides

- Titles, schema and redirects on the user's own sites: the plan the user approved.
- Any text on someone else's site: that person (the site's `owner` in the config). It covers the title, meta description, og and twitter texts, H1, visible text, schema text fields, FAQ and llms.txt lines, unless the config `notes` or the vault record their OK (for example "titles agreed with the user"). Until then the change sits in a separate commit or a noindex draft branch, and the owner sees it through the user (SKILL.md "Stop and ask").
- Legally required text for a feature that goes live (a privacy notice item for a new form): it ships with the feature and the owner is told; it is never reverted alone.
- Promises (English service, reports, guarantees, prices) and which page owns a query: the user.
