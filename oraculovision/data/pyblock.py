"""PyBLOCK pool community data via its public DATUM API.

Third-party, *community* context that a sovereign node cannot know on its own:
which blocks the PyBLOCK DATUM pool has found, and the aggregate DATUM-pooled
network size. This never replaces own-node metrics — it is clearly-labelled
community data, fetched best-effort with a short TTL cache. Any network or
parse failure degrades gracefully to an ``error`` field, never an exception.

API docs: https://pyblock.xyz:8443/api-docs.php
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

PYBLOCK_API_BASE = os.environ.get("PYBLOCK_API_URL", "https://pyblock.xyz:8443").rstrip("/")
BLOCKS_CACHE_TTL = 300
NETWORK_CACHE_TTL = 60
MAX_BLOCKS = 10

_blocks_cache: tuple[float, "CommunityBlocks"] | None = None
_network_cache: tuple[float, "PyblockDatumNetwork"] | None = None


@dataclass
class CommunityBlock:
    height: int = 0
    hash: str = ""
    tag: str = ""
    protocol: str = ""
    relay: str = ""
    confirmed: bool = False
    timestamp: int = 0

    @property
    def mempool_url(self) -> str:
        return f"https://mempool.space/block/{self.hash}" if self.hash else ""


@dataclass
class CommunityBlocks:
    blocks: list[CommunityBlock] = field(default_factory=list)
    lotto_count: int = 0
    datum_count: int = 0
    error: str = ""


@dataclass
class PyblockDatumNetwork:
    workers: int = 0
    hashrate_ths: float = 0.0
    earnings: str = "—"
    unpaid: str = "—"
    last_share: int = 0
    error: str = ""

    @property
    def hashrate_human(self) -> str:
        return _format_ths(self.hashrate_ths)


def _format_ths(value_ths: float) -> str:
    """Format a TH/s magnitude into a human-readable hashrate string."""
    try:
        ths = float(value_ths)
    except (TypeError, ValueError):
        return "—"
    if ths <= 0:
        return "0 TH/s"
    if ths >= 1e6:
        return f"{ths / 1e6:.2f} EH/s"
    if ths >= 1e3:
        return f"{ths / 1e3:.2f} PH/s"
    return f"{ths:.1f} TH/s"


def _fetch_json(path: str) -> dict | None:
    url = f"{PYBLOCK_API_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "oraculovision/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_community_blocks(data: dict | None) -> CommunityBlocks:
    """Parse the ``mode=blocks`` payload into a CommunityBlocks (pure / testable)."""
    if not data:
        return CommunityBlocks(error="PyBLOCK community data unavailable")
    out = CommunityBlocks(
        lotto_count=int(data.get("lotto", 0) or 0),
        datum_count=int(data.get("datum", 0) or 0),
    )
    raw_blocks = data.get("blocks")
    if isinstance(raw_blocks, list):
        for b in raw_blocks[:MAX_BLOCKS]:
            if not isinstance(b, dict):
                continue
            out.blocks.append(
                CommunityBlock(
                    height=int(b.get("height", 0) or 0),
                    hash=str(b.get("hash", "")),
                    tag=str(b.get("tag", "")),
                    protocol=str(b.get("protocol", "")),
                    relay=str(b.get("relay", "")),
                    confirmed=bool(b.get("confirmed", False)),
                    timestamp=int(b.get("timestamp", 0) or 0),
                )
            )
    return out


def parse_datum_network(data: dict | None) -> PyblockDatumNetwork:
    """Parse the ``mode=datum`` payload into a PyblockDatumNetwork (pure / testable)."""
    if not data:
        return PyblockDatumNetwork(error="PyBLOCK DATUM network data unavailable")
    return PyblockDatumNetwork(
        workers=int(data.get("Workers", 0) or 0),
        hashrate_ths=float(data.get("hashrate1m", 0.0) or 0.0),
        earnings=str(data.get("earnings", "—")),
        unpaid=str(data.get("unpaid", "—")),
        last_share=int(data.get("last_share", 0) or 0),
    )


def fetch_community_blocks(*, cache_ttl: int = BLOCKS_CACHE_TTL) -> CommunityBlocks:
    """Recent blocks found by the PyBLOCK community pool (cached, best-effort)."""
    global _blocks_cache
    now = time.time()
    if _blocks_cache and now - _blocks_cache[0] < cache_ttl:
        return _blocks_cache[1]
    result = parse_community_blocks(_fetch_json("/api.php?mode=blocks"))
    if not result.error:
        _blocks_cache = (now, result)
    elif _blocks_cache:
        return _blocks_cache[1]
    return result


def fetch_datum_network(*, cache_ttl: int = NETWORK_CACHE_TTL) -> PyblockDatumNetwork:
    """Aggregate DATUM-pooled network stats (cached, best-effort)."""
    global _network_cache
    now = time.time()
    if _network_cache and now - _network_cache[0] < cache_ttl:
        return _network_cache[1]
    result = parse_datum_network(_fetch_json("/api.php?mode=datum"))
    if not result.error:
        _network_cache = (now, result)
    elif _network_cache:
        return _network_cache[1]
    return result
