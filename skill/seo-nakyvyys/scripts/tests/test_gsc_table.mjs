// Offline test for scripts/gsc_table.js: runs it against a tiny fake DOM shaped like a
// Search Console performance page (Finnish UI). The site, queries and numbers are invented.
// Usage: node scripts/tests/test_gsc_table.mjs
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const here = fileURLToPath(new URL('.', import.meta.url))
const src = readFileSync(here + '../gsc_table.js', 'utf8')

class El {
  constructor(tag, text = '', children = []) { this.tag = tag; this.text = text; this.children = children }
  get innerText() { return this.children.length ? this.children.map((c) => c.innerText).join('\n') : this.text }
  querySelectorAll(sel) {
    const tags = sel.split(',').map((s) => s.trim().toLowerCase())
    const out = []
    const walk = (n) => { for (const c of n.children) { if (tags.includes(c.tag)) out.push(c); walk(c) } }
    walk(this)
    return out
  }
}
const row = (cells) => new El('tr', '', cells.map((c) => new El('td', c)))
const card = (label, value) => new El('div', '', [new El('span', label), new El('span', value)])

function page(withHeader) {
  const head = new El('tr', '', ['Suosituimmat kyselyt', 'Klikkaukset', 'Näyttökerrat', 'Klikkausprosentti', 'Sijainti'].map((h) => new El('th', h)))
  const rows = [
    ['kampaamo helsinki', '12', '300', '4 %', '4,0'],
    ['hiusten värjäys hinta', '3', '1 250', '0,2 %', '8,5'],
    ['parturi kallio', '0', '95', '0 %', '14,6'],
    ['kampaamo ajanvaraus', '1', '40', '2,5 %', '22,1'],
  ].map(row)
  const table = new El('table', '', withHeader ? [head, ...rows] : rows)
  const body = new El('body', '', [
    card('Klikkauksia yhteensä', '450'),
    card('Näyttökertoja yhteensä', '9,80 t.'),
    card('Keskimääräinen klikkausprosentti', '4,6 %'),
    card('Keskimääräinen sijainti', '11,2'),
    table,
    new El('div', '1–10/40'),
  ])
  return { document: body, location: { href: 'https://search.google.com/search-console/performance/search-analytics?resource_id=sc-domain%3Aexample.fi&num_of_months=16' } }
}

let fails = 0
const check = (name, ok, got) => { if (ok) console.log('ok  ', name); else { fails++; console.log('FAIL', name, JSON.stringify(got)) } }

for (const withHeader of [true, false]) {
  const out = JSON.parse(vm.runInNewContext(src, page(withHeader)))
  const t = out.tables[0]
  const tag = withHeader ? '[header]' : '[no header]'
  check(`${tag} totals clicks 450`, out.totals.clicks && out.totals.clicks.value === 450, out.totals)
  check(`${tag} totals impressions 9,80 t. = 9800`, out.totals.impressions && out.totals.impressions.value === 9800, out.totals)
  check(`${tag} totals ctr 4.6`, out.totals.ctr && out.totals.ctr.value === 4.6, out.totals)
  check(`${tag} totals position 11.2`, out.totals.position && out.totals.position.value === 11.2, out.totals)
  check(`${tag} one table, 4 rows`, out.tables.length === 1 && t.row_count === 4, out.tables)
  check(`${tag} parsed row`, t.parsed && t.parsed[1].key === 'hiusten värjäys hinta' && t.parsed[1].impressions === 1250 && t.parsed[1].position === 8.5 && t.parsed[0].ctr === 4, t.parsed)
  check(`${tag} assumed_columns flag`, t.assumed_columns === !withHeader, t.assumed_columns)
  check(`${tag} pager read`, out.pager.includes('1–10/40'), out.pager)
}
console.log(fails ? `${fails} failed` : 'all passed')
process.exit(fails ? 1 : 0)
