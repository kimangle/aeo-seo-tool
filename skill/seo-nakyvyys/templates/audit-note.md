<!--
Template for the vault note <vault_dir>/search-console-YYYY-MM-DD.md (config baseline_note).
The note is written in the vault's language (Finnish in this template) and grows during the run:
steps 1-2 fill Luvut, Havainnot and Ehdotukset (every ranked item, not only the five shown);
step 3 adds the decision; steps 4-6 append Toteutus, Julkaisu and Search Console -toimet.
If the day's note exists already, append a section "## <sivustot> klo HH.MM" with the same
headings one level down instead of overwriting. Run `date "+%H.%M"` before every timestamp.
Write the user's decisions in their exact words with the time. Numbers only as read, with
the date range Search Console shows. Delete these comment lines in the real note.
-->
---
tags: [seo, search-console]
paivitetty: YYYY-MM-DD
---

# Search Console -katsaus D.M.YYYY

Luettu Chromesta klo HH.MM–HH.MM. Data ulottuu D.M. asti. Edellinen vastaava: [[search-console-EDELLINEN]].

Kiinteistöt: <lista>. Vahvistamatta: <lista tai "ei yhtään">.

## Luvut

| Sivusto | Jakso | Klikkaukset | Näyttökerrat | CTR | Sijainti | Indeksissä |
|---|---|---|---|---|---|---|
| esimerkki.fi | D.M.–D.M. | 0 | 0 | 0 % | 0,0 | N (M ei: syyt) |
| esimerkki.fi | 28 pv vs. edelliset 28 | a vs. b | a vs. b | a vs. b % | a vs. b | |

## Havainnot

**esimerkki.fi.** Mistä klikkaukset tulevat (kyselyt, näytöt, sijainti). Mitkä sivut saavat näyttöjä ilman klikkauksia. Kaukana olevat pääsanat. Vertailu edelliseen katsaukseen.

## Ehdotukset (ei vielä päätetty)

1. Sivusto: korjaus. Peruste (kysely, näytöt, sijainti). Kuka hyväksyy. Arvio.
2. ...

Kaikki priorisoidut kohdat tähän; käyttäjälle näytetään viisi ensimmäistä, loput odottavat seuraavaa kierrosta.

## Päätös (<käyttäjä> D.M. klo HH.MM: "sanatarkka lainaus")

## Toteutus

Workflow `wf_...` käynnistetty klo HH.MM: N toteuttajaa, N yhdistäjää, N tarkastajaa. Worktreet kansiossa `~/wt-seo-MMDD/`.

| Sivusto | Haara @ HEAD | Esikatselu | release_ok / esteet |
|---|---|---|---|

Omistajan tarkistus: <miten X näkee luonnoksen: kuvakaappaukset tai teksti käyttäjän Chromesta, tapaaminen, käyttäjän oma jakolinkki>.

## Julkaisu klo HH.MM (<käyttäjä>: "sanatarkka lupa")

- esimerkki.fi: main <vanha> → <uusi> (fast-forward / vercel deploy --prod). Tarkistettu verify_prod.sh: N PASS, N WARN.
- Käyttäjän checkout: <päivitetty ff-only / varoitus: älä aja vercel deploy --prod vanhasta checkoutista>.
- Tiedoksi julkaistu (lakisääteinen teksti): <commit, kenelle kerrotaan>.

## Search Console -toimet ja IndexNow (klo HH.MM)

- Indeksointipyynnöt: <URL:t>.
- Sivukartat: <lähetetty / ei tarvittu>.
- IndexNow: <sivusto> HTTP <koodi>.

## Seuranta

- D.M. ja D.M.: vertaa tähän lähtötasoon (rivi muistutustiedostossa, config reminders_file).
- Seuraava kierros: <Ehdotukset-osion avoimet kohdat>.
- Avoimet: <kenen OK puuttuu, mitä käyttäjä tekee itse>.
