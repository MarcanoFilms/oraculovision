"""Ocean pool account statistics via public API v1."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

OCEAN_API_BASE = os.environ.get("OCEAN_API_URL", "https://api.ocean.xyz").rstrip("/")
DEFAULT_CACHE_TTL = 60
BLOCKS_FOUND_CACHE_TTL = 300
SECONDS_PER_DAY = 86_400
BLOCKS_PER_DAY_ESTIMATE = 144
MAX_BLOCK_PAGES = 12
BLOCK_PAGE_DELAY = 0.15

OCEAN_INTERVALS: tuple[tuple[str, str, str, str], ...] = (
    ("60s", "hashrate_60s", "shares_60s", "pool_60s"),
    ("5min", "hashrate_300s", "shares_300s", "pool_300s"),
    ("3hr", "hashrate_10800s", "shares_10800s", "pool_10800s"),
    ("24hr", "hashrate_86400s", "shares_86400s", "pool_86400s"),
)

_HASH_UNITS: tuple[tuple[float, str], ...] = (
    (1e18, "EH/s"),
    (1e15, "PH/s"),
    (1e12, "TH/s"),
    (1e9, "GH/s"),
    (1e6, "MH/s"),
    (1e3, "kH/s"),
)

_cache: dict[str, tuple[float, "OceanAccountStats"]] = {}
_blocks_found_cache: dict[str, tuple[float, int, list[str]]] = {}


@dataclass
class OceanInterval:
    label: str
    miner_hashrate: str = "—"
    pool_hashrate: str = "—"
    shares: str = "—"
    hash_pct: str = "—"


@dataclass
class OceanWorker:
    name: str = ""
    hashrate_60s: str = "—"
    hashrate_300s: str = "—"
    hashrate_10800s: str = "—"
    hashrate_86400s: str = "—"
    detected_asic: str = "—"
    is_active: bool = False


@dataclass
class OceanEarnings:
    est_per_day: str = "—"
    unpaid: str = "—"
    unpaid_value: float = 0.0
    payout_threshold: float = 0.001
    est_next_block: str = "—"
    lifetime: str = "—"
    blocks_earned_tides: int = 0
    blocks_found_by_you: int = 0
    found_worker_names: list[str] = field(default_factory=list)
    workers_hashing: int = 0
    worker_names: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class OceanBlock:
    height: int = 0
    hash: str = ""
    timestamp: str = ""
    miner_address: str = ""
    worker_name: str = ""
    reward_sats: int = 0


@dataclass
class OceanAccountStats:
    available: bool = False
    address: str = ""
    intervals: list[OceanInterval] = field(default_factory=list)
    tides_shares_pct: str = "—"
    active_workers: int = 0
    earnings: OceanEarnings = field(default_factory=OceanEarnings)
    workers: list[OceanWorker] = field(default_factory=list)
    last_pool_block: OceanBlock = field(default_factory=OceanBlock)
    error: str = ""


def normalize_address(raw: str) -> str | None:
    """Validate and return a normalized Bitcoin payout address, or None."""
    address = raw.strip()
    if not address:
        return None
    if re.match(r"^(bc1[a-z0-9]{25,87}|bc1p[a-z0-9]{25,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$", address):
        return address
    return None


def invalidate_ocean_cache(address: str = "") -> None:
    """Drop cached Ocean stats (one address or entire cache)."""
    if address:
        key = normalize_address(address) or address.strip()
        _cache.pop(key, None)
        _blocks_found_cache.pop(key, None)
    else:
        _cache.clear()
        _blocks_found_cache.clear()


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _format_hashrate(raw: object) -> str:
    hs = _parse_int(raw)
    if hs is None:
        return "—"
    if hs == 0:
        return "0 H/s"
    for scale, unit in _HASH_UNITS:
        if hs >= scale:
            return f"{hs / scale:.2f} {unit}"
    return f"{hs} H/s"


def _format_shares(raw: object) -> str:
    count = _parse_int(raw)
    if count is None:
        return "—"
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f} G"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f} M"
    if count >= 1_000:
        return f"{count / 1_000:.1f} K"
    return str(count)


def _format_pct(numerator: int | None, denominator: int | None) -> str:
    if numerator is None or denominator is None or denominator <= 0:
        return "—"
    pct = (numerator / denominator) * 100
    if pct < 0.01:
        return f"{pct:.4f}%"
    if pct < 1:
        return f"{pct:.3f}%"
    return f"{pct:.2f}%"


def _format_btc_sats(satoshis: int) -> str:
    return f"{satoshis / 1e8:.8f} BTC"


def _format_btc_amount(raw: object) -> str:
    value = _parse_float(raw)
    if value is None:
        return "—"
    return f"{value:.8f} BTC"


def _truncate_address(address: str) -> str:
    if len(address) <= 16:
        return address
    return f"{address[:8]}…{address[-8:]}"


def _fetch_json(path: str) -> dict | None:
    url = f"{OCEAN_API_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "oraculovision/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("error"):
        return None
    result = payload.get("result")
    return result if isinstance(result, dict) else None


def _fetch_user_hashrate(address: str) -> dict | None:
    data = _fetch_json(f"/v1/user_hashrate/{address}")
    if data:
        return data
    fallback = _fetch_json(f"/v1/user_hashrate_full/{address}")
    if not fallback:
        return None
    user = fallback.get("user_hashrate")
    if isinstance(user, dict):
        merged = dict(user)
        if "active_worker_count" not in merged and isinstance(fallback.get("workers"), dict):
            merged["active_worker_count"] = len(fallback["workers"])
        return merged
    return fallback


def _parse_earning_ts(raw: object) -> datetime | None:
    if not raw:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _count_blocks_found_by_user(
    address: str,
    since_ts: int | None,
) -> tuple[int, list[str]]:
    """Count pool blocks solved by this wallet via paginated /v1/blocks."""
    cutoff: datetime | None = None
    if since_ts:
        cutoff = datetime.fromtimestamp(since_ts, tz=timezone.utc)

    found = 0
    workers: list[str] = []

    for page in range(MAX_BLOCK_PAGES):
        data = _fetch_json(f"/v1/blocks?page={page}")
        if not data:
            break

        blocks = data.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            break

        oldest_ts: datetime | None = None
        for block in blocks:
            if not isinstance(block, dict):
                continue
            ts = _parse_earning_ts(block.get("ts"))
            if ts and (oldest_ts is None or ts < oldest_ts):
                oldest_ts = ts
            if block.get("username") == address:
                found += 1
                worker = block.get("workername")
                if worker:
                    name = str(worker)
                    if name not in workers:
                        workers.append(name)

        if cutoff and oldest_ts and oldest_ts < cutoff:
            break

        if page < MAX_BLOCK_PAGES - 1:
            time.sleep(BLOCK_PAGE_DELAY)

    return found, workers


def _get_blocks_found_by_user(
    address: str,
    since_ts: int | None,
) -> tuple[int, list[str]]:
    """Return blocks-found count; paginated API runs at most every 5 minutes."""
    now = time.monotonic()
    cached = _blocks_found_cache.get(address)
    if cached and (now - cached[0]) < BLOCKS_FOUND_CACHE_TTL:
        return cached[1], cached[2]

    found, workers = _count_blocks_found_by_user(address, since_ts)
    _blocks_found_cache[address] = (now, found, workers)
    return found, workers


def _workers_hashing(user_info: dict | None) -> tuple[list[str], int]:
    names: list[str] = []
    if not user_info:
        return names, 0
    for item in user_info.get("workers", []):
        if not isinstance(item, dict):
            continue
        for name, data in item.items():
            if not isinstance(data, dict):
                continue
            hr_60 = _parse_int(data.get("hashrate_60s")) or 0
            hr_300 = _parse_int(data.get("hashrate_300s")) or 0
            if hr_60 > 0 or hr_300 > 0:
                names.append(str(name))
    return names, len(names)


def _build_earnings(
    address: str,
    user_full: dict,
    user_info: dict | None,
    earnpay: dict | None,
) -> OceanEarnings:
    earnings = OceanEarnings()

    unpaid = user_full.get("unpaid")
    if unpaid is not None:
        earnings.unpaid = _format_btc_amount(unpaid)
        earnings.unpaid_value = _parse_float(unpaid) or 0.0

    next_block = user_full.get("estimated_total_earn_next_block")
    if next_block is not None:
        earnings.est_next_block = _format_btc_amount(next_block)

    worker_names, worker_count = _workers_hashing(user_info)
    earnings.worker_names = worker_names
    earnings.workers_hashing = worker_count

    if not earnpay:
        earnings.error = "Earnings data unavailable"
        return earnings

    entries = earnpay.get("earnings")
    if not isinstance(entries, list):
        earnings.error = "Earnings data unavailable"
        return earnings

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    daily_sats = 0
    lifetime_sats = 0
    blocks_earned_tides = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        sats = _parse_int(entry.get("satoshis_net_earned")) or 0
        if sats <= 0:
            continue
        lifetime_sats += sats
        blocks_earned_tides += 1
        ts = _parse_earning_ts(entry.get("ts"))
        if ts and ts >= cutoff_24h:
            daily_sats += sats

    earnings.blocks_earned_tides = blocks_earned_tides
    since_ts = _parse_int(earnpay.get("start_ts"))
    found, found_workers = _get_blocks_found_by_user(address, since_ts)
    earnings.blocks_found_by_you = found
    earnings.found_worker_names = found_workers

    if lifetime_sats > 0:
        earnings.lifetime = f"{_format_btc_sats(lifetime_sats)} (30d)"

    if daily_sats > 0:
        earnings.est_per_day = _format_btc_sats(daily_sats)
    elif blocks_earned_tides > 0:
        sample = [
            _parse_int(entry.get("satoshis_net_earned")) or 0
            for entry in entries[:20]
            if isinstance(entry, dict)
        ]
        if sample:
            avg_block = sum(sample) / len(sample)
            earnings.est_per_day = (
                f"~{_format_btc_sats(int(avg_block * BLOCKS_PER_DAY_ESTIMATE))} (est.)"
            )

    return earnings


def guess_asic_model(name: str) -> str:
    name_lower = name.lower()
    if "s19" in name_lower:
        if "xp" in name_lower:
            return "Antminer S19 XP"
        if "pro" in name_lower:
            return "Antminer S19 Pro"
        return "Antminer S19 Series"
    if "s21" in name_lower:
        return "Antminer S21 Series"
    if "t21" in name_lower:
        return "Antminer T21"
    if "m30" in name_lower:
        if "s" in name_lower:
            return "Whatsminer M30S"
        return "Whatsminer M30 Series"
    if "m50" in name_lower:
        return "Whatsminer M50 Series"
    if "m60" in name_lower:
        return "Whatsminer M60 Series"
    if "t2t" in name_lower:
        return "Innosilicon T2T"
    if "whats" in name_lower:
        return "Whatsminer ASIC"
    if "ant" in name_lower:
        return "Antminer ASIC"
    if "asic" in name_lower:
        return "Generic ASIC"
    return "Unknown/GPU/PC"


def _build_workers(user_info: dict | None) -> list[OceanWorker]:
    workers = []
    if not user_info:
        return workers
    for item in user_info.get("workers", []):
        if not isinstance(item, dict):
            continue
        for name, data in item.items():
            if not isinstance(data, dict):
                continue
            hr_60 = _parse_int(data.get("hashrate_60s")) or 0
            hr_300 = _parse_int(data.get("hashrate_300s")) or 0
            hr_10800 = _parse_int(data.get("hashrate_10800s")) or 0
            hr_86400 = _parse_int(data.get("hashrate_86400s")) or 0
            active = hr_60 > 0 or hr_300 > 0

            workers.append(
                OceanWorker(
                    name=str(name),
                    hashrate_60s=_format_hashrate(hr_60),
                    hashrate_300s=_format_hashrate(hr_300),
                    hashrate_10800s=_format_hashrate(hr_10800),
                    hashrate_86400s=_format_hashrate(hr_86400),
                    detected_asic=guess_asic_model(str(name)),
                    is_active=active,
                )
            )
    # Sort active workers first, then by name
    workers.sort(key=lambda w: (not w.is_active, w.name))
    return workers


def fetch_ocean_account_stats(address: str, *, cache_ttl: int = DEFAULT_CACHE_TTL) -> OceanAccountStats:
    """Return Ocean account stats for a Bitcoin payout address."""
    normalized = normalize_address(address)
    if normalized is None:
        if address.strip():
            return OceanAccountStats(address=address.strip(), error="Invalid Bitcoin address")
        return OceanAccountStats()

    now = time.monotonic()
    cached = _cache.get(normalized)
    if cached and (now - cached[0]) < cache_ttl:
        return cached[1]

    stats = OceanAccountStats(address=normalized)
    user_hr = _fetch_user_hashrate(normalized)
    user_info = _fetch_json(f"/v1/userinfo_full/{normalized}")
    pool_hr = _fetch_json("/v1/pool_hashrate")
    pool_stat = _fetch_json("/v1/pool_stat")
    earnpay = _fetch_json(f"/v1/earnpay/{normalized}")

    if not user_hr and not user_info:
        stats.error = "Ocean API unavailable"
        _cache[normalized] = (now, stats)
        return stats

    user_full: dict = {}
    if user_info:
        raw_full = user_info.get("user_full")
        if isinstance(raw_full, dict):
            user_full = raw_full

    stats.active_workers = _parse_int(user_hr.get("active_worker_count") if user_hr else None) or 0
    stats.earnings = _build_earnings(normalized, user_full, user_info, earnpay)
    stats.workers = _build_workers(user_info)

    # Parse payout threshold from API if available
    min_payout_sats = user_full.get("minimum_payout")
    if min_payout_sats is not None:
        stats.earnings.payout_threshold = float(min_payout_sats) / 100_000_000
    else:
        stats.earnings.payout_threshold = 0.001

    # Fetch last pool block
    blocks_data = _fetch_json("/v1/blocks?page=0")
    if blocks_data and isinstance(blocks_data.get("blocks"), list) and blocks_data["blocks"]:
        b = blocks_data["blocks"][0]
        ts_parsed = _parse_earning_ts(b.get("ts"))
        ts_str = ts_parsed.strftime("%Y-%m-%d %H:%M") if ts_parsed else "—"
        stats.last_pool_block = OceanBlock(
            height=_parse_int(b.get("height")) or 0,
            hash=str(b.get("hash") or ""),
            timestamp=ts_str,
            miner_address=str(b.get("username") or ""),
            worker_name=str(b.get("workername") or "—"),
            reward_sats=int(float(b.get("reward") or 0.0) * 100_000_000),
        )

    tides_user = _parse_int(user_full.get("shares_in_tides"))
    tides_pool = _parse_int(pool_stat.get("current_tides_shares") if pool_stat else None)
    stats.tides_shares_pct = _format_pct(tides_user, tides_pool)

    for label, hr_key, shares_key, pool_key in OCEAN_INTERVALS:
        miner_hs = _parse_int(user_hr.get(hr_key) if user_hr else None)
        pool_hs = _parse_int(pool_hr.get(pool_key) if pool_hr else None)
        shares_raw = user_full.get(shares_key) if user_full else None

        stats.intervals.append(
            OceanInterval(
                label=label,
                miner_hashrate=_format_hashrate(miner_hs),
                pool_hashrate=_format_hashrate(pool_hs),
                shares=_format_shares(shares_raw),
                hash_pct=_format_pct(miner_hs, pool_hs),
            )
        )

    stats.available = bool(user_hr or user_info)
    _cache[normalized] = (now, stats)
    return stats


def format_ocean_address(address: str) -> str:
    """Short display form for configured payout addresses."""
    return _truncate_address(address)