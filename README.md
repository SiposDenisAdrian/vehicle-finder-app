# vehicle-finder-app

Vehicle finder app for searching and comparing vehicles.

## Scraper de anunțuri auto

Scriptul Playwright caută anunțuri pe o pagină publică, cere Gemini să le
evalueze după filtrele configurate și trimite potrivirile către Telegram.
URL-urile procesate sunt păstrate în `seen_cars.json`.

### Configurare GitHub Actions

Implicit, scriptul caută pe Compexit Auto Rulate și Das WeltAuto. Pentru alte
pagini ale acestor site-uri, în **Settings → Secrets and variables → Actions →
Variables**, poți adăuga:

- `LISTING_URLS` (opțional): URL-urile paginilor de anunțuri, câte unul pe linie.
  Dacă nu este setată, sunt folosite paginile Compexit și Das WeltAuto configurate
  implicit.
- `MAX_LISTINGS` (opțional): limită de anunțuri per sursă. Dacă nu este setată,
  sunt parcurse toate paginile și toate anunțurile.

În **Settings → Secrets and variables → Actions → Secrets**, adaugă:

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Dacă Gemini răspunde temporar cu HTTP 503, scriptul încearcă automat o dată
modelul stabil de rezervă `gemini-3.6-flash`.

Workflow-ul din `.github/workflows/scraper.yml` rulează la fiecare 6 ore
(00:00, 06:00, 12:00 și 18:00 UTC), în fiecare zi, și poate fi pornit manual
din fila **Actions**. Orele sunt în UTC; România este de obicei UTC+2 iarna și
UTC+3 vara. În **Settings → Actions → General**,
permite workflow-urilor să scrie în repository pentru a salva actualizările din
`seen_cars.json`. Protecția branch-ului poate bloca push-ul automat.
La o eroare, scraperul se reîncearcă automat de cel mult 3 ori, cu pauze de
30 și 60 de secunde; starea anunțurilor procesate este salvată și după o
rulare eșuată, pentru a evita retrimiterea alertelor deja livrate.

### Surse și filtre

Sursele implicite sunt Compexit Auto Rulate (`https://www.autorulate.ro/parc-auto/`),
Das WeltAuto Volkswagen (`https://www.dasweltauto.ro/s/vw`) și Das WeltAuto Audi
(`https://www.dasweltauto.ro/s/audi`). Scriptul folosește selectori specifici
pentru linkurile anunțurilor și paginare, parcurge toate paginile și oprește
execuția cu eroare explicită dacă o pagină nu poate fi accesată sau nu găsește
anunțuri. Dacă este setat, `MAX_LISTINGS` se aplică separat fiecărei surse.

Filtrele sunt definite în promptul Gemini din `checker.py`: VW Golf (generația
7.5 sau 8) și Audi A3 (generația 8V sau 8Y), benzină, cutie automată, sub 90.000
km și sub 21.000 EUR. Das WeltAuto caută separat în stocul Volkswagen și Audi;
Compexit oferă stocul său de mașini rulate. Doar anunțurile al căror titlu
conține „Golf” sau „A3” sunt trimise către Gemini pentru evaluare, pentru a
evita apeluri AI inutile pentru alte modele.

Scraperul accesează pagina publică configurată și nu încearcă să ocolească
CAPTCHA, Cloudflare sau alte controale de acces.

### Rulare locală

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

export LISTING_URLS="$(printf '%s\n' \
  'https://www.autorulate.ro/parc-auto/' \
  'https://www.dasweltauto.ro/s/vw' \
  'https://www.dasweltauto.ro/s/audi')"
export GEMINI_API_KEY="..."
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python checker.py
```

`seen_cars.json` este actualizat după fiecare anunț procesat. Un anunț potrivit
este marcat ca văzut după livrarea cu succes a notificării Telegram; erorile
Gemini sau Telegram opresc execuția pentru a permite reîncercarea. La prima
rulare vor fi trimise alerte pentru anunțurile deja existente care corespund
filtrelor.
