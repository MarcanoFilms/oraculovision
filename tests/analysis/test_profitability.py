"""Tests for the mining profitability calculator."""

from __future__ import annotations

from oraculovision.analysis.profitability import compute_profitability


def test_gross_only_no_economics():
    p = compute_profitability(gross_sats_day=100_000)
    assert p.gross_sats_day == 100_000
    assert p.pool_fee_sats_day == 0
    assert p.net_sats_day == 100_000
    assert p.has_power is False
    assert p.has_fiat is False
    assert p.power_cost_day == 0.0
    assert p.power_sats_day == 0
    assert p.net_after_power_sats_day == 100_000
    assert p.profitable is True


def test_pool_fee_applied():
    p = compute_profitability(gross_sats_day=100_000, pool_fee_pct=2.0)
    assert p.pool_fee_sats_day == 2_000
    assert p.net_sats_day == 98_000


def test_pool_fee_clamped_to_range():
    over = compute_profitability(gross_sats_day=100_000, pool_fee_pct=150)
    assert over.pool_fee_sats_day == 100_000
    assert over.net_sats_day == 0
    under = compute_profitability(gross_sats_day=100_000, pool_fee_pct=-5)
    assert under.pool_fee_sats_day == 0


def test_power_cost_without_price():
    # 3250 W at 0.10/kWh -> 3.25 kW * 24h * 0.10 = 7.80 / day
    p = compute_profitability(
        gross_sats_day=100_000,
        power_watts=3250,
        power_cost_per_kwh=0.10,
    )
    assert p.has_power is True
    assert round(p.power_cost_day, 2) == 7.80
    # No BTC price -> can't convert to sats or fiat profit
    assert p.has_fiat is False
    assert p.power_sats_day == 0
    assert p.net_fiat_day == 0.0
    # Verdict falls back to net-after-fee since power can't be compared
    assert p.profitable is True


def test_power_requires_both_watts_and_price():
    only_watts = compute_profitability(gross_sats_day=100_000, power_watts=3250)
    assert only_watts.has_power is False
    only_rate = compute_profitability(gross_sats_day=100_000, power_cost_per_kwh=0.1)
    assert only_rate.has_power is False


def test_full_fiat_profitable():
    # 500k sats/day gross at $60k BTC = $300/day. Power 15W (Bitaxe) ~ $0.036/day.
    p = compute_profitability(
        gross_sats_day=500_000,
        power_watts=15,
        power_cost_per_kwh=0.10,
        pool_fee_pct=0.0,
        btc_price=60_000,
        currency="USD",
    )
    assert p.has_fiat is True
    assert p.power_sats_day > 0
    assert p.net_after_power_sats_day == p.net_sats_day - p.power_sats_day
    assert p.net_fiat_day > 0
    assert p.profitable is True


def test_full_fiat_unprofitable():
    # Tiny earnings, hungry rig: 1000 sats/day gross, 3250W at $0.30/kWh, $60k BTC.
    p = compute_profitability(
        gross_sats_day=1_000,
        power_watts=3250,
        power_cost_per_kwh=0.30,
        btc_price=60_000,
    )
    assert p.has_power and p.has_fiat
    assert p.net_after_power_sats_day < 0
    assert p.net_fiat_day < 0
    assert p.profitable is False


def test_fiat_conversion_consistency():
    # power_sats_day should equal power_cost_day converted at btc_price.
    p = compute_profitability(
        gross_sats_day=200_000,
        power_watts=1000,
        power_cost_per_kwh=0.20,
        btc_price=50_000,
    )
    expected_sats = round(p.power_cost_day * (100_000_000 / 50_000))
    assert p.power_sats_day == expected_sats


def test_negative_gross_floored():
    p = compute_profitability(gross_sats_day=-5)
    assert p.gross_sats_day == 0
    assert p.net_sats_day == 0
    assert p.profitable is False
