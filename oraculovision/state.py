"""Lightweight persisted UI state.

The Ocean payout address is intentionally *not* baked into the read-only
config.toml. This stores small, user-mutable preferences (currently just the
last Ocean address) in a JSON file under the user's config dir so the dashboard
can remember it across restarts. All writes are best-effort: a failure to
persist never raises into the UI.
"""

from __future__ import annotations

import json
from pathlib import Path

_STATE_DIR = Path.home() / ".config" / "oraculovision"
_STATE_FILE = _STATE_DIR / "state.json"


def _read() -> dict:
    try:
        return json.loads(_STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def load_ocean_address() -> str:
    """Return the last saved Ocean payout address (empty string if none)."""
    return str(_read().get("ocean_address", "")).strip()


def save_ocean_address(address: str) -> None:
    """Persist (or clear, if empty) the Ocean payout address."""
    data = _read()
    addr = (address or "").strip()
    if addr:
        data["ocean_address"] = addr
    else:
        data.pop("ocean_address", None)
    _write(data)
