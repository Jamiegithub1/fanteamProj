# NBA Fantasy Odds Projection System

Lokale Web-App fuer odds-basierte FanTeam NBA Projektionen.

## M1 Status

- FastAPI Backend mit Healthcheck
- React + TypeScript Frontend
- PostgreSQL via Docker Compose
- `.env.example` fuer lokale Konfiguration
- Dockerfiles fuer Backend und Frontend

## M2 Status

- SQLAlchemy Datenmodell fuer alle Phase-1-Entities
- Alembic Migration fuer PostgreSQL
- Source-Health- und Refresh-Run-Tabellen fuer robuste Scraper

## M3 Status

- Odds-Math-Engine fuer American/Decimal Odds
- Vig-freie Over/Under-Wahrscheinlichkeiten
- Expected-Value-Approximation
- Mean/Median Aggregation
- Outlier Detection
- Confidence Score

## M4 Status

- Modulare Quellen-Adapter fuer Odds-Integrationen
- Playzilla Pflichtquelle mit leichter SPA/WSDK-Discovery
- NBA Player-Prop Parser fuer alle Phase-1-Maerkte
- Speicherung von Raw Odds, Refresh Runs und Source Health
- Quellen-Endpunkte unter `/sources/health` und `/sources/playzilla/refresh`

## M5 Status

- DraftKings als zusaetzlicher modularer Quellen-Adapter
- DraftKings standardmaessig deaktiviert, weil der leichte Live-Endpunkt auf diesem Server HTTP 403 liefert
- Weitere Buchmacher bewertet und schwere/instabile Scraper bewusst uebersprungen
- DraftKings-Refresh unter `/sources/draftkings/refresh`

## M6 Status

- Aggregation von `raw_odds` zu `aggregated_odds`
- Vig-Entfernung pro Bookmaker bei Over/Under- und Yes/No-Paaren
- Konsens-Wahrscheinlichkeiten, Expected Values und Confidence Score
- Aggregations-Refresh unter `/aggregations/refresh`

## M7 Status

- FanTeam Projection Engine auf Basis von `aggregated_odds`
- Double-/Triple-Double als wahrscheinlichkeitsgewichteter Bonus
- Projektionen werden in `projections` gespeichert
- Projection-Refresh unter `/projections/refresh`

## M8 Status

- Leichter Background Scheduler ohne schwere Zusatzdienste
- 30-Minuten-Refresh, 5-Minuten-Prelock-Intervall
- Globaler Lock gegen parallele Refreshes
- Manueller Gesamtrefresh unter `/refresh/run`

## Lokal starten

```bash
cp .env.example .env
docker compose up --build
```

Danach erreichbar:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Checks

Backend:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest
```

Migration:

```bash
cd backend
../.venv/bin/alembic upgrade head
```

Die Odds-Math-Engine liegt in `backend/app/odds_math.py` und ist als reine Python-Logik getestet.

Frontend:

```bash
cd frontend
npm install
npm run build
```

## Konfiguration

Login-/Passwort-, Datenbank- und Playzilla-Werte werden ueber ENV gesetzt.
