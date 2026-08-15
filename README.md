# LLM Reliability Lab

**Experiment, evaluate, and understand your AI systems.**

LLM Reliability Lab is a local-first engineering laboratory for
developers building on top of LLMs. It's for comparing local models,
prompts, RAG configurations, embedding models, and retrieval strategies
against each other — with the tracking, tracing, and evaluation
infrastructure that comparison actually requires.

It is **not** a chatbot, not a PDF Q&A app, and not a wrapper around a
single LLM API. It's meant to feel like a developer tool — Linear,
Vercel, and modern observability platforms are the reference points, not
"AI startup" gradients and glow.

> **Status:** Phase 1 (Foundation) is complete. Project structure,
> both apps, the database, and the LLM provider abstraction are in
> place; the experiment/evaluation/RAG engines described below are not
> built yet. See [`docs/roadmap.md`](docs/roadmap.md).

## Why

Comparing LLM applications rigorously — across models, prompts, RAG
configurations — is mostly done ad hoc: a notebook here, a spreadsheet
there, no shared record of what was tried or why one configuration beat
another. This project exists to make that comparison a first-class,
local, reproducible workflow instead.

## Architecture

```
Dataset → Experiment → Prompt → Model → RAG / Tools → LLM → Trace → Evaluation → Metrics → Comparison
```

That's the pipeline the whole system is building toward. Only the
foundation it stands on — the project structure, the LLM abstraction,
and basic project management — is implemented so far. See
[`docs/architecture.md`](docs/architecture.md) for the full breakdown of
how the frontend, backend, database, and LLM abstraction are put
together, and [`docs/roadmap.md`](docs/roadmap.md) for what's next.

```
apps/
  web/            Next.js frontend
  api/             FastAPI backend
packages/
  llm/             Provider-agnostic LLM abstraction (implemented)
  evaluation/      Evaluation engine — Phase 4, not yet implemented
  rag/             RAG configuration/retrieval — Phase 5, not yet implemented
  shared/          Shared types/utilities — empty until something needs it
docker/            Compose-adjacent assets (Postgres init scripts)
docs/              Architecture and roadmap docs
scripts/           Developer tooling
```

## Technology stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, Recharts (as charts are introduced) |
| Backend | Python, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL + pgvector |
| Local AI | Ollama, via a provider-agnostic `LLMProvider` interface — see below |

### The LLM provider abstraction

Application code never talks to Ollama directly — it depends on
`LLMProvider` (`generate`, `generate_structured`, `stream`,
`get_model_info`), implemented today by `OllamaProvider`
(`packages/llm`). Adding OpenAI, Anthropic, or HuggingFace later means
implementing that interface, not rewriting the app. Details in
[`docs/architecture.md`](docs/architecture.md#llm-provider-abstraction).

## Local setup

You'll need [Docker](https://www.docker.com/) and, for local (non-Docker)
development, Node.js 20+ and Python 3.11+.

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up -d
```

This starts Postgres+pgvector, the API (`http://localhost:8000`, with
migrations applied automatically on startup), and the frontend
(`http://localhost:3000`). Both `api` and `web` bind-mount their source
directories, so edits on the host hot-reload inside the containers.

**Using a local Ollama instance:** install
[Ollama](https://ollama.com), run `ollama pull llama3.1` (or your model
of choice), and start it normally on the host —
`docker-compose.yml` already points the API at
`http://host.docker.internal:11434`. Nothing currently calls Ollama by
default (Phase 2), but `GET /api/v1/health` reports the configured
provider/model so you can confirm the connection settings are correct.

### Option B — run natively

```bash
./scripts/setup.sh          # Python venv + editable installs, pnpm install, .env
docker compose up -d db      # just the database
source .venv/bin/activate
alembic -c apps/api/alembic.ini upgrade head
uvicorn app.main:app --app-dir apps/api --reload
```

In another shell:

```bash
pnpm --filter web dev
```

### Database migrations

```bash
source .venv/bin/activate
alembic -c apps/api/alembic.ini revision --autogenerate -m "describe the change"
alembic -c apps/api/alembic.ini upgrade head
```

## Current capabilities

- Application shell: sidebar navigation, dark/light mode, responsive
  layout, keyboard-friendly, across all eight planned sections
- **Projects**: create and list — the one resource implemented end to
  end (UI → API → Postgres)
- Every other section (Experiments, Datasets, Models, Evaluations,
  Traces, Settings) renders a real empty state explaining what's coming
  and when, rather than a stub
- `GET /api/v1/health` — service, database, and configured-LLM-provider
  status
- `LLMProvider` interface + a fully implemented, tested `OllamaProvider`
  (chat and completion prompts, structured output, streaming, model
  info) — not yet wired into any UI flow

## Roadmap

Phase 1 (this repo) → LLM execution → experiment engine → evaluation
engine → RAG evaluation → tracing/observability → model routing → agent
evaluation → MCP/tool evaluation → automated optimization. Full detail
in [`docs/roadmap.md`](docs/roadmap.md).

## Contributing

1. Branch off `main`; keep commits focused (one logical change each).
2. Before opening a PR:
   ```bash
   # backend
   source .venv/bin/activate
   ruff check apps/api packages --config apps/api/pyproject.toml
   mypy apps/api/app packages/llm/src --config-file apps/api/pyproject.toml
   docker compose up -d db && pytest apps/api/tests

   # frontend
   pnpm --filter web exec eslint .
   pnpm --filter web exec tsc --noEmit
   pnpm --filter web test
   pnpm --filter web build
   ```
3. Match the phase boundaries in `docs/roadmap.md` — this repo
   deliberately doesn't build ahead of the current phase.

## License

[MIT](LICENSE)
