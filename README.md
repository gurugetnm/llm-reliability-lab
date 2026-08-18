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

> **Status:** Phases 1–4 are complete — Foundation, LLM Execution
> (Playground), the Experiment Engine (datasets, reproducible
> experiments, dataset-wide runs with bounded concurrency and live
> progress, run comparison), and the Evaluation Engine: exact-match,
> contains, local-embedding semantic similarity, and LLM-as-judge
> evaluators, aggregate metrics, and baseline-vs-candidate regression
> detection. The RAG engine described below is not built yet. See
> [`docs/roadmap.md`](docs/roadmap.md), [`docs/experiments.md`](docs/experiments.md),
> and [`docs/evaluation.md`](docs/evaluation.md).

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
the project foundation, the LLM abstraction, project management,
single-prompt LLM execution (Playground), the full
`Dataset → Experiment → Run` slice, and `Evaluation → Metrics →
Comparison` are implemented — `RAG / Tools` and `Trace` don't exist yet.
See [`docs/architecture.md`](docs/architecture.md) for the full
breakdown of how the frontend, backend, database, and LLM abstraction
are put together, [`docs/llm-execution.md`](docs/llm-execution.md) for
how a Playground run flows end to end,
[`docs/experiments.md`](docs/experiments.md) for the experiment
engine's architecture, [`docs/evaluation.md`](docs/evaluation.md) for
the evaluation engine's architecture, and
[`docs/roadmap.md`](docs/roadmap.md) for what's next.

```
apps/
  web/            Next.js frontend
  api/             FastAPI backend
packages/
  llm/             Provider-agnostic LLM abstraction (implemented)
  evaluation/      Evaluation engine — evaluator registry, metrics, regression (implemented)
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
- **Datasets**: create datasets, add/edit/delete items (plain text or
  JSON), paginated item browsing, and JSON/JSONL bulk import with
  per-line validation errors — nothing imports silently or partially
- **Experiments**: reproducible configurations — dataset, model, system
  + user prompt template (`{{input}}`), generation parameters, optional
  structured-output schema — with a review screen before running
- **Runs**: executing an experiment across its whole dataset with
  bounded concurrency (configurable, capped), live SSE progress, a
  per-item run inspector (prompt, response, tokens, latency, classified
  errors), cooperative cancellation, and run history
- **Run comparison**: two runs' responses side by side per dataset item,
  with a word-level diff — a raw text diff, deliberately without a
  quality verdict; that's what Evaluations are for
- **Evaluations**: score a completed run's outputs with exact-match,
  contains (partial-credit keyword matching), local-embedding semantic
  similarity, or LLM-as-judge (via `generate_structured()`, judge model
  kept separate from the candidate model) — bounded concurrency, live
  SSE progress, per-item failure isolation without losing the rest of
  the run's results, cooperative cancellation, aggregate metrics (pass
  rate, mean/median score, score distribution), and baseline-vs-
  candidate regression detection with a per-dataset-item score delta view
- Every other section (Traces, Settings) renders a real empty state
  explaining what's coming and when, rather than a stub
- `GET /api/v1/health` and `GET /api/v1/models/health` — service,
  database, and Ollama connectivity status
- `LLMProvider` interface + a fully implemented, tested `OllamaProvider`
  (chat and completion prompts, structured output, streaming, model
  discovery) — wired into the Playground, Models, Experiment Runner, and
  the LLM-as-judge evaluator
- `EvaluatorRegistry` (pluggable evaluators, not an if/elif chain) +
  `EmbeddingProvider` interface with a fully implemented, local
  `SentenceTransformerEmbeddingProvider` — no paid embedding API

## Roadmap

Phase 1 (Foundation) → Phase 2 (LLM Execution) → Phase 3 (Experiment
Engine) → **Phase 4 (Evaluation Engine, this repo)** → Phase 5 (RAG) →
Phase 6 (Observability) → Phase 7 (Model Routing) → Phase 8 (Agent
Evaluation) → Phase 9 (MCP) → Phase 10 (Automated Optimization). Full
detail in [`docs/roadmap.md`](docs/roadmap.md).

## Contributing

1. Branch off `main`; keep commits focused (one logical change each).
2. Before opening a PR:
   ```bash
   # backend
   source .venv/bin/activate
   ruff check apps/api packages --config apps/api/pyproject.toml
   mypy apps/api/app packages/llm/src packages/evaluation/src --config-file apps/api/pyproject.toml
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
