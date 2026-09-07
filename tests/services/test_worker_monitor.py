"""Tests for the worker online/offline transition monitor."""

from __future__ import annotations

from oraculovision.services.worker_monitor import WorkerMonitor, WorkerTransitions


def test_first_observation_is_baseline_no_alerts():
    m = WorkerMonitor()
    t = m.update(["bitaxe", "s19"])
    assert t.came_online == []
    assert t.went_offline == []
    assert not t


def test_detects_worker_going_offline():
    m = WorkerMonitor()
    m.update(["bitaxe", "s19"])
    t = m.update(["bitaxe"])
    assert t.went_offline == ["s19"]
    assert t.came_online == []
    assert bool(t) is True


def test_detects_worker_coming_online():
    m = WorkerMonitor()
    m.update(["bitaxe"])
    t = m.update(["bitaxe", "s21"])
    assert t.came_online == ["s21"]
    assert t.went_offline == []


def test_simultaneous_online_and_offline_sorted():
    m = WorkerMonitor()
    m.update(["a", "b"])
    t = m.update(["b", "c", "a2"])
    assert t.came_online == ["a2", "c"]
    assert t.went_offline == ["a"]


def test_no_change_returns_empty():
    m = WorkerMonitor()
    m.update(["x", "y"])
    t = m.update(["y", "x"])
    assert not t


def test_reset_reestablishes_baseline():
    m = WorkerMonitor()
    m.update(["a", "b"])
    m.reset()
    # After reset, the next observation is a fresh baseline (no alerts even
    # though the set changed from before the reset).
    t = m.update(["c"])
    assert not t


def test_accepts_any_iterable_and_stringifies():
    m = WorkerMonitor()
    m.update(iter(["w1"]))
    t = m.update({"w1", "w2"})
    assert t.came_online == ["w2"]


def test_transitions_bool_dunder():
    assert not WorkerTransitions([], [])
    assert WorkerTransitions(["a"], [])
    assert WorkerTransitions([], ["b"])
