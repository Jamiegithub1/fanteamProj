# Local Deployment

## Start

```bash
cp .env.example .env
docker compose up -d --build
```

## URLs

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Required ENV

- `APP_USERNAME`
- `APP_PASSWORD`
- `DATABASE_URL`

## Optional Live Odds ENV

- `BALLDONTLIE_ENABLED`
- `BALLDONTLIE_API_KEY`
- `PROPLINE_ENABLED`
- `PROPLINE_API_KEY`
- `BETMGM_ENABLED`
- `BETMGM_ACCESS_ID`
- `BETMGM_ACCESS_TOKEN`
- `BETMGM_SPORT_ID`

Use strong values in `.env` on the server. `.env.example` only contains local placeholders.

## Resource Notes

- The refresh scheduler runs inside the backend container.
- Refresh jobs use an in-process lock to avoid parallel runs.
- Current source adapters use lightweight HTTP requests only.
- No browser scraper is started by Docker Compose.

## Operations

```bash
docker compose ps
docker compose logs -f backend
docker compose restart backend
```
