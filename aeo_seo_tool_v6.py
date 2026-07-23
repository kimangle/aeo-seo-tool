#!/usr/bin/env python3
"""
AEO/SEO Audit & Auto-Fix Tool v6.0
=====================================
Auditoi ja korjaa MINKÄ TAHANSA verkkosivuston SEO:n ja AEO:n.
V5: Klar-yhteensopiva SeoResult-vienti (--klar-json) · Funnel- ja
    varauswidget-tarkistukset · Monisivuinen ryömintä URL-tilassa (--max-pages)
V6: Asiakaskohtainen korjauspaketti URL-tilassa (--fix-guide) ·
    AI-title-fixeri · Noindex-hälytys raportin kärkeen ·
    Julkaisukunto-tarkistukset (esikatseludomain, AI-bottien pääsy)

Käyttö:
    python aeo_seo_tool_v6.py --repo /polku/sivustoon
    python aeo_seo_tool_v6.py --repo . --fix
    python aeo_seo_tool_v6.py --url https://example.com --max-pages 10
    python aeo_seo_tool_v6.py --url https://example.com --fix-guide --klar-json
    python aeo_seo_tool_v6.py --repo . --fix --cuisine "italialainen" --phone "+358 40 123 4567"
"""

import sys, os, json, re, shutil, argparse, datetime
import html as html_mod
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

# ── Riippuvuudet ────────────────────────────────────────────────────────────

MISSING = []
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    MISSING.append(str(e).split("'")[1] if "'" in str(e) else str(e))

try:
    import anthropic
    _ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    # timeout + max_retries: SDK yrittää 429/5xx-virheet automaattisesti
    # uudelleen eksponentiaalisella backoffilla
    AI_CLIENT = anthropic.Anthropic(api_key=_ANTHROPIC_KEY, timeout=60.0, max_retries=3)
    AI_AVAILABLE = bool(_ANTHROPIC_KEY)
except ImportError:
    AI_AVAILABLE = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH = True
except ImportError:
    RICH = False

if MISSING:
    print(f"Puuttuvat paketit: pip install {' '.join(MISSING)}")
    sys.exit(1)

console = Console() if RICH else None

# ── Vakiot ──────────────────────────────────────────────────────────────────

VERSION = "6.0"
SKIP_DIRS: Set[str] = {
    "node_modules", ".git", "vendor", "dist", "__pycache__",
    "bower_components", ".cache", ".next", "build", "out", ".svn",
}
SOCIAL_DOMAINS = (
    "facebook.com", "twitter.com", "x.com", "linkedin.com",
    "instagram.com", "youtube.com", "tiktok.com", "pinterest.com",
    "threads.net", "bsky.app",
)

# Google Site Verification -tiedostot (esim. google0fcfed6f5a2cbae1.html)
GOOGLE_VERIFY_RE = re.compile(r"google[0-9a-f]{12,}\.html?$", re.I)

# V4: ravintolan tunnistus
RESTAURANT_SCHEMA_TYPES = {
    "Restaurant", "FoodEstablishment", "CafeOrCoffeeShop", "BarOrPub",
    "FastFoodRestaurant", "Bakery", "IceCreamShop",
}
RESTAURANT_KEYWORDS = (
    "ruokalista", "à la carte", "a la carte", "lounaslista", "lounas",
    "varaa pöytä", "pöytävaraus", "book a table", "reservation",
    "annokset", "alkuruoat", "pääruoat", "jälkiruoat",
    "menu", "takeaway", "take away", "noutoruoka", "ravintola", "restaurant",
    "keittiö on avoinna", "kitchen", "brunssi", "brunch",
)
# Vähintään näin monta eri avainsanaosumaa ennen kuin sivu tulkitaan ravintolaksi
RESTAURANT_KEYWORD_THRESHOLD = 3

ICONS  = {"pass": "✅", "warn": "⚠️ ", "fail": "❌"}
COLORS = {"pass": "green", "warn": "yellow", "fail": "red"}

# Selkokieliset nimet ja selitykset asiakasraporttia varten:
# tarkistuksen nimi → (selkokielinen nimi, yhden lauseen selitys)
PLAIN_FI = {
    "Title-tägi": ("Sivun otsikko hakutuloksissa",
        "Otsikko, joka näkyy Googlen hakutuloksissa ja selaimen välilehdellä."),
    "Meta Description": ("Hakutuloksen kuvausteksti",
        "Lyhyt teksti, jonka Google näyttää sivusi otsikon alla hakutuloksissa."),
    "Canonical-tägi": ("Sivun ensisijainen osoite",
        "Kertoo hakukoneille sivun virallisen osoitteen, ettei sama sisältö näy useana kopiona."),
    "Robots Meta": ("Hakukoneiden pääsy sivulle",
        "Kertoo, saavatko hakukoneet näyttää sivun hakutuloksissa."),
    "HTML lang-attribuutti": ("Sivun kielimerkintä",
        "Kertoo hakukoneille, millä kielellä sivu on kirjoitettu."),
    "H1-otsikko": ("Sivun pääotsikko",
        "Jokaisella sivulla tulisi olla yksi selkeä pääotsikko."),
    "Otsikkorakenne": ("Otsikoiden järjestys",
        "Väliotsikoiden pitää edetä loogisesti kuin sisällysluettelossa."),
    "Kuvien alt-tekstit": ("Kuvien tekstivastineet",
        "Sanallinen kuvaus kuvista hakukoneille ja näkövammaisten ruudunlukijoille."),
    "Open Graph": ("Some-jakotiedot",
        "Määrittää, miltä linkki näyttää, kun sivu jaetaan Facebookissa tai LinkedInissä."),
    "Twitter/X Card": ("X:n (Twitterin) jakotiedot",
        "Määrittää, miltä linkki näyttää X-palvelussa jaettuna."),
    "JSON-LD / Structured Data": ("Koneluettava sisältökuvaus",
        "Auttaa Googlea ja tekoälyassistentteja (ChatGPT, Perplexity) ymmärtämään, mitä sivu käsittelee."),
    "AEO-sisältösignaalit": ("Tekoälyystävällinen sisältö",
        "Kysymys–vastaus-muotoinen ja listamainen sisältö, jota tekoälyhaut nostavat esiin."),
    "Auktoriteetti & luottamus": ("Luotettavuuden merkit",
        "Yhteystiedot, tietosuojasivu ja some-linkit lisäävät luottamusta kävijöiden ja hakukoneiden silmissä."),
    "Sisällön laatu": ("Sisällön laatu",
        "Riittävästi tekstiä, selkeä arvolupaus ja kehotus toimintaan."),
    "Sisäiset linkit": ("Linkit omien sivujen välillä",
        "Sivujen väliset linkit auttavat kävijöitä ja hakukoneita liikkumaan sivustolla."),
    "Ravintolan tiedot (schema)": ("Ravintolan tiedot hakukoneille",
        "Aukioloajat, osoite, puhelin ja keittiötyyppi koneluettavassa muodossa — Google ja AI-avustajat osaavat kertoa ravintolasta oikeat tiedot."),
    "robots.txt": ("Hakurobottien ohjetiedosto",
        "Kertoo hakukoneille, mitä sivuston osia ne saavat lukea, ja mistä sivukartta löytyy."),
    "sitemap.xml": ("Sivukartta",
        "Luettelo sivuston kaikista sivuista — auttaa Googlea löytämään ne kaikki."),
    "llms.txt": ("AI-avustajien sisältökuvaus",
        "Uusi AEO-tiedosto, joka kertoo tekoälyavustajille (ChatGPT, Claude, Perplexity) tiiviisti mitä sivustolla on."),
    "Toimintapolku (funnel)": ("Polku yhteydenottoon",
        "Löytyykö sivulta selkeä seuraava askel kävijälle: varaus, soitto tai yhteydenotto."),
    "Varauswidget": ("Varausjärjestelmän kytkentä",
        "Onko sivulla oikea varausjärjestelmä, jolla pöydän voi oikeasti varata — ei pelkkä demolomake."),
    "Oma domain": ("Oma verkkotunnus",
        "Julkaistun sivuston pitää olla omalla domainilla — esikatseluosoite (esim. .vercel.app) ei kerää pysyvää hakukonenäkyvyyttä."),
    "AI-bottien pääsy": ("Tekoälyavustajien pääsy",
        "Pääsevätkö tekoälyavustajat (ChatGPT, Claude, Perplexity) lukemaan sivustoa — estettynä sivusto ei näy tekoälyhauissa."),
}

def plain_name(check_name: str) -> str:
    return PLAIN_FI.get(check_name, (check_name, ""))[0]

# ── Tietorakenteet ──────────────────────────────────────────────────────────

@dataclass
class Check:
    name: str
    category: str
    score: int
    max_score: int
    status: str        # pass / warn / fail
    message: str
    suggestion: str = ""
    fix_snippet: str = ""
    auto_fixable: bool = False

@dataclass
class SiteContext:
    """Auto-havaittu tai CLI:stä annettu sivustotieto."""
    name: str = ""
    url: str = ""
    email: str = ""
    logo_url: str = ""
    lang: str = "fi"
    # V4: ravintolakohtaiset tiedot
    site_type: str = "generic"          # "generic" | "restaurant"
    phone: str = ""
    address: str = ""
    opening_hours: List[str] = field(default_factory=list)  # esim. ["Mo-Fr 11:00-22:00"]
    cuisine: str = ""
    menu_url: str = ""
    price_range: str = ""
    accepts_reservations: Optional[bool] = None

    def is_complete(self) -> bool:
        return bool(self.name and self.url)

    def is_restaurant(self) -> bool:
        return self.site_type == "restaurant"

    def org_schema(self) -> dict:
        d: dict = {
            "@type": "Organization",
            "@id": "#organization",
            "name": self.name,
            "url": self.url,
        }
        if self.email:
            d["email"] = self.email
        if self.logo_url:
            d["logo"] = {"@type": "ImageObject", "url": self.logo_url}
        return d

    def website_schema(self) -> dict:
        return {
            "@type": "WebSite",
            "@id": "#website",
            "url": self.url,
            "name": self.name,
            "publisher": {"@id": "#organization"},
        }

    def restaurant_schema(self) -> dict:
        """Restaurant on LocalBusiness/Organization-alityyppi — korvaa org_schema():n ravintoloille."""
        d = self.org_schema()
        d["@type"] = "Restaurant"
        if self.phone:
            d["telephone"] = self.phone
        if self.address:
            d["address"] = self.address
        if self.opening_hours:
            d["openingHours"] = self.opening_hours
        if self.cuisine:
            d["servesCuisine"] = self.cuisine
        if self.menu_url:
            d["menu"] = self.menu_url
        if self.price_range:
            d["priceRange"] = self.price_range
        if self.accepts_reservations is not None:
            d["acceptsReservations"] = self.accepts_reservations
        return d

# ── Sivustokontekstin tunnistus ──────────────────────────────────────────────

def detect_site_context(soups: List["BeautifulSoup"], cli_url: str = "", cli_name: str = "", cli_email: str = "") -> SiteContext:
    """Tunnistaa sivuston nimen, URL:n ja emailin olemassa olevasta HTML:stä."""
    ctx = SiteContext(url=cli_url, name=cli_name, email=cli_email)

    for soup in soups:
        # 1. Etsi Organization/LocalBusiness JSON-LD:stä
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                items = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [data])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    t = item.get("@type", "")
                    if t in RESTAURANT_SCHEMA_TYPES:
                        ctx.site_type = "restaurant"
                        if item.get("telephone") and not ctx.phone:
                            ctx.phone = str(item["telephone"])
                        if item.get("servesCuisine") and not ctx.cuisine:
                            sc = item["servesCuisine"]
                            ctx.cuisine = ", ".join(sc) if isinstance(sc, list) else str(sc)
                        if item.get("address") and not ctx.address:
                            addr = item["address"]
                            if isinstance(addr, dict):
                                ctx.address = " ".join(str(addr.get(k, "")) for k in
                                    ("streetAddress", "postalCode", "addressLocality") if addr.get(k)).strip()
                            else:
                                ctx.address = str(addr)
                        oh = item.get("openingHours")
                        if oh and not ctx.opening_hours:
                            ctx.opening_hours = oh if isinstance(oh, list) else [str(oh)]
                        if item.get("menu") and not ctx.menu_url:
                            ctx.menu_url = str(item["menu"])
                    if t in ("Organization", "LocalBusiness", "Corporation") or t in RESTAURANT_SCHEMA_TYPES:
                        n = item.get("name", "")
                        u = item.get("url", "")
                        e = item.get("email", "")
                        logo = item.get("logo", {})
                        if isinstance(logo, dict):
                            logo = logo.get("url", "")
                        if n and n not in ("Yrityksesi nimi", "Sivuston nimi") and not ctx.name:
                            ctx.name = n
                        if u and u != "https://example.com" and not ctx.url:
                            ctx.url = u
                        if e and not ctx.email:
                            ctx.email = e
                        if logo and not ctx.logo_url:
                            ctx.logo_url = logo
            except Exception:
                pass

        # 2. OG-tagit
        if not ctx.name:
            site_name = soup.find("meta", property="og:site_name")
            if site_name and site_name.get("content"):
                ctx.name = site_name["content"]
        if not ctx.url:
            og_url = soup.find("meta", property="og:url")
            if og_url and og_url.get("content") and og_url["content"] != "/":
                parsed = urlparse(og_url["content"])
                if parsed.scheme and parsed.netloc:
                    ctx.url = f"{parsed.scheme}://{parsed.netloc}"

        # 3. Canonical-tägi
        if not ctx.url:
            can = soup.find("link", rel="canonical")
            if can and can.get("href") and can["href"] != "/":
                parsed = urlparse(can["href"])
                if parsed.scheme and parsed.netloc:
                    ctx.url = f"{parsed.scheme}://{parsed.netloc}"

        # 4. Title-tägi → brändinimi (" | " tai " - " jälkeinen osa)
        if not ctx.name:
            title = soup.find("title")
            if title:
                t = title.get_text(strip=True)
                for sep in [" | ", " - ", " – ", " — "]:
                    if sep in t:
                        ctx.name = t.split(sep)[-1].strip()
                        break

        # 5. Email tekstistä tai mailto-linkeistä
        if not ctx.email:
            for a in soup.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    ctx.email = a["href"][7:].split("?")[0].strip()
                    break

        # 6. Kieli
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            ctx.lang = html_tag["lang"][:2]

        if ctx.is_complete() and ctx.email:
            break

    # V4: ravintolan tunnistus sisällöstä (jos JSON-LD ei jo kertonut)
    for soup in soups:
        body_lower = soup.get_text(" ", strip=True).lower()

        if ctx.site_type != "restaurant":
            hits = {kw for kw in RESTAURANT_KEYWORDS if kw in body_lower}
            if len(hits) >= RESTAURANT_KEYWORD_THRESHOLD:
                ctx.site_type = "restaurant"

        if not ctx.phone:
            for a in soup.find_all("a", href=True):
                if a["href"].startswith("tel:"):
                    ctx.phone = a["href"][4:].strip()
                    break

        if ctx.accepts_reservations is None:
            has_booking_script = any(
                re.search(r"booking|widget\.js|varaus", s.get("src", ""), re.I)
                for s in soup.find_all("script", src=True)
            )
            if has_booking_script or "varaa pöytä" in body_lower or "book a table" in body_lower:
                ctx.accepts_reservations = True

        if not ctx.menu_url:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue
                txt = a.get_text(strip=True).lower()
                if txt in ("menu", "ruokalista", "lounaslista") or \
                   re.search(r"(ruokalista|lounaslista|(^|/)menu)", href.lower()):
                    if not href.startswith("http") and ctx.url:
                        href = ctx.url.rstrip("/") + "/" + href.lstrip("/")
                    ctx.menu_url = href
                    break

    # Logo-arvaus URL:sta
    if ctx.url and not ctx.logo_url:
        ctx.logo_url = ctx.url.rstrip("/") + "/logo.png"

    return ctx


def merge_cli_site_args(ctx: SiteContext, cli: SiteContext) -> SiteContext:
    """CLI:stä annetut tiedot voittavat aina auto-tunnistuksen (V4)."""
    if cli.logo_url:
        ctx.logo_url = cli.logo_url
    if cli.phone:
        ctx.phone = cli.phone
    if cli.address:
        ctx.address = cli.address
    if cli.opening_hours:
        ctx.opening_hours = cli.opening_hours
    if cli.cuisine:
        ctx.cuisine = cli.cuisine
    if cli.menu_url:
        ctx.menu_url = cli.menu_url
    # Ravintolatietojen antaminen käsin kertoo, että kyse on ravintolasta
    if cli.site_type == "restaurant" or cli.cuisine or cli.menu_url:
        ctx.site_type = "restaurant"
    return ctx


def detect_platform(soups: List["BeautifulSoup"]) -> str:
    """V6: tunnistaa julkaisualustan HTML:stä korjauspaketin ohjeita varten.
    Palauttaa: "wordpress" | "wix" | "squarespace" | "generic"."""
    for soup in soups:
        gen = soup.find("meta", attrs={"name": "generator"})
        gen_c = (gen.get("content") or "").lower() if gen else ""
        if "wordpress" in gen_c:
            return "wordpress"
        if "wix" in gen_c:
            return "wix"
        if "squarespace" in gen_c:
            return "squarespace"
        html_str = str(soup).lower()
        if "wp-content" in html_str or "wp-includes" in html_str:
            return "wordpress"
        if "wixstatic.com" in html_str or "parastorage.com" in html_str:
            return "wix"
        if "squarespace-cdn.com" in html_str or "static1.squarespace.com" in html_str:
            return "squarespace"
    return "generic"


def enrich_restaurant_details(site: SiteContext, body_text: str):
    """Täydentää ravintolan puuttuvat tiedot sivutekstistä AI:lla (V4, yksi Haiku-kutsu)."""
    if not AI_AVAILABLE or not site.is_restaurant():
        return
    if site.phone and site.address and site.opening_hours and site.cuisine:
        return
    _info("AI poimii ravintolan tiedot sivun tekstistä...")
    d = AIWriter(site).restaurant_details(site.name, body_text)
    if not d:
        return
    if not site.phone:
        site.phone = str(d.get("phone") or "").strip()
    if not site.address:
        site.address = str(d.get("address") or "").strip()
    if not site.opening_hours:
        oh = d.get("opening_hours") or []
        if isinstance(oh, list):
            site.opening_hours = [str(x).strip() for x in oh if str(x).strip()]
        elif str(oh).strip():
            site.opening_hours = [str(oh).strip()]
    if not site.cuisine:
        site.cuisine = str(d.get("cuisine") or "").strip()
    if not site.price_range:
        site.price_range = str(d.get("price_range") or "").strip()
    found = [n for n, v in [("puhelin", site.phone), ("osoite", site.address),
                            ("aukioloajat", site.opening_hours), ("keittiö", site.cuisine)] if v]
    if found:
        _info(f"  Ravintolatiedot: {', '.join(found)}")

# ── Kustannusseuranta ───────────────────────────────────────────────────────

# Hinnat: USD / miljoona tokenia (input, output)
MODEL_PRICES_USD = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5":          (1.00, 5.00),
}
DEFAULT_USD_EUR = 0.85  # ohitettavissa: --eur-rate tai AEO_USD_EUR


class CostTracker:
    """Kerää API-kutsujen tokenmäärät ja laskee kulut euroina."""

    def __init__(self):
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.model = ""
        try:
            self.usd_eur = float(os.environ.get("AEO_USD_EUR", DEFAULT_USD_EUR))
        except ValueError:
            self.usd_eur = DEFAULT_USD_EUR

    def record(self, model: str, usage):
        self.calls += 1
        self.model = model
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0

    def cost_eur(self) -> float:
        p_in, p_out = MODEL_PRICES_USD.get(self.model, (1.00, 5.00))
        usd = self.input_tokens / 1e6 * p_in + self.output_tokens / 1e6 * p_out
        return usd * self.usd_eur

    def summary(self) -> str:
        if self.calls == 0:
            return "AI-kulut: ei API-kutsuja tässä ajossa (0,00 €)"
        eur = self.cost_eur()
        eur_str = f"{eur:.2f}".replace(".", ",") if eur >= 0.005 else "alle 0,01"
        fmt = lambda n: f"{n:,}".replace(",", " ")
        rate = f"{self.usd_eur:.2f}".replace(".", ",")
        return (f"AI-kulut: {self.calls} API-kutsua · "
                f"{fmt(self.input_tokens)} input + {fmt(self.output_tokens)} output tokenia · "
                f"~{eur_str} € (kurssi 1 $ = {rate} €)")

    def as_dict(self) -> dict:
        return {
            "api_calls": self.calls,
            "model": self.model or None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_eur": round(self.cost_eur(), 4),
            "usd_eur_rate": self.usd_eur,
        }


COSTS = CostTracker()

# ── AI-sisällöntuottaja ─────────────────────────────────────────────────────

_AI_CONSECUTIVE_FAILURES = 0
_AI_MAX_FAILURES = 3

def _disable_ai(reason: str):
    """Kytkee AI-ominaisuudet pois loppuajoksi, ettei sama virhe toistu joka sivulla."""
    global AI_AVAILABLE
    if AI_AVAILABLE:
        AI_AVAILABLE = False
        _warn(f"AI-ominaisuudet kytketty pois loppuajoksi: {reason}")


class AIWriter:
    """Sivusto-agnostinen AI-kirjoittaja. Käyttää sivun kontekstia oikean sisällön generointiin."""

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, site: SiteContext):
        self.site = site

    @property
    def available(self) -> bool:
        return AI_AVAILABLE

    def _ask(self, prompt: str, max_tokens: int = 800) -> str:
        global _AI_CONSECUTIVE_FAILURES
        if not AI_AVAILABLE:
            return ""
        try:
            r = AI_CLIENT.messages.create(
                model=self.MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            _AI_CONSECUTIVE_FAILURES = 0
            COSTS.record(self.MODEL, r.usage)
            return next((b.text for b in r.content if b.type == "text"), "").strip()
        except anthropic.AuthenticationError:
            _disable_ai("API-avain on virheellinen tai vanhentunut — tarkista ANTHROPIC_API_KEY")
            return ""
        except anthropic.PermissionDeniedError:
            _disable_ai("API-avaimella ei ole oikeutta käyttää mallia")
            return ""
        except anthropic.RateLimitError:
            _warn("AI: käyttöraja täynnä, uudelleenyritykset eivät auttaneet — kohta ohitetaan")
        except anthropic.APIConnectionError:
            _warn("AI: verkkovirhe tai aikakatkaisu — kohta ohitetaan")
        except anthropic.APIStatusError as e:
            _warn(f"AI: API-virhe (HTTP {e.status_code}) — kohta ohitetaan")
        _AI_CONSECUTIVE_FAILURES += 1
        if _AI_CONSECUTIVE_FAILURES >= _AI_MAX_FAILURES:
            _disable_ai(f"{_AI_MAX_FAILURES} peräkkäistä epäonnistunutta AI-kutsua")
        return ""

    def _site_ctx(self) -> str:
        parts = []
        if self.site.name:
            parts.append(f"Yritys: {self.site.name}")
        if self.site.url:
            parts.append(f"Verkkosivusto: {self.site.url}")
        if self.site.email:
            parts.append(f"Sähköposti: {self.site.email}")
        return "\n".join(parts)

    def meta_description(self, title: str, body_text: str, url: str = "") -> str:
        lang_instruction = "suomeksi" if self.site.lang == "fi" else f"kielellä {self.site.lang}"
        prompt = f"""Kirjoita yksi SEO-optimoitu meta description {lang_instruction} tälle verkkosivulle.

{self._site_ctx()}
Sivun otsikko: {title}
Sivun sisältö: {body_text[:500]}

Vaatimukset:
- Täsmälleen 140–155 merkkiä
- Sisältää pääavainsanan luonnollisesti
- Houkutteleva, selkeä arvolupaus
- Ei lainausmerkkejä, ei HTML-tageja
- Palauta VAIN meta description -teksti"""
        result = self._ask(prompt, 120)
        if result and 120 <= len(result) <= 165:
            return result
        return result[:155] if result else ""

    def title(self, current_title: str, body_text: str) -> str:
        """V6: kirjoittaa/parantaa sivun title-tägin. Peilaa meta_description()-logiikkaa."""
        lang_instruction = "suomeksi" if self.site.lang == "fi" else f"kielellä {self.site.lang}"
        brand = self.site.name or ""
        prompt = f"""Kirjoita yksi SEO-optimoitu title-tägi {lang_instruction} tälle verkkosivulle.

{self._site_ctx()}
Nykyinen title: {current_title or "(puuttuu)"}
Sivun sisältö: {body_text[:500]}

Vaatimukset:
- Täsmälleen 30–60 merkkiä
- Muoto: Sivun aihe | {brand or "Brändi"}
- Tärkein avainsana alkuun, luonnollista kieltä
- Ei lainausmerkkejä, ei HTML-tageja
- Palauta VAIN title-teksti"""
        result = self._ask(prompt, 80).strip().strip('"')
        if not result:
            return ""
        # Validointi samoihin rajoihin kuin _title()-tarkistus (30–60 mk),
        # muuten korjaus jää warn-tilaan ja toistuu joka ajolla
        if len(result) > 60:
            cut = result[:61].rsplit(" ", 1)[0].strip(" -–—|")
            result = cut if len(cut) >= 30 else result[:60].rstrip()
        if len(result) < 30 and brand and brand.lower() not in result.lower():
            cand = f"{result} | {brand}"
            if len(cand) <= 60:
                result = cand
        return result if 30 <= len(result) <= 60 else ""

    def faq_items(self, title: str, body_text: str, page_type: str = "") -> List[Dict]:
        lang_instruction = "suomeksi" if self.site.lang == "fi" else f"kielellä {self.site.lang}"
        prompt = f"""Luo 5 usein kysyttyä kysymystä vastauksineen {lang_instruction} tälle verkkosivulle.

{self._site_ctx()}
Sivun otsikko: {title}
Sivutyyppi: {page_type}
Sivun sisältö: {body_text[:700]}

Palauta VAIN JSON-taulukko (ei muuta tekstiä):
[
  {{"q": "Kysymys?", "a": "Vastaus vähintään 2 lausetta."}},
  ...
]"""
        raw = self._ask(prompt, 700)
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                items = json.loads(match.group())
                return [{"q": str(i.get("q", "")), "a": str(i.get("a", ""))}
                        for i in items
                        if isinstance(i, dict) and i.get("q") and i.get("a")]
        except (json.JSONDecodeError, TypeError):
            _warn("AI palautti virheellistä JSONia (FAQ) — kohta ohitetaan")
        return []

    def howto_steps(self, title: str, body_text: str) -> List[Dict]:
        lang_instruction = "suomeksi" if self.site.lang == "fi" else f"kielellä {self.site.lang}"
        prompt = f"""Luo 4–5 selkeää HowTo-askelta {lang_instruction} tälle prosessisivulle.

{self._site_ctx()}
Sivun otsikko: {title}
Sisältö: {body_text[:500]}

Palauta VAIN JSON-taulukko:
[
  {{"name": "Askeleen nimi", "text": "Tarkempi kuvaus."}},
  ...
]"""
        raw = self._ask(prompt, 500)
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                items = json.loads(match.group())
                return [i for i in items
                        if isinstance(i, dict) and i.get("name") and i.get("text")]
        except (json.JSONDecodeError, TypeError):
            _warn("AI palautti virheellistä JSONia (HowTo) — kohta ohitetaan")
        return []

    def page_schema_type(self, title: str, body_text: str, filename: str) -> str:
        fname = filename.lower()
        kw_map = {
            "FAQPage":     ("ukk", "faq", "kysymys", "question"),
            "HowTo":       ("miten", "how", "opas", "guide", "prosessi", "vaihe"),
            "Service":     ("palvelu", "service", "hinta", "price", "paketti"),
            "ContactPage": ("yhteystiedot", "contact", "yhteys", "ota-yhteyttä"),
            "AboutPage":   ("meistä", "about", "yritys", "tietoa-meistä"),
        }
        for schema, keywords in kw_map.items():
            if any(k in fname for k in keywords):
                return schema
        # Otsikosta/tekstistä vain täsmälliset avainsanat — löyhät osumat
        # (esim. "yhteyshenkilö" → "yhteys") tuottivat vääriä skeematyyppejä
        body_kw_map = {
            "FAQPage":     ("usein kysytty", "ukk", "faq"),
            "HowTo":       ("näin se toimii", "vaihe vaiheelta", "step by step"),
            "ContactPage": ("yhteystiedot", "ota yhteyttä", "contact us"),
            "AboutPage":   ("tietoa meistä", "about us"),
        }
        combined = (title + " " + body_text[:200]).lower()
        for schema, keywords in body_kw_map.items():
            if any(k in combined for k in keywords):
                return schema
        return "WebPage"

    def restaurant_details(self, title: str, body_text: str) -> Dict:
        """Poimii sivutekstistä ravintolan puuttuvat perustiedot (V4). Yksi Haiku-kutsu."""
        prompt = f"""Poimi TÄSMÄLLEEN sivutekstissä mainitut ravintolan tiedot. Älä keksi mitään —
jos tietoa ei ole tekstissä, jätä kenttä tyhjäksi.

Sivun otsikko: {title}
Sivun teksti: {body_text[:1500]}

Palauta VAIN JSON-objekti (ei muuta tekstiä):
{{
  "phone": "puhelinnumero tai tyhjä",
  "address": "katuosoite ja kaupunki tai tyhjä",
  "opening_hours": ["aukioloajat schema.org-muodossa, esim. Mo-Fr 11:00-22:00", "..."],
  "cuisine": "keittiötyyppi yhdellä-kahdella sanalla (esim. italialainen) tai tyhjä",
  "price_range": "€, €€ tai €€€ jos hintataso käy ilmi, muuten tyhjä"
}}"""
        raw = self._ask(prompt, 300)
        try:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                d = json.loads(match.group())
                if isinstance(d, dict):
                    return d
        except (json.JSONDecodeError, TypeError):
            _warn("AI palautti virheellistä JSONia (ravintolatiedot) — kohta ohitetaan")
        return {}

    def strategic_recs(self, page_scores: Dict[str, int]) -> str:
        """Generoi strategisia AEO/SEO-suosituksia koko sivustolle."""
        if not self.available:
            return ""
        all_scores = ", ".join(f"{p}: {s}/100" for p, s in page_scores.items())
        low = [p for p, s in page_scores.items() if s < 80]
        prompt = f"""Olet kokenut hakukonenäkyvyyden konsultti. Kirjoita lyhyt yhteenveto sivuston {self.site.name or self.site.url or ''} kunnosta asiakkaalle, joka EI tunne teknistä SEO-sanastoa.

Sivujen pisteet (0–100): {all_scores}
Eniten parannettavaa: {', '.join(low) if low else 'ei yhdessäkään — sivusto on hyvässä kunnossa'}

Kirjoita:
1. Yksi lause sivuston kokonaistilanteesta arkikielellä.
2. 2–4 tärkeintä toimenpidettä tärkeysjärjestyksessä, jokainen omalla rivillään alkaen numerolla.

Vältä teknisiä termejä (älä käytä sanoja kuten "meta tag", "canonical", "JSON-LD" ilman selitystä). Puhuttele asiakasta suoraan. Vastaa suomeksi, korkeintaan 120 sanaa. Palauta VAIN teksti."""
        return self._ask(prompt, 350)


# ── Auditoija ───────────────────────────────────────────────────────────────

class PageAuditor:
    """20-tarkistuksen SEO/AEO-auditoija. Toimii mille tahansa HTML-sivulle."""

    SCORING = {
        # Tekninen SEO
        "title": 10, "meta_desc": 10, "canonical": 5, "robots_meta": 2, "lang_attr": 1,
        # Sivun rakenne
        "h1": 8, "heading_hierarchy": 5, "images_alt": 5,
        # Sosiaalinen SEO
        "open_graph": 8, "twitter_card": 4,
        # AEO & Structured Data
        "jsonld_present": 4, "schema_types": 7, "faq_schema": 7, "aeo_content": 8,
        # Luottamus & laatu
        "authority": 7, "content_quality": 7,
        # Rakenne
        "internal_links": 2,
        # V4: vain ravintolasivustoille (max-pisteet lasketaan dynaamisesti,
        # joten tavallisten sivustojen kokonaispisteet pysyvät ennallaan)
        "restaurant_schema": 8,
        # V5: funnel-tarkistukset (WS-F-runbookin mukaan)
        "funnel_cta": 6,
        "booking_widget": 4,   # vain ravintoloille
    }
    # Total = 100 (+ 8 ravintoloille)

    def __init__(self, html: str, url: str = "", file_path: str = "", site: Optional[SiteContext] = None):
        parser = "lxml" if _has_lxml() else "html.parser"
        self.soup = BeautifulSoup(html, parser)
        self.url = url
        self.file_path = file_path
        self.site = site or SiteContext()
        self.checks: List[Check] = []
        self._body_text = self.soup.get_text(" ", strip=True)
        self._words = self._body_text.split()

    def run(self) -> List[Check]:
        self._title()
        self._meta_desc()
        self._canonical()
        self._robots_meta()
        self._lang_attr()
        self._h1()
        self._heading_hierarchy()
        self._images_alt()
        self._open_graph()
        self._twitter_card()
        self._json_ld()
        if self.site.is_restaurant():
            self._restaurant_schema()
        self._aeo_content()
        self._authority()
        self._content_quality()
        self._internal_links()
        self._funnel()
        if self.site.is_restaurant():
            self._booking_widget()
        return self.checks

    # ── Tekninen SEO ──

    def _title(self):
        m = self.SCORING["title"]
        tag = self.soup.find("title")
        if not tag or not tag.get_text(strip=True):
            self.checks.append(Check("Title-tägi", "Tekninen SEO", 0, m, "fail",
                "Title puuttuu", "AI kirjoittaa titlen --fix-lipulla",
                "<title>Sivun nimi | Brändi</title>", auto_fixable=True))
            return
        t = tag.get_text(strip=True)
        ln = len(t)
        if 30 <= ln <= 60:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m, m, "pass",
                f'"{_trunc(t, 52)}" ({ln} merkkiä)'))
        elif ln < 30:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m // 2, m, "warn",
                f"Liian lyhyt ({ln} mk): \"{t}\"",
                "AI laajentaa 30–60 merkkiin --fix-lipulla", "", auto_fixable=True))
        else:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m - 3, m, "warn",
                f"Liian pitkä ({ln} mk) — Google katkaisee 60 mk kohdalta",
                "AI lyhentää alle 60 merkkiin --fix-lipulla", "", auto_fixable=True))

    def _meta_desc(self):
        m = self.SCORING["meta_desc"]
        tag = self.soup.find("meta", attrs={"name": "description"})
        if not tag or not (tag.get("content") or "").strip():
            self.checks.append(Check("Meta Description", "Tekninen SEO", 0, m, "fail",
                "Meta description puuttuu",
                "AI kirjoittaa sen automaattisesti --fix-lipulla", "", auto_fixable=True))
            return
        t = tag["content"].strip()
        ln = len(t)
        is_placeholder = any(p in t.lower() for p in
            ["kuvaile sivusi", "120–160", "placeholder", "yrityksesi", "example"])
        if is_placeholder:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m // 3, m, "warn",
                f"Placeholder-teksti ({ln} mk)",
                "AI kirjoittaa oikean sisällön --fix-lipulla", "", auto_fixable=True))
        elif 120 <= ln <= 160:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m, m, "pass",
                f"Optimaalinen ({ln} merkkiä)"))
        elif ln < 120:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m // 2, m, "warn",
                f"Liian lyhyt ({ln} mk) — tavoite 120–160",
                "AI parantaa --fix-lipulla", "", auto_fixable=True))
        else:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m - 2, m, "warn",
                f"Liian pitkä ({ln} mk)", "Lyhennä alle 160 merkkiin"))

    def _canonical(self):
        m = self.SCORING["canonical"]
        tag = self.soup.find("link", rel="canonical")
        if tag and tag.get("href") and tag["href"] not in ("/", "", None):
            href = tag["href"]
            # Tarkista onko absoluuttinen URL
            if href.startswith("http"):
                self.checks.append(Check("Canonical-tägi", "Tekninen SEO", m, m, "pass", href))
            else:
                self.checks.append(Check("Canonical-tägi", "Tekninen SEO", m - 1, m, "warn",
                    f"Suhteellinen URL: {href}", "Käytä absoluuttista URL:a"))
        else:
            page_url = self.url or (self.site.url + "/" if self.site.url else "")
            self.checks.append(Check("Canonical-tägi", "Tekninen SEO", 0, m, "warn",
                "Canonical puuttuu tai on virheellinen",
                "Lisää canonical", f'<link rel="canonical" href="{page_url}">', auto_fixable=True))

    def _robots_meta(self):
        m = self.SCORING["robots_meta"]
        tag = self.soup.find("meta", attrs={"name": "robots"})
        if tag:
            c = (tag.get("content") or "").lower()
            if "noindex" in c:
                self.checks.append(Check("Robots Meta", "Tekninen SEO", 0, m, "fail",
                    f"VAROITUS: noindex asetettu! ({c})", "Poista noindex tai muuta index,follow"))
            else:
                self.checks.append(Check("Robots Meta", "Tekninen SEO", m, m, "pass", c))
        else:
            self.checks.append(Check("Robots Meta", "Tekninen SEO", m - 1, m, "pass",
                "Puuttuu — oletus index,follow on OK"))

    def _lang_attr(self):
        m = self.SCORING["lang_attr"]
        html_tag = self.soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang = html_tag["lang"]
            self.checks.append(Check("HTML lang-attribuutti", "Tekninen SEO", m, m, "pass",
                f'lang="{lang}" — hakukoneet tietävät kielen'))
        else:
            self.checks.append(Check("HTML lang-attribuutti", "Tekninen SEO", 0, m, "warn",
                "lang-attribuutti puuttuu <html>-tagista",
                'Lisää: <html lang="fi">',
                '<html lang="fi">', auto_fixable=True))

    # ── Sivun rakenne ──

    def _h1(self):
        m = self.SCORING["h1"]
        h1s = self.soup.find_all("h1")
        if not h1s:
            self.checks.append(Check("H1-otsikko", "Sivun rakenne", 0, m, "fail",
                "H1 puuttuu", "Lisää yksi H1-otsikko sivulle", "<h1>Sivun pääotsikko</h1>"))
        elif len(h1s) == 1:
            txt = h1s[0].get_text(strip=True)
            self.checks.append(Check("H1-otsikko", "Sivun rakenne", m, m, "pass",
                f'"{_trunc(txt, 55)}"'))
        else:
            self.checks.append(Check("H1-otsikko", "Sivun rakenne", m // 2, m, "warn",
                f"{len(h1s)} H1-otsikkoa — suositellaan yhtä", "Jätä vain yksi H1 per sivu"))

    def _heading_hierarchy(self):
        m = self.SCORING["heading_hierarchy"]
        levels = []
        for lv in range(1, 7):
            for _ in self.soup.find_all(f"h{lv}"):
                levels.append(lv)
        if not levels:
            self.checks.append(Check("Otsikkorakenne", "Sivun rakenne", 0, m, "fail",
                "Ei otsikoita lainkaan"))
            return
        issues = []
        prev = 0
        for lv in levels:
            if prev and lv > prev + 1:
                issues.append(f"H{prev}→H{lv}")
            prev = lv
        if not issues:
            self.checks.append(Check("Otsikkorakenne", "Sivun rakenne", m, m, "pass",
                f"Looginen rakenne ({len(levels)} otsikkoa)"))
        else:
            deduct = min(len(issues) * 2, m)
            self.checks.append(Check("Otsikkorakenne", "Sivun rakenne", max(0, m - deduct), m, "warn",
                f"Tasoaukkoja: {', '.join(issues[:3])}",
                "Korjaa otsikkohierarkia — ei H2→H4 hyppyjä"))

    def _images_alt(self):
        m = self.SCORING["images_alt"]
        imgs = self.soup.find_all("img")
        if not imgs:
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun rakenne", m, m, "pass",
                "Ei kuvia sivulla"))
            return
        no_alt = [i for i in imgs if i.get("alt") is None]
        empty_alt = [i for i in imgs if i.get("alt") == ""]  # Decorative = OK
        bad_alt = [i for i in imgs if i.get("alt") in ("image", "photo", "kuva", "img")]
        problems = no_alt + bad_alt
        if not problems:
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun rakenne", m, m, "pass",
                f"Kaikilla {len(imgs)} kuvalla alt-teksti"))
        else:
            score = round(m * (len(imgs) - len(problems)) / len(imgs))
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun rakenne", score, m,
                "fail" if score == 0 else "warn",
                f"{len(problems)}/{len(imgs)} kuvalta puuttuu/heikko alt-teksti",
                "Lisää kuvaava alt-teksti jokaiselle sisältökuvalle"))

    # ── Sosiaalinen SEO ──

    def _open_graph(self):
        m = self.SCORING["open_graph"]
        required = ["og:title", "og:description", "og:image", "og:url"]
        found, broken = [], []
        for p in required:
            tag = self.soup.find("meta", property=p)
            if tag and (tag.get("content") or "").strip() not in ("", "/", None):
                found.append(p)
            elif tag:
                broken.append(p)
        missing = [p for p in required if p not in found]
        if not missing:
            self.checks.append(Check("Open Graph", "Sosiaalinen SEO", m, m, "pass",
                "Kaikki OG-tagit kunnossa"))
        else:
            score = round(m * len(found) / len(required))
            snippet = "\n".join(f'<meta property="{p}" content="...">' for p in missing)
            self.checks.append(Check("Open Graph", "Sosiaalinen SEO", score, m,
                "fail" if score == 0 else "warn",
                f"Puuttuu: {', '.join(missing)}",
                "Lisää puuttuvat OG-tagit", snippet, auto_fixable=True))

    def _twitter_card(self):
        m = self.SCORING["twitter_card"]
        card = self.soup.find("meta", attrs={"name": "twitter:card"})
        img  = self.soup.find("meta", attrs={"name": "twitter:image"})
        if card and (card.get("content") or "") and img and (img.get("content") or ""):
            self.checks.append(Check("Twitter/X Card", "Sosiaalinen SEO", m, m, "pass",
                "Twitter Card + kuva kunnossa"))
        elif card and (card.get("content") or ""):
            self.checks.append(Check("Twitter/X Card", "Sosiaalinen SEO", m - 2, m, "warn",
                "Twitter Card OK — twitter:image puuttuu",
                'Lisää <meta name="twitter:image" content="...">',
                '', auto_fixable=True))
        else:
            self.checks.append(Check("Twitter/X Card", "Sosiaalinen SEO", 0, m, "warn",
                "Twitter Card puuttuu",
                "Lisää Twitter Card -metatagit", "", auto_fixable=True))

    # ── AEO & Structured Data ──

    def _json_ld(self):
        mp = self.SCORING["jsonld_present"]
        ms = self.SCORING["schema_types"]
        mf = self.SCORING["faq_schema"]
        total_max = mp + ms + mf

        scripts = self.soup.find_all("script", type="application/ld+json")
        if not scripts:
            self.checks.append(Check("JSON-LD / Structured Data", "AEO & Structured Data",
                0, total_max, "fail", "JSON-LD puuttuu kokonaan",
                "AI generoi oikean JSON-LD:n --fix-lipulla", "", auto_fixable=True))
            return

        schemas, parse_errors = [], 0
        for s in scripts:
            try:
                d = json.loads(s.string or "{}")
                if isinstance(d, dict) and "@graph" in d:
                    schemas.extend(d["@graph"])
                elif isinstance(d, dict):
                    schemas.append(d)
                elif isinstance(d, list):
                    schemas.extend(d)
            except Exception:
                parse_errors += 1

        types = [str(s.get("@type", "")) for s in schemas if isinstance(s, dict)]

        has_org  = any(t in ("Organization", "LocalBusiness", "Corporation", "Store")
                       or t in RESTAURANT_SCHEMA_TYPES for t in types)
        has_site = "WebSite" in types
        has_page = any(t in ("WebPage", "Article", "BlogPosting", "Product",
                             "Service", "FAQPage", "HowTo", "ContactPage",
                             "AboutPage", "CollectionPage") for t in types)
        has_faq  = any(t in ("FAQPage", "HowTo") for t in types)

        # Tarkista placeholders
        placeholders = {"Yrityksesi nimi", "Sivuston nimi", "Your Company"}
        has_placeholder = any(
            isinstance(s, dict) and (s.get("name") in placeholders or s.get("url") == "https://example.com")
            for s in schemas
        )

        # Tarkista FAQPage rakenne
        faq_quality = 0
        for s in schemas:
            if not isinstance(s, dict):
                continue
            if s.get("@type") == "FAQPage":
                entities = s.get("mainEntity", [])
                if isinstance(entities, list) and len(entities) >= 3:
                    faq_quality = mf
                elif isinstance(entities, list) and len(entities) >= 1:
                    faq_quality = mf // 2
            elif s.get("@type") == "HowTo":
                steps = s.get("step", [])
                if isinstance(steps, list) and len(steps) >= 3:
                    faq_quality = mf
                elif isinstance(steps, list) and len(steps) >= 1:
                    faq_quality = mf // 2

        sp = mp  # JSON-LD exists
        ss = min(ms, (3 if has_org else 0) + (2 if has_site else 0) + (2 if has_page else 0))
        if has_placeholder:
            ss = max(0, ss - 2)
        sf = faq_quality

        total = sp + ss + sf
        status = "pass" if total >= total_max * 0.7 else ("warn" if total > 0 else "fail")
        type_str = ", ".join(t for t in sorted(set(types)) if t) or "tuntematon"

        notes = []
        if has_placeholder:
            notes.append("Placeholder-arvoja — AI korjaa --fix-lipulla")
        if not has_faq:
            notes.append("FAQPage/HowTo puuttuu — lisää AEO:ta varten")
        if parse_errors:
            notes.append(f"{parse_errors} JSON-LD syntaksivirhe")

        self.checks.append(Check("JSON-LD / Structured Data", "AEO & Structured Data",
            total, total_max, status,
            f"Skeematyypit: {_trunc(type_str, 50)}",
            " | ".join(notes) if notes else "",
            "", auto_fixable=has_placeholder or not has_faq))

    def _restaurant_schema(self):
        """V4: ravintolan Restaurant-JSON-LD:n kattavuus (ajetaan vain ravintolasivustoille)."""
        m = self.SCORING["restaurant_schema"]

        rest_item = None
        for s in self.soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(s.string or "{}")
                items = d.get("@graph", [d]) if isinstance(d, dict) else (d if isinstance(d, list) else [d])
                for item in items:
                    if isinstance(item, dict) and str(item.get("@type", "")) in RESTAURANT_SCHEMA_TYPES:
                        rest_item = item
                        break
            except Exception:
                pass
            if rest_item:
                break

        if not rest_item:
            self.checks.append(Check("Ravintolan tiedot (schema)", "AEO & Structured Data",
                0, m, "fail",
                "Restaurant-skeema puuttuu — sivu tunnistettu ravintolaksi",
                "AI lisää aukioloajat, osoitteen ja keittiötyypin --fix-lipulla",
                "", auto_fixable=True))
            return

        # Restaurant-tyyppi löytyy (3 p) + 1 p per keskeinen kenttä
        score = 3
        found, missing = [], []
        for key, label in [("openingHours", "aukioloajat"), ("address", "osoite"),
                           ("telephone", "puhelin"), ("servesCuisine", "keittiötyyppi"),
                           ("menu", "ruokalista")]:
            if rest_item.get(key):
                score += 1
                found.append(label)
            else:
                missing.append(label)

        status = "pass" if score >= m * 0.7 else "warn"
        self.checks.append(Check("Ravintolan tiedot (schema)", "AEO & Structured Data",
            min(score, m), m, status,
            f"Restaurant-skeema: {', '.join(found) if found else 'vain tyyppi'}",
            f"Puuttuu: {', '.join(missing)} — AI täydentää --fix-lipulla" if missing else "",
            "", auto_fixable=bool(missing)))

    def _aeo_content(self):
        m = self.SCORING["aeo_content"]
        score = 0
        notes = []
        issues = []
        body = self._body_text
        word_count = len(self._words)

        # 1. Kysymyksiä HTML:ssä (laaja havaitseminen)
        q_patterns = [
            r"[A-ZÄÖÅ][^.!?]{8,}\?",            # Iso alkukirjain + ?
            r"\b(Mik[äa]|Miten|Kuinka|Onko|Voiko|Mistä|Kenelle|Milloin)\b[^?]{5,}\?",
        ]
        qs: Set[str] = set()
        for pat in q_patterns:
            qs.update(re.findall(pat, body))

        # 2. Q&A JSON-LD:ssä (laskee myös AEO:ta varten)
        faq_q_count = 0
        for script in self.soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(script.string or "{}")
                items = d.get("@graph", [d]) if isinstance(d, dict) else [d]
                for item in (items if isinstance(items, list) else [items]):
                    if isinstance(item, dict) and item.get("@type") == "FAQPage":
                        entities = item.get("mainEntity", [])
                        faq_q_count += len(entities) if isinstance(entities, list) else 0
            except Exception:
                pass

        total_qs = len(qs) + faq_q_count
        if total_qs >= 4:
            score += 3; notes.append(f"{total_qs} Q&A")
        elif total_qs >= 2:
            score += 2; notes.append(f"{total_qs} kysymystä")
        else:
            issues.append("Lisää Q&A-sisältöä tai FAQPage-skeema")

        # 3. Listat (ul/ol) + taulukot
        lists = self.soup.find_all(["ul", "ol", "table"])
        if len(lists) >= 2:
            score += 2; notes.append(f"{len(lists)} listaa/taulukkoa")
        elif lists:
            score += 1; notes.append(f"{len(lists)} lista")
        else:
            issues.append("Lisää listoja tai taulukoita")

        # 4. Sanamäärä
        if word_count >= 400:
            score += 3; notes.append(f"{word_count} sanaa")
        elif word_count >= 150:
            score += 1; issues.append(f"Lisää tekstiä (nyt {word_count} sanaa)")
        else:
            issues.append(f"Hyvin vähän tekstiä ({word_count} sanaa)")

        status = "pass" if score >= m * 0.7 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("AEO-sisältösignaalit", "AEO & Structured Data",
            min(score, m), m, status,
            ", ".join(notes) if notes else "heikot signaalit",
            " | ".join(issues) if issues else ""))

    # ── Luottamus & laatu ──

    def _authority(self):
        m = self.SCORING["authority"]
        score = 0
        found = []
        missing = []
        body = self._body_text
        all_a = self.soup.find_all("a", href=True)
        hrefs = [a["href"].lower() for a in all_a]
        texts = [a.get_text(strip=True).lower() for a in all_a]
        nav = hrefs + texts

        # Email (2 pts)
        if re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", body) or \
           any(h.startswith("mailto:") for h in hrefs):
            score += 2; found.append("sähköposti")
        else:
            missing.append("sähköpostiosoite")

        # Puhelin (1 pt) — laaja havaitseminen
        phone_patterns = [
            r"\+[\d\s\-]{8,15}",          # +358 xx xxx xxxx
            r"0\d{2}[\s\-]?\d{3}[\s\-]?\d{4}",  # 040 123 4567
            r"tel:",                        # tel: linkit
        ]
        if any(re.search(p, body, re.I) for p in phone_patterns) or \
           any(h.startswith("tel:") for h in hrefs):
            score += 1; found.append("puhelin")
        else:
            missing.append("puhelinnumero")

        # Tietosuoja/privacy (2 pts)
        privacy_kw = ("tietosuoja", "privacy", "gdpr", "tietosuojaseloste", "cookie")
        if any(any(k in n for k in privacy_kw) for n in nav):
            score += 2; found.append("tietosuoja")
        else:
            missing.append("tietosuojasivu")

        # Tietoa meistä / About (1 pt)
        about_kw = ("meistä", "about", "yritys", "tietoa", "tiimi", "team")
        if any(any(k in n for k in about_kw) for n in nav):
            score += 1; found.append("tietoa meistä")
        else:
            missing.append("tietoa meistä")

        # Some-linkit (1 pt) — useampia alustoja
        if any(any(s in h for s in SOCIAL_DOMAINS) for h in hrefs):
            score += 1; found.append("some-linkit")
        else:
            missing.append("some-linkit")

        status = "pass" if score >= m * 0.6 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("Auktoriteetti & luottamus", "Luottamus",
            min(score, m), m, status,
            f"Löytyi: {', '.join(found) if found else '–'}",
            f"Puuttuu: {', '.join(missing)}" if missing else ""))

    def _content_quality(self):
        m = self.SCORING["content_quality"]

        # Paras kappale (ei ensimmäinen — se voi olla nav)
        paragraphs = self.soup.find_all("p")
        content_ps = [p for p in paragraphs
                     if len(p.get_text(strip=True).split()) >= 10
                     and not p.find_parent(["nav", "header"])]
        best_p_words = max((len(p.get_text(strip=True).split()) for p in content_ps), default=0)

        word_count = len(self._words)
        has_strong_para = best_p_words >= 25

        # CTA-tarkistus
        cta_kw = ("varaa", "osta", "tilaa", "lataa", "aloita", "kokeile",
                  "contact", "book", "buy", "start", "download", "learn more")
        has_cta = any(any(k in a.get_text(strip=True).lower() for k in cta_kw)
                     for a in self.soup.find_all("a"))

        score = 0
        notes = []
        if has_strong_para:
            score += 3; notes.append("vahva arvolupaus")
        else:
            notes.append("arvolupaus epäselvä")

        if word_count >= 500:
            score += 3; notes.append(f"{word_count} sanaa")
        elif word_count >= 200:
            score += 2; notes.append(f"{word_count} sanaa")
        else:
            notes.append(f"vain {word_count} sanaa")

        if has_cta:
            score += 1; notes.append("CTA löytyy")

        status = "pass" if score >= m * 0.6 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("Sisällön laatu", "Luottamus", min(score, m), m, status,
            ", ".join(notes),
            "" if score >= m * 0.6 else "Kirjoita vahva arvolupaus (yli 25 sanaa kappaleessa)"))

    def _internal_links(self):
        m = self.SCORING["internal_links"]
        all_a = self.soup.find_all("a", href=True)
        base = urlparse(self.site.url).netloc if self.site.url else ""

        internal = []
        for a in all_a:
            href = a["href"]
            if href.startswith("/") and not href.startswith("//"):
                internal.append(href)
            elif base and base in href:
                internal.append(href)
            elif href.endswith(".html") and not href.startswith("http"):
                internal.append(href)

        # Poista navigaatioduplikaatit (rough)
        unique = list(set(internal))

        if len(unique) >= 3:
            self.checks.append(Check("Sisäiset linkit", "Rakenne", m, m, "pass",
                f"{len(unique)} sisäistä linkkiä"))
        elif len(unique) >= 1:
            self.checks.append(Check("Sisäiset linkit", "Rakenne", m - 1, m, "warn",
                f"Vain {len(unique)} sisäistä linkkiä",
                "Lisää linkkejä muille omille sivuille — parantaa crawlausta"))
        else:
            self.checks.append(Check("Sisäiset linkit", "Rakenne", 0, m, "warn",
                "Ei sisäisiä linkkejä havaittu",
                "Lisää linkkejä muille sivuille"))

    # ── Funnel (V5, klar-consolen WS-F-runbookin mukaan) ──

    def _funnel(self):
        m = self.SCORING["funnel_cta"]
        score = 0
        found, missing = [], []
        all_a = self.soup.find_all("a", href=True)
        hrefs = [a["href"].lower() for a in all_a]

        cta_kw = ("varaa", "osta", "tilaa", "lataa", "aloita", "kokeile",
                  "contact", "book", "buy", "start", "download", "order", "reserve")
        has_cta = any(any(k in a.get_text(strip=True).lower() for k in cta_kw)
                      for a in all_a) or self.soup.find("button") is not None
        if has_cta:
            score += 2; found.append("toimintakehote")
        else:
            missing.append("toimintakehote (CTA)")

        if any(h.startswith("tel:") for h in hrefs):
            score += 2; found.append("soittolinkki")
        else:
            missing.append("soittolinkki (tel:)")

        contact_kw = ("yhteys", "yhteystiedot", "contact")
        has_contact = any(h.startswith("mailto:") for h in hrefs) or \
                      self.soup.find("form") is not None or \
                      any(any(k in (a.get_text(strip=True).lower() + a["href"].lower())
                              for k in contact_kw) for a in all_a)
        if has_contact:
            score += 2; found.append("yhteydenottotapa")
        else:
            missing.append("yhteydenottotapa (sähköposti/lomake)")

        status = "pass" if score >= m * 0.7 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("Toimintapolku (funnel)", "Funnel", score, m, status,
            f"Löytyi: {', '.join(found) if found else '–'}",
            f"Puuttuu: {', '.join(missing)}" if missing else ""))

    KLAR_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    BOOKING_DOMAINS = ("quandoo", "tableonline", "opentable", "resdiary",
                       "thefork", "dinnerbooking", "bookatable")

    def _booking_widget(self):
        """V5: onko ravintolalla oikea varausmekanismi (widget, muu järjestelmä vai pelkkä demo)."""
        m = self.SCORING["booking_widget"]

        widget = None
        for sc in self.soup.find_all("script", src=True):
            if "widget.js" in sc["src"]:
                widget = sc
                break

        if widget is not None:
            src = widget.get("src", "")
            slug = (widget.get("data-restaurant") or "").strip()
            if not src.startswith("http"):
                self.checks.append(Check("Varauswidget", "Funnel", m - 2, m, "warn",
                    f"Widget löytyy, mutta osoite ei ole absoluuttinen: {src}",
                    "Käytä täyttä osoitetta, esim. https://booking.klarsystems.com/widget.js"))
            elif not slug:
                self.checks.append(Check("Varauswidget", "Funnel", m - 2, m, "warn",
                    "Widget löytyy, mutta data-restaurant-tunniste puuttuu",
                    'Lisää script-tagiin data-restaurant="ravintolan-slug"'))
            elif not (self.KLAR_SLUG_RE.fullmatch(slug) and 3 <= len(slug) <= 50):
                self.checks.append(Check("Varauswidget", "Funnel", m - 2, m, "warn",
                    f'Widgetin tunniste "{slug}" ei ole kelvollinen slug',
                    "Slug: pienet kirjaimet, numerot ja viivat; 3–50 merkkiä; ei viivaa alussa/lopussa"))
            else:
                self.checks.append(Check("Varauswidget", "Funnel", m, m, "pass",
                    f"Varauswidget kytketty (slug: {slug})"))
            return

        # Esikatselupohjien feikkilomake: näyttää varaukselta mutta ei tee mitään
        demo = self.soup.find("form", class_="book-form") or \
               self.soup.find("form", onsubmit=re.compile(r"preventDefault", re.I))
        if demo is not None:
            self.checks.append(Check("Varauswidget", "Funnel", 1, m, "warn",
                "Sivulla on varauslomakkeen näköinen DEMO, joka ei oikeasti varaa mitään",
                "Vaihda demolomake oikeaan varauswidgetiin ennen julkaisua"))
            return

        # Muu tunnettu varausjärjestelmä linkitettynä
        for a in self.soup.find_all("a", href=True):
            if any(d in a["href"].lower() for d in self.BOOKING_DOMAINS):
                self.checks.append(Check("Varauswidget", "Funnel", m - 1, m, "pass",
                    "Ulkoinen varausjärjestelmä linkitetty",
                    "Oma varauswidget säästäisi välityspalkkiot"))
                return

        if self.site.accepts_reservations:
            self.checks.append(Check("Varauswidget", "Funnel", 0, m, "warn",
                "Sivu lupaa pöytävarauksen, mutta varausmekanismia ei löydy",
                "Lisää varauswidget tai varauslinkki"))
        else:
            self.checks.append(Check("Varauswidget", "Funnel", 1, m, "warn",
                "Varausmekanismia ei löydy",
                "Jos ravintola ottaa pöytävarauksia, lisää varauswidget; noutopaikalle riittää soittolinkki"))


# ── AI-korjaaja ─────────────────────────────────────────────────────────────

class AIFixer:
    """Sivusto-agnostinen AI-korjaaja. Käyttää SiteContext-tietoja."""

    def __init__(self, html: str, url: str = "", filename: str = "", site: Optional[SiteContext] = None):
        parser = "lxml" if _has_lxml() else "html.parser"
        self.soup = BeautifulSoup(html, parser)
        self.url = url
        self.filename = filename
        self.site = site or SiteContext()
        self.applied: List[str] = []
        # V6: (tarkistuksen nimi, valmis HTML-pätkä) -parit korjauspaketin ohjetta varten
        self.snippets: List[Tuple[str, str]] = []
        self._body_text = self.soup.get_text(" ", strip=True)
        title_tag = self.soup.find("title")
        self._title_text = title_tag.get_text(strip=True) if title_tag else ""

    def fix(self, checks: List[Check]) -> str:
        head = self.soup.find("head")
        if not head:
            return str(self.soup)
        for c in checks:
            if c.auto_fixable and c.status != "pass":
                self._apply(c, head)
        return str(self.soup)

    def _apply(self, c: Check, head):
        dispatch = {
            "Title-tägi":                  lambda h: self._fix_title(h),
            "Meta Description":            self._fix_meta_desc,
            "Open Graph":                  lambda h: self._fix_og(h),
            "Twitter/X Card":              lambda h: self._fix_twitter(h),
            "Canonical-tägi":              lambda h: self._fix_canonical(h),
            "JSON-LD / Structured Data":   lambda h: self._fix_jsonld(h),
            "Ravintolan tiedot (schema)":  lambda h: self._fix_jsonld(h),
            "HTML lang-attribuutti":       lambda h: self._fix_lang(),
        }
        fn = dispatch.get(c.name)
        if fn:
            try:
                fn(head)
            except Exception as e:
                _warn(f"  Korjausvirhe ({c.name}): {e}")

    def _fix_lang(self):
        html_tag = self.soup.find("html")
        if html_tag and not html_tag.get("lang"):
            lang = self.site.lang or "fi"
            html_tag["lang"] = lang
            self.applied.append(f"lang-attribuutti lisätty: {lang}")
            self.snippets.append(("HTML lang-attribuutti", f'<html lang="{lang}">'))

    def _fix_title(self, head):
        """V6: AI kirjoittaa puuttuvan tai parantaa liian lyhyen/pitkän titlen."""
        if not AI_AVAILABLE:
            return
        _info("  AI kirjoittaa titleä...")
        new_title = AIWriter(self.site).title(self._title_text, self._body_text)
        if not new_title:
            return
        tag = self.soup.find("title")
        if tag:
            tag.string = new_title
        else:
            tag = self.soup.new_tag("title")
            tag.string = new_title
            head.insert(0, tag)
        # Myöhemmät korjaukset (meta desc, OG, Twitter) käyttävät uutta titleä
        self._title_text = new_title
        self.applied.append(f"Title kirjoitettu AI:lla ({len(new_title)} mk)")
        self.snippets.append(("Title-tägi", f"<title>{html_mod.escape(new_title)}</title>"))

    def _fix_meta_desc(self, head):
        if not AI_AVAILABLE:
            return
        writer = AIWriter(self.site)
        _info("  AI kirjoittaa meta descriptionia...")
        new_desc = writer.meta_description(self._title_text, self._body_text, self.url)
        if not new_desc:
            return
        existing = self.soup.find("meta", attrs={"name": "description"})
        if existing:
            existing["content"] = new_desc
        else:
            t = self.soup.new_tag("meta", attrs={"name": "description", "content": new_desc})
            head.append(t)
        self.applied.append(f"Meta description kirjoitettu AI:lla ({len(new_desc)} mk)")
        self.snippets.append(("Meta Description",
            f'<meta name="description" content="{html_mod.escape(new_desc, quote=True)}">'))

    def _fix_og(self, head):
        page_url = self._page_url()
        title = self._title_text or self.site.name
        desc_tag = self.soup.find("meta", attrs={"name": "description"})
        desc = (desc_tag.get("content") or "") if desc_tag else ""
        image = self.site.logo_url or (self.site.url.rstrip("/") + "/logo.png" if self.site.url else "")

        props = {
            "og:title":       title,
            "og:description": desc,
            "og:type":        "website",
            "og:url":         page_url,
            "og:image":       image,
            "og:locale":      "fi_FI" if self.site.lang == "fi" else self.site.lang,
        }
        added = []
        snips = []
        for prop, val in props.items():
            if not val:
                continue
            existing = self.soup.find("meta", property=prop)
            if not existing:
                t = self.soup.new_tag("meta")
                t["property"] = prop
                t["content"] = val
                head.append(t)
                added.append(prop)
                snips.append(str(t))
            elif (existing.get("content") or "") in ("/", "", None):
                existing["content"] = val
                added.append(f"{prop}✎")
                snips.append(str(existing))
        if added:
            self.applied.append(f"OG-tagit: {', '.join(added)}")
            self.snippets.append(("Open Graph", "\n".join(snips)))

    def _fix_twitter(self, head):
        title = self._title_text or self.site.name
        desc_tag = self.soup.find("meta", attrs={"name": "description"})
        desc = (desc_tag.get("content") or "")[:200] if desc_tag else ""
        image = self.site.logo_url or ""

        added = []
        snips = []
        for name, content in [
            ("twitter:card",        "summary_large_image"),
            ("twitter:title",       title),
            ("twitter:description", desc),
            ("twitter:image",       image),
        ]:
            if not content:
                continue
            if not self.soup.find("meta", attrs={"name": name}):
                t = self.soup.new_tag("meta")
                t["name"] = name
                t["content"] = content
                head.append(t)
                added.append(name)
                snips.append(str(t))
        if added:
            self.applied.append(f"Twitter Card -tagit lisätty: {', '.join(added)}")
            self.snippets.append(("Twitter/X Card", "\n".join(snips)))

    def _fix_canonical(self, head):
        page_url = self._page_url()
        existing = self.soup.find("link", rel="canonical")
        if not existing:
            t = self.soup.new_tag("link")
            t["rel"] = "canonical"
            t["href"] = page_url
            head.append(t)
            self.applied.append(f"Canonical lisätty: {page_url}")
            self.snippets.append(("Canonical-tägi", str(t)))
        elif (existing.get("href") or "") in ("/", "", None):
            existing["href"] = page_url
            self.applied.append(f"Canonical korjattu: {page_url}")
            self.snippets.append(("Canonical-tägi", str(existing)))

    def _fix_jsonld(self, head):
        # Idempotenssi: jos työkalu on jo generoinut skeeman tälle sivulle
        # eikä sivulla ole enää placeholder-dataa, ei tehdä mitään.
        # V4: vanha työkaluskeema ilman Restaurant-tyyppiä päivitetään ravintoloille.
        own = self.soup.find("script", attrs={"data-aeo-tool": True})
        if own:
            if not self.site.is_restaurant() or "Restaurant" in (own.string or ""):
                return
            own.decompose()  # regeneroidaan ravintolatiedoilla

        writer = AIWriter(self.site)
        schema_type = writer.page_schema_type(self._title_text, self._body_text, self.filename)

        # Jos sivulla on jo aito (ei-placeholder) Organization/WebSite-skeema,
        # ei lisätä duplikaattia — @id-viittaus toimii saman dokumentin sisällä.
        existing_types: Set[str] = set()
        for old in self.soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(old.string or "{}")
                items = d.get("@graph", [d]) if isinstance(d, dict) else (d if isinstance(d, list) else [d])
                for item in items:
                    if isinstance(item, dict) and item.get("name") not in ("Yrityksesi nimi", "Sivuston nimi", "Your Company"):
                        existing_types.add(str(item.get("@type", "")))
            except Exception:
                pass

        page_has_org = bool(existing_types & ({"Organization", "LocalBusiness", "Corporation"}
                                              | RESTAURANT_SCHEMA_TYPES))
        # V4: ravintolalle riittää pelkkä nimi — osoite, puhelin ja aukioloajat
        # ovat arvokkaita ilman sivuston URL:iakin
        can_add_org = self.site.is_complete() or (self.site.is_restaurant() and bool(self.site.name))
        has_org = can_add_org or page_has_org
        graph = []

        if can_add_org and not page_has_org:
            # V4: ravintolalle Restaurant-skeema (LocalBusiness-alityyppi) Organizationin sijaan
            if self.site.is_restaurant():
                graph.append(self.site.restaurant_schema())
                self.applied.append("Restaurant-skeema (aukioloajat, osoite, keittiötyyppi) lisätty")
            else:
                graph.append(self.site.org_schema())
            if "WebSite" not in existing_types and self.site.is_complete():
                graph.append(self.site.website_schema())

        if schema_type == "FAQPage":
            _info("  AI generoi FAQ-pareja...")
            items = writer.faq_items(self._title_text, self._body_text, "FAQ")
            if items:
                graph.append({
                    "@type": "FAQPage",
                    "mainEntity": [
                        {"@type": "Question", "name": i["q"],
                         "acceptedAnswer": {"@type": "Answer", "text": i["a"]}}
                        for i in items
                    ]
                })
                self.applied.append(f"FAQPage-skeema generoitu AI:lla ({len(items)} Q&A)")
            else:
                graph.append({"@type": "FAQPage", "mainEntity": []})

        elif schema_type == "HowTo":
            _info("  AI generoi HowTo-askeleet...")
            steps = writer.howto_steps(self._title_text, self._body_text)
            if steps:
                graph.append({
                    "@type": "HowTo",
                    "name": self._title_text,
                    "description": self._body_text[:200],
                    "step": [
                        {"@type": "HowToStep", "position": i + 1,
                         "name": s.get("name", ""), "text": s.get("text", "")}
                        for i, s in enumerate(steps)
                    ]
                })
                self.applied.append(f"HowTo-skeema generoitu AI:lla ({len(steps)} askelta)")
            else:
                graph.append({"@type": "WebPage", "name": self._title_text, "url": self._page_url()})

        elif schema_type == "Service":
            graph.append({
                "@type": "Service",
                "name": self._title_text,
                "provider": {"@id": "#organization"} if has_org else None,
                "url": self._page_url(),
            })
            self.applied.append("Service-skeema lisätty")

        elif schema_type == "ContactPage":
            graph.append({
                "@type": "ContactPage",
                "name": self._title_text,
                "url": self._page_url(),
                "mainEntity": {"@id": "#organization"} if has_org else None,
            })
            self.applied.append("ContactPage-skeema lisätty")

        elif schema_type == "AboutPage":
            graph.append({
                "@type": "AboutPage",
                "name": self._title_text,
                "url": self._page_url(),
                "publisher": {"@id": "#organization"} if has_org else None,
            })
            self.applied.append("AboutPage-skeema lisätty")

        else:
            graph.append({
                "@type": "WebPage",
                "name": self._title_text,
                "url": self._page_url(),
                "publisher": {"@id": "#organization"} if has_org else None,
            })
            self.applied.append("WebPage-skeema lisätty")

        # Siivoa None- ja tyhjät arvot
        graph = [{k: v for k, v in item.items() if v is not None and v != ""}
                 for item in graph if item]

        new_data = {"@context": "https://schema.org", "@graph": graph}
        new_script = self.soup.new_tag("script", type="application/ld+json")
        new_script["data-aeo-tool"] = VERSION  # merkki: tämän generoi työkalu (idempotenssi)
        new_script.string = "\n" + json.dumps(new_data, indent=2, ensure_ascii=False) + "\n"

        # Poista vanhat placeholders
        for old in self.soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(old.string or "{}")
                items = d.get("@graph", [d]) if isinstance(d, dict) else [d]
                has_ph = any(
                    isinstance(i, dict) and (
                        i.get("name") in ("Yrityksesi nimi", "Sivuston nimi", "Your Company") or
                        i.get("url") == "https://example.com"
                    )
                    for i in items
                )
                if has_ph:
                    old.decompose()
            except Exception:
                pass

        head.append(new_script)
        self.snippets.append(("JSON-LD / Structured Data", str(new_script)))

    def _page_url(self) -> str:
        if self.url:
            return self.url
        if self.site.url and self.filename:
            name = re.sub(r"\.html?$", "", self.filename)
            slug = "" if name == "index" else name
            base = self.site.url.rstrip("/")
            return f"{base}/{slug}" if slug else base + "/"
        return ""


# ── Apufunktiot ─────────────────────────────────────────────────────────────

def _trunc(t: str, n: int) -> str:
    return t if len(t) <= n else t[:n] + "…"

def _has_lxml() -> bool:
    try:
        import lxml
        return True
    except ImportError:
        return False

def scores(checks: List[Check]) -> Tuple[int, int]:
    return sum(c.score for c in checks), sum(c.max_score for c in checks)

def score_pct(checks: List[Check]) -> float:
    s, m = scores(checks)
    return round(s / m * 100, 1) if m else 0.0

def grade(pct: float) -> str:
    for threshold, g in [(92, "A+"), (85, "A"), (75, "B+"), (65, "B"), (55, "C"), (40, "D")]:
        if pct >= threshold:
            return g
    return "F"

def col(pct: float) -> str:
    return "green" if pct >= 75 else ("yellow" if pct >= 50 else "red")

def _info(msg): console.print(f"[dim]{msg}[/dim]") if RICH else print(msg)
def _ok(msg):   console.print(f"[green]{msg}[/green]") if RICH else print(msg)
def _warn(msg): console.print(f"[yellow]⚠ {msg}[/yellow]") if RICH else print(f"VAROITUS: {msg}")
def _err(msg):  console.print(f"[red]{msg}[/red]") if RICH else print(f"VIRHE: {msg}")
def _hdr(msg):  console.print(f"\n[bold blue]{msg}[/bold blue]\n") if RICH else print(f"\n{msg}\n")


def print_results(checks: List[Check], title: str = ""):
    s, mx = scores(checks)
    pct = s / mx * 100 if mx else 0
    if not RICH:
        print(f"\n{'='*55}\n  {title}\n  {s}/{mx} ({pct:.0f}%) – {grade(pct)}\n{'='*55}")
        for c in checks:
            icon = ICONS.get(c.status, "?")
            print(f"  {icon} {c.name}: {c.score}/{c.max_score} — {c.message}")
            if c.suggestion:
                print(f"     → {c.suggestion}")
        return

    c_col = col(pct)
    if title:
        console.print(f"\n[bold]{title}[/bold]")
    console.print(Panel(
        f"[bold {c_col}]{s}/{mx} ({pct:.0f}%) – {grade(pct)}[/bold {c_col}]",
        title="AEO/SEO Score", border_style=c_col))

    cats: Dict[str, List[Check]] = {}
    for ch in checks:
        cats.setdefault(ch.category, []).append(ch)

    for cat, chs in cats.items():
        cs, cm = scores(chs)
        tbl = Table(title=f"{cat}  ({cs}/{cm})", box=box.ROUNDED, min_width=75)
        tbl.add_column("", width=3)
        tbl.add_column("Tarkistus", style="bold", min_width=22)
        tbl.add_column("Tulos", ratio=3)
        tbl.add_column("Pisteet", width=9, justify="right")
        for ch in chs:
            cc = COLORS.get(ch.status, "white")
            tbl.add_row(ICONS.get(ch.status, "?"), ch.name,
                        f"[{cc}]{ch.message}[/{cc}]", f"{ch.score}/{ch.max_score}")
            if ch.suggestion:
                tbl.add_row("", "", f"[dim]→ {ch.suggestion}[/dim]", "")
        console.print(tbl)


def collect_critical_alerts(results: Dict[str, List[Check]]) -> List[str]:
    """V6: kerää sivun kokonaan hakukoneilta piilottavat virheet omaksi
    hälytyslistaksi, joka nostetaan raporttien ja terminaalin kärkeen.
    Taulukkorivit säilyvät ennallaan — tämä on puhdas lisäys."""
    alerts: List[str] = []
    for fname, checks in results.items():
        for c in checks:
            if c.name == "Robots Meta" and c.status == "fail":
                alerts.append(f"{fname} on PIILOSSA hakukoneilta: noindex asetettu "
                              "— sivu ei näy Googlessa eikä tekoälyhauissa")
            elif c.name == "robots.txt" and c.status == "fail":
                alerts.append("robots.txt estää KOKO sivuston hakukoneilta (Disallow: /)")
    return alerts


def recommendations(checks: List[Check]) -> List[str]:
    priority = [
        ("JSON-LD / Structured Data", "Lisää sivuille koneluettava sisältökuvaus (JSON-LD) — sen avulla Google ja tekoälyhaut kuten ChatGPT ymmärtävät, mitä yrityksesi tekee"),
        ("Meta Description",          "Kirjoita jokaiselle sivulle kuvausteksti, jonka Google näyttää hakutuloksissa (120–160 merkkiä)"),
        ("Title-tägi",                "Muotoile sivujen otsikot: 30–60 merkkiä, tärkein hakusana ja yrityksen nimi"),
        ("H1-otsikko",                "Lisää jokaiselle sivulle yksi selkeä pääotsikko"),
        ("Open Graph",                "Lisää some-jakotiedot, jotta linkit näyttävät hyviltä Facebookissa ja LinkedInissä"),
        ("Twitter/X Card",            "Lisää X:n (Twitterin) jakotiedot"),
        ("AEO-sisältösignaalit",      "Lisää sivuille usein kysyttyjä kysymyksiä vastauksineen — tekoälyhaut nostavat tällaista sisältöä esiin"),
        ("Auktoriteetti & luottamus", "Varmista, että yhteystiedot, tietosuojaseloste ja some-linkit löytyvät sivuilta"),
        ("Kuvien alt-tekstit",        "Lisää kuville sanalliset kuvaukset (alt-tekstit)"),
        ("Otsikkorakenne",            "Korjaa väliotsikoiden järjestys loogiseksi — ei hyppyjä tasolta toiselle"),
        ("Canonical-tägi",            "Lisää sivuille ensisijainen osoite (canonical), ettei sama sisältö näy hakukoneille useana kopiona"),
        ("HTML lang-attribuutti",     "Lisää sivuille kielimerkintä, jotta hakukoneet tietävät sisällön kielen"),
        ("Sisäiset linkit",           "Lisää linkkejä omien sivujen välille — helpottaa sekä kävijöitä että hakukoneita"),
    ]
    bad = {c.name for c in checks if c.status != "pass"}
    return [r for n, r in priority if n in bad]


# ── HTML-raporttigeneroija ───────────────────────────────────────────────────

def generate_html_report(
    results: Dict[str, List[Check]],
    site: SiteContext,
    before_results: Optional[Dict[str, List[Check]]] = None,
    fixes_applied: Dict[str, List[str]] = None,
    output_path: Path = None,
    ai_summary: str = "",
) -> Path:
    """Generoi kauniin dark-theme HTML-raportin tuloksista."""

    fixes_applied = fixes_applied or {}
    esc = html_mod.escape  # sivuilta peräisin oleva teksti escapetaan aina
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    site_label = esc(site.name or site.url or "Sivusto")

    total_pages = len(results)
    all_checks = [c for chs in results.values() for c in chs]
    overall_s, overall_m = scores(all_checks)
    overall_pct = overall_s / overall_m * 100 if overall_m else 0
    overall_grade = grade(overall_pct)

    before_pct = 0.0
    if before_results:
        before_checks = [c for chs in before_results.values() for c in chs]
        b_s, b_m = scores(before_checks)
        before_pct = b_s / b_m * 100 if b_m else 0

    total_fixes = sum(len(v) for v in fixes_applied.values())

    # V6: kriittiset hälytykset raportin kärkeen
    critical_alerts = collect_critical_alerts(results)
    alert_banner = ""
    if critical_alerts:
        alert_items = "".join(f"<li>{esc(a)}</li>" for a in critical_alerts)
        alert_banner = f"""
<div class="alert-banner">
  <div class="alert-title">⛔ KRIITTINEN — vaatii välittömän toimenpiteen</div>
  <ul>{alert_items}</ul>
</div>"""

    def score_color(pct: float) -> str:
        if pct >= 85: return "#22c55e"
        if pct >= 70: return "#f59e0b"
        return "#ef4444"

    def bar_html(s: int, mx: int, width: int = 100) -> str:
        pct_val = s / mx * 100 if mx else 0
        c = score_color(pct_val)
        return (f'<div class="bw"><div class="bar" style="width:{min(pct_val,100):.0f}%;'
                f'background:{c}"></div></div>')

    def status_icon(status: str) -> str:
        return {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "?")

    # Per-page rows
    page_rows = ""
    for fname, chs in sorted(results.items()):
        ps, pm = scores(chs)
        ppct = ps / pm * 100 if pm else 0
        pg = grade(ppct)
        pc = score_color(ppct)

        delta_html = ""
        if before_results and fname in before_results:
            bs2, bm2 = scores(before_results[fname])
            bpct2 = bs2 / bm2 * 100 if bm2 else 0
            delta = ppct - bpct2
            d_col = "#4ade80" if delta > 0 else ("#ef4444" if delta < 0 else "#64748b")
            delta_html = f'<span style="color:{d_col};font-weight:700">{delta:+.0f}</span>'

        page_fixes = fixes_applied.get(fname, [])
        fixes_html = "".join(f"<li>✅ {esc(f)}</li>" for f in page_fixes) if page_fixes else "<li style='color:#475569'>Ei muutoksia</li>"

        page_rows += f"""
    <tr>
      <td class="page-name">{esc(fname.replace('.html',''))}<br><span class="filename">{esc(fname)}</span></td>
      <td>
        <div class="sc">
          <span class="sn" style="color:{pc}">{ps}</span>
          {bar_html(ps, pm)}
          <span class="gr" style="color:{pc}">{pg}</span>
        </div>
      </td>
      <td><span class="delta">{delta_html}</span></td>
      <td><ul class="fl">{fixes_html}</ul></td>
    </tr>"""

    # Checks detail per page
    detail_sections = ""
    for fname, chs in sorted(results.items()):
        ps, pm = scores(chs)
        ppct = ps / pm * 100 if pm else 0
        pc = score_color(ppct)
        pg = grade(ppct)

        check_rows = ""
        cats: Dict[str, List[Check]] = {}
        for c in chs:
            cats.setdefault(c.category, []).append(c)

        for cat, cat_chs in cats.items():
            cs2, cm2 = scores(cat_chs)
            check_rows += f'<tr class="cat-row"><td colspan="4">{esc(cat)} ({cs2}/{cm2})</td></tr>'
            for c in cat_chs:
                icon = status_icon(c.status)
                sug = f'<br><span class="sug">→ {esc(c.suggestion)}</span>' if c.suggestion else ""
                pname = plain_name(c.name)
                tech = f'<br><span class="filename">{esc(c.name)}</span>' if pname != c.name else ""
                check_rows += f"""
        <tr>
          <td>{icon}</td>
          <td>{esc(pname)}{tech}</td>
          <td>{esc(c.message)}{sug}</td>
          <td style="text-align:right;font-weight:700">{c.score}/{c.max_score}</td>
        </tr>"""

        detail_sections += f"""
  <div class="page-detail">
    <div class="page-detail-header">
      <span class="page-detail-name">{esc(fname)}</span>
      <span class="score-badge" style="background:{pc}20;border-color:{pc};color:{pc}">{ps}/{pm} · {pg}</span>
    </div>
    <table class="detail-table">
      <thead><tr><th></th><th>Tarkistus</th><th>Tulos</th><th>Pisteet</th></tr></thead>
      <tbody>{check_rows}</tbody>
    </table>
  </div>"""

    # Recommendations
    recs = recommendations(all_checks)
    rec_items = ""
    for i, r in enumerate(recs, 1):
        tag_cls = "r" if i <= 3 else ("y" if i <= 6 else "g")
        pri = "Korkea" if i <= 3 else ("Keskitaso" if i <= 6 else "Matala")
        rec_items += f'<li><span class="tag {tag_cls}">{pri}</span> {esc(r)}</li>'

    # AI:n kirjoittama yhteenveto (jos käytettävissä)
    ai_summary_html = ""
    if ai_summary:
        paras = "".join(f"<p>{esc(p)}</p>" for p in ai_summary.split("\n") if p.strip())
        ai_summary_html = f"""
<div class="sec">
  <div class="sec-t">Yhteenveto ja tärkeimmät toimenpiteet</div>
  <div class="ai-recs">{paras}</div>
</div>"""

    # Sanasto selkokielisistä termeistä
    glossary_rows = "".join(
        f"<tr><td style='font-weight:600;color:#f1f5f9;white-space:nowrap'>{esc(pn)}</td>"
        f"<td class='filename' style='vertical-align:middle'>{esc(tech)}</td>"
        f"<td>{esc(expl)}</td></tr>"
        for tech, (pn, expl) in PLAIN_FI.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="fi"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AEO/SEO Raportti v{VERSION} — {site_label}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;font-size:14px}}
.hero{{background:linear-gradient(135deg,#1e293b,#0f172a);padding:52px 40px 44px;text-align:center;border-bottom:1px solid #1e293b}}
.hero h1{{font-size:1.8rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}}
.hero .sub{{color:#64748b;font-size:.85rem;margin-bottom:40px}}
.scores{{display:flex;justify-content:center;align-items:center;gap:0;max-width:680px;margin:0 auto 22px}}
.sb{{flex:1;background:#1e293b;border-radius:16px;padding:26px 18px;text-align:center}}
.sb.b{{border:1px solid #334155}}.sb.a{{border:2px solid #22c55e;box-shadow:0 0 24px rgba(34,197,94,.14)}}
.sb .lbl{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:#64748b;margin-bottom:8px}}
.sb .big{{font-size:3.4rem;font-weight:800;line-height:1}}
.sb .grd{{font-size:1.3rem;font-weight:700;margin-top:4px}}
.sb .s2{{font-size:.76rem;color:#64748b;margin-top:4px}}
.arrow{{font-size:2rem;color:#22c55e;padding:0 18px;flex-shrink:0}}
.badges{{display:flex;justify-content:center;gap:10px;flex-wrap:wrap}}
.badge{{font-size:.88rem;font-weight:700;padding:6px 16px;border-radius:99px;display:inline-block}}
.badge.g{{background:#052e16;border:1px solid #22c55e;color:#4ade80}}
.badge.b{{background:#0c1a38;border:1px solid #3b82f6;color:#60a5fa}}
.badge.y{{background:#451a03;border:1px solid #f59e0b;color:#fbbf24}}
.sec{{max-width:1200px;margin:32px auto;padding:0 20px}}
.sec-t{{font-size:.9rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden;border:1px solid #334155}}
th{{background:#0f172a;padding:11px 13px;text-align:left;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;color:#64748b;border-bottom:1px solid #334155}}
td{{padding:13px;border-bottom:1px solid #1a2744;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#243050}}
.cat-row td{{background:#0f172a;color:#64748b;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;padding:8px 13px;font-weight:700}}
.page-name{{font-weight:600;color:#f1f5f9}}
.filename{{font-size:.7rem;color:#475569;font-family:monospace}}
.sc{{display:flex;align-items:center;gap:6px}}
.sn{{font-size:1.2rem;font-weight:800;width:28px;text-align:right;flex-shrink:0}}
.bw{{flex:1;background:#0f172a;border-radius:99px;height:6px;min-width:50px}}
.bar{{height:6px;border-radius:99px}}
.gr{{font-size:.78rem;font-weight:700;width:22px;flex-shrink:0}}
.delta{{font-weight:700;font-size:.9rem}}
.fl{{list-style:none;font-size:.78rem;line-height:1.9;color:#94a3b8;padding:0}}
.sug{{color:#f59e0b;font-size:.75rem}}
.recs{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px}}
.recs ol{{padding-left:18px}}
.recs li{{padding:8px 0;border-bottom:1px solid #1a2744;color:#cbd5e1;font-size:.88rem;line-height:1.5}}
.recs li:last-child{{border-bottom:none}}
.tag{{display:inline-block;font-size:.66rem;font-weight:700;padding:2px 7px;border-radius:4px;margin-right:5px;text-transform:uppercase}}
.tag.r{{background:#450a0a;color:#f87171}}.tag.y{{background:#451a03;color:#fbbf24}}.tag.g{{background:#052e16;color:#4ade80}}
.page-detail{{background:#1e293b;border:1px solid #334155;border-radius:12px;margin-bottom:16px;overflow:hidden}}
.page-detail-header{{padding:14px 18px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;background:#0f172a}}
.page-detail-name{{font-weight:700;color:#f1f5f9}}
.score-badge{{font-size:.8rem;font-weight:700;padding:4px 12px;border-radius:99px;border:1px solid}}
.detail-table{{width:100%;border-collapse:collapse}}
.detail-table td{{padding:11px 13px;border-bottom:1px solid #1a2744;vertical-align:top;font-size:.82rem}}
.detail-table td:last-child{{text-align:right;width:70px}}
.detail-table tr:hover td{{background:#243050}}
.detail-table tr:last-child td{{border-bottom:none}}
.ai-recs{{background:#1e293b;border:1px solid #3b82f6;border-radius:12px;padding:20px;color:#cbd5e1;line-height:1.7;font-size:.9rem}}
footer{{text-align:center;padding:32px;color:#334155;font-size:.72rem;border-top:1px solid #1e293b;margin-top:40px}}
.alert-banner{{background:#450a0a;border-bottom:3px solid #ef4444;padding:20px 40px}}
.alert-banner .alert-title{{color:#f87171;font-weight:800;font-size:1.05rem;margin-bottom:8px}}
.alert-banner ul{{list-style:none;padding:0}}
.alert-banner li{{color:#fecaca;font-size:.92rem;padding:3px 0}}
</style></head><body>
{alert_banner}
<div class="hero">
  <h1>AEO/SEO Auditointi v{VERSION} — {site_label}</h1>
  <p class="sub">
    {now_str} &nbsp;·&nbsp;
    {total_pages} sivua analysoitu &nbsp;·&nbsp;
    {total_fixes} korjausta tehty &nbsp;·&nbsp;
    20 tarkistusta per sivu
  </p>
  <div class="scores">
    {'<div class="sb b"><div class="lbl">Lähtötila</div><div class="big" style="color:' + score_color(before_pct) + '">' + f"{before_pct:.0f}" + '</div><div class="grd" style="color:' + score_color(before_pct) + '">' + grade(before_pct) + '</div><div class="s2">/ 100 — keskiarvo</div></div><div class="arrow">→</div>' if before_results else ""}
    <div class="sb a">
      <div class="lbl">{"Lopputila" if before_results else "Nykyinen tila"}</div>
      <div class="big" style="color:{score_color(overall_pct)}">{overall_pct:.0f}</div>
      <div class="grd" style="color:{score_color(overall_pct)}">{overall_grade}</div>
      <div class="s2">/ 100 — keskiarvo {total_pages} sivua</div>
    </div>
  </div>
  <div class="badges">
    {f'<span class="badge g">+{overall_pct - before_pct:.0f} pistettä parannus</span>' if before_results and overall_pct > before_pct else ""}
    <span class="badge b">{total_pages} sivua analysoitu</span>
    <span class="badge {'g' if total_fixes else 'y'}">{total_fixes} korjausta tehty</span>
    <span class="badge {'g' if overall_pct >= 85 else 'y'}">{"Tavoite saavutettu ✅" if overall_pct >= 80 else "Tarvitsee parannuksia"}</span>
  </div>
</div>

<div class="sec">
  <div class="sec-t">Mitä tämä raportti kertoo</div>
  <div class="recs" style="line-height:1.7;font-size:.9rem;color:#cbd5e1">
    <p>Tämä raportti arvioi, kuinka hyvin sivustosi löytyy Googlesta ja tekoälyhauista
    (esimerkiksi ChatGPT ja Perplexity). Jokainen sivu on pisteytetty asteikolla 0–100
    viidentoista tarkistuksen perusteella.</p>
    <p style="margin-top:10px"><strong style="color:#4ade80">85–100</strong> = erinomaisessa kunnossa &nbsp;·&nbsp;
    <strong style="color:#fbbf24">65–84</strong> = hyvä, pieniä parannuksia &nbsp;·&nbsp;
    <strong style="color:#f87171">alle 65</strong> = vaatii toimenpiteitä</p>
    <p style="margin-top:10px">Osa puutteista on korjattu automaattisesti tässä ajossa
    (näkyvät sarakkeessa &quot;Korjaukset&quot;). Loput löytyvät kohdasta
    &quot;Seuraavat toimenpiteet&quot; tärkeysjärjestyksessä.</p>
  </div>
</div>
{ai_summary_html}
<div class="sec">
  <div class="sec-t">Sivukohtainen yhteenveto</div>
  <table>
    <thead><tr>
      <th>Sivu</th>
      <th>Pisteet</th>
      <th>Δ</th>
      <th>Korjaukset tässä ajossa</th>
    </tr></thead>
    <tbody>{page_rows}</tbody>
  </table>
</div>

<div class="sec">
  <div class="sec-t">Seuraavat toimenpiteet (prioriteettijärjestyksessä)</div>
  <div class="recs"><ol>{rec_items}</ol></div>
</div>

<div class="sec">
  <div class="sec-t">Sivukohtaiset tarkistukset</div>
  {detail_sections}
</div>

<div class="sec">
  <div class="sec-t">Sanasto — mitä tarkistukset tarkoittavat</div>
  <table>
    <thead><tr><th>Tarkistus</th><th>Tekninen termi</th><th>Selitys</th></tr></thead>
    <tbody>{glossary_rows}</tbody>
  </table>
</div>

<footer>
  AEO/SEO Audit Tool v{VERSION} &nbsp;·&nbsp; {site_label} &nbsp;·&nbsp; {now_str}<br>
  {esc(COSTS.summary())}
</footer>
</body></html>"""

    if output_path is None:
        output_path = Path("./reports")
    output_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]", "_", site_label)[:30]
    out_file = output_path / f"audit_v6_{safe}_{ts}.html"
    out_file.write_text(html, encoding="utf-8")
    return out_file


# ── Raporttien tallennus ─────────────────────────────────────────────────────

def save_reports(
    target: str,
    target_type: str,
    results: Dict[str, List[Check]],
    before: Optional[Dict[str, List[Check]]],
    fixes: Dict[str, List[str]],
    site: SiteContext,
    out: Path,
    ai_summary: str = "",
):
    ts_label = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    ts_file  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]", "_", target)[:35]

    all_checks = [c for chs in results.values() for c in chs]
    s, m = scores(all_checks)
    pct = round(s / m * 100, 1) if m else 0

    before_pct = None
    if before:
        bc = [c for chs in before.values() for c in chs]
        bs, bm = scores(bc)
        before_pct = round(bs / bm * 100, 1) if bm else None

    all_fixes = [f"{pg}: {fix}" for pg, fl in fixes.items() for fix in fl]

    # V6: kriittiset hälytykset terminaaliin ja raportteihin
    critical_alerts = collect_critical_alerts(results)
    if critical_alerts:
        if RICH:
            console.print(Panel(
                "\n".join(f"⛔ {a}" for a in critical_alerts),
                title="KRIITTINEN — vaatii välittömän toimenpiteen",
                border_style="red", style="bold red"))
        else:
            print("\n=== KRIITTINEN ===")
            for a in critical_alerts:
                print(f"  ⛔ {a}")

    # JSON
    json_path = out / f"audit_v6_{safe}_{ts_file}.json"
    json_path.write_text(json.dumps({
        "tool_version": VERSION,
        "target": target,
        "target_type": target_type,
        "timestamp": ts_label,
        "site": {"name": site.name, "url": site.url, "email": site.email},
        "overall_score": pct,
        "before_score": before_pct,
        "critical_alerts": critical_alerts,
        "pages": {
            fname: {
                "score": score_pct(chs),
                "grade": grade(score_pct(chs)),
                "checks": [{"name": c.name, "category": c.category,
                            "score": c.score, "max": c.max_score,
                            "status": c.status, "message": c.message} for c in chs]
            }
            for fname, chs in results.items()
        },
        "fixes_applied": all_fixes,
        "recommendations": recommendations(all_checks),
        "ai_summary": ai_summary or None,
        "ai_usage": COSTS.as_dict(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown
    md_path = out / f"audit_v6_{safe}_{ts_file}.md"
    recs = recommendations(all_checks)
    md_esc = lambda t: str(t).replace("|", "\\|")
    lines = [f"# AEO/SEO Raportti v{VERSION} — {target}", ""]
    if critical_alerts:
        lines += ["## ⛔ KRIITTISET HÄLYTYKSET", ""]
        lines += [f"- **{a}**" for a in critical_alerts]
        lines += [""]
    lines += [f"**Päiväys:** {ts_label}  ",
             f"**Sivusto:** {site.name} ({site.url})  ",
             f"**Kokonaistulos:** {pct:.0f}/100 — {grade(pct)}  ",
             f"**Ennen:** {before_pct:.0f}/100  " if before_pct is not None else "",
             "", "---", "", "## Sivukohtaiset pisteet", ""]
    for fname, chs in sorted(results.items()):
        p = score_pct(chs)
        lines.append(f"- **{fname}**: {p:.0f}/100 ({grade(p)})")
    # Tarkistuskohtaiset taulukot sivuittain
    for fname, chs in sorted(results.items()):
        p = score_pct(chs)
        lines += ["", f"### {fname} — {p:.0f}/100 ({grade(p)})", "",
                  "| | Tarkistus | Pisteet | Tulos |",
                  "|---|-----------|---------|-------|"]
        for c in chs:
            lines.append(f"| {ICONS.get(c.status, '?').strip()} | {md_esc(plain_name(c.name))} "
                         f"| {c.score}/{c.max_score} | {md_esc(c.message)} |")
    if ai_summary:
        lines += ["", "## Yhteenveto ja tärkeimmät toimenpiteet", "", ai_summary]
    if all_fixes:
        lines += ["", "## Tehdyt korjaukset", ""]
        for f in all_fixes:
            lines.append(f"- ✅ {f}")
    if recs:
        lines += ["", "## Seuraavat toimenpiteet", ""]
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r}")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # HTML
    html_path = generate_html_report(results, site, before, fixes, out, ai_summary=ai_summary)

    if RICH:
        console.print(f"\n[bold green]Raportit tallennettu:[/bold green]")
        console.print(f"  📊 {json_path}")
        console.print(f"  📄 {md_path}")
        console.print(f"  🌐 {html_path}")
    else:
        print(f"\nRaportit:\n  {json_path}\n  {md_path}\n  {html_path}")

    return html_path



# ── V5: Klar-yhteensopiva vienti (klar-consolen WS-F SeoResult-muoto) ────────
# Muoto: docs/specs/ws-f-seo-ads.md — SeoResult { url, score, findings },
# findings[].severity ∈ info|warn|critical. Tallennus seo_runs-tauluun tehdään
# Klarin puolella ohuella TS-kerroksella (governedWrite) — tämä vienti on
# puhdasta analyysia, ei sisällöntuotantoa.

KLAR_KINDS = {
    "Title-tägi": "title",
    "Meta Description": "meta-description",
    "Canonical-tägi": "canonical",
    "Robots Meta": "robots-meta",
    "HTML lang-attribuutti": "html-lang",
    "H1-otsikko": "h1",
    "Otsikkorakenne": "heading-hierarchy",
    "Kuvien alt-tekstit": "img-alt",
    "Open Graph": "open-graph",
    "Twitter/X Card": "twitter-card",
    "JSON-LD / Structured Data": "structured-data",
    "Ravintolan tiedot (schema)": "restaurant-schema",
    "AEO-sisältösignaalit": "aeo-content",
    "Auktoriteetti & luottamus": "trust-signals",
    "Sisällön laatu": "content-quality",
    "Sisäiset linkit": "internal-links",
    "robots.txt": "robots-txt",
    "sitemap.xml": "sitemap",
    "llms.txt": "llms-txt",
    "Toimintapolku (funnel)": "funnel-cta",
    "Varauswidget": "booking-widget",
    # V6: julkaisukunto
    "Oma domain": "preview-domain",
    "AI-bottien pääsy": "ai-bot-access",
}
KLAR_DIMENSIONS = {
    "Tekninen SEO": "onPage", "Sivun rakenne": "onPage", "Sosiaalinen SEO": "onPage",
    "Luottamus": "onPage", "Rakenne": "onPage",
    "AEO & Structured Data": "aeo",
    "Funnel": "funnel",
}


def _fname_to_url(fname: str, base: str) -> str:
    name = re.sub(r"\.html?$", "", fname)
    return (base + "/") if name == "index" else f"{base}/{name}"


def _klar_dimension(c: Check) -> str:
    if c.category == "Sivustotason tiedostot":
        return "aeo" if c.name == "llms.txt" else "onPage"
    if c.category == "Julkaisukunto":
        return "aeo" if c.name == "AI-bottien pääsy" else "onPage"
    return KLAR_DIMENSIONS.get(c.category, "onPage")


def export_klar_json(target: str, results: Dict[str, List[Check]],
                     page_urls: Dict[str, str], out: Path) -> Path:
    """Kirjoittaa SeoResult-listan (yksi per sivu; sivustotason tarkistukset
    liitetään ensimmäiseen sivuun)."""
    site_checks = results.get(SITE_PSEUDO_PAGE, [])
    seo_results = []
    for fname, checks in results.items():
        if fname == SITE_PSEUDO_PAGE:
            continue
        combined = list(checks) + (site_checks if not seo_results else [])
        dims: Dict[str, List[Tuple[int, int]]] = {}
        findings = []
        for c in combined:
            dims.setdefault(_klar_dimension(c), []).append((c.score, c.max_score))
            if c.status != "pass":
                kind = KLAR_KINDS.get(c.name) or re.sub(r"[^a-z0-9]+", "-", c.name.lower()).strip("-")
                f = {"kind": kind,
                     "severity": "critical" if c.status == "fail" else "warn",
                     "message": c.message}
                if c.suggestion:
                    f["fix"] = c.suggestion
                findings.append(f)
        score = {d: round(sum(sc for sc, _ in v) / max(1, sum(mx for _, mx in v)) * 100)
                 for d, v in sorted(dims.items())}
        seo_results.append({"url": page_urls.get(fname, fname),
                            "score": score, "findings": findings})
    ts_file = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]", "_", target)[:35]
    path = out / f"klar_seoresult_{safe}_{ts_file}.json"
    path.write_text(json.dumps(seo_results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── Cross-page analyysi ──────────────────────────────────────────────────────

def cross_page_warnings(html_map: Dict[str, str]) -> List[str]:
    """Havaitsee ristiriitoja/duplikaatteja sivujen välillä."""
    warnings = []
    titles: Dict[str, str] = {}
    descs: Dict[str, str] = {}
    parser = "lxml" if _has_lxml() else "html.parser"

    for fname, html in html_map.items():
        soup = BeautifulSoup(html, parser)
        t = soup.find("title")
        d = soup.find("meta", attrs={"name": "description"})
        if t:
            txt = t.get_text(strip=True)
            if txt in titles.values():
                orig = [k for k, v in titles.items() if v == txt]
                warnings.append(f"Duplikaatti title: '{_trunc(txt, 40)}' ({fname} == {orig[0]})")
            titles[fname] = txt
        if d:
            txt = (d.get("content") or "").strip()
            if txt and txt in descs.values():
                orig = [k for k, v in descs.items() if v == txt]
                warnings.append(f"Duplikaatti meta description ({fname} == {orig[0]})")
            if txt:
                descs[fname] = txt

    return warnings


# ── V4: Sivustotason tiedostot (robots.txt, sitemap.xml, llms.txt) ──────────

SITE_PSEUDO_PAGE = "sivusto (yleiset)"


def _fetch_optional(url: str) -> Optional[str]:
    """Hakee valinnaisen tiedoston verkosta — None jos ei löydy (404 ei ole virhe)."""
    try:
        resp = requests.get(url, headers={"User-Agent": f"AEOSEOAuditBot/{VERSION}"}, timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            return resp.text
    except requests.RequestException:
        pass
    return None


def evaluate_site_files(robots: Optional[str], sitemap: Optional[str],
                        llms: Optional[str]) -> List[Check]:
    """Pisteyttää sivustotason tiedostot. Sisältö annetaan merkkijonoina (None = puuttuu)."""
    cat = "Sivustotason tiedostot"
    checks: List[Check] = []

    # robots.txt (max 3)
    if robots is None:
        checks.append(Check("robots.txt", cat, 1, 3, "warn",
            "robots.txt puuttuu — hakukoneet lukevat silti kaiken, mutta sivukarttaviittaus jää puuttumaan",
            "Luodaan --fix-lipulla", "", auto_fixable=True))
    else:
        lines = [l.strip().lower() for l in robots.splitlines()]
        blocks_all = any(l.startswith("disallow:") and l.split(":", 1)[1].strip() == "/"
                         for l in lines)
        has_sitemap_ref = any(l.startswith("sitemap:") for l in lines)
        if blocks_all:
            checks.append(Check("robots.txt", cat, 0, 3, "fail",
                "VAROITUS: robots.txt estää koko sivuston (Disallow: /)",
                "Poista Disallow: / -rivi, jos sivuston kuuluu näkyä hakukoneissa"))
        elif has_sitemap_ref:
            checks.append(Check("robots.txt", cat, 3, 3, "pass",
                "robots.txt kunnossa, viittaa sivukarttaan"))
        else:
            checks.append(Check("robots.txt", cat, 2, 3, "warn",
                "robots.txt löytyy, mutta Sitemap-viittaus puuttuu",
                "Lisätään Sitemap-rivi --fix-lipulla", "", auto_fixable=True))

    # sitemap.xml (max 4)
    if sitemap is None:
        checks.append(Check("sitemap.xml", cat, 0, 4, "fail",
            "sitemap.xml puuttuu — Google ei välttämättä löydä kaikkia sivuja",
            "Luodaan sivuston sivuista --fix-lipulla", "", auto_fixable=True))
    else:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(sitemap.strip())
            n_urls = len([e for e in root.iter() if e.tag.endswith("loc")])
            checks.append(Check("sitemap.xml", cat, 4, 4, "pass",
                f"Sivukartta löytyy ({n_urls} URL-osoitetta)"))
        except Exception:
            checks.append(Check("sitemap.xml", cat, 1, 4, "warn",
                "sitemap.xml löytyy, mutta ei ole validia XML:ää",
                "Korjaa tiedoston syntaksi tai generoi uusi"))

    # llms.txt (max 3)
    if llms is None:
        checks.append(Check("llms.txt", cat, 0, 3, "warn",
            "llms.txt puuttuu — uusi AEO-tiedosto AI-avustajia varten",
            "Luodaan sivujen sisällöstä --fix-lipulla", "", auto_fixable=True))
    else:
        checks.append(Check("llms.txt", cat, 3, 3, "pass",
            f"llms.txt löytyy ({len(llms)} merkkiä)"))

    return checks


# ── V6: Julkaisukunto-tarkistukset ──────────────────────────────────────────

PREVIEW_DOMAINS = (".vercel.app", ".netlify.app", ".pages.dev", ".github.io")
AI_BOTS = ("GPTBot", "ClaudeBot", "PerplexityBot")


def _blocked_ai_bots(robots: Optional[str]) -> List[str]:
    """Jäsentää robots.txt:n User-agent-ryhmät ja palauttaa estetyt AI-botit.
    Botti on estetty, jos sitä (tai *-ryhmää, ellei botilla ole omaa ryhmää)
    koskee Disallow: / eikä Allow: / kumoa sitä."""
    if not robots:
        return []
    groups: List[Tuple[List[str], List[Tuple[str, str]]]] = []
    agents: List[str] = []
    rules: List[Tuple[str, str]] = []
    for raw in robots.splitlines():
        line = raw.split("#")[0].strip()
        if not line or ":" not in line:
            continue
        key, val = [x.strip() for x in line.split(":", 1)]
        k = key.lower()
        if k == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(val)
        elif k in ("disallow", "allow"):
            rules.append((k, val))
    if agents or rules:
        groups.append((agents, rules))

    blocked = []
    for bot in AI_BOTS:
        grp = next((g for g in groups
                    if any(a.lower() == bot.lower() for a in g[0])), None)
        if grp is None:
            grp = next((g for g in groups if "*" in g[0]), None)
        if grp is None:
            continue
        dis_all = any(k == "disallow" and v == "/" for k, v in grp[1])
        allow_root = any(k == "allow" and v == "/" for k, v in grp[1])
        if dis_all and not allow_root:
            blocked.append(bot)
    return blocked


def publish_readiness_checks(base_url: str, robots: Optional[str]) -> List[Check]:
    """V6: onko sivusto julkaisukunnossa — oma domain ja AI-bottien pääsy.
    Puhdas funktio: sisällöt annetaan parametreina (testattavuus ilman verkkoa).
    Ei auto-korjauksia: AI-bottien esto voi olla tietoinen valinta."""
    cat = "Julkaisukunto"
    checks: List[Check] = []

    # 1. Esikatseludomain vs. oma domain (max 3)
    netloc = urlparse(base_url).netloc.lower() if base_url else ""
    if not netloc:
        checks.append(Check("Oma domain", cat, 3, 3, "pass",
            "Ei arvioitavissa paikallisesti — anna --site-url tarkistaaksesi"))
    elif any(netloc.endswith(d) for d in PREVIEW_DOMAINS):
        checks.append(Check("Oma domain", cat, 1, 3, "warn",
            f"Sivusto on esikatseludomainilla ({netloc}) — oma domain puuttuu",
            "Kytke oma domain ennen julkaisua — esikatseluosoitteelle kertynyt "
            "näkyvyys ei siirry omalle domainille"))
    else:
        checks.append(Check("Oma domain", cat, 3, 3, "pass",
            f"Oma domain käytössä ({netloc})"))

    # 2. AI-bottien pääsy robots.txt:ssä (max 3) — vain varoitus, ei korjausta
    blocked = _blocked_ai_bots(robots)
    if robots is None:
        checks.append(Check("AI-bottien pääsy", cat, 3, 3, "pass",
            "Ei estoja — AI-avustajat (GPTBot, ClaudeBot, PerplexityBot) pääsevät sivustolle"))
    elif blocked:
        checks.append(Check("AI-bottien pääsy", cat, 1, 3, "warn",
            f"robots.txt estää AI-botit: {', '.join(blocked)}",
            "Estetyt AI-avustajat eivät voi lukea sivustoa eivätkä suositella sitä "
            "tekoälyhauissa — poista estot, jos esto ei ole tietoinen valinta"))
    else:
        checks.append(Check("AI-bottien pääsy", cat, 3, 3, "pass",
            "AI-avustajat (GPTBot, ClaudeBot, PerplexityBot) pääsevät sivustolle"))

    return checks


def site_file_checks_repo(repo: Path) -> List[Check]:
    def read(name: str) -> Optional[str]:
        p = repo / name
        try:
            return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else None
        except OSError:
            return None
    return evaluate_site_files(read("robots.txt"), read("sitemap.xml"), read("llms.txt"))


def site_file_checks_url(base_url: str) -> List[Check]:
    base = base_url.rstrip("/")
    return evaluate_site_files(
        _fetch_optional(f"{base}/robots.txt"),
        _fetch_optional(f"{base}/sitemap.xml"),
        _fetch_optional(f"{base}/llms.txt"),
    )


def generate_site_files(dest: Path, site: SiteContext, html_map: Dict[str, str],
                        checks: List[Check]) -> List[str]:
    """Luo puuttuvat sivustotason tiedostot dest-hakemistoon. Palauttaa kuvaukset tehdyistä."""
    applied: List[str] = []
    base = site.url.rstrip("/") if site.url else ""
    by_name = {c.name: c for c in checks}
    parser = "lxml" if _has_lxml() else "html.parser"
    dest.mkdir(parents=True, exist_ok=True)

    def page_url(fname: str) -> str:
        name = re.sub(r"\.html?$", "", fname)
        return base + "/" if name == "index" else f"{base}/{name}"

    # Otsikot ja kuvaukset llms.txt:tä varten
    page_meta: Dict[str, Tuple[str, str]] = {}
    for fname, html in sorted(html_map.items()):
        soup = BeautifulSoup(html, parser)
        t = soup.find("title")
        d = soup.find("meta", attrs={"name": "description"})
        page_meta[fname] = (
            t.get_text(strip=True) if t else fname,
            (d.get("content") or "").strip() if d else "",
        )

    # sitemap.xml
    sm_check = by_name.get("sitemap.xml")
    if sm_check and sm_check.status != "pass" and sm_check.auto_fixable:
        if not base:
            _warn("sitemap.xml: sivuston URL ei tiedossa (--site-url) — ohitetaan")
        elif not (dest / "sitemap.xml").exists():
            today = datetime.date.today().isoformat()
            entries = "\n".join(
                f"  <url>\n    <loc>{html_mod.escape(page_url(f))}</loc>\n"
                f"    <lastmod>{today}</lastmod>\n  </url>"
                for f in sorted(html_map))
            (dest / "sitemap.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f"{entries}\n</urlset>\n", encoding="utf-8")
            applied.append(f"sitemap.xml luotu ({len(html_map)} sivua)")

    # robots.txt: luo puuttuva tai lisää Sitemap-rivi olemassa olevaan
    rb_check = by_name.get("robots.txt")
    if rb_check and rb_check.status != "pass" and rb_check.auto_fixable:
        rb_path = dest / "robots.txt"
        sitemap_line = f"Sitemap: {base}/sitemap.xml\n" if base else ""
        if not rb_path.exists():
            rb_path.write_text(f"User-agent: *\nAllow: /\n\n{sitemap_line}", encoding="utf-8")
            applied.append("robots.txt luotu (sallii hakukoneet" +
                           (", viittaa sivukarttaan)" if sitemap_line else ")"))
        elif sitemap_line:
            content = rb_path.read_text(encoding="utf-8", errors="ignore")
            if "sitemap:" not in content.lower():
                rb_path.write_text(content.rstrip("\n") + "\n\n" + sitemap_line, encoding="utf-8")
                applied.append("robots.txt: Sitemap-viittaus lisätty")

    # llms.txt
    ll_check = by_name.get("llms.txt")
    if ll_check and ll_check.status != "pass" and ll_check.auto_fixable \
            and not (dest / "llms.txt").exists():
        site_desc = next((d for _, (_, d) in sorted(page_meta.items()) if d), "")
        lines = [f"# {site.name or base or 'Sivusto'}", ""]
        if site_desc:
            lines += [f"> {site_desc}", ""]
        if site.is_restaurant():
            facts = [("Osoite", site.address), ("Puhelin", site.phone),
                     ("Aukioloajat", ", ".join(site.opening_hours)),
                     ("Keittiö", site.cuisine)]
            fact_lines = [f"- {k}: {v}" for k, v in facts if v]
            if fact_lines:
                lines += ["## Perustiedot", ""] + fact_lines + [""]
        lines += ["## Sivut", ""]
        for fname, (title, desc) in sorted(page_meta.items()):
            u = page_url(fname) if base else fname
            lines.append(f"- [{title}]({u})" + (f": {desc}" if desc else ""))
        (dest / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        applied.append(f"llms.txt luotu ({len(page_meta)} sivun kuvaus)")

    return applied


# ── V6: Asiakaskohtainen korjauspaketti (--fix-guide) ───────────────────────

PLATFORM_LABELS = {
    "wordpress": "WordPress", "wix": "Wix", "squarespace": "Squarespace",
    "generic": "Yleinen (HTML)",
}

# Per alusta: "overrides" = tarkistuskohtainen ohje, "head" = oletus head-pätkille,
# "files" = juurihakemistotiedostojen ohje.
PLATFORM_GUIDES = {
    "wordpress": {
        "overrides": {
            "Title-tägi": "Avaa sivu muokkaukseen ja kirjoita otsikko SEO-lisäosan "
                "(Yoast SEO tai Rank Math) SEO title -kenttään. Liitä pelkkä otsikkoteksti "
                "ilman <title>-tageja.",
            "Meta Description": "Avaa sivu muokkaukseen ja liitä teksti SEO-lisäosan "
                "(Yoast SEO tai Rank Math) Meta description -kenttään. Liitä pelkkä "
                "teksti ilman <meta>-tagia.",
        },
        "head": "Liitä pätkä sivuston <head>-osioon: helpoiten WPCode- tai "
            "\"Insert Headers and Footers\" -lisäosalla (Header-kenttä). Vaihtoehtoisesti "
            "Ulkoasu → Teemaeditori → header.php, ennen </head>-riviä — ota ensin "
            "varmuuskopio tiedostosta.",
        "files": "Lataa tiedostot sivuston juurihakemistoon (sama kansio, jossa "
            "wp-config.php on) FTP:llä tai webhotellin tiedostonhallinnalla. "
            "robots.txt:n voi vaihtoehtoisesti hallita SEO-lisäosan työkaluista.",
    },
    "wix": {
        "overrides": {
            "Title-tägi": "Wixin hallintapaneeli → Marketing & SEO → SEO-asetukset → "
                "valitse sivu → Title tag -kenttä. Liitä pelkkä otsikkoteksti.",
            "Meta Description": "Wixin hallintapaneeli → Marketing & SEO → SEO-asetukset → "
                "valitse sivu → Meta description -kenttä. Liitä pelkkä teksti.",
        },
        "head": "Wixin hallintapaneeli → Settings → Custom Code → Add Custom Code → "
            "liitä pätkä, sijoitukseksi Head, ja valitse sivut joita se koskee.",
        "files": "Wix ei salli tiedostojen latausta juurihakemistoon. robots.txt: "
            "Marketing & SEO → SEO-asetukset → robots.txt-editori. Sivukartan Wix luo "
            "automaattisesti (/sitemap.xml). llms.txt:n sisällön voi julkaista "
            "tavallisena sivuna (esim. osoitteessa /llms).",
    },
    "squarespace": {
        "overrides": {
            "Title-tägi": "Squarespacessa: sivun asetukset (hammasratas) → SEO-välilehti → "
                "SEO Title -kenttä. Liitä pelkkä otsikkoteksti.",
            "Meta Description": "Squarespacessa: sivun asetukset (hammasratas) → "
                "SEO-välilehti → SEO Description -kenttä. Liitä pelkkä teksti.",
        },
        "head": "Squarespacessa: Settings → Advanced → Code Injection → Header-kenttä. "
            "Sivukohtaiset pätkät: sivun asetukset → Advanced → Page Header Code Injection.",
        "files": "Squarespace ei salli tiedostoja juurihakemistoon: sivukartta syntyy "
            "automaattisesti eikä robots.txt:tä voi muokata. llms.txt:n sisällön voi "
            "julkaista tavallisena sivuna.",
    },
    "generic": {
        "overrides": {},
        "head": "Avaa sivun HTML-tiedosto ja liitä pätkä <head>-osion sisään ennen "
            "</head>-riviä. Nopein tapa: korvaa koko sivu tämän paketin "
            "korjatut-sivut-kansion valmiilla kopiolla.",
        "files": "Lataa tiedostot palvelimen juurihakemistoon (sama taso kuin etusivun "
            "index.html) FTP:llä tai hostingin hallintapaneelista.",
    },
}


def generate_fix_guide(
    pkg_dir: Path,
    site: SiteContext,
    platform: str,
    snippets_by_page: Dict[str, List[Tuple[str, str]]],
    page_urls: Dict[str, str],
    site_files_applied: List[str],
    fixed_pages: List[str],
) -> Path:
    """Kirjoittaa korjauspaketin OHJEET.html:n. Vaalea Anglés-tyyli — tämä on
    asiakkaalle luovutettava dokumentti, ei sisäinen raportti."""
    esc = html_mod.escape
    guide = PLATFORM_GUIDES.get(platform, PLATFORM_GUIDES["generic"])
    platform_label = PLATFORM_LABELS.get(platform, platform)
    now_str = datetime.datetime.now().strftime("%d.%m.%Y")
    site_label = esc(site.name or site.url or "Sivusto")
    n_snippets = sum(len(v) for v in snippets_by_page.values())

    def instruction(label: str) -> str:
        return guide["overrides"].get(label, guide["head"])

    # Sivukohtaiset osiot
    page_sections = ""
    for fname, snips in sorted(snippets_by_page.items()):
        if not snips:
            continue
        page_url = page_urls.get(fname, fname)
        blocks = ""
        for label, snippet in snips:
            pname, expl = PLAIN_FI.get(label, (label, ""))
            expl_html = f'<p class="why">{esc(expl)}</p>' if expl else ""
            blocks += f"""
      <div class="fix">
        <h3>{esc(pname)}</h3>
        {expl_html}
        <p class="step"><strong>Näin liität ({esc(platform_label)}):</strong> {esc(instruction(label))}</p>
        <div class="snip">
          <pre>{esc(snippet)}</pre>
          <button class="copy" onclick="cp(this)">Kopioi</button>
        </div>
      </div>"""
        fixed_note = ""
        if fname in fixed_pages:
            fixed_note = (f'<p class="fixed-note">Valmis korjattu kopio tästä sivusta: '
                          f'<code>korjatut-sivut/{esc(fname)}</code></p>')
        page_sections += f"""
    <section class="page">
      <h2>{esc(page_url)}</h2>
      {fixed_note}
      {blocks}
    </section>"""

    # Sivustotiedostot
    files_section = ""
    if site_files_applied:
        items = "".join(f"<li>{esc(f)}</li>" for f in site_files_applied)
        files_section = f"""
    <section class="page">
      <h2>Sivustotason tiedostot</h2>
      <p>Kansiossa <code>sivustotiedostot/</code> ovat valmiit tiedostot:</p>
      <ul>{items}</ul>
      <p class="step"><strong>Näin viet ne ({esc(platform_label)}):</strong> {esc(guide["files"])}</p>
    </section>"""

    checklist = """
    <section class="page">
      <h2>Tarkistuslista lopuksi</h2>
      <ol>
        <li>Avaa sivusto selaimessa ja katso lähdekoodi (Ctrl/Cmd+U) — näkyvätkö lisätyt pätkät?</li>
        <li>Tarkista että <code>robots.txt</code> ja <code>sitemap.xml</code> aukeavat osoitteista /robots.txt ja /sitemap.xml.</li>
        <li>Testaa jaettu linkki esim. Facebookin jakotyökalulla — näkyykö otsikko ja kuva oikein?</li>
        <li>Muutokset näkyvät Googlessa tyypillisesti 1–4 viikon kuluessa.</li>
      </ol>
    </section>"""

    html = f"""<!DOCTYPE html>
<html lang="fi"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Korjausohjeet — {site_label}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,Arial,-apple-system,sans-serif;background:#fff;color:#111;
  font-size:15px;line-height:1.65;max-width:820px;margin:0 auto;padding:40px 24px}}
header{{border-bottom:3px solid #89CFF0;padding-bottom:24px;margin-bottom:32px}}
header h1{{font-size:1.7rem;font-weight:800;margin-bottom:6px}}
.meta{{color:#555;font-size:.88rem}}
.platform-badge{{display:inline-block;background:#89CFF0;color:#111;font-weight:700;
  font-size:.8rem;padding:4px 14px;border-radius:99px;margin-top:10px}}
.intro{{background:#f4fafd;border-left:4px solid #89CFF0;padding:16px 18px;
  margin-bottom:32px;border-radius:0 8px 8px 0}}
section.page{{margin-bottom:40px}}
section.page h2{{font-size:1.15rem;font-weight:700;border-bottom:1px solid #ddd;
  padding-bottom:8px;margin-bottom:16px;word-break:break-all}}
.fix{{margin:0 0 26px 0}}
.fix h3{{font-size:1rem;font-weight:700;margin-bottom:4px}}
.why{{color:#555;font-size:.88rem;margin-bottom:6px}}
.step{{font-size:.9rem;margin-bottom:8px}}
.fixed-note{{font-size:.85rem;color:#555;margin-bottom:14px}}
.snip{{position:relative}}
.snip pre{{background:#f6f6f6;border:1px solid #ddd;border-radius:8px;padding:14px;
  overflow-x:auto;font-size:.8rem;line-height:1.5;font-family:ui-monospace,Menlo,monospace}}
.copy{{position:absolute;top:8px;right:8px;background:#89CFF0;border:none;color:#111;
  font-weight:700;font-size:.75rem;padding:5px 12px;border-radius:6px;cursor:pointer;font-family:inherit}}
.copy:hover{{background:#6dbfe8}}
code{{background:#f6f6f6;border:1px solid #ddd;border-radius:4px;padding:1px 6px;
  font-size:.82rem;font-family:ui-monospace,Menlo,monospace}}
ol,ul{{padding-left:22px}}
li{{margin-bottom:6px}}
footer{{border-top:1px solid #ddd;margin-top:48px;padding-top:18px;color:#555;
  font-size:.82rem;text-align:center}}
footer strong{{color:#111}}
</style></head><body>

<header>
  <h1>Korjausohjeet — {site_label}</h1>
  <div class="meta">{now_str} · {n_snippets} korjausta · {len(fixed_pages)} korjattua sivukopiota</div>
  <div class="platform-badge">Tunnistettu alusta: {esc(platform_label)}</div>
</header>

<div class="intro">
  <p>Tämä paketti sisältää sivustollesi valmiit hakukone- ja tekoälynäkyvyyden
  korjaukset. Jokaisesta korjauksesta on alla valmis pätkä (Kopioi-nappi) ja
  ohje, mihin se liitetään {esc(platform_label)}-alustalla. Kaikki pätkät ovat
  myös valmiina korjatuissa sivukopioissa <code>korjatut-sivut/</code>-kansiossa.</p>
</div>
{page_sections}
{files_section}
{checklist}

<footer>
  Korjauspaketin laati <strong>Anglés Marketing</strong> · {now_str}
</footer>
<script>
function cp(btn){{
  var pre = btn.parentElement.querySelector("pre");
  navigator.clipboard.writeText(pre.textContent).then(function(){{
    btn.textContent = "Kopioitu ✓";
    setTimeout(function(){{ btn.textContent = "Kopioi"; }}, 1500);
  }});
}}
</script>
</body></html>"""

    pkg_dir.mkdir(parents=True, exist_ok=True)
    out_file = pkg_dir / "OHJEET.html"
    out_file.write_text(html, encoding="utf-8")
    return out_file


# ── Repo-ajuri ───────────────────────────────────────────────────────────────

def audit_repo(repo: Path, fix: bool, out: Path, site_args: SiteContext, open_report: bool = True,
               klar_json: bool = False):
    _hdr(f"AEO/SEO Audit v{VERSION} — {repo}")

    if not AI_AVAILABLE:
        _warn("anthropic-paketti puuttuu tai API-avain puuttuu — AI-ominaisuudet pois")
    else:
        _info(f"AI käytössä: claude-haiku-4-5-20251001")

    html_files = sorted([
        f for f in (list(repo.rglob("*.html")) + list(repo.rglob("*.htm")))
        if not SKIP_DIRS.intersection(set(f.parts))
        and not GOOGLE_VERIFY_RE.fullmatch(f.name)
    ])
    if not html_files:
        _warn("HTML-tiedostoja ei löydy"); return

    _info(f"Löytyi {len(html_files)} HTML-tiedostoa")

    # Lue kaikki HTML:t
    html_map: Dict[str, str] = {}
    for f in html_files:
        try:
            html_map[f.name] = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            _warn(f"Ei voitu lukea: {e}")

    # Tunnista sivustokonteksti
    soups = [BeautifulSoup(h, "lxml" if _has_lxml() else "html.parser")
             for h in html_map.values()]
    site = detect_site_context(soups, site_args.url, site_args.name, site_args.email)
    site = merge_cli_site_args(site, site_args)

    if site.name:
        _info(f"Sivusto tunnistettu: {site.name} ({site.url})")
    else:
        _warn("Sivuston nimeä ei tunnistettu — käytä --site-name")

    if site.is_restaurant():
        _info("Sivusto tunnistettu ravintolaksi — Restaurant-schema-tarkistus käytössä")
        if fix:
            all_text = " ".join(s.get_text(" ", strip=True) for s in soups)
            enrich_restaurant_details(site, all_text)

    # Cross-page varoitukset
    xp_warns = cross_page_warnings(html_map)
    if xp_warns:
        console.print("\n[bold yellow]Cross-page varoitukset:[/bold yellow]") if RICH else print("\nVaroitukset:")
        for w in xp_warns:
            _warn(w)

    results: Dict[str, List[Check]] = {}
    before_results: Dict[str, List[Check]] = {}
    fixes_applied: Dict[str, List[str]] = {}

    for f in html_files:
        fname = f.name
        html = html_map.get(fname, "")
        if not html:
            continue

        if RICH:
            console.rule(f"[dim]{fname}[/dim]")
        else:
            print(f"\n{'─'*50}\n{fname}")

        before_checks = PageAuditor(html, file_path=str(f), site=site).run()
        before_results[fname] = before_checks
        print_results(before_checks, fname)

        if fix:
            fixer = AIFixer(html, filename=fname, site=site)
            fixed_html = fixer.fix(before_checks)
            if fixer.applied:
                try:
                    bak = f.with_suffix(f.suffix + ".bak")
                    if not bak.exists():
                        shutil.copy2(f, bak)
                    f.write_text(fixed_html, encoding="utf-8")
                except OSError as e:
                    _warn(f"Ei voitu kirjoittaa {fname}: {e} — sivu ohitettu")
                    results[fname] = before_checks
                    continue
                for msg in fixer.applied:
                    _ok(f"  ✅ {fname}: {msg}")
                fixes_applied[fname] = fixer.applied
                html_map[fname] = fixed_html  # V4: llms.txt käyttää korjattuja kuvauksia
                results[fname] = PageAuditor(fixed_html, file_path=str(f), site=site).run()
                print_results(results[fname], f"{fname} (jälkeen)")
            else:
                results[fname] = before_checks
        else:
            results[fname] = before_checks

    # V4: sivustotason tiedostot (robots.txt, sitemap.xml, llms.txt)
    if RICH:
        console.rule("[dim]sivustotason tiedostot[/dim]")

    def _repo_robots() -> Optional[str]:
        p = repo / "robots.txt"
        try:
            return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else None
        except OSError:
            return None

    # V6: julkaisukunto-tarkistukset samaan pseudosivuun
    site_checks = site_file_checks_repo(repo) + \
        publish_readiness_checks(site.url, _repo_robots())
    before_results[SITE_PSEUDO_PAGE] = site_checks
    if fix:
        applied = generate_site_files(repo, site, html_map, site_checks)
        if applied:
            for msg in applied:
                _ok(f"  ✅ {msg}")
            fixes_applied[SITE_PSEUDO_PAGE] = applied
            site_checks = site_file_checks_repo(repo) + \
                publish_readiness_checks(site.url, _repo_robots())  # uudelleentarkistus
    results[SITE_PSEUDO_PAGE] = site_checks
    print_results(site_checks, "Sivustotason tiedostot")

    # Yhteenveto
    all_checks = [c for chs in results.values() for c in chs]
    ts, tm = scores(all_checks)
    tpct = ts / tm * 100 if tm else 0
    if RICH:
        console.rule("[bold]YHTEENVETO[/bold]")
        c_col = col(tpct)
        console.print(Panel(
            f"[bold {c_col}]{tpct:.0f}/100 – {grade(tpct)}[/bold {c_col}]\n"
            f"Sivuja: {len([k for k in results if k != SITE_PSEUDO_PAGE])} | "
            f"Korjauksia: {sum(len(v) for v in fixes_applied.values())}",
            title="Lopputulos", border_style=c_col))

        # Per-sivu pisteet
        from rich.table import Table as RTable
        t = RTable(box=box.SIMPLE)
        t.add_column("Sivu", style="bold")
        t.add_column("Pisteet", justify="right")
        t.add_column("Arvosana")
        t.add_column("Status")
        for fname, chs in sorted(results.items()):
            p = score_pct(chs)
            g = grade(p)
            c2 = "green" if p >= 80 else ("yellow" if p >= 60 else "red")
            icon = "✅" if p >= 80 else ("⚠️" if p >= 60 else "❌")
            t.add_row(fname, f"[{c2}]{p:.0f}[/{c2}]", f"[{c2}]{g}[/{c2}]", icon)
        console.print(t)

    # AI kirjoittaa selkokielisen yhteenvedon raporttiin
    ai_summary = ""
    if AI_AVAILABLE:
        _info("AI kirjoittaa yhteenvetoa raporttiin...")
        page_scores = {fname: int(score_pct(chs)) for fname, chs in results.items()}
        ai_summary = AIWriter(site).strategic_recs(page_scores)

    html_report = save_reports(
        str(repo), "repo", results,
        before_results if fix else None,
        fixes_applied, site, out,
        ai_summary=ai_summary,
    )

    if klar_json:
        base = site.url.rstrip("/") if site.url else ""
        page_urls = {fn: (_fname_to_url(fn, base) if base else fn)
                     for fn in results if fn != SITE_PSEUDO_PAGE}
        kp = export_klar_json(str(repo), results, page_urls, out)
        _ok(f"Klar SeoResult -vienti: {kp}")

    _info(f"\n{COSTS.summary()}")

    # Avaa HTML-raportti automaattisesti (ellei --no-open)
    if open_report:
        try:
            import subprocess
            subprocess.Popen(["open", str(html_report)])
            _ok(f"\nHTML-raportti avattu selaimessa: {html_report}")
        except OSError:
            pass


# ── URL-ajuri ────────────────────────────────────────────────────────────────

def _fetch_url(url: str, attempts: int = 3) -> str:
    """Hakee sivun HTML:n. Uudelleenyrittää verkko- ja palvelinvirheet (5xx),
    ei asiakasvirheitä (4xx). Selkeät suomenkieliset virheilmoitukset."""
    import time
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": f"AEOSEOAuditBot/{VERSION}"}, timeout=20)
            if resp.status_code >= 500:
                last_error = f"Palvelin vastasi virheellä HTTP {resp.status_code}"
            elif resp.status_code >= 400:
                _err(f"Sivua ei voitu hakea: HTTP {resp.status_code} "
                     f"({'sivua ei löydy' if resp.status_code == 404 else 'pääsy estetty tai virheellinen pyyntö'}) — {url}")
                sys.exit(1)
            else:
                return resp.text
        except requests.exceptions.SSLError:
            _err(f"SSL-varmennevirhe osoitteessa {url} — sivuston varmenne voi olla vanhentunut")
            sys.exit(1)
        except requests.exceptions.Timeout:
            last_error = "Aikakatkaisu (sivu ei vastannut 20 sekunnissa)"
        except requests.exceptions.ConnectionError:
            last_error = "Yhteysvirhe (tarkista osoite ja internet-yhteys)"
        except requests.RequestException as e:
            last_error = str(e)
        if attempt < attempts:
            wait = 2 * attempt
            _warn(f"{last_error} — yritetään uudelleen {wait} s kuluttua ({attempt}/{attempts - 1})")
            time.sleep(wait)
    _err(f"Sivun haku epäonnistui {attempts} yrityksen jälkeen: {last_error} — {url}")
    sys.exit(1)


def _collect_internal_links(soup, base_url: str, limit: int) -> List[str]:
    """V5: kerää sivuston omat alasivulinkit ryömintää varten."""
    from urllib.parse import urljoin
    base_netloc = urlparse(base_url).netloc
    found: List[str] = []
    seen: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absu = urljoin(base_url, href)
        pu = urlparse(absu)
        if pu.scheme not in ("http", "https") or pu.netloc != base_netloc:
            continue
        path = pu.path or "/"
        if re.search(r"\.(png|jpe?g|gif|svg|webp|pdf|zip|css|js|ico|xml|txt|woff2?)$", path, re.I):
            continue
        clean = f"{pu.scheme}://{pu.netloc}{path}"
        if clean.rstrip("/") == base_url.rstrip("/") or clean in seen:
            continue
        seen.add(clean)
        found.append(clean)
        if len(found) >= limit:
            break
    return found


def audit_url(url: str, fix: bool, out: Path, site_args: SiteContext,
              max_pages: int = 10, klar_json: bool = False, fix_guide: bool = False):
    _hdr(f"AEO/SEO Audit v{VERSION} — {url}")
    html = _fetch_url(url)

    parser = "lxml" if _has_lxml() else "html.parser"
    url_soup = BeautifulSoup(html, parser)

    def fname_of(u: str) -> str:
        f = urlparse(u).path.strip("/").replace("/", "_") or "index"
        return re.sub(r"\.html?$", "", f) + ".html"

    # V5: monisivuinen ryömintä — kerätään sivuston omat linkit aloitussivulta
    pages: Dict[str, str] = {fname_of(url): html}
    page_urls: Dict[str, str] = {fname_of(url): url}
    if max_pages > 1:
        import time
        links = _collect_internal_links(url_soup, url, max_pages - 1)
        if links:
            _info(f"Ryömitään {len(links)} alasivua (kohteliaasti 0,5 s välein)...")
        for link in links:
            time.sleep(0.5)
            sub = _fetch_optional(link)
            if sub is None:
                _warn(f"Alasivua ei voitu hakea: {link} — ohitetaan")
                continue
            fn = fname_of(link)
            if fn in pages:
                continue
            pages[fn] = sub
            page_urls[fn] = link

    soups = {fn: BeautifulSoup(h, parser) for fn, h in pages.items()}
    site = detect_site_context(list(soups.values()),
                               site_args.url or url, site_args.name, site_args.email)
    site = merge_cli_site_args(site, site_args)
    if not site.url:
        parsed = urlparse(url)
        site.url = f"{parsed.scheme}://{parsed.netloc}"

    if site.is_restaurant():
        _info("Sivusto tunnistettu ravintolaksi — Restaurant-schema-tarkistus käytössä")
        if fix:
            enrich_restaurant_details(
                site, " ".join(sp.get_text(" ", strip=True) for sp in soups.values()))

    results: Dict[str, List[Check]] = {}
    before_results: Dict[str, List[Check]] = {}
    fixes_applied: Dict[str, List[str]] = {}
    ts_file = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # V6: korjauspaketti — fixed-kopiot ja sivustotiedostot yhteen kansioon + OHJEET.html
    pkg_dir: Optional[Path] = None
    snippets_by_page: Dict[str, List[Tuple[str, str]]] = {}
    fixed_pages: List[str] = []
    if fix_guide:
        safe = re.sub(r"[^\w]", "_", url)[:35]
        pkg_dir = out / f"korjauspaketti_{safe}_{ts_file}"

    for fn, page_html in pages.items():
        if RICH:
            console.rule(f"[dim]{fn}[/dim]")
        else:
            print(f"\n{'─'*50}\n{fn}")

        before_checks = PageAuditor(page_html, url=page_urls[fn], site=site).run()
        before_results[fn] = before_checks
        print_results(before_checks, fn)

        if fix:
            fixer = AIFixer(page_html, url=page_urls[fn], filename=fn, site=site)
            fixed_html = fixer.fix(before_checks)
            if fixer.applied:
                fixes_applied[fn] = fixer.applied
                if pkg_dir is not None:
                    fixed_dir = pkg_dir / "korjatut-sivut"
                    fixed_dir.mkdir(parents=True, exist_ok=True)
                    fixed_path = fixed_dir / fn
                    snippets_by_page[fn] = fixer.snippets
                    fixed_pages.append(fn)
                else:
                    fixed_path = out / f"fixed_v6_{ts_file}_{fn}"
                fixed_path.write_text(fixed_html, encoding="utf-8")
                _ok(f"Korjattu HTML → {fixed_path}")
                results[fn] = PageAuditor(fixed_html, url=page_urls[fn], site=site).run()
                print_results(results[fn], f"{fn} (jälkeen)")
            else:
                results[fn] = before_checks
        else:
            results[fn] = before_checks

    # V4: sivustotason tiedostot (haetaan verkosta sivuston juuresta)
    _info("Tarkistetaan sivustotason tiedostot (robots.txt, sitemap.xml, llms.txt)...")
    base = site.url or f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    base_r = base.rstrip("/")
    robots_txt = _fetch_optional(f"{base_r}/robots.txt")
    site_checks = evaluate_site_files(
        robots_txt,
        _fetch_optional(f"{base_r}/sitemap.xml"),
        _fetch_optional(f"{base_r}/llms.txt"),
    )
    # V6: julkaisukunto — esikatseludomain tarkistetaan auditoidusta URL:sta
    # (ei site.url:sta, joka voi olla sivun itse ilmoittama), robots jaetaan
    site_checks += publish_readiness_checks(url, robots_txt)
    results[SITE_PSEUDO_PAGE] = site_checks
    print_results(site_checks, "Sivustotason tiedostot")
    site_files_applied: List[str] = []
    if fix and any(c.auto_fixable and c.status != "pass" for c in site_checks):
        # URL-tilassa palvelimelle ei voi kirjoittaa — tiedostot luodaan raporttikansioon
        dest = (pkg_dir / "sivustotiedostot") if pkg_dir is not None else (out / "sivustotiedostot")
        applied = generate_site_files(dest, site, pages, site_checks)
        if applied:
            site_files_applied = applied
            fixes_applied[SITE_PSEUDO_PAGE] = [
                f"{msg} → {dest}/ — lataa tiedostot sivuston juureen" for msg in applied]
            for msg in fixes_applied[SITE_PSEUDO_PAGE]:
                _ok(f"  ✅ {msg}")

    # V6: korjauspaketin ohjetiedosto
    if pkg_dir is not None and (snippets_by_page or site_files_applied):
        platform = detect_platform(list(soups.values()))
        _info(f"Tunnistettu alusta: {PLATFORM_LABELS.get(platform, platform)}")
        guide_path = generate_fix_guide(pkg_dir, site, platform, snippets_by_page,
                                        page_urls, site_files_applied, fixed_pages)
        _ok(f"Korjauspaketti: {pkg_dir}/")
        _ok(f"  📋 Ohjeet: {guide_path}")
    elif pkg_dir is not None:
        _info("Ei korjattavaa — korjauspakettia ei luotu")

    ai_summary = ""
    if AI_AVAILABLE:
        _info("AI kirjoittaa yhteenvetoa raporttiin...")
        page_scores = {fn: int(score_pct(chs)) for fn, chs in results.items()}
        ai_summary = AIWriter(site).strategic_recs(page_scores)

    save_reports(url, "url", results,
                 before_results if fix else None,
                 fixes_applied, site, out,
                 ai_summary=ai_summary)

    if klar_json:
        kp = export_klar_json(url, results, page_urls, out)
        _ok(f"Klar SeoResult -vienti: {kp}")

    _info(f"\n{COSTS.summary()}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description=f"AEO/SEO Audit Tool v{VERSION} — toimii mille tahansa sivustolle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Esimerkkejä:
  python aeo_seo_tool_v5.py --repo ./sivusto
  python aeo_seo_tool_v5.py --repo . --fix
  python aeo_seo_tool_v5.py --url https://example.com
  python aeo_seo_tool_v5.py --repo . --fix --site-url https://oma.fi --site-name "Yritys Oy"
  python aeo_seo_tool_v5.py --repo . --fix --restaurant --cuisine "italialainen" \\
      --hours "Mo-Fr 11:00-22:00,Sa 12:00-23:00" --phone "+358 40 123 4567"
  python aeo_seo_tool_v5.py --url https://example.com --max-pages 10 --klar-json
""")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--url",  metavar="URL", help="Auditoitavan sivuston URL")
    g.add_argument("--repo", metavar="POLKU", help="Auditoitavan repositorion polku")
    p.add_argument("--fix",        action="store_true", help="Sovella AI-korjaukset tiedostoihin")
    p.add_argument("--output",     default="./reports",  metavar="HAKEMISTO",
                   help="Raporttihakemisto (oletus: ./reports)")
    p.add_argument("--site-url",   default="", metavar="URL",
                   help="Sivuston base URL (auto-havaitaan jos puuttuu)")
    p.add_argument("--site-name",  default="", metavar="NIMI",
                   help="Sivuston/yrityksen nimi (auto-havaitaan jos puuttuu)")
    p.add_argument("--site-email", default="", metavar="EMAIL",
                   help="Yrityksen sähköpostiosoite")
    p.add_argument("--site-logo",  default="", metavar="URL",
                   help="Logo-kuvan URL")
    # V4: ravintolatiedot (kaikki valinnaisia — auto-tunnistus + AI täydentävät)
    p.add_argument("--restaurant", action="store_true",
                   help="Pakota ravintolatila (yleensä tunnistetaan automaattisesti)")
    p.add_argument("--phone",      default="", metavar="NUMERO",
                   help="Ravintolan puhelinnumero")
    p.add_argument("--address",    default="", metavar="OSOITE",
                   help="Ravintolan katuosoite ja kaupunki")
    p.add_argument("--hours",      default="", metavar="AJAT",
                   help='Aukioloajat pilkuin eroteltuna, esim. "Mo-Fr 11:00-22:00,Sa 12:00-23:00"')
    p.add_argument("--cuisine",    default="", metavar="KEITTIÖ",
                   help='Keittiötyyppi, esim. "italialainen"')
    p.add_argument("--menu-url",   default="", metavar="URL",
                   help="Ruokalistasivun osoite")
    p.add_argument("--no-open",    action="store_true",
                   help="Älä avaa HTML-raporttia automaattisesti selaimessa")
    # V5: ryömintä ja Klar-vienti
    p.add_argument("--max-pages",  type=int, default=10, metavar="N",
                   help="URL-tilassa auditoitavien sivujen enimmäismäärä (oletus 10, 1 = vain annettu sivu)")
    p.add_argument("--klar-json",  action="store_true",
                   help="Tuota lisäksi klar-consolen WS-F-muotoinen SeoResult-JSON")
    # V6: asiakaskohtainen korjauspaketti
    p.add_argument("--fix-guide",  action="store_true",
                   help="URL-tilassa: kokoa korjaukset asiakaskohtaiseksi korjauspaketiksi "
                        "(OHJEET.html + korjatut sivut + sivustotiedostot; sisältää --fix)")
    p.add_argument("--eur-rate",   type=float, default=None, metavar="KURSSI",
                   help=f"USD→EUR-kurssi kustannuslaskentaan (oletus {DEFAULT_USD_EUR}, myös AEO_USD_EUR-ympäristömuuttuja)")

    args = p.parse_args()
    if args.eur_rate:
        COSTS.usd_eur = args.eur_rate
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    site_args = SiteContext(
        url=args.site_url,
        name=args.site_name,
        email=args.site_email,
        logo_url=args.site_logo,
        site_type="restaurant" if args.restaurant else "generic",
        phone=args.phone,
        address=args.address,
        opening_hours=[h.strip() for h in args.hours.split(",") if h.strip()] if args.hours else [],
        cuisine=args.cuisine,
        menu_url=args.menu_url,
    )

    if args.url:
        audit_url(args.url, args.fix or args.fix_guide, out, site_args,
                  max_pages=max(1, args.max_pages), klar_json=args.klar_json,
                  fix_guide=args.fix_guide)
    else:
        if args.fix_guide:
            _warn("--fix-guide toimii vain --url-tilassa (repo-tilassa --fix "
                  "kirjoittaa korjaukset suoraan tiedostoihin) — lippu ohitetaan")
        repo = Path(args.repo).resolve()
        if not repo.exists():
            _err(f"Hakemistoa ei löydy: {repo}"); sys.exit(1)
        audit_repo(repo, args.fix, out, site_args, open_report=not args.no_open,
                   klar_json=args.klar_json)


if __name__ == "__main__":
    main()
