"""V8: ilmoitus uudesta liidistä — Resend, yksi requests.post.

Lähettäjänä on anglesmarketing.fi, verifioitu Resendissä (alue eu-west-1,
Irlanti — henkilötiedot pysyvät EU:ssa). RESEND_FROM voi yhä ohittaa arvon
ilman koodimuutosta.

Jos RESEND_API_KEY tai NOTIFY_EMAIL puuttuu, ohitetaan hiljaa ja kerrotaan se
paluuarvossa. Puuttuva konfiguraatio ei ole virhe jonka asiakas näkee.
"""
import os
from typing import Any, Dict

import requests

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "Anglés liidit <liidit@anglesmarketing.fi>"
TIMEOUT = (2, 5)


def _rivi(otsikko: str, arvo: Any) -> str:
    arvo = str(arvo or "").strip()
    return f"{otsikko}: {arvo}\n" if arvo else ""


def contact_lead(lead: Dict[str, Any]) -> str:
    """Lähettää ilmoituksen uudesta yhteydenotosta.

    Palauttaa: "ok" | "skipped" (konfiguraatio puuttuu) | "error"."""
    key = os.environ.get("RESEND_API_KEY", "")
    to = os.environ.get("NOTIFY_EMAIL", "")
    if not key or not to:
        return "skipped"

    nimi = str(lead.get("nimi") or "").strip()
    email = str(lead.get("email") or "").strip()
    teksti = (
        "Uusi yhteydenotto anglesmarketing.fi:stä.\n\n"
        + _rivi("Nimi", nimi)
        + _rivi("Sähköposti", email)
        + _rivi("Ala", lead.get("ala"))
        + _rivi("Paketti", lead.get("paketti"))
        + _rivi("Lähde", lead.get("source"))
        + "\nViesti:\n"
        + str(lead.get("viesti") or "(ei viestiä)")
        + "\n"
    )

    try:
        resp = requests.post(RESEND_URL, timeout=TIMEOUT, headers={
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
        }, json={
            "from": os.environ.get("RESEND_FROM", DEFAULT_FROM),
            "to": [t.strip() for t in to.split(",") if t.strip()],
            # reply_to, jotta Kim voi vastata liidille suoraan postilaatikosta
            "reply_to": email,
            "subject": f"Uusi yhteydenotto: {nimi or email or 'tuntematon'}",
            "text": teksti,
        })
        return "ok" if resp.status_code in (200, 201, 202) else "error"
    except requests.RequestException:
        return "error"
