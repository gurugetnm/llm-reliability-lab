# Built with repo root as context (see docker-compose.yml) so it can
# install the local `packages/*` dependencies alongside the API itself.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libpq is needed by psycopg (used by Alembic migrations).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY packages/llm packages/llm
COPY packages/shared packages/shared
COPY apps/api apps/api

RUN pip install --upgrade pip \
    && pip install -e packages/llm -e packages/shared -e apps/api

WORKDIR /app/apps/api
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
