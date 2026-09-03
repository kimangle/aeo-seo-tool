# AEO/SEO-työkalun muutoshistoria: v3 → v4 → v5 → v6 → v7

*Päivitetty 23.7.2026 · Kaikki versiot repossa rinnakkain — vanhoja ei muokata, uusin on käytössä.*

## Yhdellä silmäyksellä

| | **v3** | **v4** | **v5** | **v6** | **v7** |
|---|---|---|---|---|---|
| **Julkaistu** | 13.7.2026 (`8a3cd38`) | 13.7.2026 (`2f10f14`) | 13.7.2026 (`93aa37e`) | 23.7.2026 (`30513d1`) | 23.7.2026 |
| **Teema** | Luotettavuus ja selkokielisyys | Ravintolat ja AEO-tiedostot | Klar-yhteensopivuus | Korjauspaketti ja julkaisukunto | Kuukausiraportointi |
| **Tarkistuksia per sivu** | 15 | 16 (+ ravintolatarkistus) | 18 (+ funnel ja widget) | 18 | 18 |
| **Sivustotason tarkistuksia** | – | 3 (robots, sitemap, llms.txt) | 3 | 5 (+ domain ja AI-botit) | 5 |
| **Auditoi verkosta** | 1 sivu | 1 sivu | jopa 10 sivua (ryömintä) | jopa 10 sivua | jopa 10 sivua |
| **Klar-vienti** | – | – | ✅ `--klar-json` | ✅ | ✅ |
| **Korjauspaketti asiakkaalle** | – | – | – | ✅ `--fix-guide` | ✅ |
| **Kehitysvertailu** | – | – | – | – | ✅ `--compare` |

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

## v6 — Korjauspaketti ja julkaisukunto

*Tausta: v5:n analyysi osoitti kolme aukkoa: URL-tilan korjaukset jäivät irrallisiksi
tiedostoiksi ilman ohjeita, title (10 p) oli suurin tarkistus ilman fixeriä, ja
noindex hukkui taulukkoriviksi. Lisäksi v5:n "mitä seuraavaksi" -listalta toteutettiin
julkaisukunto-tarkistukset.*

**Uutta:**

1. **Asiakaskohtainen korjauspaketti** (`--fix-guide`, URL-tila) — korjaukset kootaan
   luovutettavaksi paketiksi `reports/korjauspaketti_*/`: korjatut sivukopiot
   (`korjatut-sivut/`), sivustotiedostot ja **OHJEET.html**. Ohjeessa jokaiselle
   korjaukselle on copy-paste-snippet (Kopioi-nappi) ja alustakohtainen askel:
   alusta tunnistetaan HTML:stä (wp-content → WordPress, wixstatic → Wix,
   squarespace-cdn → Squarespace, muuten yleisohje). OHJEET.html on asiakkaalle
   luovutettava dokumentti omalla vaalealla Anglés-tyylillä (ei raportin dark-teemaa).
2. **Title-fixeri** — AI kirjoittaa puuttuvan tai parantaa liian lyhyen/pitkän titlen
   samalla logiikalla kuin meta descriptionin. Validointi samoihin rajoihin (30–60 mk)
   kuin tarkistus, jotta korjaus ei jää warn-tilaan ja toistu.
3. **Noindex-eskalaatio** — noindex-sivut ja koko sivuston estävä robots.txt nostetaan
   omana kriittisenä hälytyksenä raportin kärkeen: punainen banneri HTML-raportissa,
   oma osio markdownissa, `critical_alerts`-kenttä JSONissa ja punainen paneeli
   terminaalissa. Taulukkorivit ennallaan — eskalaatio on puhdas lisäys.
4. **Julkaisukunto-tarkistukset** (sivustotason pseudosivuun): onko sivusto
   esikatseludomainilla (.vercel.app, .netlify.app, .pages.dev, .github.io) ja
   pääsevätkö AI-botit (GPTBot, ClaudeBot, PerplexityBot) sivustolle robots.txt:n
   mukaan. Vain varoituksia — bottien esto voi olla tietoinen valinta, `--fix` ei
   koske siihen. Klar-viennissä uudet kindit `preview-domain` (onPage) ja
   `ai-bot-access` (aeo).

**Testattu:** vanhojen tarkistusten regressio v5:tä vasten (identtiset tulokset ja
Klar-JSON fixture-sivustolla); title-fixerin idempotenssi tupla-ajolla; korjauspaketin
snippettien vastaavuus korjattuihin kopioihin sivu sivulta; alustatunnistuksen neljä
tapausta; AI-bot-jäsentimen 9 syötetapausta ja domain-tarkistuksen 4 tapausta.

## v7 — Kuukausiraportointi

*Tausta: Kim myy kuukausipaketteja, joissa asiakkaalle raportoidaan SEO/AEO-tilanteen
kehitys kuukausittain. Työkalu tuotti jo täydet audit-JSONit, mutta ei osannut
verrata kahta eri ajankohtina ajettua audittia.*

**Uutta:**

1. **Ennen/jälkeen-vertailu** (`--compare vanha_audit.json`) — ajaa normaalin
   auditin (repo- tai URL-tila, yhdistettävissä --fix/--fix-guiden kanssa) ja
   vertaa tulosta aiempaan audit-JSONiin. Muutosluokat statussiirtymistä:
   parannus (fail/warn → pass, fail → warn), huononnus (warn → fail) ja uusi
   puute (pass → warn/fail).
2. **Kehitysraportti asiakkaalle** — `reports/vertailu_*/`-kansioon VERTAILU.html
   (vaalea Anglés-tyyli; iso ennen→jälkeen-pistenäkymä päiväyksineen kärjessä,
   parannukset selkokielellä, "korjataan seuraavaksi" -lista rakentavaan sävyyn),
   VERTAILU.md sähköpostiin ja vertailu.json (score_delta, improved, regressed,
   new_issues). AI kirjoittaa 2–3 lauseen kehityskuvauksen, jos avain on käytössä.
3. **Versioturvallinen vertailu** — vanha JSON voi olla v5:n tai v6:n tuottama:
   tarkistukset, jotka puuttuvat vanhasta ajosta, raportoidaan "uusi tarkistus"
   -tilassa eivätkä koskaan näy parannuksina tai huononnuksina. Lisäksi lasketaan
   vertailukelpoinen delta pelkistä yhteisistä tarkistuksista. Kadonneet ja uudet
   sivut listataan erikseen — vertailu ei kaadu sivumuutoksiin.

**Testattu:** vanhojen tarkistusten regressio v6:ta vasten (identtiset tulokset
fixturella, myös OHJEET.html tyylirefaktoroinnin jälkeen); vertailulogiikan 8
yksikkötestiä; päästä päähän -ajo (audit → käsinkorjaus → vertailu näytti täsmälleen
tehdyt parannukset, +8 p); v5-JSON vertailusyötteenä (julkaisukunto "uusi tarkistus"
-tilassa, 0 väärää parannusta, vertailukelpoinen delta 0); sivun poisto/lisäys.

## v7.1 — Liiketyypin tunnistus ja sitemap-ryömintä

*Julkaistu 3.9.2026. Tausta: klarsystems.com sai 76,2 pistettä, mutta 44 pistettä
488:sta oli mahdotonta ansaita rehellisesti — työkalu luuli B2B-ohjelmistoyritystä
ravintolaksi, koska sen markkinointiteksti puhuu ruokalistoista ja pöytävarauksista.
Myydyn tuotteen pitää pisteyttää se, mitä sivusto oikeasti on.*

**1. Liiketyyppi luetaan JSON-LD:stä, ei avainsanoista**

Jos sivuston JSON-LD ilmoittaa muun liiketyypin kuin ruokapaikan
(`ProfessionalService`, `LegalService`, `Dentist`, `HairSalon`, `Hotel`,
`SoftwareApplication`, `Corporation`, … yhteensä 24 tyyppiä), avainsanapohjaista
ravintolapäättelyä ei enää ajeta. Aiemmin kolme osumaa sanoihin *menu, restaurant,
reservation, book a table, takeaway, kitchen* riitti tekemään mistä tahansa sivusta
ravintolan.

Listalla **ei** ole paljaita `Organization`-, `LocalBusiness`- eikä `Store`-tyyppejä:
ne ovat epämääräisiä ja oikeat ravintolat käyttävät niitä usein Restaurant-tyypin
sijasta. Jos ne olisivat listalla, aidot ravintolat menettäisivät juuri ne
tarkistukset, joita niille myydään. `--restaurant`-lippu ja käsin annetut
ravintolatiedot (`--cuisine`, `--menu-url`) voittavat edelleen kaiken.

**2. Ravintolatarkistukset vain ravintoloille — ja vain oikeille sivuille**

"Ravintolan tiedot (schema)" ja "Varauswidget" eivät enää lisää maksimipisteitä
sivustolle, joka ei ole ravintola. Lisäksi varauswidget tarkistetaan vain sivuilla,
joilla on varausintentio (teksti "varaa pöytä" / "book a table", varausskripti tai
varaus-CTA) — tietosuojaseloste ei voi sisältää varausjärjestelmää, joten siitä ei
enää rangaista.

**3. `ProfessionalService` on validi yritysmerkintä**

JSON-LD-tarkistus tunsi vain `Organization`, `LocalBusiness`, `Corporation` ja
`Store` -tyypit, joten schema.orgin LocalBusiness-alityypit (kuten
`ProfessionalService`) menettivät 3 pistettä joka sivulta. Samalla korjattiin
listamuotoiset `@type`-arvot: `["Restaurant","LocalBusiness"]` muuttui aiemmin
merkkijonoksi `"['Restaurant', 'LocalBusiness']"` eikä osunut mihinkään — tämä vei
ravintolalta sekä yrityspisteet että koko Restaurant-skeematarkistuksen.

**4. Puhelinnumeron puute ei ole enää automaattinen virhe B2B-sivustolla**

Ravintolaan soitetaan, joten ravintolatilassa `tel:`-linkki pysyy vaatimuksena.
Muulla sivustolla samat pisteet ansaitaan myös ajanvarauslinkillä (Calendly, Cal.com,
HubSpot Meetings, Zcal, SavvyCal) tai yhteydenottolomakkeella, ja luottamuspisteen
saa puhelimen sijasta postiosoitteella (`<address>` tai JSON-LD:n `PostalAddress`).
Julkaisematon puhelinnumero on liiketoimintapäätös, ei SEO-virhe. **Maksimipisteet
eivät muutu kummallakaan sivustotyypillä** — vain se muuttuu, mikä ansaitsee pisteen.

**5. Ryömintä lukee myös sivukartan**

Ryömin keräsi linkit vain HTML:stä, joten sitemap.xml:ssä oleva mutta linkittämätön
sivu jäi auditin ulkopuolelle, vaikka Google indeksoi sen. Nyt `sitemap.xml` haetaan
ja saman hostin osoitteet lisätään jonoon HTML-linkkien **jälkeen**, `--max-pages`-rajan
sisällä ja ilman duplikaatteja. Puuttuva tai rikkinäinen sivukartta ei kaada ajoa.

**Mitattu (3.9.2026):**

| Sivusto | v7.0 | v7.1 | Muutos |
|---|---|---|---|
| klarsystems.com (paikallinen esikatselu, 4 sivua) | 372/488 = 76,2 % | 386/440 = 87,7 % | tunnistus `generic`, ravintolatarkistukset pois, JSON-LD 8/18 → 11/18 alasivuilla |
| ani.fi (oikea ravintola, 3 sivua) | 224/370 = 60,5 % | 224/370 = 60,5 % | ei muutosta — ravintolatila ja Restaurant-tarkistus säilyivät |
| boom16.vercel.app (oikea ravintola) | 76/134 = 56,7 % | 76/134 = 56,7 % | ei muutosta |
| anglesmarketing.fi | 323/334 = 96,7 % | 323/334 = 96,7 % | ei muutosta |

Sivukartta-ryömintä testattiin erillisellä fixturella: etusivu ilman sisäisiä
linkkejä + sitemap, jossa orpo sivu ja vieraan domainin osoite → orpo sivu tuli
mukaan, vieras domain ei. `--compare` v7.0-JSONia vastaan toimii: poistuneet
tarkistukset raportoidaan `removed_checks`-listassa eivätkä ne näy huononnuksina.

## Tärkeät periaatteet (kaikki versiot)

- **Idempotenssi**: `--fix` uudelleen ajettuna ei koskaan duplikoi mitään
  (työkalun lisäämä data merkitään `data-aeo-tool`-attribuutilla).
- **Varmuuskopiot**: korjaukset ottavat aina .bak-kopion ennen kirjoitusta.
- **Toimii ilman AI:takin**: ilman API-avainta työkalu on pelkkä auditoija.
- **Kulut näkyvissä**: jokainen ajo kertoo AI-kulut euroina.
- **Klar-vienti on puhdasta analyysia**: AI-sisällöntuotanto (--fix) pysyy
  erillään, kuten Klarin säännöt vaativat.

## Mitä seuraavaksi (todettu, ei vielä tehty)

- **Suorituskykytarkistukset**: sivun paino, latausta hidastavat skriptit.
- **Klar-integraation viimeistely** Edvin-keskustelun jälkeen: ohut TypeScript-kerros,
  joka tallentaa työkalun JSONin konsolin tietokantaan.
