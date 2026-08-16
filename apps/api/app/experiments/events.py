"""An in-process pub/sub bus for run progress events.

Deliberately in-process (a module-level singleton, `asyncio.Queue` per
subscriber) rather than backed by Redis/Kafka/etc — Part 21 asks for a
lightweight mechanism for this phase, not a real job queue. Swapping
this for a Redis pub/sub-backed implementation later wouldn't change
`ExperimentRunner`'s or the SSE route's calling code, since both only
ever call `publish`/`subscribe`/`unsubscribe`.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunEvent:
    event: str
    data: dict[str, Any]


class RunEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue[RunEvent]]] = defaultdict(set)

    def subscribe(self, run_id: uuid.UUID) -> asyncio.Queue[RunEvent]:
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: uuid.UUID, queue: asyncio.Queue[RunEvent]) -> None:
        subscribers = self._subscribers.get(run_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(run_id, None)

    async def publish(self, run_id: uuid.UUID, event: str, data: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(run_id, ())):
            await queue.put(RunEvent(event=event, data=data))


#: Process-wide singleton — every request handler and the runner's
#: background task share it, which is exactly what makes "a route
#: subscribes to events the runner publishes" work without a broker.
run_event_bus = RunEventBus()
