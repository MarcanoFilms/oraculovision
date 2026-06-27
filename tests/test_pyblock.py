"""Tests for the PyBLOCK community data client (pure parsing + cache)."""

from oraculovision.data import pyblock


def test_parse_community_blocks_full():
    data = {
        "lotto": 0,
        "datum": 1,
        "blocks": [
            {
                "height": 928997,
                "hash": "0000000000000000000189c5e4d2232e",
                "tag": "PyBLOCK",
                "protocol": "DATUM",
                "relay": "OCEAN",
                "confirmed": True,
                "timestamp": 1777641191,
            }
        ],
    }
    result = pyblock.parse_community_blocks(data)
    assert result.error == ""
    assert result.datum_count == 1
    assert len(result.blocks) == 1
    b = result.blocks[0]
    assert b.height == 928997
    assert b.relay == "OCEAN"
    assert b.confirmed is True
    assert b.mempool_url.endswith(b.hash)


def test_parse_community_blocks_none_is_error():
    result = pyblock.parse_community_blocks(None)
    assert result.error
    assert result.blocks == []


def test_parse_community_blocks_caps_count():
    blocks = [{"height": h} for h in range(50)]
    result = pyblock.parse_community_blocks({"blocks": blocks})
    assert len(result.blocks) == pyblock.MAX_BLOCKS


def test_parse_community_blocks_skips_non_dict():
    result = pyblock.parse_community_blocks({"blocks": ["bad", {"height": 1}]})
    assert len(result.blocks) == 1
    assert result.blocks[0].height == 1


def test_parse_datum_network():
    data = {
        "Workers": 260,
        "hashrate1m": 49446.96,
        "earnings": "0.00031697",
        "unpaid": "0.00141052",
        "last_share": 1782434462,
    }
    n = pyblock.parse_datum_network(data)
    assert n.error == ""
    assert n.workers == 260
    assert n.unpaid == "0.00141052"
    assert "PH/s" in n.hashrate_human


def test_parse_datum_network_none_is_error():
    n = pyblock.parse_datum_network(None)
    assert n.error
    assert n.workers == 0


def test_format_ths_scaling():
    assert pyblock._format_ths(0) == "0 TH/s"
    assert pyblock._format_ths(309) == "309.0 TH/s"
    assert pyblock._format_ths(49446.96) == "49.45 PH/s"
    assert pyblock._format_ths(2_000_000) == "2.00 EH/s"
    assert pyblock._format_ths("bad") == "—"


def test_blocks_cache_serves_stale_on_failure(monkeypatch):
    # Prime cache with a good parse, then a failing fetch should serve stale.
    pyblock._blocks_cache = None
    good = {"datum": 2, "blocks": [{"height": 5}]}
    monkeypatch.setattr(pyblock, "_fetch_json", lambda path: good)
    first = pyblock.fetch_community_blocks(cache_ttl=0)
    assert first.datum_count == 2
    monkeypatch.setattr(pyblock, "_fetch_json", lambda path: None)
    second = pyblock.fetch_community_blocks(cache_ttl=0)
    assert second.datum_count == 2  # served stale, not error
    pyblock._blocks_cache = None
