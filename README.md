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

Frontend:

```bash
cd frontend
npm install
npm run build
```

## Konfiguration

Login-/Passwort- und Datenbankwerte werden ueber ENV gesetzt. Scraper und Auth folgen in spaeteren Meilensteinen.
