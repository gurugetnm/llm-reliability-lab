# LLM Reliability Lab — API

FastAPI backend. See the [repository README](../../README.md) for setup
and [`docs/architecture.md`](../../docs/architecture.md) for the design.

## Local development

```bash
# from the repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/llm -e "apps/api[dev]"

cp .env.example .env   # if you haven't already
docker compose up -d db

alembic -c apps/api/alembic.ini upgrade head
uvicorn app.main:app --app-dir apps/api --reload
```

## Tests

```bash
docker compose up -d db
pytest apps/api/tests
```
