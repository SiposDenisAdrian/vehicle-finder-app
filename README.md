# vehicle-finder-app

Vehicle finder app for searching and comparing vehicles.

## Scraper de anunțuri auto

Scriptul Playwright caută anunțuri pe paginile configurate, cere Gemini să
evalueze potrivirile și trimite pe Telegram un top de până la trei recomandări.
Evaluările anunțurilor sunt păstrate în `car_evaluations.json` și refăcute când
se schimbă detaliile anunțului.

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

Scriptul folosește `gemini-3.1-flash-lite`, un model optimizat de Google pentru
taskuri simple și de volum mare. Dacă răspunde temporar cu HTTP 503, încearcă
automat modelul de rezervă `gemini-3.5-flash-lite`.

Workflow-ul din `.github/workflows/scraper.yml` rulează la fiecare 6 ore
(00:00, 06:00, 12:00 și 18:00 UTC), în fiecare zi, și poate fi pornit manual
din fila **Actions**. Orele sunt în UTC; România este de obicei UTC+2 iarna și
UTC+3 vara. În **Settings → Actions → General**, permite workflow-urilor să
scrie în repository pentru a salva evaluările actualizate. Protecția branch-ului
poate bloca push-ul automat.
La o eroare, scraperul se reîncearcă automat de cel mult 3 ori, cu pauze de
30 și 60 de secunde; evaluările deja făcute sunt salvate și după o rulare
eșuată, ca să poată fi reutilizate.

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
Compexit oferă stocul său de mașini rulate. Doar titlurile care conțin „Golf”
sau „A3” sunt evaluate de Gemini.

La fiecare rulare, anunțurile care respectă filtrele sunt ordonate după un scor
combinat: fiabilitatea generală estimată a combinației model/motor/cutie (50%),
prețul (25%) și kilometrajul (25%). Telegram primește un singur mesaj cu până
la primele trei. Dacă există mai puțin de trei potriviri, mesajul include doar
pe cele disponibile; dacă nu există potriviri, nu se trimite mesaj. Topul poate
repeta mașini la verificările următoare dacă ele rămân cele mai bune opțiuni.
Scorul de fiabilitate este orientativ și nu verifică VIN-ul, istoricul de
service sau starea concretă a vehiculului.

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

`car_evaluations.json` salvează evaluările Gemini; anunțurile neschimbate nu
generează apeluri AI la fiecare verificare. Evaluările sunt actualizate când se
schimbă textul sau titlul anunțului.

Testele se pot rula cu `python -m unittest discover -s tests -v`.
