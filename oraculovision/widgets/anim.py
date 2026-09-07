"""Frame-based animation helpers for live widgets.

Pure functions driven by an integer frame counter. No global state, no
side effects — each helper maps ``(frame, ...)`` to a small string fragment
that widgets blend into their existing Rich renders. Designed so that if a
widget stops ticking, the output simply freezes on a valid frame (never
crashes, never renders ``None``).
"""

from __future__ import annotations

# Shaded blocks used for a "flowing" leading edge on progress bars.
_FLOW_EDGE = "▓▒░"

# Pulsing energy glyphs (low → high intensity).
_ENERGY = "◇◈◆"

# Brightness ramp for a breathing dot (dim → bright).
_PULSE_DOTS = "·•●"


def flow_edge(frame: int) -> str:
    """Return the current shaded char for an animated bar leading edge."""
    return _FLOW_EDGE[frame % len(_FLOW_EDGE)]


def energy_glyph(frame: int, active: bool = True) -> str:
    """Pulsing energy glyph. When ``active`` is False, returns a steady dim glyph."""
    if not active:
        return _ENERGY[0]
    return _ENERGY[frame % len(_ENERGY)]


def pulse_dot(frame: int) -> str:
    """Breathing dot that cycles dim → bright → dim."""
    cycle = (len(_PULSE_DOTS) - 1) * 2  # 0..N-1..0
    pos = frame % cycle
    if pos >= len(_PULSE_DOTS):
        pos = cycle - pos
    return _PULSE_DOTS[pos]


def flowing_bar(pct: float, frame: int, width: int = 20, *, fill: str = "█", empty: str = "░") -> str:
    """Progress bar whose leading edge shimmers through ▓▒░ as ``frame`` advances.

    The filled/empty body is deterministic from ``pct`` (data-driven); only the
    single boundary character animates, so the bar never misrepresents progress.
    """
    pct = max(0.0, min(100.0, pct))
    filled = int(pct / 100 * width)
    if filled <= 0:
        return empty * width
    if filled >= width:
        return fill * width
    edge = flow_edge(frame)
    return fill * (filled - 1) + edge + empty * (width - filled)


# Filled / empty diamonds for a discrete capacity meter (e.g. peer count).
_DIAMOND_FILL = "◆"
_DIAMOND_EMPTY = "◇"


def diamond_meter(value: int, capacity: int = 10, width: int = 10) -> str:
    """Discrete ◆/◇ meter: ``value`` filled diamonds out of ``width`` slots.

    ``capacity`` is the value that fills the whole meter. Values above capacity
    simply cap at a full meter (never overflow or crash).
    """
    if capacity <= 0 or width <= 0:
        return ""
    ratio = max(0.0, min(1.0, value / capacity))
    filled = round(ratio * width)
    filled = max(0, min(width, filled))
    return _DIAMOND_FILL * filled + _DIAMOND_EMPTY * (width - filled)


def trend_arrow(delta: float) -> str:
    """Return ↗ / → / ↘ for positive / flat / negative change."""
    if delta > 0:
        return "↗"
    if delta < 0:
        return "↘"
    return "→"
