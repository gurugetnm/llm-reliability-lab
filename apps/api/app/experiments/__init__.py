"""The experiment engine: prompt templating and the run engine
(`app.experiments.runner`) that drives dataset items through
`GenerationService`. Kept independent of FastAPI — nothing here imports
`fastapi`, so it's testable (and reusable from a future job queue)
without a request/response cycle.
"""
