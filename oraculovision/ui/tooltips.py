"""First-open tooltip manager.

Tracks which panel tooltips the user has already seen and stores that
state in ~/.local/share/oraculovision/tooltips.json.  Tooltips are
shown at most once; after the first dismissal they never reappear.
"""

from __future__ import annotations

import json
from pathlib import Path


def _state_path() -> Path:
    p = Path.home() / ".local" / "share" / "oraculovision"
    p.mkdir(parents=True, exist_ok=True)
    return p / "tooltips.json"


class TooltipManager:
    """Guards tooltip display so each panel tip shows at most once."""

    def __init__(self, *, path: Path | None = None, enabled: bool = True) -> None:
        self._path = path or _state_path()
        self._enabled = enabled
        self._seen: set[str] = self._load()

    def _load(self) -> set[str]:
        try:
            data = json.loads(self._path.read_text())
            return set(data.get("seen", []))
        except Exception:
            return set()

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps({"seen": sorted(self._seen)}))
        except Exception:
            pass

    def should_show(self, panel_id: str) -> bool:
        """Return True if this tooltip has never been shown before."""
        return self._enabled and panel_id not in self._seen

    def mark_shown(self, panel_id: str) -> None:
        """Record that panel_id tooltip was shown; won't show again."""
        self._seen.add(panel_id)
        self._save()


# Per-panel tooltip texts
PANEL_TIPS: dict[str, str] = {
    "sov-brief": (
        "SOVEREIGNTY BRIEF summarises your node health at a glance. "
        "Green = all good · Yellow = degraded · Red = action needed."
    ),
    "node-status": (
        "NODE STATUS shows live RPC data. Press [u] to refresh the slow "
        "UTXO set scan (~2 min). Sparklines show peer/mempool trends."
    ),
    "bip110": (
        "BIP-110 DETECTOR scans recent blocks for consensus violations and spam. "
        "Press Enter on any row for a full block report."
    ),
    "mempool-glass": (
        "MEMPOOL GLASS analyses the *actual block template* your node built — "
        "not a sample. Spam % here is what the next miner would include."
    ),
    "datum": (
        "DATUM MINING shows your DATUM gateway status and Ocean account stats. "
        "Press [o] to set or change your Ocean payout address."
    ),
    "charts": (
        "LIVE CHARTS roll for up to 60 samples (≈30 min). "
        "They share the same data buffers as the node-status sparklines."
    ),
    "metric-score": (
        "SOVEREIGNTY SCORE is a 0-100 composite: sync, peers, Knots, "
        "template spam, and tip-block spam. Formula is in analysis/sovereignty_score.py."
    ),
}
