# Writing a new evaluator

This is the practical, "I want to add a fifth evaluator" companion to
[`docs/evaluation.md`](./evaluation.md)'s architecture overview. Adding
an evaluator never requires touching `EvaluationRunner`, the API routes,
or the registry itself — that's the point of `EvaluatorRegistry`.

## 1. Write the config model

A plain Pydantic model. This is both the runtime validation and the
source of the JSON Schema `GET /api/v1/evaluators` exposes — never hand
those two things separately.

```python
from pydantic import BaseModel, Field

class WordCountConfig(BaseModel):
    min_words: int = Field(ge=0, description="Minimum acceptable word count.")
    max_words: int | None = Field(default=None, description="Optional upper bound.")
```

## 2. Write the evaluator

```python
from reliability_lab_evaluation.base import Evaluator
from reliability_lab_evaluation.registry import EvaluatorRegistry
from reliability_lab_evaluation.types import EvaluationInput, EvaluationOutput, EvaluatorMetadata

@EvaluatorRegistry.register
class WordCountEvaluator(Evaluator):
    metadata = EvaluatorMetadata(
        name="word_count",
        version="v1",
        description="Scores 1.0 if the response's word count falls within a configured range.",
        score_range=(0.0, 1.0),
        higher_is_better=True,
    )
    config_model = WordCountConfig

    async def evaluate(self, item: EvaluationInput) -> EvaluationOutput:
        config: WordCountConfig = self.config  # type: ignore[assignment]
        count = len(item.actual_text().split())
        in_range = count >= config.min_words and (config.max_words is None or count <= config.max_words)
        return EvaluationOutput(
            score=1.0 if in_range else 0.0,
            passed=in_range,
            reason=f"{count} words.",
            details={"word_count": count, "min_words": config.min_words, "max_words": config.max_words},
        )
```

Rules that keep an evaluator honest:

- **Never touch a database.** Everything needed is on `EvaluationInput`.
  If you need something that isn't there, add a field to
  `EvaluationInput` (and populate it in `app/evaluation/runner.py`'s
  `_build_input`) rather than reaching around the abstraction.
- **Never fabricate a score or a `passed` value.** If the metric
  genuinely can't be computed for an item (no `expected_output`, say),
  return `EvaluationOutput(score=None, passed=None, reason="...")`.
- **Raise, don't swallow, on a real failure.** If something goes wrong
  in a way that means this item wasn't actually scored — a provider
  call failed, a response didn't parse — raise
  `reliability_lab_evaluation.exceptions.EvaluatorExecutionError` (with
  `details` carrying whatever's useful for debugging). The runner turns
  that into a failed `EvaluationResult` without aborting the rest of the
  evaluation.
- **Only declare a provider dependency you actually need.** Set
  `requires_embedding_provider=True` / `requires_llm_provider=True` on
  `metadata` only if `evaluate()` needs one — `EvaluatorRegistry.create()`
  uses those flags to reject configuration up front if the provider
  wasn't supplied.

## 3. Register it

Add the import to `packages/evaluation/src/reliability_lab_evaluation/evaluators/__init__.py`:

```python
from reliability_lab_evaluation.evaluators.word_count import WordCountEvaluator
```

That module is imported by `reliability_lab_evaluation/__init__.py` for
its side effect (populating the registry), so this one line is the only
change needed outside the new evaluator's own file. `EvaluatorRegistry.names()`,
`GET /api/v1/evaluators`, and the evaluation creation flow all pick it
up automatically.

## 4. Test it

Follow `test_evaluators_basic.py`'s pattern: construct the evaluator via
`EvaluatorRegistry.create("word_count", {...})`, build `EvaluationInput`
values by hand, and assert on the returned `EvaluationOutput`. No
database, no HTTP, no live model. If the evaluator needs a provider, use
`tests/fakes.py`'s `FakeEmbeddingProvider`/`FakeLLMProvider` — never a
real model download or a live Ollama instance in a unit test.

## 5. (Optional) add frontend configuration fields

`apps/web/src/components/evaluations/evaluator-config-fields.tsx` is a
hand-written `switch` over `evaluatorType`, not a generic JSON-Schema
form renderer (see `docs/evaluation.md`'s reasoning). Add a case there
if the new evaluator needs configuration beyond a threshold the existing
generic controls already cover.
