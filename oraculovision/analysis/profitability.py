"""Mining profitability — turn gross pool earnings into net figures.

Pure functions, no I/O. Given an estimated gross sat/day from the pool and
the operator's local economics (pool fee, rig wattage, electricity price,
and optionally a BTC spot price), returns pool-fee-adjusted and
electricity-adjusted results. Inspired by DeepSea-Dashboard's net-earnings
panel, adapted for the terminal.
"""

from __future__ import annotations

from dataclasses import dataclass

SATS_PER_BTC = 100_000_000
HOURS_PER_DAY = 24


@dataclass(frozen=True)
class Profitability:
    gross_sats_day: int
    pool_fee_sats_day: int
    net_sats_day: int  # gross minus pool fee — always meaningful
    has_power: bool  # whether electricity economics were applied
    power_cost_day: float  # electricity cost per day, in `currency`
    power_sats_day: int  # that cost expressed in sats (needs btc_price), else 0
    net_after_power_sats_day: int  # net_sats_day minus power_sats_day
    has_fiat: bool  # whether a BTC price was supplied
    net_fiat_day: float  # net profit/day in `currency` (needs btc_price), else 0.0
    currency: str
    profitable: bool  # best-available verdict given the inputs


def compute_profitability(
    *,
    gross_sats_day: int,
    power_watts: float = 0.0,
    power_cost_per_kwh: float = 0.0,
    pool_fee_pct: float = 0.0,
    btc_price: float = 0.0,
    currency: str = "USD",
) -> Profitability:
    """Return a :class:`Profitability` breakdown.

    Only ``gross_sats_day`` is required. The pool fee is always applied when
    > 0. Electricity is applied when both ``power_watts`` and
    ``power_cost_per_kwh`` are > 0. The electricity-vs-earnings comparison and
    the fiat figures additionally need ``btc_price`` > 0.
    """
    gross = max(0, int(gross_sats_day))
    pool_fee_pct = min(100.0, max(0.0, pool_fee_pct))
    fee_sats = int(round(gross * (pool_fee_pct / 100.0)))
    net_sats = gross - fee_sats

    has_power = power_watts > 0 and power_cost_per_kwh > 0
    power_cost_day = (power_watts / 1000.0) * HOURS_PER_DAY * power_cost_per_kwh if has_power else 0.0

    has_fiat = btc_price > 0
    power_sats_day = 0
    net_after_power = net_sats
    net_fiat_day = 0.0
    if has_fiat:
        sats_per_currency_unit = SATS_PER_BTC / btc_price
        power_sats_day = int(round(power_cost_day * sats_per_currency_unit))
        net_after_power = net_sats - power_sats_day
        net_fiat_day = (net_sats / SATS_PER_BTC) * btc_price - power_cost_day

    if has_power and has_fiat:
        profitable = net_after_power > 0
    else:
        profitable = net_sats > 0

    return Profitability(
        gross_sats_day=gross,
        pool_fee_sats_day=fee_sats,
        net_sats_day=net_sats,
        has_power=has_power,
        power_cost_day=power_cost_day,
        power_sats_day=power_sats_day,
        net_after_power_sats_day=net_after_power,
        has_fiat=has_fiat,
        net_fiat_day=net_fiat_day,
        currency=currency,
        profitable=profitable,
    )
