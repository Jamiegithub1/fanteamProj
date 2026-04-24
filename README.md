# NBA Fantasy Odds Projection System

Lokale Web-App fuer odds-basierte FanTeam NBA Projektionen.

## M1 Status

- FastAPI Backend mit Healthcheck
- React + TypeScript Frontend
- PostgreSQL via Docker Compose
- `.env.example` fuer lokale Konfiguration
- Dockerfiles fuer Backend und Frontend

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
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

## Konfiguration

Login-/Passwort- und Datenbankwerte werden ueber ENV gesetzt. Fuer M1 ist nur die lokale PostgreSQL-Verbindung vorbereitet; Scraper und Auth folgen in spaeteren Meilensteinen.
