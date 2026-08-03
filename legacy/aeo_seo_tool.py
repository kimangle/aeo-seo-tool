#!/usr/bin/env python3
"""
AEO/SEO Audit & Optimization Tool v1.0
========================================
Auditoi verkkosivustot ja repositoriot SEO- ja AEO-signaalien varalta.
Tuottaa mitattavan ennen/jälkeen-raportin ja soveltaa turvalliset korjaukset.

SEO = Search Engine Optimization (perinteiset hakukoneet)
AEO = Answer Engine Optimization (AI-assistentit: ChatGPT, Perplexity, Google SGE)

Käyttö:
    python aeo_seo_tool.py --url https://example.com
    python aeo_seo_tool.py --url https://example.com --fix
    python aeo_seo_tool.py --repo /path/to/website
    python aeo_seo_tool.py --repo /path/to/website --fix
    python aeo_seo_tool.py --repo . --fix --output ./raportit
"""

import sys
import os
import json
import re
import shutil
import argparse
import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ─── Riippuvuuksien tarkistus ──────────────────────────────────────────────

MISSING_DEPS: List[str] = []
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    MISSING_DEPS.append(str(e).split("'")[1] if "'" in str(e) else str(e))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH = True
except ImportError:
    RICH = False

if MISSING_DEPS:
    print(f"Puuttuvat paketit: {', '.join(MISSING_DEPS)}")
    print(f"Asenna: pip install {' '.join(MISSING_DEPS)}")
    sys.exit(1)

console = Console() if RICH else None

# ─── Tietorakenteet ────────────────────────────────────────────────────────

@dataclass
class Check:
    name: str
    category: str
    score: int
    max_score: int
    status: str          # 'pass' | 'warn' | 'fail'
    message: str
    suggestion: str = ""
    fix_snippet: str = ""
    auto_fixable: bool = False


ICONS = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
COLORS = {"pass": "green", "warn": "yellow", "fail": "red"}


# ─── Auditoija ─────────────────────────────────────────────────────────────

class PageAuditor:
    """Auditoi yksittäisen HTML-sivun SEO- ja AEO-signaalien varalta. Pisteet 0–100."""

    # Pisteytys – yhteensä 100
    SCORING = {
        "title":             10,
        "meta_desc":         10,
        "open_graph":         8,
        "twitter_card":       4,
        "h1":                 8,
        "heading_hierarchy":  5,
        "images_alt":         5,
        # JSON-LD alla kolme erää yhteensä 20:
        "jsonld_present":     5,
        "schema_types":       8,
        "faq_schema":         7,
        "canonical":          5,
        "robots_meta":        2,
        "aeo_content":        8,
        "authority":          8,
        "content_quality":    7,
    }

    def __init__(self, html: str, url: str = "", file_path: str = ""):
        self.soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")
        self.url = url
        self.file_path = file_path
        self.checks: List[Check] = []

    def run(self) -> List[Check]:
        self._title()
        self._meta_desc()
        self._open_graph()
        self._twitter_card()
        self._h1()
        self._heading_hierarchy()
        self._images_alt()
        self._json_ld()
        self._canonical()
        self._robots_meta()
        self._aeo_content()
        self._authority()
        self._content_quality()
        return self.checks

    # ── Yksittäiset tarkistukset ──────────────────────────────────────────

    def _title(self):
        m = self.SCORING["title"]
        tag = self.soup.find("title")
        if not tag or not tag.get_text(strip=True):
            self.checks.append(Check(
                "Title-tägi", "Tekninen SEO", 0, m, "fail",
                "Title-tägi puuttuu tai on tyhjä",
                "Lisää <title>Sivun nimi | Brändi</title> <head>-osioon",
                "<title>Sivun nimi | Brändinimi</title>",
            ))
            return
        text = tag.get_text(strip=True)
        length = len(text)
        if 30 <= length <= 60:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m, m, "pass",
                f'Title optimaalinen ({length} merkkiä): "{_trunc(text, 50)}"'))
        elif length < 30:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m // 2, m, "warn",
                f'Title liian lyhyt ({length} merkkiä): "{text}"',
                "Laajenna titlea 30–60 merkkiin – lisää avainsana ja brändinimi",
                f"<title>{text} | Brändinimi</title>"))
        else:
            self.checks.append(Check("Title-tägi", "Tekninen SEO", m - 3, m, "warn",
                f"Title liian pitkä ({length} merkkiä) – katkeaa hakutuloksissa",
                "Lyhennä titlea alle 60 merkkiin",
                f"<title>{text[:55]}…</title>"))

    def _meta_desc(self):
        m = self.SCORING["meta_desc"]
        tag = self.soup.find("meta", attrs={"name": "description"})
        if not tag or not (tag.get("content") or "").strip():
            self.checks.append(Check(
                "Meta Description", "Tekninen SEO", 0, m, "fail",
                "Meta description puuttuu",
                "Lisää kuvaava meta description 120–160 merkkiä",
                '<meta name="description" content="Kuvaile sivusi sisältöä '
                'houkuttelevasti 120–160 merkissä. Sisällytä pääavainsana.">',
                auto_fixable=True,
            ))
            return
        text = tag["content"].strip()
        length = len(text)
        if 120 <= length <= 160:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m, m, "pass",
                f"Meta description optimaalinen ({length} merkkiä)"))
        elif length < 120:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m // 2, m, "warn",
                f"Meta description liian lyhyt ({length} merkkiä)",
                "Laajenna kuvausta 120–160 merkkiin – lisää avainsana ja CTA"))
        else:
            self.checks.append(Check("Meta Description", "Tekninen SEO", m - 3, m, "warn",
                f"Meta description liian pitkä ({length} merkkiä) – katkeaa",
                "Lyhennä kuvausta alle 160 merkkiin"))

    def _open_graph(self):
        m = self.SCORING["open_graph"]
        required = ["og:title", "og:description", "og:image", "og:url"]
        found = [p for p in required
                 if self.soup.find("meta", property=p) and
                 self.soup.find("meta", property=p).get("content")]
        score = round(m * len(found) / len(required))
        missing = [p for p in required if p not in found]
        if not missing:
            self.checks.append(Check("Open Graph", "Sosiaalinen SEO", m, m, "pass",
                "Kaikki OG-tagit löytyivät"))
        else:
            snippet = "\n".join(f'<meta property="{p}" content="...">' for p in missing)
            self.checks.append(Check(
                "Open Graph", "Sosiaalinen SEO", score, m,
                "fail" if score == 0 else "warn",
                f"Puuttuvat OG-tagit: {', '.join(missing)}",
                "Lisää puuttuvat Open Graph -metatagit some-jakoa varten",
                snippet, auto_fixable=True,
            ))

    def _twitter_card(self):
        m = self.SCORING["twitter_card"]
        tag = self.soup.find("meta", attrs={"name": "twitter:card"})
        if tag and tag.get("content"):
            self.checks.append(Check("Twitter Card", "Sosiaalinen SEO", m, m, "pass",
                f"Twitter Card: {tag['content']}"))
        else:
            self.checks.append(Check(
                "Twitter Card", "Sosiaalinen SEO", 0, m, "warn",
                "Twitter Card -tägi puuttuu",
                "Lisää Twitter Card Twitter/X-jakoa varten",
                '<meta name="twitter:card" content="summary_large_image">\n'
                '<meta name="twitter:title" content="...">\n'
                '<meta name="twitter:description" content="...">',
                auto_fixable=True,
            ))

    def _h1(self):
        m = self.SCORING["h1"]
        h1s = self.soup.find_all("h1")
        if not h1s:
            self.checks.append(Check("H1-otsikko", "Sivun SEO", 0, m, "fail",
                "Sivulta puuttuu H1-otsikko",
                "Lisää yksi H1, joka sisältää tärkeimmän avainsanan",
                "<h1>Sivun pääotsikko</h1>"))
        elif len(h1s) == 1:
            self.checks.append(Check("H1-otsikko", "Sivun SEO", m, m, "pass",
                f'Yksi H1 löytyy: "{_trunc(h1s[0].get_text(strip=True), 60)}"'))
        else:
            self.checks.append(Check("H1-otsikko", "Sivun SEO", m // 2, m, "warn",
                f"Sivulla on {len(h1s)} H1-otsikkoa – tulisi olla täsmälleen yksi",
                "Jätä vain yksi H1, muut muuta H2-otsikoiksi"))

    def _heading_hierarchy(self):
        m = self.SCORING["heading_hierarchy"]
        headings = []
        for level in range(1, 7):
            for tag in self.soup.find_all(f"h{level}"):
                headings.append(level)
        if not headings:
            self.checks.append(Check("Otsikkorakenne", "Sivun SEO", 0, m, "fail",
                "Sivulla ei ole otsikoita lainkaan",
                "Rakenna hierarkia: H1 (pääotsikko) → H2 (alaotsikot) → H3 (tarkentavat)"))
            return
        issues = []
        prev = 0
        for lv in headings:
            if prev and lv > prev + 1:
                issues.append(f"H{prev}→H{lv}")
            prev = lv
        if not issues:
            self.checks.append(Check("Otsikkorakenne", "Sivun SEO", m, m, "pass",
                f"Otsikkorakenne looginen ({len(headings)} otsikkoa)"))
        else:
            score = max(0, m - len(issues) * 2)
            self.checks.append(Check("Otsikkorakenne", "Sivun SEO", score, m, "warn",
                f"Otsikkohierarkiassa aukkoja: {', '.join(issues)}",
                "Korjaa otsikkojärjestys – älä hyppää tasoja yli"))

    def _images_alt(self):
        m = self.SCORING["images_alt"]
        imgs = self.soup.find_all("img")
        if not imgs:
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun SEO", m, m, "pass",
                "Sivulla ei ole kuvia"))
            return
        no_alt = [i for i in imgs if not i.get("alt")]
        if not no_alt:
            self.checks.append(Check("Kuvien alt-tekstit", "Sivun SEO", m, m, "pass",
                f"Kaikilla {len(imgs)} kuvalla on alt-teksti"))
        else:
            score = round(m * (len(imgs) - len(no_alt)) / len(imgs))
            self.checks.append(Check(
                "Kuvien alt-tekstit", "Sivun SEO", score, m,
                "fail" if score == 0 else "warn",
                f"{len(no_alt)}/{len(imgs)} kuvalta puuttuu alt-teksti",
                "Lisää kuvaava alt='...' jokaiselle kuvalle (SEO + saavutettavuus)"))

    def _json_ld(self):
        """Tarkistaa JSON-LD:n olemassaolon, skeematyypit ja FAQ-skeeman. Yhdistetty max 20."""
        mp = self.SCORING["jsonld_present"]
        ms = self.SCORING["schema_types"]
        mf = self.SCORING["faq_schema"]
        total_max = mp + ms + mf  # 20

        scripts = self.soup.find_all("script", type="application/ld+json")
        if not scripts:
            self.checks.append(Check(
                "JSON-LD / Structured Data", "AEO & Structured Data",
                0, total_max, "fail",
                "Sivulla ei ole JSON-LD rakenteellista dataa",
                "Lisää JSON-LD – kriittistä AEO:lle ja modernille SEO:lle. "
                "AI-assistentit käyttävät tätä sivun ymmärtämiseen.",
                self._basic_jsonld_snippet(),
                auto_fixable=True,
            ))
            return

        schemas = []
        for s in scripts:
            try:
                data = json.loads(s.string or "{}")
                if isinstance(data, list):
                    schemas.extend(data)
                elif isinstance(data, dict):
                    # Handle @graph
                    if "@graph" in data:
                        schemas.extend(data["@graph"])
                    else:
                        schemas.append(data)
            except json.JSONDecodeError:
                pass

        types = [str(s.get("@type", "")) for s in schemas]

        has_org = any(t in ("Organization", "LocalBusiness", "Corporation", "NGO") for t in types)
        has_site = any(t == "WebSite" for t in types)
        has_page = any(t in ("WebPage", "Article", "BlogPosting", "Product",
                             "Service", "FAQPage", "HowTo") for t in types)
        has_faq = any(t == "FAQPage" for t in types)

        sp = mp  # present
        ss = min(ms, (3 if has_org else 0) + (3 if has_site else 0) + (2 if has_page else 0))
        sf = mf if has_faq else 0
        total = sp + ss + sf

        missing_recs = []
        missing_snippets = []
        if not has_org:
            missing_recs.append("Organization-skeema")
            missing_snippets.append(self._org_schema())
        if not has_faq:
            missing_recs.append("FAQPage-skeema (tärkein AEO:lle)")
            missing_snippets.append(self._faq_schema())
        if not has_site:
            missing_recs.append("WebSite-skeema")

        status = "pass" if total >= total_max * 0.7 else ("warn" if total > 0 else "fail")
        type_str = ", ".join(t for t in types if t) or "tuntematon"

        self.checks.append(Check(
            "JSON-LD / Structured Data", "AEO & Structured Data",
            total, total_max, status,
            f"Skeematyypit: {type_str}",
            "Lisää: " + ", ".join(missing_recs) if missing_recs else "",
            self._missing_jsonld_snippet(has_org, has_site, has_faq) if missing_recs else "",
            auto_fixable=bool(missing_snippets),
        ))

    def _canonical(self):
        m = self.SCORING["canonical"]
        tag = self.soup.find("link", rel="canonical")
        if tag and tag.get("href"):
            self.checks.append(Check("Canonical-tägi", "Tekninen SEO", m, m, "pass",
                f"Canonical löytyy: {tag['href']}"))
        else:
            href = self.url or "https://example.com/sivu"
            self.checks.append(Check(
                "Canonical-tägi", "Tekninen SEO", 0, m, "warn",
                "Canonical-tägi puuttuu",
                "Lisää canonical duplikaattisisällön välttämiseksi",
                f'<link rel="canonical" href="{href}">',
                auto_fixable=True,
            ))

    def _robots_meta(self):
        m = self.SCORING["robots_meta"]
        tag = self.soup.find("meta", attrs={"name": "robots"})
        if tag:
            content = (tag.get("content") or "").lower()
            if "noindex" in content:
                self.checks.append(Check(
                    "Robots Meta", "Tekninen SEO", 0, m, "fail",
                    f"VAROITUS: Sivu on merkitty noindex! Hakukoneet eivät indeksoi tätä.",
                    "Poista noindex, jos sivu halutaan hakukoneiden löydettäväksi",
                ))
            else:
                self.checks.append(Check("Robots Meta", "Tekninen SEO", m, m, "pass",
                    f"Robots meta: {content}"))
        else:
            # Puuttuva = oletus index,follow = OK
            self.checks.append(Check("Robots Meta", "Tekninen SEO", m - 1, m, "pass",
                "Robots meta puuttuu (oletus index,follow on OK)"))

    def _aeo_content(self):
        """AEO-sisältösignaalit: Q&A-rakenne, listat, sanasto."""
        m = self.SCORING["aeo_content"]
        score = 0
        notes = []
        issues = []

        body = self.soup.get_text(" ", strip=True)
        words = len(body.split())

        questions = re.findall(r"[A-ZÄÖÅ][^.!?]{10,}\?", body)
        if len(questions) >= 2:
            score += 3
            notes.append(f"{len(questions)} kysymystä")
        else:
            issues.append("Lisää Q&A-sisältöä – AI suosii kysymys-vastaus-muotoista tekstiä")

        lists = self.soup.find_all(["ul", "ol"])
        if lists:
            score += 2
            notes.append(f"{len(lists)} listaa")
        else:
            issues.append("Lisää listas (ul/ol) – AI siteeraa mieluiten rakenteellista sisältöä")

        if words >= 300:
            score += 3
            notes.append(f"{words} sanaa")
        elif words >= 100:
            score += 1
            notes.append(f"{words} sanaa")
            issues.append(f"Lisää tekstiä – tavoite vähintään 300 sanaa (nyt {words})")
        else:
            issues.append(f"Sivulla hyvin vähän tekstiä ({words} sanaa)")

        status = "pass" if score >= m * 0.7 else ("warn" if score > 0 else "fail")
        self.checks.append(Check(
            "AEO-sisältösignaalit", "AEO & Structured Data",
            score, m, status,
            f"Sisältösignaalit: {', '.join(notes) if notes else 'ei löydetty'}",
            " | ".join(issues) if issues else "",
        ))

    def _authority(self):
        """Auktoriteetti- ja luotettavuussignaalit."""
        m = self.SCORING["authority"]
        score = 0
        found = []
        missing = []

        body = self.soup.get_text(" ", strip=True)
        links = self.soup.find_all("a")
        hrefs = [a.get("href", "").lower() for a in links]
        texts = [a.get_text(strip=True).lower() for a in links]
        nav = hrefs + texts

        if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", body):
            score += 2; found.append("sähköposti")
        else:
            missing.append("sähköpostiosoite")

        if re.search(r"[\+\d][\d\s\-\(\)]{6,}\d", body):
            score += 1; found.append("puhelin")
        else:
            missing.append("puhelinnumero")

        if any("tietosuoja" in n or "privacy" in n or "gdpr" in n for n in nav):
            score += 2; found.append("tietosuojasivu")
        else:
            missing.append("tietosuojasivu (GDPR)")

        if any(any(k in n for k in ("meistä", "about", "yritys", "tietoa meistä")) for n in nav):
            score += 1; found.append("tietoa meistä")
        else:
            missing.append("tietoa meistä -sivu")

        socials = ("facebook.com", "twitter.com", "linkedin.com",
                   "instagram.com", "youtube.com", "x.com")
        if any(any(s in h for s in socials) for h in hrefs):
            score += 2; found.append("some-linkit")
        else:
            missing.append("some-linkit")

        status = "pass" if score >= m * 0.7 else ("warn" if score > 0 else "fail")
        self.checks.append(Check(
            "Auktoriteetti & luottamus", "Auktoriteetti",
            score, m, status,
            f"Löytyi: {', '.join(found) if found else '–'}",
            f"Puuttuu: {', '.join(missing)}" if missing else "",
        ))

    def _content_quality(self):
        m = self.SCORING["content_quality"]
        score = 0
        body = self.soup.get_text(" ", strip=True)
        words = len(body.split())

        first_p = self.soup.find("p")
        has_vp = first_p and len(first_p.get_text(strip=True).split()) >= 20
        if has_vp:
            score += 3

        if words >= 500:
            score += 4
        elif words >= 200:
            score += 2

        status = "pass" if score >= m * 0.6 else ("warn" if score > 0 else "fail")
        self.checks.append(Check(
            "Sisällön laatu", "Sisältö",
            score, m, status,
            f"{words} sanaa{', selkeä arvolupaus' if has_vp else ', arvolupaus epäselvä'}",
            "" if score >= m * 0.6 else
            "Kirjoita vahva arvolupaus ensimmäiseen kappaleeseen – mitä, kenelle, miksi nyt",
        ))

    # ── JSON-LD-generoijat ─────────────────────────────────────────────────

    def _basic_jsonld_snippet(self) -> str:
        data = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "@id": "#organization",
                    "name": "Yrityksesi nimi",
                    "url": self.url or "https://example.com",
                    "logo": {"@type": "ImageObject", "url": "https://example.com/logo.png"},
                    "contactPoint": {
                        "@type": "ContactPoint",
                        "telephone": "+358-xx-xxxxxxx",
                        "contactType": "customer service",
                        "availableLanguage": "Finnish",
                    },
                },
                {
                    "@type": "WebSite",
                    "@id": "#website",
                    "url": self.url or "https://example.com",
                    "name": "Sivuston nimi",
                    "publisher": {"@id": "#organization"},
                },
                {
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": "Mikä on palvelunne?",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": "Vastaus kysymykseen…",
                            },
                        }
                    ],
                },
            ],
        }
        return (
            '<script type="application/ld+json">\n'
            + json.dumps(data, indent=2, ensure_ascii=False)
            + "\n</script>"
        )

    def _org_schema(self) -> dict:
        return {
            "@type": "Organization",
            "@id": "#organization",
            "name": "Yrityksesi nimi",
            "url": self.url or "https://example.com",
        }

    def _faq_schema(self) -> dict:
        return {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "Mikä on palvelunne?",
                    "acceptedAnswer": {"@type": "Answer", "text": "Vastaus kysymykseen…"},
                }
            ],
        }

    def _missing_jsonld_snippet(self, has_org: bool, has_site: bool, has_faq: bool) -> str:
        additions = []
        if not has_org:
            additions.append(self._org_schema())
        if not has_site:
            additions.append({
                "@type": "WebSite",
                "url": self.url or "https://example.com",
                "name": "Sivuston nimi",
            })
        if not has_faq:
            additions.append(self._faq_schema())
        if not additions:
            return ""
        data = {"@context": "https://schema.org", "@graph": additions}
        return (
            '<script type="application/ld+json">\n'
            + json.dumps(data, indent=2, ensure_ascii=False)
            + "\n</script>"
        )


# ─── Korjaaja ──────────────────────────────────────────────────────────────

class PageFixer:
    """Soveltaa turvalliset, automaattiset korjaukset HTML-sivulle."""

    def __init__(self, html: str, url: str = ""):
        self.soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")
        self.url = url
        self.applied: List[str] = []

    def fix(self, checks: List[Check]) -> str:
        head = self.soup.find("head")
        if not head:
            return str(self.soup)
        for c in checks:
            if c.auto_fixable and c.status != "pass" and c.fix_snippet:
                self._apply(c, head)
        return str(self.soup)

    def _apply(self, c: Check, head):
        if c.name == "Meta Description":
            if not self.soup.find("meta", attrs={"name": "description"}):
                t = self.soup.new_tag("meta")
                t["name"] = "description"
                t["content"] = "Kuvaile sivusi sisältöä 120–160 merkissä. Sisällytä pääavainsana."
                head.append(t)
                self.applied.append("Lisätty meta description")

        elif c.name == "Canonical-tägi":
            if not self.soup.find("link", rel="canonical"):
                t = self.soup.new_tag("link")
                t["rel"] = "canonical"
                t["href"] = self.url or "/"
                head.append(t)
                self.applied.append("Lisätty canonical-tägi")

        elif c.name == "Open Graph":
            props = {
                "og:title": lambda: (self.soup.find("title") or {}).get_text() if hasattr(
                    self.soup.find("title"), "get_text") else "Otsikko",
                "og:description": lambda: (
                    self.soup.find("meta", attrs={"name": "description"}) or {}
                ).get("content", "Kuvaus"),
                "og:type": lambda: "website",
                "og:url": lambda: self.url or "/",
            }
            added = []
            for prop, getter in props.items():
                if not self.soup.find("meta", property=prop):
                    try:
                        val = getter()
                    except Exception:
                        val = "..."
                    t = self.soup.new_tag("meta")
                    t["property"] = prop
                    t["content"] = val or "..."
                    head.append(t)
                    added.append(prop)
            if added:
                self.applied.append(f"Lisätty OG-tagit: {', '.join(added)}")

        elif c.name == "Twitter Card":
            if not self.soup.find("meta", attrs={"name": "twitter:card"}):
                title_text = ""
                title_tag = self.soup.find("title")
                if title_tag:
                    title_text = title_tag.get_text()
                for name, content in [
                    ("twitter:card", "summary_large_image"),
                    ("twitter:title", title_text or "Otsikko"),
                ]:
                    t = self.soup.new_tag("meta")
                    t["name"] = name
                    t["content"] = content
                    head.append(t)
                self.applied.append("Lisätty Twitter Card -tagit")

        elif c.name == "JSON-LD / Structured Data" and c.fix_snippet:
            if not self.soup.find("script", type="application/ld+json"):
                parsed = BeautifulSoup(c.fix_snippet, "html.parser")
                head.append(parsed)
                self.applied.append("Lisätty JSON-LD (Organization, WebSite, FAQPage)")


# ─── Apufunktiot ───────────────────────────────────────────────────────────

def _trunc(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + "…"

def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False

def scores(checks: List[Check]) -> Tuple[int, int]:
    return sum(c.score for c in checks), sum(c.max_score for c in checks)

def grade(pct: float) -> str:
    for threshold, letter in [(90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")]:
        if pct >= threshold:
            return letter
    return "F"

def color_for(pct: float) -> str:
    return "green" if pct >= 70 else ("yellow" if pct >= 50 else "red")


# ─── Tulostus ──────────────────────────────────────────────────────────────

def print_results(checks: List[Check], title: str = "") -> None:
    s, mx = scores(checks)
    pct = s / mx * 100 if mx else 0
    if RICH:
        _rich_results(checks, title, s, mx, pct)
    else:
        _plain_results(checks, title, s, mx, pct)

def _rich_results(checks: List[Check], title: str, s: int, mx: int, pct: float) -> None:
    c = color_for(pct)
    if title:
        console.print(f"\n[bold]{title}[/bold]")
    console.print(Panel(
        f"[bold {c}]Pisteet: {s}/{mx} ({pct:.0f}%) – Arvosana: {grade(pct)}[/bold {c}]",
        title="AEO/SEO Score", border_style=c,
    ))
    cats: Dict[str, List[Check]] = {}
    for ch in checks:
        cats.setdefault(ch.category, []).append(ch)
    for cat, chs in cats.items():
        cs, cm = scores(chs)
        tbl = Table(title=f"{cat}  ({cs}/{cm})", box=box.ROUNDED, show_header=True, min_width=80)
        tbl.add_column("", width=3)
        tbl.add_column("Tarkistus", style="bold", min_width=22)
        tbl.add_column("Tulos", ratio=3)
        tbl.add_column("Pisteet", width=9, justify="right")
        for ch in chs:
            col = COLORS.get(ch.status, "white")
            tbl.add_row(
                ICONS.get(ch.status, "?"),
                ch.name,
                f"[{col}]{ch.message}[/{col}]",
                f"{ch.score}/{ch.max_score}",
            )
            if ch.suggestion:
                tbl.add_row("", "", f"[dim]→ {ch.suggestion}[/dim]", "")
        console.print(tbl)

def _plain_results(checks: List[Check], title: str, s: int, mx: int, pct: float) -> None:
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
    print(f"  Pisteet: {s}/{mx} ({pct:.0f}%) – {grade(pct)}")
    print("="*60)
    for ch in checks:
        print(f"\n  {ICONS.get(ch.status,'?')} [{ch.category}] {ch.name}: {ch.score}/{ch.max_score}")
        print(f"     {ch.message}")
        if ch.suggestion:
            print(f"     → {ch.suggestion}")


# ─── Raporttien generointi ─────────────────────────────────────────────────

def recommendations(checks: List[Check]) -> List[str]:
    priority = [
        ("JSON-LD / Structured Data",
         "Lisää JSON-LD rakenteellinen data – kriittistä AEO:lle. AI-assistentit käyttävät tätä."),
        ("Title-tägi", "Optimoi title: 30–60 merkkiä, pääavainsana + brändinimi"),
        ("Meta Description", "Kirjoita houkutteleva meta description: 120–160 merkkiä"),
        ("H1-otsikko", "Lisää yksi selkeä H1-otsikko pääavainsanalla"),
        ("Open Graph", "Lisää Open Graph -tagit some-jakoa varten"),
        ("AEO-sisältösignaalit", "Lisää Q&A-osio ja listat – AI suosii vastausmuotoista sisältöä"),
        ("Auktoriteetti & luottamus", "Lisää yhteystiedot, tietosuojasivu ja some-linkit"),
        ("Kuvien alt-tekstit", "Lisää alt-teksti kaikille kuville"),
        ("Canonical-tägi", "Lisää canonical-tägi duplikaattisisällön välttämiseksi"),
    ]
    bad = {c.name for c in checks if c.status != "pass"}
    return [rec for name, rec in priority if name in bad]

def md_report(
    target: str,
    target_type: str,
    before: List[Check],
    after: Optional[List[Check]],
    fixes: List[str],
    recs: List[str],
    ts: str,
) -> str:
    bs, bm = scores(before)
    bpct = bs / bm * 100 if bm else 0

    lines = [
        f"# AEO/SEO Auditointi – {target}",
        "",
        f"**Päivämäärä:** {ts}  ",
        f"**Kohde:** `{target}`  ",
        f"**Tyyppi:** {'URL (live-sivu)' if target_type == 'url' else 'Repositorio (paikalliset tiedostot)'}  ",
        "",
        "---",
        "",
        "## Ennen-tila",
        "",
        f"### Kokonaispisteet: {bs}/{bm} ({bpct:.0f}%) – Arvosana {grade(bpct)}",
        "",
    ]

    cats: Dict[str, List[Check]] = {}
    for c in before:
        cats.setdefault(c.category, []).append(c)

    for cat, chs in cats.items():
        cs, cm = scores(chs)
        lines += [f"#### {cat} ({cs}/{cm})", "",
                  "| Status | Tarkistus | Pisteet | Tulos |",
                  "|--------|-----------|---------|-------|"]
        for c in chs:
            lines.append(f"| {ICONS.get(c.status,'?')} | {c.name} | {c.score}/{c.max_score} | {c.message} |")
        lines.append("")
        sug = [(c.name, c.suggestion) for c in chs if c.suggestion]
        if sug:
            lines.append("**Parannusehdotukset:**")
            for name, s in sug:
                lines.append(f"- **{name}:** {s}")
            lines.append("")

    if fixes:
        lines += ["---", "", "## Tehdyt automaattiset korjaukset", ""]
        for f in fixes:
            lines.append(f"- ✅ {f}")
        lines.append("")

    if after:
        asc, amx = scores(after)
        apct = asc / amx * 100 if amx else 0
        delta = apct - bpct
        lines += [
            "---", "",
            "## Jälkeen-tila",
            "",
            f"### Kokonaispisteet: {asc}/{amx} ({apct:.0f}%) – Arvosana {grade(apct)}",
            "",
            f"**Parannus: {delta:+.0f} prosenttiyksikköä** "
            f"({'↑ parantunut' if delta > 0 else '→ ei muutosta'})",
            "",
        ]

    if recs:
        lines += ["---", "", "## Seuraavat suositellut toimenpiteet", ""]
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r}")
        lines.append("")

    lines += ["---", "", "*Raportti: AEO/SEO Audit Tool v1.0*"]
    return "\n".join(lines)


# ─── URL-auditointi ────────────────────────────────────────────────────────

def audit_url(url: str, fix: bool, out: Path) -> None:
    _header(f"AEO/SEO Auditointi – {url}")
    _info("Haetaan sivua…")

    try:
        resp = requests.get(url, headers={"User-Agent": "AEOSEOAuditBot/1.0"}, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        _err(f"Virhe haettaessa URL:ia: {e}")
        sys.exit(1)

    before = PageAuditor(html, url=url).run()
    print_results(before, "ENNEN – lähtötilanne")

    fixes_done: List[str] = []
    after: Optional[List[Check]] = None

    if fix:
        _info("Sovelletaan automaattiset korjaukset…")
        fixer = PageFixer(html, url=url)
        fixed_html = fixer.fix(before)
        fixes_done = fixer.applied
        after = PageAuditor(fixed_html, url=url).run()
        print_results(after, "JÄLKEEN – korjausten jälkeen")

        ts_file = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fixed_path = out / f"fixed_{ts_file}.html"
        fixed_path.write_text(fixed_html, encoding="utf-8")
        _ok(f"Korjattu HTML → {fixed_path}")

    _save_report(url, "url", before, after, fixes_done, out)

def _save_report(target: str, ttype: str, before: List[Check],
                 after: Optional[List[Check]], fixes: List[str], out: Path) -> None:
    recs = recommendations(before)
    ts_label = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    ts_file = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_name = re.sub(r"[^\w]", "_", target)[:40]
    md_path = out / f"audit_{safe_name}_{ts_file}.md"
    json_path = out / f"audit_{safe_name}_{ts_file}.json"

    md_path.write_text(
        md_report(target, ttype, before, after, fixes, recs, ts_label),
        encoding="utf-8",
    )

    bs, bm = scores(before)
    result_json = {
        "target": target,
        "target_type": ttype,
        "timestamp": ts_label,
        "before_score": bs,
        "before_max": bm,
        "before_pct": round(bs / bm * 100, 1) if bm else 0,
        "after_score": scores(after)[0] if after else bs,
        "fixes_applied": fixes,
        "recommendations": recs,
        "checks": [
            {"name": c.name, "category": c.category, "score": c.score,
             "max_score": c.max_score, "status": c.status,
             "message": c.message, "suggestion": c.suggestion}
            for c in before
        ],
    }
    json_path.write_text(json.dumps(result_json, indent=2, ensure_ascii=False), encoding="utf-8")

    if RICH:
        console.print(f"\n[bold green]Raportit tallennettu:[/bold green]")
        console.print(f"  📄 Markdown: {md_path}")
        console.print(f"  📊 JSON:     {json_path}")
    else:
        print(f"\nRaportit tallennettu:\n  {md_path}\n  {json_path}")


# ─── Repositorio-auditointi ────────────────────────────────────────────────

SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "__pycache__",
             "bower_components", ".cache", ".next", "build", "out"}

def audit_repo(repo: Path, fix: bool, out: Path) -> None:
    _header(f"AEO/SEO Repositorio-auditointi – {repo}")

    html_files = [
        f for f in (list(repo.rglob("*.html")) + list(repo.rglob("*.htm")))
        if not SKIP_DIRS.intersection(set(f.parts))
    ]

    if not html_files:
        _warn("Repositoriosta ei löydetty HTML-tiedostoja.")
        return

    _info(f"Löytyi {len(html_files)} HTML-tiedostoa")

    all_before: List[Check] = []
    all_after: List[Check] = []
    all_fixes: List[str] = []
    file_summaries = []

    for f in html_files:
        rel = f.relative_to(repo)
        if RICH:
            console.rule(f"[dim]{rel}[/dim]")
        else:
            print(f"\n{'─'*50}\n{rel}")

        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            _warn(f"Ei voitu lukea {f}: {e}")
            continue

        before = PageAuditor(html, file_path=str(f)).run()
        all_before.extend(before)
        print_results(before, str(rel))

        file_fixes: List[str] = []
        after = before

        if fix:
            bak = f.with_suffix(f.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(f, bak)
            fixer = PageFixer(html)
            fixed = fixer.fix(before)
            if fixer.applied:
                f.write_text(fixed, encoding="utf-8")
                file_fixes = fixer.applied
                for msg in file_fixes:
                    _ok(f"  {rel}: {msg}")
                all_fixes.extend(f"{rel}: {m}" for m in file_fixes)
                after = PageAuditor(fixed, file_path=str(f)).run()
                all_after.extend(after)

        bs, bm = scores(before)
        file_summaries.append({
            "file": str(rel),
            "before_score": bs,
            "before_max": bm,
            "before_pct": round(bs / bm * 100, 1) if bm else 0,
            "fixes": file_fixes,
        })

    # Yhteenveto
    ts, tm = scores(all_before)
    tpct = ts / tm * 100 if tm else 0
    if RICH:
        console.rule("[bold]YHTEENVETO[/bold]")
        c = color_for(tpct)
        console.print(Panel(
            f"[bold {c}]Kokonaispisteet (ka.): {ts}/{tm} ({tpct:.0f}%) – {grade(tpct)}[/bold {c}]\n"
            f"Tiedostoja auditoitu: {len(file_summaries)}"
            + (f"\nKorjauksia tehty: {len(all_fixes)}" if all_fixes else ""),
            title="Repositorion AEO/SEO Score", border_style=c,
        ))
        if fix and all_fixes:
            console.print("[yellow]Alkuperäiset tiedostot varmuuskopioitu (.bak)[/yellow]")
    else:
        print(f"\n{'='*60}")
        print(f"YHTEENVETO: {ts}/{tm} ({tpct:.0f}%) – {grade(tpct)}")
        print(f"Tiedostoja: {len(file_summaries)}")
        print("="*60)

    _save_repo_report(repo, all_before, all_after if fix else None,
                      all_fixes, file_summaries, out)

def _save_repo_report(repo: Path, before: List[Check], after: Optional[List[Check]],
                      fixes: List[str], summaries, out: Path) -> None:
    recs = recommendations(before)
    ts_label = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    ts_file = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = repo.name.replace(" ", "_")

    md_path = out / f"audit_{name}_{ts_file}.md"
    json_path = out / f"audit_{name}_{ts_file}.json"

    md_path.write_text(
        md_report(str(repo), "repo", before, after, fixes, recs, ts_label),
        encoding="utf-8",
    )

    bs, bm = scores(before)
    result_json = {
        "target": str(repo),
        "target_type": "repo",
        "timestamp": ts_label,
        "files_audited": len(summaries),
        "before_score": bs,
        "before_max": bm,
        "before_pct": round(bs / bm * 100, 1) if bm else 0,
        "after_score": scores(after)[0] if after else bs,
        "fixes_applied": fixes,
        "recommendations": recs,
        "files": summaries,
    }
    json_path.write_text(json.dumps(result_json, indent=2, ensure_ascii=False), encoding="utf-8")

    if RICH:
        console.print(f"\n[bold green]Raportit tallennettu:[/bold green]")
        console.print(f"  📄 Markdown: {md_path}")
        console.print(f"  📊 JSON:     {json_path}")
    else:
        print(f"\nRaportit:\n  {md_path}\n  {json_path}")


# ─── Konsoliapufunktiot ────────────────────────────────────────────────────

def _header(msg: str) -> None:
    if RICH:
        console.print(f"\n[bold blue]{msg}[/bold blue]\n")
    else:
        print(f"\n{msg}\n")

def _info(msg: str) -> None:
    if RICH:
        console.print(f"[dim]{msg}[/dim]")
    else:
        print(msg)

def _ok(msg: str) -> None:
    if RICH:
        console.print(f"[green]{msg}[/green]")
    else:
        print(msg)

def _warn(msg: str) -> None:
    if RICH:
        console.print(f"[yellow]{msg}[/yellow]")
    else:
        print(f"VAROITUS: {msg}")

def _err(msg: str) -> None:
    if RICH:
        console.print(f"[red]{msg}[/red]")
    else:
        print(f"VIRHE: {msg}")


# ─── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEO/SEO Audit & Optimization Tool v1.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esimerkkejä:
  %(prog)s --url https://example.com
  %(prog)s --url https://example.com --fix
  %(prog)s --repo /path/to/website
  %(prog)s --repo /path/to/website --fix
  %(prog)s --repo . --fix --output ./raportit
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Auditoitavan sivuston URL")
    group.add_argument("--repo", help="Auditoitavan repositorion polku")
    parser.add_argument("--fix", action="store_true",
                        help="Sovella automaattiset korjaukset")
    parser.add_argument("--output", default="./reports",
                        help="Raporttihakemisto (oletus: ./reports)")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    if args.url:
        audit_url(args.url, args.fix, out)
    else:
        repo = Path(args.repo).resolve()
        if not repo.exists():
            _err(f"Hakemistoa ei löydy: {repo}")
            sys.exit(1)
        audit_repo(repo, args.fix, out)


if __name__ == "__main__":
    main()
