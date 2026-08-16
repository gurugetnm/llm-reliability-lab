# Roadmap

LLM Reliability Lab is built in phases, each shipping a usable slice
rather than scaffolding for its own sake. Phases are sequential —
later phases assume earlier ones are in place — but scope within a
phase is expected to shift as earlier phases surface real requirements.

## Phase 1 — Foundation ✅ (this repository, current state)

Monorepo structure, Next.js + FastAPI + Postgres/pgvector development
environment, the `LLMProvider` abstraction (implemented against
Ollama), basic project management (create/list), health/observability
basics, and the tooling (tests, linting, CI) to build on safely.

## Phase 2 — LLM execution ✅

Actually running a prompt against a model and getting a result back
through the UI: model discovery (`GET /api/v1/models`, populated from
Ollama's `/api/tags`, never hardcoded), a Playground page with a
prompt editor and streamed output (`POST /api/v1/generate/stream`,
Server-Sent Events), non-streaming structured output validated against
a runtime JSON Schema, and execution metadata (latency, token usage).
No persistence and no cross-run comparison yet — a Playground run only
lives in the browser (localStorage); the permanent run/trace schema
and comparison UI are Phase 3. See
[`docs/llm-execution.md`](./llm-execution.md).

## Phase 3 — Experiment engine

The `Dataset → Experiment → Prompt → Model → LLM` half of the
pipeline: experiments as first-class objects with versioned prompts,
running an experiment across multiple models/configurations, and a
side-by-side diff view of outputs. This is also where `tests/`
(top-level, cross-app integration tests) gets its first real content.

## Phase 4 — Evaluation engine

Scoring experiment outputs against a dataset: exact-match/regex
scorers, embedding-similarity scorers, LLM-as-judge (via
`generate_structured()`), and regression detection comparing metrics
across runs over time. `packages/evaluation` gets implemented here.

## Phase 5 — RAG evaluation

The `RAG / Tools` stage of the pipeline: chunking strategy comparison,
embedding model comparison (pgvector-backed), retrieval strategy
comparison (similarity/hybrid/re-ranked), and retrieval-quality metrics
(recall@k, MRR) evaluated independently of end-to-end generation
quality. `packages/rag` gets implemented here.

## Phase 6 — Tracing and observability

Every step of a run — retrieval calls, LLM calls, tool calls — recorded
as a span with timing and inputs/outputs, viewable per-run in the
Traces screen and linked back to the experiment/evaluation that
produced it.

## Phase 7 — Model routing

Routing a request across multiple configured providers/models based on
cost, latency, or capability — this is also when a second `LLMProvider`
implementation (most likely `OpenAIProvider` or `AnthropicProvider`)
gets built, exercising the abstraction from Phase 1 with a real second
backend.

## Phase 8 — Agent evaluation

Evaluating multi-step agent behavior, not just single-turn generation:
trajectory scoring, task success rate, and step-level tracing built on
top of Phase 6's tracing infrastructure.

## Phase 9 — MCP / tool evaluation

Evaluating tool-use and MCP server interactions specifically: whether
the right tool was called, with the right arguments, and whether the
result was used correctly.

## Phase 10 — Automated optimization

Using the evaluation infrastructure from Phases 4–5 to automatically
search over prompts/configurations (e.g. prompt optimization, automated
RAG configuration search) rather than requiring a human to run and
compare each variant by hand.
