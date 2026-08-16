# Architecture

This document describes how LLM Reliability Lab is put together today,
and how the pieces that don't exist yet are expected to slot in. For
what's planned and in what order, see [`roadmap.md`](./roadmap.md).

## Repository layout

```
apps/
  web/            Next.js frontend
  api/             FastAPI backend
packages/
  llm/             LLMProvider abstraction (implemented)
  evaluation/      Evaluation engine (Phase 4, not yet implemented)
  rag/             RAG configuration/retrieval (Phase 5, not yet implemented)
  shared/          Types/utilities shared across packages (empty until needed)
docker/            Compose-adjacent assets (Postgres init scripts)
docs/              This directory
scripts/           Developer tooling (local environment bootstrap)
tests/             Reserved for cross-app integration tests (Phase 3+)
```

A monorepo, not a set of independently-versioned services: `apps/api`
depends on `packages/llm` via a local editable install, and the frontend
and backend are developed and deployed together via
[`docker-compose.yml`](../docker-compose.yml). `packages/*` exist so that
logic with a clear boundary (the LLM abstraction; later, evaluation and
RAG) isn't tangled into `apps/api`'s HTTP layer — each is independently
testable and importable from a script or notebook without booting FastAPI.

## Frontend architecture

**Stack:** Next.js (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui
(Base UI primitives under the hood, not Radix — see `components.json`).

- **App shell** (`src/components/layout/`): a fixed sidebar
  (`sidebar.tsx`) on desktop, collapsing into a `Sheet` on mobile
  (`site-header.tsx`), around a `<main>` content region. Both read the
  same nav config (`src/lib/nav.ts`) so desktop/mobile never drift.
- **Routing:** one route per sidebar item (`src/app/<section>/page.tsx`).
  Sections without real functionality yet render `<EmptyState>` with
  copy that says what's coming and when, rather than a bare "TODO".
- **Data:** a small typed client (`src/lib/api.ts`) wraps `fetch` against
  `NEXT_PUBLIC_API_URL`; `src/lib/llm/` holds the LLM-execution-specific
  client, including a hand-rolled SSE reader (`stream.ts`, over `fetch`
  rather than `EventSource` since streaming requires a POST body) and
  the `useGeneration()` hook that drives the Playground's state machine.
  `src/lib/runs/events.ts` is the same SSE-over-`fetch` pattern applied
  to run progress (`GET /runs/{id}/events`). No React Query / SWR yet —
  the data-fetching surface is still small enough that plain
  `useEffect`/`useState` stays readable; revisit if it stops being true.
- **Theming:** `next-themes` drives a `class`-based dark mode; every
  color is a CSS variable in `globals.css`, themed per-mode. Components
  reference tokens (`bg-card`, `text-muted-foreground`, ...), never raw
  colors, so theming stays centralized.
- **Testing:** Vitest + React Testing Library, colocated `*.test.tsx`
  files. Covers logic worth covering (active-nav-link matching, the API
  client's error handling, a relative-time formatter) — not every
  presentational component.

## Backend architecture

**Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + Alembic.

```
apps/api/app/
  main.py          FastAPI app, middleware, exception handlers, router mount
  config.py        Settings (pydantic-settings, env-var driven)
  core/            Cross-cutting: structured logging, exception types/handlers, SSE formatting
  api/
    routes/        One module per resource (health, projects, datasets, experiments, runs, models, generate)
    router.py       Aggregates routes under /api/v1
    deps.py         Shared FastAPI dependencies (DbSession, ...)
  db/               Engine/session setup, declarative Base + mixins
  models/           SQLAlchemy ORM models
  schemas/          Pydantic request/response models
  repositories/      Thin, rule-free data-access functions (one module per aggregate root)
  services/         Business logic, framework-agnostic (no FastAPI imports)
  experiments/      The experiment engine: prompt templates, the runner, concurrency, lifecycle, error classification, the SSE event bus — see docs/experiments.md
  llm/              FastAPI-specific wiring for the LLM provider abstraction
```

**Layering:** routes translate HTTP ⟷ Pydantic schemas and delegate to
`services/`; services take a session and ORM models, validate business
rules (ownership, lifecycle, prompt templates), and delegate raw
queries to `repositories/`. This means `services/project_service.py` (or
`experiment_service.py`, `run_service.py`, ...) is reusable from a
script, a background job, or a test without importing FastAPI or
constructing a request — and `app/experiments/runner.py` specifically
takes a plain `LLMProvider` and session factory, not a FastAPI
dependency, so it runs the same way from a background `asyncio.Task`
today as it would from a real job queue later.

**Error handling:** routes/services raise typed exceptions
(`app.core.exceptions.NotFoundError`, etc.) rather than building
`HTTPException`s inline; handlers registered in `main.py` translate
those into a consistent `{"detail": ...}` JSON shape. A catch-all handler
logs and returns a generic 500 for anything unexpected, so internals
never leak into a response.

**Logging:** one JSON object per line (`app.core.logging`), including
uvicorn's own access/error logs — greppable locally today, shippable to
a log aggregator later with no code change.

**API versioning:** everything lives under `/api/v1`
(`app/api/router.py`). A `/api/v2` would mount alongside it, not replace
it — existing clients keep working.

## Database architecture

PostgreSQL + [pgvector](https://github.com/pgvector/pgvector), run via
Docker Compose (`pgvector/pgvector:pg17`). pgvector is enabled today
even though nothing uses it yet, because retrieval/RAG evaluation
(Phase 5) is the reason Postgres was chosen over SQLite in the first
place — better to prove the extension works now than to migrate later.

- **Models** (`app/models/`) use SQLAlchemy 2.0's typed `Mapped`/
  `mapped_column` style, a client-generated UUID primary key
  (`UUIDPrimaryKeyMixin`), and database-maintained `created_at`/
  `updated_at` (`TimestampMixin`).
- **Migrations** (`apps/api/alembic/`) run against a synchronous
  `psycopg` connection, even though the app itself talks to Postgres
  asynchronously via `asyncpg` at runtime — `alembic/env.py` swaps the
  driver in the connection string. This is the standard
  SQLAlchemy-recommended split and keeps `env.py` simple (no async
  migration boilerplate).
- **Tests** run against a dedicated `<database>_test` database (created
  by `docker/postgres/init.sql`), never the database local dev / Docker
  Compose's `api` service use — see `apps/api/tests/conftest.py`.
- **Request-scoped sessions commit on success, roll back on exception**
  (`app/db/session.py`'s `get_db`) — the standard pattern, so a service
  that only calls `db.flush()` for a mid-request id still ends up
  durably persisted once the request completes.

Tables: `projects`, `datasets`, `dataset_items`, `experiments`,
`experiment_runs`, `run_items` — see
[`docs/experiments.md`](./experiments.md#data-model) for the full
entity-relationship diagram and the reasoning behind each table's
cascade/constraint choices. Future tables (evaluation results, traces)
are added incrementally, each with its own migration, as the
corresponding feature is built — not speculatively.

## LLM provider abstraction

The single most important architectural decision in this codebase:
**nothing outside `packages/llm` and `app/llm/dependencies.py` knows
Ollama exists.**

```
packages/llm/src/reliability_lab_llm/
  base.py          LLMProvider (ABC): generate, generate_structured, stream, get_model_info, get_models
  types.py         Provider-agnostic types: Message, GenerationOptions, GenerationResult, ModelSummary, ...
  ollama.py         OllamaProvider(LLMProvider) — the only Ollama-aware code
  exceptions.py     ProviderError, ProviderConnectionError, ModelNotFoundError, StructuredOutputError
```

`apps/api/app/llm/dependencies.py` is the only place that constructs a
concrete provider, via a `get_llm_provider()` FastAPI dependency cached
with `functools.lru_cache`. Adding `OpenAIProvider` or
`AnthropicProvider` means implementing `LLMProvider` in
`packages/llm` and changing that one factory function — no route,
service, or future evaluation/RAG code should ever import
`OllamaProvider` directly.

`generate_structured()` accepts either a Pydantic model type (typed
callers get a validated instance back) or a raw JSON Schema `dict`
(callers building a schema at runtime — the Playground — get a
validated plain `dict` back), using Ollama's structured-output support
(`format: <json schema>`). This is what the future evaluation and
experiment engines will use to get typed judgments and structured tool
calls out of a model, rather than parsing free text. See
[`docs/llm-execution.md`](./llm-execution.md) for the full request flow,
including streaming.

## Experiment engine architecture (Phase 3)

```
Dataset → Experiment → ExperimentRun → ExperimentRunner → GenerationService → LLMProvider → Ollama → RunItem
```

An `Experiment` is a reproducible configuration (dataset + model +
prompts + generation parameters); running it produces an
`ExperimentRun` and one `RunItem` per dataset item. The runner is
independent of FastAPI, runs dataset items under bounded concurrency
(`asyncio.Semaphore`, default 3, hard-capped at 10), classifies and
persists per-item failures without aborting the run, and supports
cooperative cancellation. Progress streams over SSE from an in-process
pub/sub bus. Full detail, diagrams, and the reasoning behind every
cascade/constraint choice: [`docs/experiments.md`](./experiments.md).

## Future: evaluation architecture (Phase 4)

Not implemented yet (`packages/evaluation` is a scaffold). Expected
shape: a `Scorer` interface (exact-match/regex, embedding similarity,
LLM-as-judge via `LLMProvider.generate_structured()`) run against a
`RunItem`'s response and its dataset item's expected answer, producing
an `EvaluationResult` (metric, score, reason, evaluator) — a separate
table referencing `run_item_id`, never a column on `RunItem` itself, so
evaluation stays additive and re-runnable without re-executing the
experiment. Regression detection compares metrics across runs over time.

## Future: RAG architecture (Phase 5)

Not implemented yet (`packages/rag` is a scaffold). Expected shape:
pluggable chunking strategies and embedding models (stored via
pgvector), pluggable retrieval strategies (similarity, hybrid,
re-ranked), and retrieval-quality metrics (recall@k, MRR) evaluated
independently of end-to-end generation quality.

## Future: tracing architecture (Phase 6)

Not implemented yet. Expected shape: every step of a run (retrieval
calls, LLM calls, tool calls) recorded as a span with timing, inputs,
and outputs, linked to the experiment/evaluation that produced it.
`ExecutionResult` (`apps/api/app/schemas/generation.py`) — the record a
Playground generation returns today — already carries an id, model,
timing, usage, and parameters for exactly this reason; it's not
persisted yet (Phase 2 deliberately doesn't touch the database), but
its shape is meant to survive into the eventual trace/run record
largely unchanged.
