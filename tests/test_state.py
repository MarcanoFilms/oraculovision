"""Tests for persisted UI state (Ocean address)."""

import pathlib
import tempfile

import pytest

from oraculovision import state


@pytest.fixture
def temp_state(monkeypatch):
    d = pathlib.Path(tempfile.mkdtemp())
    monkeypatch.setattr(state, "_STATE_DIR", d)
    monkeypatch.setattr(state, "_STATE_FILE", d / "state.json")
    return d


def test_load_empty_when_no_file(temp_state):
    assert state.load_ocean_address() == ""


def test_save_and_load_roundtrip(temp_state):
    addr = "bc1qyqw74c488n39wfw3ctw0l2ujaa6q3sa39zvp3g"
    state.save_ocean_address(addr)
    assert state.load_ocean_address() == addr


def test_save_strips_whitespace(temp_state):
    state.save_ocean_address("  bc1qabc  ")
    assert state.load_ocean_address() == "bc1qabc"


def test_empty_save_clears(temp_state):
    state.save_ocean_address("bc1qabc")
    state.save_ocean_address("")
    assert state.load_ocean_address() == ""


def test_corrupt_file_returns_empty(temp_state):
    (temp_state / "state.json").write_text("{ not json")
    assert state.load_ocean_address() == ""
