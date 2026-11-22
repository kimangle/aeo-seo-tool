// gsc_table.js - read a Google Search Console report page in the browser.
//
// Run it with the Claude in Chrome javascript_tool (action "javascript_exec") on a
// Search Console page that is already loaded: Performance (queries, pages, a page
// filter, a date comparison) or the indexing report. Paste the whole file as the
// script text; it is one expression and returns a JSON string.
//
// Why: get_page_text only shows the rows of the current table page ("1-10/40"),
// while the DOM holds every row. This reads all <tr>/<td> cells, the total cards
// and, when the columns are the four standard metrics, parsed numbers.
//
// Output: {url, read_at, totals:{clicks, impressions, ctr, position}, tables:[{header,
// row_count, rows, parsed}], note}. Numbers in Finnish format ("9,80 t.", "4,6 %")
// and English format ("9.80K", "4.6%") are parsed; the raw text stays in rows.
// If a table's row_count equals the page size and the footer shows more ("1-500/812"),
// set "Rows per page" to 500, page forward and run it again.

(() => {
  const clean = (s) => (s || '').replace(/ | /g, ' ').replace(/\s+/g, ' ').trim();

  const num = (raw) => {
    let s = clean(raw).toLowerCase();
    if (!s || s === '-' || s === '–' || s === '—') return null;
    let mult = 1;
    if (/\s?(t\.|k)$/.test(s)) { mult = 1e3; s = s.replace(/\s?(t\.|k)$/, ''); }
    else if (/\s?(milj\.|m)$/.test(s)) { mult = 1e6; s = s.replace(/\s?(milj\.|m)$/, ''); }
    s = s.replace('%', '').trim();
    // Finnish: space as thousands separator, comma as decimal. English: comma thousands, dot decimal.
    if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, '');
    else s = s.replace(/\s/g, '').replace(',', '.');
    const v = Number(s);
    return Number.isFinite(v) ? Math.round(v * mult * 1000) / 1000 : null;
  };

  const TOTALS = {
    clicks: /^(Klikkauksia yhteensä|Total clicks)\s+(.+)$/i,
    impressions: /^(Näyttökertoja yhteensä|Total impressions)\s+(.+)$/i,
    ctr: /^(Keskimääräinen klikkausprosentti|Average CTR)\s+(.+)$/i,
    position: /^(Keskimääräinen sijainti|Average position)\s+(.+)$/i,
  };
  const totals = {};
  for (const el of document.querySelectorAll('div, span')) {
    const t = clean(el.innerText);
    if (!t || t.length > 60) continue;
    for (const [k, re] of Object.entries(TOTALS)) {
      if (totals[k]) continue;
      const m = t.match(re);
      if (m && /\d/.test(m[2])) totals[k] = { text: m[2], value: num(m[2]) };
    }
  }

  const METRIC = [
    ['clicks', /^(klikkaukset|clicks)$/i],
    ['impressions', /^(näyttökerrat|impressions)$/i],
    ['ctr', /^(klikkausprosentti|ctr)$/i],
    ['position', /^(sijainti|position)$/i],
  ];

  const parse = (header, rows) => {
    let cols = null;
    if (header.length >= 2) {
      const names = header.slice(1).map((h) => {
        const hit = METRIC.find(([, re]) => re.test(h));
        return hit ? hit[0] : null;
      });
      if (names.every(Boolean)) cols = ['key', ...names];
    }
    let assumed = false;
    if (!cols && rows.length && rows.every((r) => r.length === 5)) {
      cols = ['key', 'clicks', 'impressions', 'ctr', 'position'];
      assumed = true;
    }
    if (!cols) return { parsed: null, assumed };
    const parsed = rows
      .filter((r) => r.length === cols.length)
      .map((r) => Object.fromEntries(cols.map((c, i) => [c, i === 0 ? r[i] : num(r[i])])));
    return { parsed, assumed };
  };

  const readRows = (root) =>
    [...root.querySelectorAll('tr')]
      .map((tr) => [...tr.querySelectorAll('td')].map((td) => clean(td.innerText)))
      .filter((r) => r.length && r.some(Boolean));

  let tables = [...document.querySelectorAll('table')].map((t) => {
    const header = [...t.querySelectorAll('th')].map((th) => clean(th.innerText)).filter(Boolean);
    const rows = readRows(t);
    const { parsed, assumed } = parse(header, rows);
    return { header, row_count: rows.length, rows, parsed, assumed_columns: assumed };
  }).filter((t) => t.row_count);

  if (!tables.length) {
    const rows = readRows(document);
    const { parsed, assumed } = parse([], rows);
    if (rows.length) tables = [{ header: [], row_count: rows.length, rows, parsed, assumed_columns: assumed }];
  }

  const footer = [...document.querySelectorAll('div, span')]
    .map((el) => clean(el.innerText))
    .filter((t) => /^\d+\s*[–-]\s*\d+\s*\/\s*\d+$/.test(t));

  return JSON.stringify({
    url: location.href,
    read_at: new Date().toISOString(),
    totals,
    tables,
    pager: [...new Set(footer)],
    note: 'Totals can be rounded on the cards ("9,80 t."); rows are exact but leave out anonymized queries, so rows do not add up to the totals.',
  });
})()
