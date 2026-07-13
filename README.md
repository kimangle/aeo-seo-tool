# AEO/SEO Audit Tool

Auditoi ja korjaa verkkosivuston SEO:n (hakukonenäkyvyys) ja AEO:n
(näkyvyys tekoälyhauissa kuten ChatGPT ja Perplexity). Uusin versio on
`aeo_seo_tool_v3.py` — v1 ja v2 ovat mukana vertailun vuoksi.

## Asennus

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # tarvitaan vain AI-korjauksiin (--fix)
```

## Käyttö

```bash
# Auditoi paikallinen sivusto (HTML-tiedostot hakemistossa)
python3 aeo_seo_tool_v3.py --repo ./sivusto

# Auditoi ja korjaa automaattisesti (AI kirjoittaa mm. meta descriptionit)
python3 aeo_seo_tool_v3.py --repo ./sivusto --fix

# Auditoi julkinen URL
python3 aeo_seo_tool_v3.py --url https://example.com

# Hyödyllisiä lippuja
#   --no-open              älä avaa HTML-raporttia selaimeen
#   --site-name "Yritys"   sivuston nimi, jos auto-tunnistus ei onnistu
#   --site-url https://... sivuston osoite
#   --eur-rate 0.90        USD→EUR-kurssi kustannuslaskentaan
```

## Mitä työkalu tekee

- 15 tarkistusta per sivu (title, meta description, otsikkorakenne,
  JSON-LD, Open Graph, luotettavuussignaalit, AEO-sisältö ym.)
- `--fix` korjaa puutteet suoraan HTML-tiedostoihin ja ottaa `.bak`-varmuuskopiot;
  AI (Claude Haiku) kirjoittaa aidon sisällön placeholderien sijaan
- Raportit `reports/`-hakemistoon: selkokielinen HTML-raportti asiakkaalle,
  markdown ja JSON
- Tulostaa ajon lopuksi API-kulut euroina

## Huomioita

- AI-korjaukset ovat idempotentteja: `--fix` uudelleen ajettuna ei duplikoi mitään
- Ilman `ANTHROPIC_API_KEY`-avainta työkalu toimii pelkkänä auditoijana
