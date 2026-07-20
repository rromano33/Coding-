# Trading Diary — backend

API FastAPI para o diário de trades: autenticação, CRUD de trades, notas de
mercado, entradas de diário psicológico e estatísticas de performance.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Rodar

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Banco SQLite é criado automaticamente em `data/trading_diary.db` na primeira
execução. Para trocar para Postgres, defina `DATABASE_URL` no `.env`
(ex: `postgresql://user:pass@host/db`).

Defina `SECRET_KEY` no `.env` em produção (o default é só para dev local).

## Endpoints principais

- `POST /auth/register`, `POST /auth/login` (form `username`/`password`), `GET /auth/me`
- `GET/POST /trades`, `GET/PUT/DELETE /trades/{id}`
- `GET/POST /market-notes`, `PUT/DELETE /market-notes/{id}`
- `GET/POST /journal`, `PUT/DELETE /journal/{id}`
- `GET /stats/summary`, `GET /stats/equity-curve`, `GET /stats/by-strategy`, `GET /stats/by-asset`, `GET /stats/by-market`

Docs interativas em `/docs` (Swagger).
