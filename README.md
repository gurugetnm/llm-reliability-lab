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

> **Status:** Phase 1 (Foundation) and Phase 2 (LLM Execution) are
> complete — you can run a prompt against a local Ollama model through
> the Playground UI, streamed, with structured output and execution
> metadata. The experiment/evaluation/RAG engines described below are
> not built yet. See [`docs/roadmap.md`](docs/roadmap.md).

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

That's the pipeline the whole system is building toward. So far:
the project foundation, the LLM abstraction, basic project management,
and single-prompt LLM execution (Playground) are implemented — there's
no persisted `Experiment`/`Trace`/`Evaluation` yet. See
[`docs/architecture.md`](docs/architecture.md) for the full breakdown of
how the frontend, backend, database, and LLM abstraction are put
together, [`docs/llm-execution.md`](docs/llm-execution.md) for how a
Playground run actually flows end to end, and
[`docs/roadmap.md`](docs/roadmap.md) for what's next.

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
`get_model_info`, `get_models`), implemented today by `OllamaProvider`
(`packages/llm`). Adding OpenAI, Anthropic, or HuggingFace later means
implementing that interface, not rewriting the app. Details in
[`docs/architecture.md`](docs/architecture.md#llm-provider-abstraction)
and [`docs/llm-execution.md`](docs/llm-execution.md).

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
of choice), and start it normally on the host — `docker-compose.yml`
already points the containerized API at
`http://host.docker.internal:11434` (via `OLLAMA_BASE_URL_DOCKER`; see
[`docs/llm-execution.md`](docs/llm-execution.md) for why that's a
separate variable from `OLLAMA_BASE_URL`). Open
[`http://localhost:3000/playground`](http://localhost:3000/playground)
to run a prompt against it, or check `GET /api/v1/models/health` to
confirm connectivity without the UI.

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
  layout, keyboard-friendly, across all nine planned sections
- **Projects**: create and list — a full resource end to end (UI → API
  → Postgres)
- **Models**: real Ollama model discovery (`GET /api/v1/models`), with
  distinct loading / no-models-installed / Ollama-unreachable states
  and a refresh action — never hardcoded
- **Playground**: run a prompt against an installed model — system +
  user prompt, temperature/max tokens, streamed text output (SSE) or
  non-streaming structured JSON output validated against a schema you
  define, execution metadata (latency, token usage, finish reason),
  and a lightweight localStorage run history
- Every other section (Experiments, Datasets, Evaluations, Traces,
  Settings) renders a real empty state explaining what's coming and
  when, rather than a stub
- `GET /api/v1/health` and `GET /api/v1/models/health` — service,
  database, and Ollama connectivity status
- `LLMProvider` interface + a fully implemented, tested `OllamaProvider`
  (chat and completion prompts, structured output, streaming, model
  discovery) — now wired into the Playground and Models pages

## Roadmap

Phase 1 (Foundation) → **Phase 2 (LLM Execution, this repo)** → Phase 3
(Experiment Engine) → Phase 4 (Evaluation) → Phase 5 (RAG) → Phase 6
(Observability) → Phase 7 (Model Routing) → Phase 8 (Agent Evaluation)
→ Phase 9 (MCP) → Phase 10 (Automated Optimization). Full detail in
[`docs/roadmap.md`](docs/roadmap.md).

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
