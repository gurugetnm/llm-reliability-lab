"""SSE progress events for evaluation runs.

Reuses `app.experiments.events.RunEventBus` as-is (it's already generic
over "some id -> subscribers") rather than reimplementing an identical
in-process pub/sub bus — a second process-wide singleton, scoped to
evaluation run ids, is all that's needed.
"""

from __future__ import annotations

from app.experiments.events import RunEventBus

#: Process-wide singleton for evaluation progress — separate from
#: `app.experiments.events.run_event_bus` so an evaluation run id and an
#: experiment run id (both UUIDs) can never collide as subscription keys.
evaluation_event_bus = RunEventBus()
