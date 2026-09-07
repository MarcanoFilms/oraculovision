"""Debounced milestone tracker for notify() celebrations.

Persists seen milestones in ~/.local/share/oraculovision/milestones.json
so the same event never fires twice across restarts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _state_dir() -> Path:
    p = Path.home() / ".local" / "share" / "oraculovision"
    p.mkdir(parents=True, exist_ok=True)
    return p


class MilestoneTracker:
    """Records milestone events and gates celebration notifications.

    ``should_celebrate(event_id)`` returns True at most once per event_id
    per session (and never again after the event is persisted to disk).
    """

    def __init__(self, *, state_file: Path | None = None) -> None:
        self._path = state_file or (_state_dir() / "milestones.json")
        self._seen: set[str] = self._load()
        self._session_seen: set[str] = set()

    def _load(self) -> set[str]:
        try:
            data = json.loads(self._path.read_text())
            return set(data.get("seen", []))
        except Exception:
            return set()

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps({"seen": sorted(self._seen), "updated": int(time.time())})
            )
        except Exception:
            pass

    def should_celebrate(self, event_id: str) -> bool:
        """Return True exactly once per unique event_id, then never again."""
        if event_id in self._seen or event_id in self._session_seen:
            return False
        self._session_seen.add(event_id)
        self._seen.add(event_id)
        self._save()
        return True

    def round_height_event(self, height: int) -> str | None:
        """Return a milestone event_id for round-number heights, else None.

        Every 10,000th block counts (which also covers the 100,000th).
        """
        if height > 0 and height % 10_000 == 0:
            return f"height:{height}"
        return None
