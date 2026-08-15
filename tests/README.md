# tests/

Reserved for cross-cutting integration tests that span multiple apps
(e.g. a full pipeline run through the frontend, API, and database
together). Nothing lives here yet — there's no cross-app pipeline to
test until the experiment engine (Phase 3) exists.

Until then, tests live next to the code they cover:

| Location | Covers |
|---|---|
| [`apps/api/tests`](../apps/api/tests) | API routes, services, database, LLM provider |
| [`apps/web`](../apps/web) | Frontend (component/unit tests, colocated under `src/`) |
| [`packages/llm`](../packages/llm) | Exercised via `apps/api/tests/test_llm_provider.py` today |
