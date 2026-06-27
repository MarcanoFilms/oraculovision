"""Tests for frame-based animation helpers."""

from oraculovision.widgets import anim


def test_flow_edge_cycles():
    edges = [anim.flow_edge(i) for i in range(6)]
    assert edges[:3] == ["▓", "▒", "░"]
    assert edges[3:] == ["▓", "▒", "░"]  # wraps


def test_pulse_dot_breathes():
    seq = [anim.pulse_dot(i) for i in range(5)]
    # dim -> bright -> dim cycle, all valid glyphs
    assert all(d in "·•●" for d in seq)
    assert anim.pulse_dot(0) == "·"
    assert anim.pulse_dot(2) == "●"
    assert anim.pulse_dot(4) == "·"  # back to dim


def test_energy_glyph_active_vs_idle():
    assert anim.energy_glyph(0, active=True) == "◇"
    assert anim.energy_glyph(2, active=True) == "◆"
    # idle always steady dim glyph regardless of frame
    assert anim.energy_glyph(1, active=False) == "◇"
    assert anim.energy_glyph(99, active=False) == "◇"


def test_flowing_bar_width_is_stable():
    for pct in (0, 13, 50, 87, 100):
        for frame in range(10):
            assert len(anim.flowing_bar(pct, frame, 20)) == 20


def test_flowing_bar_empty_and_full():
    assert anim.flowing_bar(0, 5, 20) == "░" * 20
    assert anim.flowing_bar(100, 5, 20) == "█" * 20


def test_flowing_bar_data_driven_body():
    # 50% of 20 = 10 filled; 9 solid + 1 animated edge
    bar = anim.flowing_bar(50, 1, 20)
    assert bar.count("█") == 9
    assert bar[9] in "▓▒░"
    assert bar[10:] == "░" * 10


def test_flowing_bar_clamps_out_of_range():
    assert anim.flowing_bar(-10, 0, 20) == "░" * 20
    assert anim.flowing_bar(150, 0, 20) == "█" * 20


def test_diamond_meter_matches_mockup():
    # 6 of 12 peers, 10-wide meter → 5 filled (round(0.5*10))
    assert anim.diamond_meter(6, 12, 10) == "◆◆◆◆◆◇◇◇◇◇"
    # exact mockup case: 6 filled of 10
    assert anim.diamond_meter(6, 10, 10) == "◆◆◆◆◆◆◇◇◇◇"


def test_diamond_meter_bounds():
    assert anim.diamond_meter(0, 10, 10) == "◇" * 10
    assert anim.diamond_meter(99, 10, 10) == "◆" * 10
    assert anim.diamond_meter(5, 0, 10) == ""   # zero capacity → empty string
    assert anim.diamond_meter(5, 10, 0) == ""   # zero width → empty string


def test_trend_arrow():
    assert anim.trend_arrow(5) == "↗"
    assert anim.trend_arrow(-3) == "↘"
    assert anim.trend_arrow(0) == "→"
