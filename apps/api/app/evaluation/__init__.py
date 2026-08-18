"""The evaluation engine: turns a completed `ExperimentRun` into scored
`EvaluationResult`s.

    EvaluationRun
        -> EvaluationRunner   (app.evaluation.runner)
        -> EvaluatorRegistry  (reliability_lab_evaluation)
        -> Evaluator
        -> EvaluationResult

Mirrors `app.experiments`'s shape on purpose — concurrency limits,
lifecycle transitions, an SSE event bus, and a runner independent of
FastAPI — so anyone already familiar with the experiment engine
recognizes this immediately. See `docs/evaluation.md`.
"""
