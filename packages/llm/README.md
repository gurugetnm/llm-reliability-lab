# reliability-lab-llm

Provider-agnostic LLM abstraction used by the API (and, later, the
evaluation and RAG engines). Application code depends on `LLMProvider`,
never on a specific vendor SDK.

```python
from reliability_lab_llm import LLMProvider, OllamaProvider, GenerationOptions

provider: LLMProvider = OllamaProvider(base_url="http://localhost:11434")

result = await provider.generate(
    "Explain vector search in one sentence.",
    model="llama3.1",
    options=GenerationOptions(temperature=0.2),
)
print(result.text)
```

## Interface

Every provider implements:

| Method | Purpose |
|---|---|
| `generate()` | Single completion for a prompt or chat message list |
| `generate_structured()` | Completion parsed and validated against a Pydantic schema |
| `stream()` | Async-iterate completion chunks as they're generated |
| `get_model_info()` | Metadata about a model (parameter size, context length, ...) |

## Adding a provider

Implement `LLMProvider` (see `ollama.py` for a full example) and register
it wherever providers are constructed (currently
`apps/api/app/llm/dependencies.py`). Planned: `OpenAIProvider`,
`AnthropicProvider`, `HuggingFaceProvider`.

## Development

```bash
pip install -e ".[dev]"
pytest
```
