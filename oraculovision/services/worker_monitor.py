"""Detect worker online/offline transitions across refreshes.

In-memory only: state lives for the session so a restart never replays old
transitions as fresh alerts. The first observation establishes a baseline and
emits nothing — alerts fire only on subsequent changes. Inspired by
DeepSea-Dashboard's worker status notifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class WorkerTransitions:
    came_online: list[str]
    went_offline: list[str]

    def __bool__(self) -> bool:
        return bool(self.came_online or self.went_offline)


class WorkerMonitor:
    """Tracks the set of active worker names to surface online/offline changes."""

    def __init__(self) -> None:
        self._prev_active: set[str] | None = None

    def reset(self) -> None:
        """Forget history (e.g. after the payout address changes)."""
        self._prev_active = None

    def update(self, active_names: Iterable[str]) -> WorkerTransitions:
        """Record the current active workers and return what changed.

        The first call only establishes a baseline and returns no transitions.
        """
        current = {str(n) for n in active_names}
        if self._prev_active is None:
            self._prev_active = current
            return WorkerTransitions([], [])
        came = sorted(current - self._prev_active)
        went = sorted(self._prev_active - current)
        self._prev_active = current
        return WorkerTransitions(came, went)
