"""Shared Server-Sent Events formatting — used by `/generate/stream` and
`/runs/{id}/events` so both speak the exact same wire format.
"""

import json
from typing import Any


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
