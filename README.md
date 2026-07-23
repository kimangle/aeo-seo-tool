# AEO/SEO Audit Tool

Auditoi ja korjaa verkkosivuston SEO:n (hakukonenäkyvyys) ja AEO:n
(näkyvyys tekoälyhauissa kuten ChatGPT ja Perplexity). Uusin versio on
`aeo_seo_tool_v6.py` — v1–v5 ovat mukana vertailun vuoksi.

## Asennus

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # tarvitaan vain AI-korjauksiin (--fix)
```

## Käyttö

```bash
# Auditoi paikallinen sivusto (HTML-tiedostot hakemistossa)
python3 aeo_seo_tool_v6.py --repo ./sivusto

# Auditoi ja korjaa automaattisesti (AI kirjoittaa mm. titlet ja meta descriptionit)
python3 aeo_seo_tool_v6.py --repo ./sivusto --fix

# Auditoi julkinen URL
python3 aeo_seo_tool_v6.py --url https://example.com

# Auditoi julkinen URL ja kokoa asiakkaalle korjauspaketti ohjeineen
python3 aeo_seo_tool_v6.py --url https://example.com --fix-guide

# Hyödyllisiä lippuja
#   --no-open              älä avaa HTML-raporttia selaimeen
#   --site-name "Yritys"   sivuston nimi, jos auto-tunnistus ei onnistu
#   --site-url https://... sivuston osoite
#   --eur-rate 0.90        USD→EUR-kurssi kustannuslaskentaan
```

## Uutta v6:ssa

**Asiakaskohtainen korjauspaketti** (`--fix-guide`, URL-tila). Korjaukset kootaan
yhdeksi luovutettavaksi paketiksi `reports/korjauspaketti_*/`: korjatut sivukopiot,
sivustotiedostot ja **OHJEET.html** — selkeä ohje, jossa jokaiselle korjaukselle on
copy-paste-snippet ja alustakohtainen "mihin tämä liitetään" -askel. Alusta
tunnistetaan HTML:stä automaattisesti (WordPress / Wix / Squarespace / yleinen).

**Title-fixeri.** AI kirjoittaa puuttuvan tai parantaa liian lyhyen/pitkän titlen
(30–60 mk) samalla logiikalla kuin meta descriptionin.

**Noindex-hälytys raportin kärkeen.** Jos sivu on noindex-tilassa (piilossa
Googlelta) tai robots.txt estää koko sivuston, asia nostetaan omana kriittisenä
bannerina HTML-raportin, markdownin, JSONin ja terminaalin kärkeen.

**Julkaisukunto-tarkistukset.** Onko sivusto esikatseludomainilla (.vercel.app,
.netlify.app, .pages.dev, .github.io) ja pääsevätkö AI-botit (GPTBot, ClaudeBot,
PerplexityBot) sivustolle robots.txt:n mukaan. Vain varoituksia — bottien esto voi
olla tietoinen valinta, joten `--fix` ei koske siihen.

## Uutta v5:ssä

**Klar-yhteensopiva vienti** (`--klar-json`). Tuottaa raporttien rinnalle
klar-consolen WS-F-määrittelyn mukaisen SeoResult-JSONin: pisteet ulottuvuuksittain
(onPage / aeo / funnel, 0–100) ja löydökset vakavuusluokittain (warn / critical)
korjausehdotuksineen. Tiedosto (`reports/klar_seoresult_*.json`) on suoraan siinä
muodossa, jonka konsolin `seo_runs`-taulu odottaa — tallennus tehdään Klarin
puolella ohuella TS-kerroksella. Vienti on puhdasta analyysia (ei AI-generoitua
sisältöä), kuten Klarin säännöt vaativat.

**Funnel- ja varauswidget-tarkistukset.** Uusi tarkistusryhmä: löytyykö sivulta
toimintakehote, soittolinkki ja yhteydenottotapa — ja ravintoloilla: onko
varauswidget kytketty oikein (`widget.js` + kelvollinen `data-restaurant`-slug).
Esikatselupohjien demolomake (näyttää varaukselta, ei tee mitään) tunnistetaan
ja siitä varoitetaan.

**Monisivuinen ryömintä** (`--max-pages`, oletus 10). URL-tilassa työkalu seuraa
sivuston omia linkkejä ja auditoi useita sivuja yhdellä komennolla — kohteliaasti
0,5 sekunnin välein. Arvolla 1 saat vanhan yhden sivun käytöksen.

```bash
python3 aeo_seo_tool_v5.py --url https://ravintola.fi --max-pages 10 --klar-json
```

## Uutta v4:ssä

**Ravintola-schema.** Työkalu tunnistaa ravintolasivuston automaattisesti
(ruokalista, pöytävaraus ym. sisällöstä) ja tarkistaa/lisää Restaurant-rakennedatan:
aukioloajat, osoitteen, puhelimen, keittiötyypin ja ruokalistalinkin. Puuttuvat
tiedot AI poimii sivun tekstistä, tai ne voi antaa itse:

```bash
python3 aeo_seo_tool_v4.py --repo ./sivusto --fix \
    --cuisine "italialainen" --phone "+358 40 123 4567" \
    --hours "Mo-Fr 11:00-22:00,Sa 12:00-23:00" --address "Esimerkkikatu 1, Helsinki"
```

**Sivustotason tiedostot.** Uusi tarkistusryhmä: `robots.txt` (estääkö vahingossa
koko sivuston?), `sitemap.xml` (sivukartta Googlelle) ja `llms.txt` (uusi
AEO-tiedosto, joka kertoo AI-avustajille mitä sivustolla on). `--fix` luo puuttuvat
tiedostot — repo-tilassa sivuston juureen, URL-tilassa `reports/sivustotiedostot/`-
kansioon, josta ne voi ladata palvelimelle.

## Mitä työkalu tekee

- Jopa 20 tarkistusta per sivu (title, meta description, otsikkorakenne,
  JSON-LD, Open Graph, luotettavuussignaalit, AEO-sisältö, funnel ym.)
  + sivustotason tarkistukset (robots.txt, sitemap.xml, llms.txt, julkaisukunto)
- `--fix` korjaa puutteet suoraan HTML-tiedostoihin ja ottaa `.bak`-varmuuskopiot;
  AI (Claude Haiku) kirjoittaa aidon sisällön placeholderien sijaan
- Raportit `reports/`-hakemistoon: selkokielinen HTML-raportti asiakkaalle,
  markdown ja JSON
- Tulostaa ajon lopuksi API-kulut euroina

## Huomioita

- AI-korjaukset ovat idempotentteja: `--fix` uudelleen ajettuna ei duplikoi mitään
- Ilman `ANTHROPIC_API_KEY`-avainta työkalu toimii pelkkänä auditoijana
