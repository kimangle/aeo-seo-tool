# AEO/SEO-työkalun muutoshistoria: v3 → v4 → v5

*Päivitetty 13.7.2026 · Kaikki versiot repossa rinnakkain — vanhoja ei muokata, uusin on käytössä.*

## Yhdellä silmäyksellä

| | **v3** | **v4** | **v5** |
|---|---|---|---|
| **Julkaistu** | 13.7.2026 (`8a3cd38`) | 13.7.2026 (`2f10f14`) | 13.7.2026 (`93aa37e`) |
| **Teema** | Luotettavuus ja selkokielisyys | Ravintolat ja AEO-tiedostot | Klar-yhteensopivuus |
| **Tarkistuksia per sivu** | 15 | 16 (+ ravintolatarkistus) | 18 (+ funnel ja widget) |
| **Sivustotason tarkistuksia** | – | 3 (robots, sitemap, llms.txt) | 3 |
| **Auditoi verkosta** | 1 sivu | 1 sivu | jopa 10 sivua (ryömintä) |
| **Klar-vienti** | – | – | ✅ `--klar-json` |

## v3 — Luotettavuus ja selkokielisyys *(pohjaversio)*

Mitä työkalu teki v3:ssa:

- **15 tarkistusta per sivu**: otsikot, kuvaustekstit, canonical, kielimerkintä,
  otsikkorakenne, kuvien alt-tekstit, some-jakotiedot (Open Graph, Twitter),
  koneluettava sisältökuvaus (JSON-LD), AEO-sisältösignaalit, luotettavuus,
  sisällön laatu, sisäiset linkit.
- **AI-korjaukset** (`--fix`): Claude Haiku kirjoittaa puuttuvat kuvaustekstit ja
  JSON-LD:n suoraan HTML-tiedostoihin, varmuuskopiot talteen (.bak).
- **Virheenkäsittely**: API-virheet eivät kaada ajoa; kolme peräkkäistä virhettä
  sammuttaa AI:n loppuajoksi.
- **Kustannuslogitus euroina**: jokaisen ajon lopussa näet AI-kulut (esim. "alle 0,01 €").
- **Selkokielinen asiakasraportti**: HTML-raportti, jossa tekniset termit on
  suomennettu arkikielelle.

## v4 — Ravintolat ja AEO-tiedostot

*Tausta: klar-consolen tutkiminen paljasti, että Klarin asiakkaat ovat ravintoloita
ja niiden sivuilta puuttuu juuri se rakennedata, jota Google ja AI-avustajat tarvitsevat.*

**Uutta:**

1. **Ravintolan automaattinen tunnistus** — työkalu päättelee sisällöstä
   (ruokalista, pöytävaraus, lounas...) että kyseessä on ravintola.
2. **Restaurant-rakennedata** — tarkistaa ja lisää koneluettavat ravintolatiedot:
   aukioloajat, osoite, puhelin, keittiötyyppi, ruokalistalinkki, varausmahdollisuus.
   Näiden avulla Google ja AI-avustajat (ChatGPT, Claude, Perplexity) osaavat kertoa
   ravintolasta oikeat tiedot.
3. **AI täydentää puuttuvat tiedot** sivun tekstistä — tai voit antaa ne itse
   uusilla lipuilla: `--restaurant --phone --address --hours --cuisine --menu-url`.
4. **Sivustotason tiedostot** — uusi tarkistusryhmä:
   - `robots.txt` — estääkö vahingossa koko sivuston hakukoneilta?
   - `sitemap.xml` — sivukartta, jotta Google löytää kaikki sivut
   - `llms.txt` — uusi AEO-tiedosto, joka kertoo AI-avustajille mitä sivustolla on
   - `--fix` luo puuttuvat tiedostot valmiiksi.

**Testattu:** Klarin ravintolasivupohjalla (pisteet nousivat, kaikki tiedostot
syntyivät), tuplakorjausajolla (ei tuplia) ja livenä Ravintola Anin sivustolla.

## v5 — Klar-yhteensopivuus

*Tausta: klar-consolen syvempi luenta paljasti valmiin määrittelyn (WS-F), jossa
kerrotaan täsmälleen missä muodossa Klarin konsoli odottaa SEO-tulokset. Kim
keskustelee Edvinin kanssa työkalun roolista Klarissa.*

**Uutta:**

1. **Klar-vienti** (`--klar-json`) — tuottaa raporttien rinnalle Klarin
   määrittelyn mukaisen SeoResult-JSONin:
   - pisteet ulottuvuuksittain: onPage / aeo / funnel (0–100)
   - löydökset vakavuusluokittain (warn / critical) korjausehdotuksineen
   - englanninkieliset tunnisteet (esim. `restaurant-schema`, `meta-description`)
   - suoraan siinä muodossa, jonka Klarin `seo_runs`-tietokantataulu ottaa vastaan.
2. **Funnel-tarkistus** (kaikille sivustoille) — löytyykö kävijälle selkeä
   seuraava askel: toimintakehote, soittolinkki ja yhteydenottotapa.
3. **Varauswidget-tarkistus** (ravintoloille) — onko Klarin varauswidget kytketty
   oikein (`widget.js` + kelvollinen ravintolatunniste). Tunnistaa myös
   esikatselupohjien **demolomakkeen, joka näyttää varaukselta mutta ei oikeasti
   varaa mitään** — ja varoittaa siitä ennen julkaisua.
4. **Monisivuinen ryömintä** (`--max-pages`, oletus 10) — URL-tilassa työkalu
   seuraa sivuston omia linkkejä ja auditoi useita sivuja yhdellä komennolla,
   kohteliaasti 0,5 sekunnin välein.

**Testattu:** Klar-JSONin rakenne validoitu kenttä kentältä; widget-tarkistuksen
kolme tapausta (oikea widget / viallinen tunniste / demolomake); ryömintä livenä
Roba Delillä; vanhat tarkistukset täsmälleen samat kuin v4:ssä.

## Tärkeät periaatteet (kaikki versiot)

- **Idempotenssi**: `--fix` uudelleen ajettuna ei koskaan duplikoi mitään
  (työkalun lisäämä data merkitään `data-aeo-tool`-attribuutilla).
- **Varmuuskopiot**: korjaukset ottavat aina .bak-kopion ennen kirjoitusta.
- **Toimii ilman AI:takin**: ilman API-avainta työkalu on pelkkä auditoija.
- **Kulut näkyvissä**: jokainen ajo kertoo AI-kulut euroina.
- **Klar-vienti on puhdasta analyysia**: AI-sisällöntuotanto (--fix) pysyy
  erillään, kuten Klarin säännöt vaativat.

## Mitä seuraavaksi (todettu, ei vielä tehty)

- **Julkaisukunto-tarkistukset**: live-sivu noindex-tilassa (piilossa Googlelta!),
  .vercel.app vs. oma domain, AI-bottien pääsy robots.txt:ssä (GPTBot, ClaudeBot,
  PerplexityBot).
- **Suorituskykytarkistukset**: sivun paino, latausta hidastavat skriptit.
- **Klar-integraation viimeistely** Edvin-keskustelun jälkeen: ohut TypeScript-kerros,
  joka tallentaa työkalun JSONin konsolin tietokantaan.
