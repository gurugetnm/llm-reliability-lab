"""Small validators shared across request schemas — kept in one place so
"what's a valid model name" has exactly one definition.
"""

import re

# Conservative but permissive: covers Ollama tags like "llama3.1:8b-instruct-q4_0"
# and future providers' "gpt-4o-mini"/"claude-opus-5" style names. Never
# allows a model name to shape a server-side URL/path (see Part 35).
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._:/-]{0,199})$")


def validate_model_name(value: str) -> str:
    if not MODEL_NAME_PATTERN.match(value):
        raise ValueError("Model name may only contain letters, numbers, and . _ : / -")
    return value
