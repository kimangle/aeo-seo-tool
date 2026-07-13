#!/usr/bin/env python3
"""
AEO/SEO Audit & Optimization Tool v2.0 — AI-powered
======================================================
Auditoi ja parantaa verkkosivuja SEO ja AEO:n osalta.
V2: Claude AI kirjoittaa oikean sisällön — ei placeholdereita.

Käyttö:
    python aeo_seo_tool_v2.py --url https://example.com --fix
    python aeo_seo_tool_v2.py --repo /polku/sivustoon --fix
    python aeo_seo_tool_v2.py --repo . --fix --output ./raportit
"""

import sys, os, json, re, shutil, argparse, datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple
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
    AI_CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    AI_AVAILABLE = True
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

# ── Tietorakenteet ──────────────────────────────────────────────────────────

@dataclass
class Check:
    name: str
    category: str
    score: int
    max_score: int
    status: str
    message: str
    suggestion: str = ""
    fix_snippet: str = ""
    auto_fixable: bool = False

ICONS  = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
COLORS = {"pass": "green", "warn": "yellow", "fail": "red"}

# ── AI-sisällöntuottaja ─────────────────────────────────────────────────────

class AIWriter:
    """Käyttää Claude AI:ta tuottamaan oikeaa SEO/AEO-sisältöä."""

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        self.available = AI_AVAILABLE and bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _ask(self, prompt: str, max_tokens: int = 800) -> str:
        if not self.available:
            return ""
        try:
            r = AI_CLIENT.messages.create(
                model=self.MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return r.content[0].text.strip()
        except Exception as e:
            _warn(f"AI-virhe: {e}")
            return ""

    def meta_description(self, title: str, body_text: str, url: str = "") -> str:
        """Kirjoittaa optimoidun meta descriptionin sivun sisällöstä."""
        prompt = f"""Kirjoita yksi SEO-optimoitu meta description suomeksi tälle verkkosivulle.

Sivun otsikko: {title}
Sivun sisältö (alku): {body_text[:600]}
URL: {url}

Vaatimukset:
- Täsmälleen 140–155 merkkiä
- Sisältää pääavainsanan luonnollisesti
- Houkutteleva, toimintaan kutsuva
- Ei lainausmerkkejä
- Palauta VAIN meta description -teksti, ei mitään muuta"""
        result = self._ask(prompt, 100)
        # Varmista pituus
        if result and 120 <= len(result) <= 160:
            return result
        if result:
            return result[:155]
        return ""

    def faq_items(self, title: str, body_text: str, page_type: str = "") -> List[Dict]:
        """Generoi 4–6 relevanttia FAQ-paria sivun sisällöstä."""
        prompt = f"""Luo 5 usein kysyttyä kysymystä vastauksineen tälle verkkosivulle suomeksi.

Sivun otsikko: {title}
Sivutyyp: {page_type}
Sivun sisältö: {body_text[:800]}

Palauta VAIN JSON-taulukko tässä muodossa (ei muuta tekstiä):
[
  {{"q": "Kysymys tähän?", "a": "Vastaus tähän. Vähintään 1–2 lausetta."}},
  ...
]"""
        raw = self._ask(prompt, 600)
        try:
            # Etsi JSON taulukko vastauksesta
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                items = json.loads(match.group())
                return [{"q": i["q"], "a": i["a"]} for i in items if "q" in i and "a" in i]
        except Exception:
            pass
        return []

    def howto_steps(self, title: str, body_text: str) -> List[Dict]:
        """Generoi HowTo-askeleet miten-tyyppisille sivuille."""
        prompt = f"""Luo 4–5 selkeää HowTo-askelta tälle prosessisivulle suomeksi.

Sivun otsikko: {title}
Sisältö: {body_text[:600]}

Palauta VAIN JSON-taulukko:
[
  {{"name": "Askeleen nimi", "text": "Tarkempi kuvaus askeleesta."}},
  ...
]"""
        raw = self._ask(prompt, 400)
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return []

    def page_schema_type(self, title: str, body_text: str, filename: str) -> str:
        """Tunnistaa parhaan skeematyypin sivulle."""
        fname = filename.lower()
        if any(k in fname for k in ("ukk", "faq", "kysymys")):
            return "FAQPage"
        if any(k in fname for k in ("miten", "how", "opas", "guide")):
            return "HowTo"
        if any(k in fname for k in ("palvelu", "service", "hinta", "price")):
            return "Service"
        if any(k in fname for k in ("yhteystiedot", "contact", "yhteys")):
            return "ContactPage"
        if any(k in fname for k in ("tulos", "result", "case")):
            return "WebPage"
        if any(k in fname for k in ("index", "etusivu", "home")):
            return "WebPage"
        return "WebPage"


ai = AIWriter()

# ── Auditoija ───────────────────────────────────────────────────────────────

class PageAuditor:
    SCORING = {
        "title": 10, "meta_desc": 10, "open_graph": 8, "twitter_card": 4,
        "h1": 8, "heading_hierarchy": 5, "images_alt": 5,
        "jsonld_present": 5, "schema_types": 8, "faq_schema": 7,
        "canonical": 5, "robots_meta": 2, "aeo_content": 8,
        "authority": 8, "content_quality": 7,
    }

    def __init__(self, html: str, url: str = "", file_path: str = ""):
        self.soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")
        self.url = url
        self.file_path = file_path
        self.checks: List[Check] = []

    def run(self) -> List[Check]:
        self._title(); self._meta_desc(); self._open_graph(); self._twitter_card()
        self._h1(); self._heading_hierarchy(); self._images_alt()
        self._json_ld(); self._canonical(); self._robots_meta()
        self._aeo_content(); self._authority(); self._content_quality()
        return self.checks

    def _title(self):
        m = self.SCORING["title"]
        tag = self.soup.find("title")
        if not tag or not tag.get_text(strip=True):
            self.checks.append(Check("Title-tägi", "Tekninen SEO", 0, m, "fail",
                "Title puuttuu", "Lisää <title>", "<title>Sivun nimi | Brändi</title>"))
            return
        t = tag.get_text(strip=True); ln = len(t)
        if 30 <= ln <= 60:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m, m, "pass", f'"{_trunc(t,50)}" ({ln} merkkiä)'))
        elif ln < 30:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m//2, m, "warn",
                f"Liian lyhyt ({ln} merkkiä): \"{t}\"", "Laajenna 30–60 merkkiin"))
        else:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m-3, m, "warn",
                f"Liian pitkä ({ln} merkkiä)", "Lyhennä alle 60 merkkiin"))

    def _meta_desc(self):
        m = self.SCORING["meta_desc"]
        tag = self.soup.find("meta", attrs={"name": "description"})
        if not tag or not (tag.get("content") or "").strip():
            self.checks.append(Check("Meta Description", "Tekninen SEO", 0, m, "fail",
                "Meta description puuttuu", "AI kirjoittaa sen automaattisesti --fix-lipulla",
                "", auto_fixable=True))
            return
        t = tag["content"].strip(); ln = len(t)
        is_placeholder = any(p in t for p in ["Kuvaile sivusi", "120–160", "placeholder"])
        if is_placeholder:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m//3, m, "warn",
                f"Placeholder-teksti ({ln} merkkiä) — ei optimoitu",
                "AI kirjoittaa oikean descriptionin --fix-lipulla", "", auto_fixable=True))
        elif 120 <= ln <= 160:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m, m, "pass", f"Optimaalinen ({ln} merkkiä)"))
        elif ln < 120:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m//2, m, "warn",
                f"Liian lyhyt ({ln} merkkiä)", "AI parantaa --fix-lipulla", "", auto_fixable=True))
        else:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m-3, m, "warn",
                f"Liian pitkä ({ln} merkkiä)", "Lyhennä alle 160 merkkiin"))

    def _open_graph(self):
        m = self.SCORING["open_graph"]
        required = ["og:title", "og:description", "og:image", "og:url"]
        found = [p for p in required if self.soup.find("meta", property=p)
                 and (self.soup.find("meta", property=p).get("content") or "").strip()
                 and self.soup.find("meta", property=p).get("content") != "/"]
        score = round(m * len(found) / len(required))
        missing = [p for p in required if p not in found]
        if not missing:
            self.checks.append(Check("Open Graph", "Sosiaalinen SEO", m, m, "pass", "Kaikki OG-tagit kunnossa"))
        else:
            snippet = "\n".join(f'<meta property="{p}" content="...">' for p in missing)
            self.checks.append(Check("Open Graph", "Sosiaalinen SEO", score, m,
                "fail" if score == 0 else "warn",
                f"Puuttuu: {', '.join(missing)}",
                "Lisää puuttuvat OG-tagit", snippet, auto_fixable=True))

    def _twitter_card(self):
        m = self.SCORING["twitter_card"]
        tag = self.soup.find("meta", attrs={"name": "twitter:card"})
        img = self.soup.find("meta", attrs={"name": "twitter:image"})
        if tag and tag.get("content") and img and img.get("content"):
            self.checks.append(Check("Twitter Card", "Sosiaalinen SEO", m, m, "pass", "Twitter Card + kuva kunnossa"))
        elif tag and tag.get("content"):
            self.checks.append(Check("Twitter Card", "Sosiaalinen SEO", m-2, m, "warn",
                "Twitter Card ok, mutta twitter:image puuttuu",
                'Lisää <meta name="twitter:image" content="URL">',
                '<meta name="twitter:image" content="https://anglesmarketing.fi/logo.png">',
                auto_fixable=True))
        else:
            self.checks.append(Check("Twitter Card", "Sosiaalinen SEO", 0, m, "warn",
                "Twitter Card puuttuu", "Lisää Twitter Card -tagit",
                '<meta name="twitter:card" content="summary_large_image">',
                auto_fixable=True))

    def _h1(self):
        m = self.SCORING["h1"]
        h1s = self.soup.find_all("h1")
        if not h1s:
            self.checks.append(Check("H1-otsikko", "Sivun SEO", 0, m, "fail", "H1 puuttuu",
                "Lisää yksi H1-otsikko", "<h1>Sivun pääotsikko</h1>"))
        elif len(h1s) == 1:
            self.checks.append(Check("H1-otsikko", "Sivun SEO", m, m, "pass",
                f'"{_trunc(h1s[0].get_text(strip=True), 55)}"'))
        else:
            self.checks.append(Check("H1-otsikko", "Sivun SEO", m//2, m, "warn",
                f"{len(h1s)} H1-otsikkoa — pitäisi olla yksi", "Jätä vain yksi H1"))

    def _heading_hierarchy(self):
        m = self.SCORING["heading_hierarchy"]
        levels = []
        for lv in range(1, 7):
            for _ in self.soup.find_all(f"h{lv}"):
                levels.append(lv)
        if not levels:
            self.checks.append(Check("Otsikkorakenne", "Sivun SEO", 0, m, "fail", "Ei otsikoita"))
            return
        issues = []
        prev = 0
        for lv in levels:
            if prev and lv > prev + 1:
                issues.append(f"H{prev}→H{lv}")
            prev = lv
        if not issues:
            self.checks.append(Check("Otsikkorakenne", "Sivun SEO", m, m, "pass",
                f"Looginen rakenne ({len(levels)} otsikkoa)"))
        else:
            self.checks.append(Check("Otsikkorakenne", "Sivun SEO", max(0, m-len(issues)*2), m, "warn",
                f"Aukkoja: {', '.join(issues)}", "Korjaa otsikkorakenne"))

    def _images_alt(self):
        m = self.SCORING["images_alt"]
        imgs = self.soup.find_all("img")
        if not imgs:
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun SEO", m, m, "pass", "Ei kuvia"))
            return
        no_alt = [i for i in imgs if not i.get("alt")]
        if not no_alt:
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun SEO", m, m, "pass",
                f"Kaikilla {len(imgs)} kuvalla alt-teksti"))
        else:
            score = round(m * (len(imgs)-len(no_alt)) / len(imgs))
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun SEO", score, m,
                "fail" if score == 0 else "warn",
                f"{len(no_alt)}/{len(imgs)} kuvalta puuttuu alt-teksti",
                "Lisää alt-teksti jokaiselle kuvalle"))

    def _json_ld(self):
        mp, ms, mf = self.SCORING["jsonld_present"], self.SCORING["schema_types"], self.SCORING["faq_schema"]
        total_max = mp + ms + mf
        scripts = self.soup.find_all("script", type="application/ld+json")
        if not scripts:
            self.checks.append(Check("JSON-LD / Structured Data", "AEO & Structured Data",
                0, total_max, "fail", "JSON-LD puuttuu kokonaan",
                "AI generoi oikean JSON-LD:n --fix-lipulla", "", auto_fixable=True))
            return
        schemas = []
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
                pass
        types = [str(s.get("@type", "")) for s in schemas]
        has_org  = any(t in ("Organization","LocalBusiness","Corporation") for t in types)
        has_site = "WebSite" in types
        has_page = any(t in ("WebPage","Article","BlogPosting","Product","Service",
                             "FAQPage","HowTo","ContactPage") for t in types)
        has_faq  = any(t in ("FAQPage","HowTo") for t in types)
        # Tarkista onko placeholder-data
        has_placeholder = any(
            s.get("name") in ("Yrityksesi nimi", "Sivuston nimi") or
            s.get("url") == "https://example.com"
            for s in schemas
        )
        sp = mp
        ss = min(ms, (3 if has_org else 0) + (3 if has_site else 0) + (2 if has_page else 0))
        sf = mf if has_faq else 0
        if has_placeholder:
            ss = max(0, ss - 3)
        total = sp + ss + sf
        status = "pass" if total >= total_max*0.7 else ("warn" if total > 0 else "fail")
        type_str = ", ".join(t for t in types if t) or "tuntematon"
        notes = []
        if has_placeholder: notes.append("Placeholder-arvoja — AI korjaa --fix-lipulla")
        if not has_faq: notes.append("FAQPage/HowTo puuttuu")
        self.checks.append(Check("JSON-LD / Structured Data", "AEO & Structured Data",
            total, total_max, status, f"Skeematyypit: {type_str}",
            " | ".join(notes) if notes else "", "", auto_fixable=has_placeholder or not has_faq))

    def _canonical(self):
        m = self.SCORING["canonical"]
        tag = self.soup.find("link", rel="canonical")
        if tag and tag.get("href") and tag["href"] != "/":
            self.checks.append(Check("Canonical-tägi", "Tekninen SEO", m, m, "pass", tag["href"]))
        else:
            href = self.url or "https://anglesmarketing.fi/"
            self.checks.append(Check("Canonical-tägi", "Tekninen SEO", 0, m, "warn",
                "Canonical puuttuu tai on virheellinen",
                "Lisää canonical", f'<link rel="canonical" href="{href}">', auto_fixable=True))

    def _robots_meta(self):
        m = self.SCORING["robots_meta"]
        tag = self.soup.find("meta", attrs={"name": "robots"})
        if tag:
            c = (tag.get("content") or "").lower()
            if "noindex" in c:
                self.checks.append(Check("Robots Meta", "Tekninen SEO", 0, m, "fail",
                    f"VAROITUS: noindex! ({c})", "Poista noindex"))
            else:
                self.checks.append(Check("Robots Meta", "Tekninen SEO", m, m, "pass", c))
        else:
            self.checks.append(Check("Robots Meta", "Tekninen SEO", m-1, m, "pass",
                "Puuttuu (oletus index,follow = OK)"))

    def _aeo_content(self):
        m = self.SCORING["aeo_content"]
        score = 0; notes = []; issues = []
        body = self.soup.get_text(" ", strip=True)
        words = len(body.split())
        qs = re.findall(r"[A-ZÄÖÅ][^.!?]{10,}\?", body)
        if len(qs) >= 2:
            score += 3; notes.append(f"{len(qs)} kysymystä")
        else:
            issues.append("Lisää Q&A-sisältöä")
        lists = self.soup.find_all(["ul", "ol"])
        if lists:
            score += 2; notes.append(f"{len(lists)} listaa")
        else:
            issues.append("Lisää listoja (ul/ol)")
        if words >= 300:
            score += 3; notes.append(f"{words} sanaa")
        elif words >= 100:
            score += 1; issues.append(f"Lisää tekstiä (nyt {words} sanaa)")
        else:
            issues.append(f"Hyvin vähän tekstiä ({words} sanaa)")
        status = "pass" if score >= m*0.7 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("AEO-sisältösignaalit", "AEO & Structured Data",
            score, m, status,
            f"{', '.join(notes) if notes else 'heikot signaalit'}",
            " | ".join(issues) if issues else ""))

    def _authority(self):
        m = self.SCORING["authority"]
        score = 0; found = []; missing = []
        body = self.soup.get_text(" ", strip=True)
        hrefs = [a.get("href","").lower() for a in self.soup.find_all("a")]
        texts = [a.get_text(strip=True).lower() for a in self.soup.find_all("a")]
        nav = hrefs + texts
        if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", body):
            score += 2; found.append("sähköposti")
        else:
            missing.append("sähköpostiosoite")
        if re.search(r"[\+\d][\d\s\-\(\)]{6,}\d", body):
            score += 1; found.append("puhelin")
        else:
            missing.append("puhelinnumero")
        if any("tietosuoja" in n or "privacy" in n for n in nav):
            score += 2; found.append("tietosuoja")
        else:
            missing.append("tietosuojasivu")
        if any(any(k in n for k in ("meistä","about","yritys","tietoa")) for n in nav):
            score += 1; found.append("tietoa meistä")
        else:
            missing.append("tietoa meistä")
        socials = ("facebook.com","twitter.com","linkedin.com","instagram.com","youtube.com","x.com")
        if any(any(s in h for s in socials) for h in hrefs):
            score += 2; found.append("some-linkit")
        else:
            missing.append("some-linkit")
        status = "pass" if score >= m*0.7 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("Auktoriteetti & luottamus", "Auktoriteetti",
            score, m, status,
            f"Löytyi: {', '.join(found) if found else '–'}",
            f"Puuttuu: {', '.join(missing)}" if missing else ""))

    def _content_quality(self):
        m = self.SCORING["content_quality"]
        body = self.soup.get_text(" ", strip=True)
        words = len(body.split())
        first_p = self.soup.find("p")
        has_vp = first_p and len(first_p.get_text(strip=True).split()) >= 20
        score = (3 if has_vp else 0) + (4 if words >= 500 else 2 if words >= 200 else 0)
        status = "pass" if score >= m*0.6 else ("warn" if score > 0 else "fail")
        self.checks.append(Check("Sisällön laatu", "Sisältö", score, m, status,
            f"{words} sanaa{', selkeä arvolupaus' if has_vp else ', arvolupaus epäselvä'}",
            "" if score >= m*0.6 else "Kirjoita vahva arvolupaus ensimmäiseen kappaleeseen"))


# ── AI-korjaaja ─────────────────────────────────────────────────────────────

class AIFixer:
    """Käyttää Claude AI:ta tekemään älykkäitä korjauksia HTML-tiedostoon."""

    ORG = {
        "@type": "Organization",
        "@id": "#organization",
        "name": "Anglés Marketing",
        "url": "https://anglesmarketing.fi",
        "logo": {"@type": "ImageObject", "url": "https://anglesmarketing.fi/logo.png"},
        "email": "kimangle@anglesmarketing.fi",
        "address": {"@type": "PostalAddress", "addressLocality": "Helsinki", "addressCountry": "FI"},
    }
    WEBSITE = {
        "@type": "WebSite",
        "@id": "#website",
        "url": "https://anglesmarketing.fi",
        "name": "Anglés Marketing",
        "publisher": {"@id": "#organization"},
    }

    def __init__(self, html: str, url: str = "", filename: str = ""):
        self.soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")
        self.url = url
        self.filename = filename
        self.applied: List[str] = []
        self._body_text = self.soup.get_text(" ", strip=True)
        self._title_text = (self.soup.find("title") or {}).get_text(strip=True) if self.soup.find("title") else ""

    def fix(self, checks: List[Check]) -> str:
        head = self.soup.find("head")
        if not head:
            return str(self.soup)
        for c in checks:
            if c.auto_fixable and c.status != "pass":
                self._apply(c, head)
        return str(self.soup)

    def _apply(self, c: Check, head):
        if c.name == "Meta Description":
            self._fix_meta_desc(head)
        elif c.name == "Open Graph":
            self._fix_og(head)
        elif c.name == "Twitter Card":
            self._fix_twitter(head)
        elif c.name == "Canonical-tägi":
            self._fix_canonical(head)
        elif c.name == "JSON-LD / Structured Data":
            self._fix_jsonld(head)

    def _fix_meta_desc(self, head):
        if not AI_AVAILABLE:
            return
        _info("  AI kirjoittaa meta descriptionia...")
        new_desc = ai.meta_description(self._title_text, self._body_text, self.url)
        if not new_desc:
            return
        existing = self.soup.find("meta", attrs={"name": "description"})
        if existing:
            existing["content"] = new_desc
            self.applied.append(f"Meta description uudelleenkirjoitettu AI:lla ({len(new_desc)} merkkiä)")
        else:
            tag = self.soup.new_tag("meta")
            tag["name"] = "description"
            tag["content"] = new_desc
            head.append(tag)
            self.applied.append(f"Meta description luotu AI:lla ({len(new_desc)} merkkiä)")

    def _fix_og(self, head):
        page_url = self.url or f"https://anglesmarketing.fi/{self.filename.replace('.html','')}"
        title = self._title_text or "Anglés Marketing"
        desc_tag = self.soup.find("meta", attrs={"name": "description"})
        desc = desc_tag["content"] if desc_tag else ""
        props = {
            "og:title": title,
            "og:description": desc,
            "og:type": "website",
            "og:url": page_url,
            "og:image": "https://anglesmarketing.fi/logo.png",
            "og:locale": "fi_FI",
        }
        added = []
        for prop, val in props.items():
            existing = self.soup.find("meta", property=prop)
            if not existing:
                t = self.soup.new_tag("meta")
                t["property"] = prop
                t["content"] = val
                head.append(t)
                added.append(prop)
            elif existing.get("content") in ("/", "", None):
                existing["content"] = val
                added.append(f"{prop} (korjattu)")
        if added:
            self.applied.append(f"OG-tagit: {', '.join(added)}")

    def _fix_twitter(self, head):
        title = self._title_text or "Anglés Marketing"
        desc_tag = self.soup.find("meta", attrs={"name": "description"})
        desc = desc_tag["content"][:200] if desc_tag else ""
        for name, content in [
            ("twitter:card", "summary_large_image"),
            ("twitter:title", title),
            ("twitter:description", desc),
            ("twitter:image", "https://anglesmarketing.fi/logo.png"),
        ]:
            if not self.soup.find("meta", attrs={"name": name}):
                t = self.soup.new_tag("meta")
                t["name"] = name
                t["content"] = content
                head.append(t)
        self.applied.append("Twitter Card -tagit lisätty/täydennetty")

    def _fix_canonical(self, head):
        page_url = self.url or f"https://anglesmarketing.fi/{self.filename.replace('.html','')}"
        existing = self.soup.find("link", rel="canonical")
        if not existing:
            t = self.soup.new_tag("link")
            t["rel"] = "canonical"
            t["href"] = page_url
            head.append(t)
            self.applied.append(f"Canonical lisätty: {page_url}")
        elif existing.get("href") in ("/", "", None):
            existing["href"] = page_url
            self.applied.append(f"Canonical korjattu: {page_url}")

    def _fix_jsonld(self, head):
        schema_type = ai.page_schema_type(self._title_text, self._body_text, self.filename)
        graph = [self.ORG, self.WEBSITE]

        if schema_type == "FAQPage":
            _info("  AI generoi FAQ-pareja...")
            items = ai.faq_items(self._title_text, self._body_text, "FAQ")
            if items:
                graph.append({
                    "@type": "FAQPage",
                    "mainEntity": [
                        {"@type": "Question", "name": i["q"],
                         "acceptedAnswer": {"@type": "Answer", "text": i["a"]}}
                        for i in items
                    ]
                })
                self.applied.append(f"FAQPage-skeema generoitu AI:lla ({len(items)} kysymystä)")
            else:
                graph.append({"@type": "FAQPage", "mainEntity": []})

        elif schema_type == "HowTo":
            _info("  AI generoi HowTo-askeleet...")
            steps = ai.howto_steps(self._title_text, self._body_text)
            if steps:
                graph.append({
                    "@type": "HowTo",
                    "name": self._title_text,
                    "description": self._body_text[:200],
                    "step": [
                        {"@type": "HowToStep", "position": i+1,
                         "name": s.get("name",""), "text": s.get("text","")}
                        for i, s in enumerate(steps)
                    ]
                })
                self.applied.append(f"HowTo-skeema generoitu AI:lla ({len(steps)} askelta)")
            else:
                graph.append({"@type": "WebPage", "name": self._title_text, "url": self.url})

        elif schema_type == "Service":
            graph.append({
                "@type": "Service",
                "name": self._title_text,
                "provider": {"@id": "#organization"},
                "areaServed": {"@type": "City", "name": "Helsinki"},
                "url": self.url or f"https://anglesmarketing.fi/{self.filename.replace('.html','')}",
            })
            self.applied.append("Service-skeema lisätty")

        elif schema_type == "ContactPage":
            graph.append({
                "@type": "ContactPage",
                "name": self._title_text,
                "url": self.url or f"https://anglesmarketing.fi/{self.filename.replace('.html','')}",
            })
            self.applied.append("ContactPage-skeema lisätty")

        else:
            graph.append({
                "@type": "WebPage",
                "name": self._title_text,
                "url": self.url or f"https://anglesmarketing.fi/{self.filename.replace('.html','')}",
                "publisher": {"@id": "#organization"},
            })
            self.applied.append("WebPage-skeema lisätty")

        new_data = {"@context": "https://schema.org", "@graph": graph}
        new_script = self.soup.new_tag("script", type="application/ld+json")
        new_script.string = "\n" + json.dumps(new_data, indent=2, ensure_ascii=False) + "\n"

        # Poista vanhat JSON-LD:t (placeholder tai puuttuvat)
        for old in self.soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(old.string or "{}")
                is_placeholder = False
                items = d.get("@graph", [d]) if isinstance(d, dict) else d
                for item in (items if isinstance(items, list) else [items]):
                    if item.get("name") in ("Yrityksesi nimi","Sivuston nimi") or item.get("url") == "https://example.com":
                        is_placeholder = True
                if is_placeholder:
                    old.decompose()
            except Exception:
                pass

        head.append(new_script)


# ── Apufunktiot ─────────────────────────────────────────────────────────────

def _trunc(t: str, n: int) -> str: return t if len(t) <= n else t[:n] + "…"
def _has_lxml() -> bool:
    try: import lxml; return True
    except ImportError: return False
def scores(checks: List[Check]) -> Tuple[int, int]:
    return sum(c.score for c in checks), sum(c.max_score for c in checks)
def grade(n: float) -> str:
    for t, g in [(90,"A+"),(80,"A"),(70,"B"),(60,"C"),(50,"D")]:
        if n >= t: return g
    return "F"
def col(n: float) -> str:
    return "green" if n >= 70 else ("yellow" if n >= 50 else "red")

def _info(msg): (console.print(f"[dim]{msg}[/dim]") if RICH else print(msg))
def _ok(msg):   (console.print(f"[green]{msg}[/green]") if RICH else print(msg))
def _warn(msg): (console.print(f"[yellow]{msg}[/yellow]") if RICH else print(f"VAROITUS: {msg}"))
def _err(msg):  (console.print(f"[red]{msg}[/red]") if RICH else print(f"VIRHE: {msg}"))
def _hdr(msg):  (console.print(f"\n[bold blue]{msg}[/bold blue]\n") if RICH else print(f"\n{msg}\n"))

def print_results(checks: List[Check], title: str = ""):
    s, mx = scores(checks)
    pct = s/mx*100 if mx else 0
    if not RICH:
        print(f"\n{'='*55}\n  {title}\n  {s}/{mx} ({pct:.0f}%) – {grade(pct)}\n{'='*55}")
        for c in checks:
            print(f"  {ICONS.get(c.status,'?')} {c.name}: {c.score}/{c.max_score} — {c.message}")
            if c.suggestion: print(f"     → {c.suggestion}")
        return
    c_col = col(pct)
    if title: console.print(f"\n[bold]{title}[/bold]")
    console.print(Panel(
        f"[bold {c_col}]{s}/{mx} ({pct:.0f}%) – {grade(pct)}[/bold {c_col}]",
        title="AEO/SEO Score", border_style=c_col))
    cats: Dict[str, List[Check]] = {}
    for ch in checks: cats.setdefault(ch.category, []).append(ch)
    for cat, chs in cats.items():
        cs, cm = scores(chs)
        tbl = Table(title=f"{cat}  ({cs}/{cm})", box=box.ROUNDED, min_width=75)
        tbl.add_column("", width=3); tbl.add_column("Tarkistus", style="bold", min_width=22)
        tbl.add_column("Tulos", ratio=3); tbl.add_column("Pisteet", width=9, justify="right")
        for ch in chs:
            cc = COLORS.get(ch.status,"white")
            tbl.add_row(ICONS.get(ch.status,"?"), ch.name,
                f"[{cc}]{ch.message}[/{cc}]", f"{ch.score}/{ch.max_score}")
            if ch.suggestion:
                tbl.add_row("","",f"[dim]→ {ch.suggestion}[/dim]","")
        console.print(tbl)

def recommendations(checks: List[Check]) -> List[str]:
    priority = [
        ("JSON-LD / Structured Data", "Lisää/korjaa JSON-LD rakenteellinen data — kriittistä AEO:lle"),
        ("Meta Description", "Kirjoita optimoitu meta description (120–160 merkkiä)"),
        ("Title-tägi", "Optimoi title: 30–60 merkkiä, pääavainsana + brändi"),
        ("H1-otsikko", "Lisää yksi H1-otsikko"),
        ("Open Graph", "Lisää Open Graph -tagit some-jakoa varten"),
        ("AEO-sisältösignaalit", "Lisää Q&A-osio ja listat — AI suosii vastausmuotoista sisältöä"),
        ("Auktoriteetti & luottamus", "Lisää yhteystiedot, tietosuojasivu ja some-linkit"),
        ("Kuvien alt-tekstit", "Lisää alt-teksti kaikille kuville"),
        ("Canonical-tägi", "Lisää canonical-tägi"),
    ]
    bad = {c.name for c in checks if c.status != "pass"}
    return [r for n, r in priority if n in bad]

SKIP_DIRS = {"node_modules",".git","vendor","dist","__pycache__","bower_components",".cache",".next","build","out"}

def md_report(target, ttype, before, after, fixes, recs, ts):
    bs, bm = scores(before); bpct = bs/bm*100 if bm else 0
    lines = [f"# AEO/SEO Auditointi v2 (AI-powered) – {target}", "",
             f"**Päiväys:** {ts}  ", f"**Tyyppi:** {'URL' if ttype=='url' else 'Repositorio'}  ",
             f"**AI-malli:** Claude Haiku (meta desc + FAQ + skeema)  ", "", "---", "",
             "## Ennen-tila", "", f"### {bs}/{bm} ({bpct:.0f}%) – {grade(bpct)}", ""]
    cats: Dict[str, List[Check]] = {}
    for c in before: cats.setdefault(c.category, []).append(c)
    for cat, chs in cats.items():
        cs, cm = scores(chs)
        lines += [f"#### {cat} ({cs}/{cm})", "",
                  "| Status | Tarkistus | Pisteet | Tulos |",
                  "|--------|-----------|---------|-------|"]
        for c in chs:
            lines.append(f"| {ICONS.get(c.status,'?')} | {c.name} | {c.score}/{c.max_score} | {c.message} |")
        lines.append("")
    if fixes:
        lines += ["---", "", "## AI-korjaukset", ""]
        for f in fixes: lines.append(f"- ✅ {f}")
        lines.append("")
    if after:
        asc, amx = scores(after); apct = asc/amx*100 if amx else 0
        lines += ["---", "", "## Jälkeen-tila (AI-korjausten jälkeen)", "",
                  f"### {asc}/{amx} ({apct:.0f}%) – {grade(apct)}", "",
                  f"**Parannus: {apct-bpct:+.0f} prosenttiyksikköä**", ""]
    if recs:
        lines += ["---", "", "## Seuraavat toimenpiteet", ""]
        for i, r in enumerate(recs, 1): lines.append(f"{i}. {r}")
    lines += ["", "---", "", "*AEO/SEO Audit Tool v2.0 — AI-powered*"]
    return "\n".join(lines)

def save_report(target, ttype, before, after, fixes, out):
    recs = recommendations(before)
    ts_label = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    ts_file  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w]","_",target)[:40]
    md_path   = out / f"audit_v2_{safe}_{ts_file}.md"
    json_path = out / f"audit_v2_{safe}_{ts_file}.json"
    md_path.write_text(md_report(target,ttype,before,after,fixes,recs,ts_label), encoding="utf-8")
    bs, bm = scores(before)
    json_path.write_text(json.dumps({
        "tool_version": "2.0", "ai_powered": True,
        "target": target, "target_type": ttype, "timestamp": ts_label,
        "before_score": bs, "before_max": bm,
        "before_pct": round(bs/bm*100,1) if bm else 0,
        "after_score": scores(after)[0] if after else bs,
        "fixes_applied": fixes, "recommendations": recs,
        "checks": [{"name":c.name,"category":c.category,"score":c.score,
                    "max_score":c.max_score,"status":c.status,"message":c.message} for c in before]
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    if RICH:
        console.print(f"\n[bold green]Raportit:[/bold green]\n  📄 {md_path}\n  📊 {json_path}")
    else:
        print(f"\nRaportit:\n  {md_path}\n  {json_path}")

# ── Repo-ajuri ───────────────────────────────────────────────────────────────

def audit_repo(repo: Path, fix: bool, out: Path):
    _hdr(f"AEO/SEO v2 (AI) — {repo}")
    if not AI_AVAILABLE:
        _warn("anthropic-paketti puuttuu: pip install anthropic")
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        _warn("ANTHROPIC_API_KEY puuttuu — AI-ominaisuudet pois käytöstä")

    html_files = [f for f in (list(repo.rglob("*.html")) + list(repo.rglob("*.htm")))
                  if not SKIP_DIRS.intersection(set(f.parts))]
    if not html_files:
        _warn("HTML-tiedostoja ei löydy"); return

    _info(f"Löytyi {len(html_files)} HTML-tiedostoa — {'AI-korjaukset käytössä ✨' if AI_AVAILABLE and fix else 'vain auditointi'}")

    all_before, all_after, all_fixes = [], [], []

    for f in html_files:
        rel = f.relative_to(repo)
        if RICH: console.rule(f"[dim]{rel}[/dim]")
        else: print(f"\n{'─'*50}\n{rel}")
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            _warn(f"Ei voitu lukea: {e}"); continue

        before = PageAuditor(html, file_path=str(f)).run()
        all_before.extend(before)
        print_results(before, str(rel))

        if fix:
            bak = f.with_suffix(f.suffix + ".bak")
            if not bak.exists(): shutil.copy2(f, bak)
            fixer = AIFixer(html, filename=f.name)
            fixed = fixer.fix(before)
            if fixer.applied:
                f.write_text(fixed, encoding="utf-8")
                for msg in fixer.applied: _ok(f"  ✅ {rel}: {msg}")
                all_fixes.extend(f"{rel}: {m}" for m in fixer.applied)
                after_checks = PageAuditor(fixed, file_path=str(f)).run()
                all_after.extend(after_checks)
            else:
                all_after.extend(before)

    ts, tm = scores(all_before); tpct = ts/tm*100 if tm else 0
    if RICH:
        console.rule("[bold]YHTEENVETO[/bold]")
        c = col(tpct)
        console.print(Panel(
            f"[bold {c}]{ts}/{tm} ({tpct:.0f}%) – {grade(tpct)}[/bold {c}]\n"
            f"Tiedostoja: {len(html_files)} | Korjauksia: {len(all_fixes)}",
            title="Lopputulos", border_style=c))

    save_report(str(repo), "repo", all_before, all_after if fix else None, all_fixes, out)

# ── URL-ajuri ────────────────────────────────────────────────────────────────

def audit_url(url: str, fix: bool, out: Path):
    _hdr(f"AEO/SEO v2 (AI) — {url}")
    try:
        resp = requests.get(url, headers={"User-Agent":"AEOSEOAuditBot/2.0"}, timeout=15)
        resp.raise_for_status(); html = resp.text
    except requests.RequestException as e:
        _err(f"Virhe: {e}"); sys.exit(1)
    before = PageAuditor(html, url=url).run()
    print_results(before, "ENNEN")
    fixes, after = [], None
    if fix:
        fixer = AIFixer(html, url=url)
        fixed = fixer.fix(before)
        fixes = fixer.applied
        after = PageAuditor(fixed, url=url).run()
        print_results(after, "JÄLKEEN (AI-korjaukset)")
        ts_file = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        p = out / f"fixed_v2_{ts_file}.html"
        p.write_text(fixed, encoding="utf-8")
        _ok(f"Korjattu HTML → {p}")
    save_report(url, "url", before, after, fixes, out)

# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AEO/SEO Audit Tool v2.0 — AI-powered")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--url",  help="Auditoitavan sivuston URL")
    g.add_argument("--repo", help="Auditoitavan repositorion polku")
    parser.add_argument("--fix",    action="store_true", help="Sovella AI-korjaukset")
    parser.add_argument("--output", default="./reports",  help="Raporttihakemisto")
    args = parser.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    if args.url:
        audit_url(args.url, args.fix, out)
    else:
        repo = Path(args.repo).resolve()
        if not repo.exists(): _err(f"Ei löydy: {repo}"); sys.exit(1)
        audit_repo(repo, args.fix, out)

if __name__ == "__main__":
    main()
