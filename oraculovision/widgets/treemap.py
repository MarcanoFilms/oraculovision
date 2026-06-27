"""Block-template treemap — a mempool.space-style visualization.

Renders the current GBT (getblocktemplate) as a squarified treemap: one cell
per transaction, sized by weight, coloured by fee rate.  Wrapped in a
box-drawing border with a title and tx count.

Detail comes from *sextant* block glyphs (🬀🬂🬞█ …, U+1FB00 range): each terminal
character packs a 2×3 sub-pixel grid with two colours — btop-style density.
That is six sub-pixels per cell (vs four for half-block quadrants), for a
finer, higher-definition mempool-like texture.
"""

from __future__ import annotations

import time

from rich.text import Text

from oraculovision.data.bitcoin import BitcoinCLI, BitcoinCLIError

_CACHE_TTL = 30.0
_MAX_CELLS = 900
_cache: tuple[float, list[tuple[int, int]]] | None = None

_BORDER_FG = "#26262b"
_TITLE_FG = "bold #ff6600"
_COUNT_FG = "bold #888888"

_STOPS = [
    (1, (36, 128, 246)),      # 1 sat/vB: Cool Blue (#2480f6)
    (3, (46, 204, 113)),      # 3 sat/vB: Emerald Green (#2ecc71)
    (10, (241, 196, 15)),     # 10 sat/vB: Gold (#f1c40f)
    (25, (230, 126, 34)),     # 25 sat/vB: Orange (#e67e22)
    (60, (231, 76, 60)),      # 60 sat/vB: Red (#e74c3c)
    (120, (155, 89, 182)),    # 120 sat/vB: Purple (#9b59b6)
    (250, (142, 68, 173)),    # 250+ sat/vB: Dark Purple/Violet (#8e44ad)
]

_BG = (12, 12, 14)
_GUTTER_COLOR = (12, 12, 14)


# 2x3 sextant glyphs (Unicode "Symbols for Legacy Computing", U+1FB00..3B)
# keyed by a 6-bit mask. Bit order is row-major: TL=1, TR=2, ML=4, MR=8,
# BL=16, BR=32; a set bit means that sub-pixel takes the foreground colour.
# Four combinations coincide with pre-existing block elements (blank, left
# half ▌, right half ▐, full █) and are not in the U+1FB00 range.
_SEXTANT_BITS = (1, 2, 4, 8, 16, 32)  # TL, TR, ML, MR, BL, BR
_CELL_W, _CELL_H = 2, 3


def _build_sextants() -> dict[int, str]:
    table: dict[int, str] = {0: " ", 21: "▌", 42: "▐", 63: "█"}
    codepoint = 0x1FB00
    for mask in range(1, 63):
        if mask in (21, 42):  # left/right columns are pre-existing chars
            continue
        table[mask] = chr(codepoint)
        codepoint += 1
    return table


_SEXTANT_GLYPHS = _build_sextants()


def _fetch_template_data(*, cli: BitcoinCLI | None = None) -> list[tuple[int, int]]:
    """Return [(weight, fee), ...] for the current block template (cached)."""
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _CACHE_TTL:
        return _cache[1]
    try:
        tmpl = (cli or BitcoinCLI()).get_block_template()
    except (BitcoinCLIError, OSError):
        return _cache[1] if _cache else []
    data = [
        (int(t.get("weight", 0)), int(t.get("fee", 0)))
        for t in tmpl.get("transactions", [])
        if int(t.get("weight", 0)) > 0
    ]
    _cache = (now, data)
    return data


def _color(fee_rate: float) -> tuple[int, int, int]:
    if fee_rate <= _STOPS[0][0]:
        return _STOPS[0][1]
    for i in range(len(_STOPS) - 1):
        f0, c0 = _STOPS[i]
        f1, c1 = _STOPS[i + 1]
        if fee_rate <= f1:
            t = (fee_rate - f0) / (f1 - f0) if f1 > f0 else 0
            t = max(0.0, min(1.0, t))
            return tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
    return _STOPS[-1][1]


def _squarify(values, x, y, w, h):
    rects = []

    def worst(row, length):
        s = sum(v for v, _ in row)
        if s == 0:
            return float("inf")
        mx = max(v for v, _ in row)
        mn = min(v for v, _ in row)
        return max((length * length * mx) / (s * s), (s * s) / (length * length * mn))

    def layoutrow(row, x, y, w, h, horizontal):
        s = sum(v for v, _ in row)
        if horizontal:
            rw = s / h if h else 0
            cy = y
            for v, i in row:
                rh = (v / s) * h if s else 0
                rects.append((x, cy, rw, rh, i))
                cy += rh
            return x + rw, y, w - rw, h
        rh = s / w if w else 0
        cx = x
        for v, i in row:
            rw = (v / s) * w if s else 0
            rects.append((cx, y, rw, rh, i))
            cx += rw
        return x, y + rh, w, h - rh

    total = sum(v for v, _ in values)
    if total <= 0:
        return rects
    area = w * h
    vals = [(v / total * area, i) for v, i in values]
    row: list = []
    while vals:
        if not row:
            row.append(vals.pop(0))
            continue
        length = min(w, h)
        if worst(row + [vals[0]], length) <= worst(row, length):
            row.append(vals.pop(0))
        else:
            x, y, w, h = layoutrow(row, x, y, w, h, h < w)
            row = []
    if row:
        layoutrow(row, x, y, w, h, h < w)
    return rects


def _center_in_border(label: str, total: int) -> str:
    """Center *label* inside *total* chars, padded with ─."""
    vis_len = len(label)
    pad = total - vis_len
    left = max(0, pad // 2)
    right = max(0, pad - left)
    return "─" * left + label + "─" * right


def _dist(a, b) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _sextant_cell(pix) -> tuple[str, tuple[int, int, int], tuple[int, int, int]]:
    """Reduce six sub-pixels to a (glyph, fg, bg) two-colour sextant cell."""
    uniq = list(dict.fromkeys(pix))
    if len(uniq) == 1:
        fg = bg = uniq[0]
    elif len(uniq) == 2:
        fg, bg = uniq[0], uniq[1]
    else:
        # Two-means on the colours: anchor = first, other = the farthest.
        fg = pix[0]
        bg = max(pix, key=lambda c: _dist(c, fg))
    mask = 0
    for i, p in enumerate(pix):
        if _dist(p, fg) <= _dist(p, bg):
            mask |= _SEXTANT_BITS[i]
    return _SEXTANT_GLYPHS[mask], fg, bg


def render_block_treemap(width: int = 36, height: int = 15) -> Text | None:
    """Render the block template as a bordered Rich Text treemap.

    *width* and *height* are the **outer** dimensions (including the
    box-drawing border and the title/footer lines).
    """
    data = _fetch_template_data()
    if not data:
        return None

    total_txs = len(data)
    biggest = sorted(data, reverse=True)[:_MAX_CELLS]
    values = [(wt, idx) for idx, (wt, fee) in enumerate(biggest)]

    iw = width - 2
    inner_lines = height - 2
    # Sub-pixel canvas: 2 wide × 3 tall per character (sextants), so each text
    # row resolves 3 vertical sub-pixels — btop-grade definition.
    sw = iw * _CELL_W
    sh = inner_lines * _CELL_H
    rects = _squarify(values, 0, 0, sw, sh)

    grid = [[_BG for _ in range(sw)] for _ in range(sh)]
    for rx, ry, rw, rh, idx in rects:
        wt, fee = biggest[idx]
        vsize = wt / 4
        col = _color(fee / vsize if vsize else 0)
        gutter = _GUTTER_COLOR
        x0, y0 = int(rx), int(ry)
        x1, y1 = int(round(rx + rw)), int(round(ry + rh))
        # Solid tile; a subtle darker seam on the right/bottom edges when the
        # cell is large enough to spare a pixel — keeps tiny cells solid and
        # big ones cleanly tiled, mempool-style.
        gut_x = x1 - 1 if (x1 - x0) >= 3 else -1
        gut_y = y1 - 1 if (y1 - y0) >= 3 else -1
        for py in range(max(0, y0), min(sh, y1)):
            row_gut = py == gut_y
            for px in range(max(0, x0), min(sw, x1)):
                grid[py][px] = gutter if (row_gut or px == gut_x) else col

    text = Text(no_wrap=True)

    title = " 🧱 BLOCK TEMPLATE "
    top_inner = _center_in_border(title, iw)
    text.append("╭", style=_BORDER_FG)
    for ch in top_inner:
        text.append(ch, style=_BORDER_FG if ch == "─" else _TITLE_FG)
    text.append("╮\n", style=_BORDER_FG)

    for cy in range(inner_lines):
        text.append("│", style=_BORDER_FG)
        ry = cy * _CELL_H
        for cx in range(iw):
            rx = cx * _CELL_W
            pix = (
                grid[ry][rx],          # TL
                grid[ry][rx + 1],      # TR
                grid[ry + 1][rx],      # ML
                grid[ry + 1][rx + 1],  # MR
                grid[ry + 2][rx],      # BL
                grid[ry + 2][rx + 1],  # BR
            )
            glyph, fg, bg = _sextant_cell(pix)
            text.append(
                glyph,
                style=f"#{fg[0]:02x}{fg[1]:02x}{fg[2]:02x} "
                f"on #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}",
            )
        text.append("│", style=_BORDER_FG)
        text.append("\n")

    footer = f" {total_txs:,} txs "
    bot_inner = _center_in_border(footer, iw)
    text.append("╰", style=_BORDER_FG)
    for ch in bot_inner:
        text.append(ch, style=_BORDER_FG if ch == "─" else _COUNT_FG)
    text.append("╯", style=_BORDER_FG)

    return text
