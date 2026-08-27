# Kotitaulu — määrittelydokumentti

**Versio:** 1.0.1
**Päivitetty:** 2026-08-27
**Tila:** Kuvaa nykyistä toteutusta (reverse-engineered koodista) + tiedossa olevia jatkokehitystarpeita

## 1. Tarkoitus ja tavoite

Kotitaulu on kodin seinälle/tabletille tarkoitettu **päivittäinen muistitaulu**, joka kokoaa yhdelle näkymälle perheen kannalta olennaisen ajantasaisen tiedon: kalenteritapahtumat, tärkeät sähköpostit, kodin älylaitteiden tilat ja ostoslistat, sään, uutisotsikot, osakekurssit sekä paikallisia tapahtumia. Tavoitteena on korvata jääkaapin muistilaput ja useiden sovellusten erillinen tarkistaminen yhdellä automaattisesti päivittyvällä näytöllä, joka toimii ilman käyttäjän aktiivista vuorovaikutusta.

**Käytössä oleva ajoympäristö on kaksi erillistä Raspberry Pi -laitetta:**

1. **HA-palvelin** (Raspberry Pi, ajaa Home Assistantia) — Kotitaulu ajetaan tällä **HA-lisäosana** (add-on), asennettuna GitHub-repositoriosta (`https://github.com/jventa/kotitaulu`).
2. **Näyttö-Pi** (Raspberry Pi 3 + kytketty kosketusnäyttö) — erillinen laite, jolla pyörii selain kioskitilassa ja joka näyttää HA-palvelimen tarjoaman web-käyttöliittymän (`http://<ha-palvelin>:8000`) verkon yli.

Tämä kahden laitteen jako on tietoinen arkkitehtuurivalinta: sovelluslogiikka ja data-integraatiot (Google, HA, sää, uutiset…) pysyvät HA-palvelimella, kun taas näyttöyksikkö on kevyt, tilaton kioski-pääte joka voidaan tarvittaessa vaihtaa tai käynnistää uudelleen vaikuttamatta dataan.

## 2. Arkkitehtuuri

### 2.1 Fyysinen topologia

```
┌───────────────────────────────┐        ┌──────────────────────────────────┐
│  NÄYTTÖ-PI (Raspberry Pi 3)    │  HTTP  │  HA-PALVELIN (Raspberry Pi)       │
│  + kytketty kosketusnäyttö     │◄──────►│  Home Assistant OS/Supervised     │
│  Chromium kioskitilassa        │  LAN   │  └─ Kotitaulu-lisäosa (Docker)    │
│  (ei sovelluslogiikkaa,        │        │      koko backend + frontend     │
│   vain selain + kosketus)      │        │      kts. kaavio alla            │
└───────────────────────────────┘        └──────────────────────────────────┘
```

Näyttö-Pi ei aja mitään Kotitaulun koodia — se on pelkkä selainpääte, joka lataa HA-palvelimen tarjoaman sivun (`http://<ha-palvelin>:8000`) verkon yli. Kaikki data, ajastus ja integraatiot elävät yksinomaan HA-palvelimella ajettavassa lisäosassa.

### 2.2 Sovelluksen sisäinen arkkitehtuuri (HA-palvelimella ajettava lisäosa)

```
┌─────────────────────────────────────────────────────────┐
│  Selain (kioskitila, tablettti / seinänäyttö)            │
│  frontend/ — vanilla HTML + CSS + JS, ei build-vaihetta  │
└───────────────────────┬─────────────────────────────────┘
                         │ HTTP (staattinen + JSON-API)
┌───────────────────────▼─────────────────────────────────┐
│  FastAPI-sovellus (backend/main.py)                      │
│  ├─ StaticFiles: tarjoilee frontend/-hakemiston          │
│  ├─ GET  /health                                         │
│  ├─ GET  /api/items     ← lukee SQLitestä                │
│  └─ POST /api/refresh   ← ajaa kaikki fetcherit heti     │
├───────────────────────────────────────────────────────────┤
│  APScheduler (backend/scheduler.py)                      │
│  └─ ajastettu cron-job (oletus klo 06:00) → fetcherit    │
├───────────────────────────────────────────────────────────┤
│  Fetcher-moduulit (backend/fetchers/*.py)                │
│  google_calendar · gmail · home_assistant · weather ·    │
│  rss · stocks · web_scraper · kauhavan_seurakunta        │
├───────────────────────────────────────────────────────────┤
│  Tallennus (backend/storage.py) — aiosqlite               │
│  taulut: items, fetcher_log                              │
└─────────────────────────────────────────────────────────┘
```

**Teknologiavalinnat**

| Osa-alue | Teknologia |
|---|---|
| Backend-runko | Python 3.12, FastAPI + Uvicorn |
| Ajastus | APScheduler (`AsyncIOScheduler`, cron-tyyppinen job) |
| Tietokanta | SQLite (`aiosqlite`), tiedosto `kotitaulu.db` |
| HTTP-kutsut ulos | `httpx` (async) |
| HTML-jäsennys | `BeautifulSoup4` |
| RSS | `feedparser` |
| Osakekurssit | `yfinance` |
| Google-integraatiot | `google-api-python-client` + OAuth 2.0 (`google-auth-oauthlib`) |
| Konfigurointi | `PyYAML` + `python-dotenv` |
| Frontend | Vanilla JS/HTML/CSS, ei kehysriippuvuutta, ei build-askelta |
| Kontitus | Docker (`python:3.12-alpine`), sekä Home Assistant add-on (`config.yaml`, `build.yaml`) |

Backend ja frontend eivät ole erotettu erillisiksi palveluiksi: FastAPI mountaa `frontend/`-hakemiston juureen (`StaticFiles(..., html=True)`), joten koko sovellus ajetaan yhdellä prosessilla ja yhdellä portilla (8000).

## 3. Tietomalli

### Taulu `items`

| Sarake | Tyyppi | Kuvaus |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `source` | TEXT | Fetcherin nimi (esim. `weather`, `google_calendar`) |
| `title` | TEXT | Otsikko/pääteksti |
| `detail` | TEXT? | Lisätieto (paikka, lähettäjä, hinta, kuvaus…) |
| `time` | TEXT? | ISO-aikaleima tai `null` (aikaan sitomaton kohde) |
| `url` | TEXT? | Linkki, jos relevantti |
| `priority` | TEXT | `low` \| `normal` \| `high`, oletus `normal` |
| `fetched_at` | TEXT | Haun ajanhetki (UTC ISO) |

**Kirjoitusperiaate:** `save_items(source, items)` **poistaa ensin kaikki kyseisen lähteen rivit** ja lisää sen jälkeen tuoreet — taulu edustaa siis aina vain viimeisimmän onnistuneen haun tilaa lähteittäin, ei historiaa.

### Taulu `fetcher_log`

| Sarake | Tyyppi | Kuvaus |
|---|---|---|
| `id` | INTEGER PK | Autoincrement |
| `source` | TEXT | Fetcherin nimi |
| `status` | TEXT | `ok` \| `error` |
| `message` | TEXT | Vapaamuotoinen viesti (esim. rivimäärä tai virheteksti) |
| `fetched_at` | TEXT | Ajanhetki (UTC ISO) |

Lokitaulua ei tällä hetkellä näytetä käyttöliittymässä — se on diagnostiikkaa varten tietokannassa.

## 4. Rajapinnat (API)

| Metodi | Polku | Kuvaus | Vastaus |
|---|---|---|---|
| `GET` | `/health` | Liveness-tarkistus | `{"status": "ok"}` |
| `GET` | `/api/items` | Kaikki tallennetut kohteet, ryhmiteltynä lähteittäin | `{"sources": {lähde: [kohde, …]}, "total": n}` |
| `POST` | `/api/refresh` | Käynnistää kaikkien fetchereiden haun synkronisesti ja palauttaa tulokset | `{"refreshed": {lähde: määrä, …}}` |
| `GET` | `/` (ja muut staattiset polut) | Frontend (`index.html`, `app.js`, `style.css`) | HTML/JS/CSS |

Autentikointia tai käyttäjätunnistusta rajapinnoissa ei ole — sovellus on tarkoitettu ajettavaksi luotetussa kotiverkossa.

## 5. Tietolähteet (fetcherit)

Jokainen fetcher toteuttaa yhteisen rajapinnan `async def fetch() -> list[FetchResult]` (`backend/fetchers/__init__.py`), ja jokainen kunnioittaa oman lähteensä `enabled`-asetusta konfiguraatiossa. Virhetilanteessa yksittäisen fetcherin poikkeus kirjataan lokiin, eikä se estä muiden fetchereiden ajoa (`scheduler.run_all_fetchers`).

| Fetcher | Lähde / rajapinta | Mitä hakee | Keskeiset asetukset | Prioriteettilogiikka |
|---|---|---|---|---|
| `google_calendar` | Google Calendar API v3 | Kaikkien käyttäjän kalenterien tapahtumat seuraavan N päivän ajalta, duplikaatit poistettu ID:n perusteella, aikajärjestyksessä | `days_ahead` | aina `normal` |
| `gmail` | Gmail API | Viimeisimmät viestit annetulla hakulausekkeella (oletus `is:unread is:important`) | `max_results`, `query` | `high` jos Gmail-labeli `IMPORTANT` |
| `home_assistant` | HA REST API (`/api/states`, `/api/services/todo/get_items`) | Valittujen entiteettien nykyarvot (lämpötila, sähkön hinta, termostaatti…) + valittujen todo-listojen avoimet (`needs_action`) rivit | `entities[]`, `todo_lists[]` | aina `normal` |
| `weather` | Open-Meteo (avainton) | Nykysää (lämpötila, sääkoodi, tuuli) + 2 seuraavan päivän ennuste (min/max, sade) | sijainti `LOCATION` (lat/lon/timezone) | aina `normal` |
| `rss` | `feedparser` | Uusimmat otsikot määritetyistä RSS-syötteistä | `feeds[]` (url, title, max_items) | aina `normal` |
| `stocks` | Yahoo Finance (`yfinance`) | Viimeisin kurssi + muutos-% edelliseen päätöskurssiin | `symbols[]` | `high` jos \|muutos-%\| ≥ 5 |
| `web_scraper` | Yleiskäyttöinen HTML-kaavinta (`httpx` + BeautifulSoup, valinnaisesti ScrapingBee JS-renderöintiin) | CSS-selectorilla poimitut otsikot/linkit miltä tahansa sivustolta | `sites[]` (url, selector, title, max_items, render_js) | aina `normal` |
| `kauhavan_seurakunta` | Kauhavan seurakunnan tapahtumasivu (kaavinta, FlareSolverr tai ScrapingBee Cloudflare-suojan ohitukseen) | Tämän ja huomisen päivän tapahtumat (otsikko, klo, paikka, kuvaus) | kiinteä URL koodissa; `FLARESOLVERR_URL` / `SCRAPINGBEE_API_KEY` | aina `normal` |

> Huom: `kauhavan_seurakunta` on käyttäjäkohtainen/paikallinen esimerkki yleisestä `web_scraper`-mekanismista — se ei ole yleiskäyttöinen, vaan koodattu erikseen sivuston erikoisrakenteen (päivämäärien jäsennys suomeksi, Cloudflare-suoja) vuoksi.

## 6. Ajastus ja päivityslogiikka

- **Automaattinen haku:** `APScheduler`-cron-job ajaa `run_all_fetchers()` kerran päivässä, oletusarvoisesti klo 06:00 (`scheduler.daily_refresh_hour/minute` konfiguraatiossa).
- **Manuaalinen haku:** `POST /api/refresh` ajaa kaikki fetcherit heti pyynnön sisällä (synkronisesti), ja frontendin päivitysnappi kutsuu tätä.
- **Frontendin auto-refresh:** selain hakee `/api/items`-datan uudelleen 60 sekunnin välein, joten näytölle päivittyvät viimeisimmän onnistuneen taustahaun tulokset ilman sivun uudelleenlatausta. Kello päivittyy joka sekunti.
- Yksittäisen lähteen epäonnistuminen (esim. verkkovirhe, token vanhentunut) ei poista sen vanhoja rivejä tietokannasta eikä estä muita lähteitä — vanha data jää näkyviin kunnes seuraava onnistunut haku korvaa sen.

## 7. Käyttöliittymä

- **Näkymä on yksi näyttö ilman vierittämistä** (`html, body { overflow: hidden }`) — suunniteltu kiinteälle seinänäytölle/tabletille, ei mobiilikäyttöön skrollattavaksi listaksi.
- **Header:** sovelluksen nimi, keskellä reaaliaikainen kello + päivämäärä suomeksi, oikealla manuaalinen päivitysnappi (↻).
- **Pääsisältö:** lähdekohtaiset kortit (`source-card`) kiinteässä järjestyksessä: sää → kalenteri → seurakunta → koti → uutiset → osakkeet → sähköposti → verkkosivut. Jokaisella lähteellä oma ikoni ja suomenkielinen otsikko (`SOURCE_LABELS`/`SOURCE_ICONS` `app.js`:ssä).
- **Kohteen esitys:** aika (tänään = klo, huomenna = "huom. klo", muu päivä = viikonpäivä + pvm), otsikko (linkkinä jos `url` asetettu), lisätieto. Prioriteetti (`priority-high/normal/low`) vaikuttaa CSS-korostukseen (esim. oranssi `--high`-väri kiireellisille).
- **Tyhjä lähde:** näytetään "Ei kohteita" -teksti kortissa piilottamisen sijaan.
- **Tumma teema** oletuksena (`--bg: #0f1117`), suunniteltu luettavaksi huoneen valaistuksessa etäältä.
- **Footer:** viimeisimmän frontend-päivityksen kellonaika.

## 8. Konfiguraatio

Sovelluksella on kaksi rinnakkaista konfiguraatiotapaa riippuen ajoympäristöstä (`backend/config.py` tunnistaa tämän `/data/options.json`-tiedoston olemassaolosta):

### 8.1 Itsenäinen ajo (`.env` + `app_config.yaml`)

`.env` — salaisuudet ja ympäristökohtaiset arvot:
- `HA_URL`, `HA_TOKEN` — Home Assistant -yhteys
- `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_TOKEN_FILE` — Google OAuth -tiedostopolut
- `SCRAPINGBEE_API_KEY` — JS-renderöityjen/Cloudflare-suojattujen sivujen kaavintaan

`app_config.yaml` — toiminnallinen konfiguraatio:
- `location` (lat/lon/timezone) — sään ja aikavyöhykkeen perusta
- `scheduler` (daily_refresh_hour/minute)
- `sources.*` — jokaisen fetcherin `enabled`-lippu ja lähdekohtaiset asetukset (feedit, symbolit, entiteetit, sivustot…)
- `flaresolverr_url` — vaihtoehto ScrapingBeelle Cloudflare-ohitukseen

### 8.2 Home Assistant -lisäosana (`config.yaml` + `build.yaml`)

Sovellus on pakattu myös HA:n add-on-formaattiin:
- `config.yaml` määrittää add-onin metatiedot (nimi, versio, portit, arkkitehtuurit `aarch64/amd64/armhf/armv7`), sekä HA:lta saatavat oikeudet (`homeassistant_api: true`, `auth_api: true`, `map: [config:rw]`).
- Käyttäjän muokattavat optiot (`ha_token`, `scrapingbee_api_key`, `flaresolverr_url`, Google-tiedostopolut) syötetään HA:n lisäosa-UI:n kautta ja luetaan ajonaikaisesti `/data/options.json`:sta.
- Add-on-tilassa `HA_URL`/`HA_TOKEN` haetaan automaattisesti Supervisorilta (`http://supervisor/core`, `SUPERVISOR_TOKEN`/`HASSIO_TOKEN`) — käsin asetettua tokenia ei tällöin tarvita.
- Tietokanta ja pysyvä data tallennetaan `/data`-hakemistoon (add-onin persistentti tila), Google-tiedostot luetaan `/config`-hakemistosta (HA:n jaettu config-kansio).

## 9. Google OAuth -integraatio

- `python -m backend.auth_setup` ajetaan kertaluontoisesti kehittäjän/käyttäjän toimesta: avaa selaimen OAuth-suostumusta varten `credentials.json`-tiedoston pohjalta (luotu Google Cloud Consolessa, tyyppi "Desktop app", API:t Calendar + Gmail käytössä) ja tallentaa saadun `token.json`:n.
- `token.json` sisältää refresh-tokenin, jolla `google_calendar.py` ja `gmail.py` uusivat access-tokenin automaattisesti tarvittaessa (`creds.refresh(Request())`) — käyttäjän ei tarvitse kirjautua uudelleen normaalikäytössä.
- Jos `token.json` puuttuu, `google_calendar`-fetcher palauttaa tyhjän listan sen sijaan että kaataisi koko haun.

## 10. Käyttöönotto

**Paikallinen kehitys/ajo:**
```bash
pip install -r requirements.txt
cp .env.example .env           # täytä HA_TOKEN
python -m backend.auth_setup   # kerran: Google OAuth (kalenteri + gmail)
uvicorn backend.main:app --reload
```
Sovellus avautuu osoitteessa `http://localhost:8000`. Manuaalinen haku: `curl -X POST http://localhost:8000/api/refresh`.

**Docker:** `Dockerfile` rakentaa `python:3.12-alpine`-pohjaisen kuvan, kopioi `backend/`, `frontend/` ja `app_config.yaml`, ja käynnistää Uvicornin porttiin 8000.

**Home Assistant -lisäosana:** repositorio lisätään HA:n add-on-lähteeksi, `config.yaml`/`build.yaml` ohjaavat asennuksen ja optioiden UI:n muodostumisen kaikille tuetuille arkkitehtuureille.

### 10.1 Päivitysvirta: tästä kehityshakemistosta HA-palvelimelle

Kotitaulua **ei** päivitetä kopioimalla tiedostoja käsin HA-palvelimelle — päivitys kulkee kokonaan Git-repositorion kautta, koska lisäosa on asennettu HA:n Add-on Storeen repositorio-lähteenä (ei paikallisena/local-lisäosana):

```
tämä hakemisto (kehitys)
   │  git commit + git push
   ▼
GitHub: github.com/jventa/kotitaulu (origin/master)
   │  HA Supervisor pollaa/pullaa repositorion sisällön
   ▼
HA Add-on Store havaitsee version noston config.yaml:ssa
   │  käyttäjä (tai automaatio) painaa "Update" → Supervisor rakentaa imagen build.yaml:n mukaan
   ▼
Kotitaulu-lisäosa käynnistyy uudelleen HA-palvelimella
```

**Ehdot, jotta päivitys näkyy automaattisesti:**
1. Muutokset on pushattu `master`-haaraan GitHubissa (paikallinen `git commit` ei riitä).
2. `config.yaml`:n `version`-kenttää **on nostettu** edelliseen julkaistuun versioon nähden — HA Supervisor vertailee vain tätä kenttää, ei commit-historiaa tai tiedostosisältöä.
3. HA on hakenut repositorion tuoreen tilan — tämä tapahtuu joko Supervisorin omalla ajastetulla tarkistuksella, tai manuaalisesti: *Lisäosakauppa → ⋮ → Reload/Tarkista päivitykset*.

Kun nämä kolme ehtoa täyttyvät, Add-on Store näyttää "Update available" ilman että HA-palvelimelle tarvitsee ottaa erikseen SSH-yhteyttä tai ajaa mitään käsin — koko virta on Git-pohjainen, kuten haluttu.

**Käytännön muistilista jokaiselle julkaisulle:**
```bash
# tässä hakemistossa
# 1. tee muutokset
# 2. nosta versio config.yaml:ssa (esim. 1.0.1 → 1.0.2)
git add -A
git commit -m "kuvaus muutoksesta"
git push origin master
# → mene HA:n Lisäosakauppaan, Reload, Update, Restart
```

### 10.2 Näyttö-Pi (kioski) — asennus ja vaatimukset

Näyttö-Pi (Raspberry Pi 3 + kosketusnäyttö) ei ole osa tätä repositoriota — se on erillinen laite, jolla ajetaan pelkkää selainta kioskitilassa osoitteessa `http://<ha-palvelimen-ip>:8000`.

**Vaatimus — kosketuksella herätys:** Näytön tulee olla oletuksena sammutettuna/himmennettynä (energiansäästö, ruudunpolton esto), ja **herätä päälle heti kun sitä kosketetaan**. Tämä ei ole tällä hetkellä toteutettu, ja se toteutetaan kokonaan Näyttö-Pi:n käyttöjärjestelmätasolla (X11/Wayland-näytönhallinta), ei Kotitaulun sovelluskoodissa — sovellus itsessään ei tiedä mitään näytön virtatilasta.

Tyypillinen toteutustapa Raspberry Pi OS + X11 -yhdistelmällä:
- `xset` hallitsee DPMS-tilaa (`xset dpms 0 0 <sekuntia>` sammuttaa näytön X sekunnin jouten olon jälkeen)
- Kosketustapahtuma X-palvelimessa lasketaan "aktiviteetiksi" ja herättää näytön automaattisesti DPMS:n omalla logiikalla — tämä toimii yleensä suoraan ilman lisäkonfigurointia, jos näyttöajuri raportoi kosketuksen oikein X:lle
- Jos kosketus ei herätä näyttöä luotettavasti (yleinen ongelma joillain kosketuspaneeleilla/ajureilla), tarvitaan erillinen taustaprosessi joka kuuntelee `/dev/input/eventX`-laitetta (esim. `evtest`/`libinput`) ja pakottaa `xset dpms force on` kosketuksen yhteydessä

Tämä osio jätetään tässä vaiheessa **vaatimustasolle** — konkreettinen toteutus (käytettävä näyttöohjain, Raspberry Pi OS -versio, X11 vs. Wayland) pitää selvittää Näyttö-Pi:n nykyisestä asennuksesta ennen kuin ratkaisu voidaan koodata.

## 11. Laajennettavuus — uuden tietolähteen lisääminen

1. Luo `backend/fetchers/uusi.py`, toteuta `async def fetch() -> list[FetchResult]`.
2. Lisää rivi `_FETCHERS`-listaan (`backend/scheduler.py`).
3. Lisää asetukset `app_config.yaml`:n `sources:`-osioon, lue ne `config.SOURCES`:sta.
4. Halutessa lisää lähteelle otsikko/ikoni `frontend/app.js`:n `SOURCE_LABELS`/`SOURCE_ICONS`-tauluihin ja järjestys `order`-listaan — muuten kortti näkyy raa'alla lähdenimellä oletusikonilla.

## 12. Ei-toiminnalliset vaatimukset ja rajoitukset

- **Suorituskyky:** haut ajetaan kerran päivässä + manuaalisesti; ei reaaliaikavaatimusta. `/api/refresh` on synkroninen ja voi kestää useita sekunteja (erityisesti kaavinta-fetcherit), koska se odottaa kaikkien lähteiden valmistumista.
- **Luotettavuus:** yhden lähteen virhe ei kaada koko päivitystä; vanha data säilyy näkyvissä lähteen epäonnistuessa.
- **Turvallisuus:** ei autentikointia API-tasolla — sovellus on tarkoitettu vain luotettuun kotiverkkoon. Salaisuudet (HA-token, Google-credentials, ScrapingBee-avain) pidetään `.env`/`credentials.json`/`token.json`-tiedostoissa, jotka on syytä pitää pois versionhallinnasta (`.gitignore`).
- **Ylläpidettävyys:** fetcher-per-lähde-arkkitehtuuri pitää lähteet toisistaan riippumattomina ja helposti lisättävinä/poistettavina ilman ydinkoodin muutoksia.
- **Tunnetut rajoitukset:**
  - `items`-taulu ei säilytä historiaa — jokainen haku korvaa lähteen edelliset rivit kokonaan.
  - `fetcher_log`-taulua ei näytetä käyttöliittymässä; virheiden näkeminen vaatii tietokannan tai lokien tarkastelua suoraan.
  - Ei käyttäjäkohtaista näkymää tai muokattavuutta ajonaikaisesti — kaikki asetukset ovat konfiguraatiotiedostoissa.
  - `kauhavan_seurakunta`-fetcher on kovakoodattu yhdelle sivustolle eikä ole yleiskäyttöinen kuten `web_scraper`.
  - Näyttö-Pi:n kosketusherätys (näytön automaattinen sammutus + herätys kosketuksesta) **ei ole vielä toteutettu** — ks. kohta 10.2. Tämä on tiedossa oleva jatkokehitystarve, ei tämän repon koodin piirissä.
