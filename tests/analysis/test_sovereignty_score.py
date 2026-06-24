"""Tests for the Sovereignty Score calculation."""

from __future__ import annotations

import pytest

from oraculovision.analysis.sovereignty_score import (
    SovereigntyScoreResult,
    compute_sovereignty_score,
    _grade,
)


def _score(**kwargs) -> SovereigntyScoreResult:
    defaults = dict(
        is_synced=True,
        sync_pct=100.0,
        peer_count=12,
        min_peers=8,
        knots=True,
        template_spam_pct=0.0,
        tip_spam_score=None,
        violation_pct=0.0,
    )
    defaults.update(kwargs)
    return compute_sovereignty_score(**defaults)


class TestGrade:
    def test_grade_a_plus(self):
        assert _grade(100) == "A+"
        assert _grade(96) == "A+"

    def test_grade_a(self):
        assert _grade(95) == "A"
        assert _grade(90) == "A"

    def test_grade_b(self):
        assert _grade(89) == "B"
        assert _grade(80) == "B"

    def test_grade_c(self):
        assert _grade(79) == "C"
        assert _grade(70) == "C"

    def test_grade_d(self):
        assert _grade(69) == "D"
        assert _grade(60) == "D"

    def test_grade_f(self):
        assert _grade(59) == "F"
        assert _grade(0) == "F"


class TestPerfectScore:
    def test_perfect_node_scores_100(self):
        result = _score()
        assert result.score == 100
        assert result.grade == "A+"
        assert result.penalties == {}

    def test_result_type(self):
        result = _score()
        assert isinstance(result, SovereigntyScoreResult)
        assert isinstance(result.score, int)
        assert isinstance(result.grade, str)
        assert isinstance(result.penalties, dict)


class TestSyncPenalty:
    def test_not_synced_low_pct(self):
        result = _score(is_synced=False, sync_pct=10.0)
        assert result.penalties.get("sync") == 25
        assert result.score == 75

    def test_not_synced_high_pct(self):
        result = _score(is_synced=False, sync_pct=95.0)
        sync_pen = result.penalties.get("sync", 0)
        assert 0 < sync_pen <= 25

    def test_synced_no_penalty(self):
        result = _score(is_synced=True, sync_pct=100.0)
        assert "sync" not in result.penalties


class TestPeerPenalty:
    def test_no_peers_max_penalty(self):
        result = _score(peer_count=0, min_peers=8)
        assert result.penalties.get("peers") == 20  # capped at 20

    def test_one_below_minimum(self):
        result = _score(peer_count=7, min_peers=8)
        assert result.penalties.get("peers") == 5

    def test_at_minimum_no_penalty(self):
        result = _score(peer_count=8, min_peers=8)
        assert "peers" not in result.penalties

    def test_above_minimum_no_penalty(self):
        result = _score(peer_count=20, min_peers=8)
        assert "peers" not in result.penalties


class TestKnotsPenalty:
    def test_not_knots_penalised(self):
        result = _score(knots=False)
        assert result.penalties.get("no_knots") == 10
        assert result.score == 90

    def test_knots_no_penalty(self):
        result = _score(knots=True)
        assert "no_knots" not in result.penalties


class TestTemplateSpamPenalty:
    def test_high_spam(self):
        result = _score(template_spam_pct=35.0)
        assert result.penalties.get("template_spam") == 20

    def test_medium_spam(self):
        result = _score(template_spam_pct=20.0)
        assert result.penalties.get("template_spam") == 10

    def test_low_spam(self):
        result = _score(template_spam_pct=10.0)
        assert result.penalties.get("template_spam") == 5

    def test_minimal_spam_no_penalty(self):
        result = _score(template_spam_pct=3.0)
        assert "template_spam" not in result.penalties


class TestTipSpamPenalty:
    def test_very_high_tip_spam(self):
        result = _score(tip_spam_score=75)
        assert result.penalties.get("tip_spam") == 15

    def test_medium_tip_spam(self):
        result = _score(tip_spam_score=50)
        assert result.penalties.get("tip_spam") == 8

    def test_low_tip_spam_no_penalty(self):
        result = _score(tip_spam_score=20)
        assert "tip_spam" not in result.penalties

    def test_none_tip_spam_no_penalty(self):
        result = _score(tip_spam_score=None)
        assert "tip_spam" not in result.penalties


class TestChainHealthPenalty:
    def test_high_violation_pct(self):
        result = _score(violation_pct=25.0)
        assert result.penalties.get("chain_health") == 10

    def test_medium_violation_pct(self):
        result = _score(violation_pct=15.0)
        assert result.penalties.get("chain_health") == 5

    def test_low_violation_pct_no_penalty(self):
        result = _score(violation_pct=5.0)
        assert "chain_health" not in result.penalties


class TestScoreClamping:
    def test_score_never_below_zero(self):
        result = _score(
            is_synced=False, sync_pct=10.0,
            peer_count=0, min_peers=8,
            knots=False,
            template_spam_pct=50.0,
            tip_spam_score=80,
            violation_pct=30.0,
        )
        assert result.score >= 0

    def test_score_never_above_100(self):
        result = _score()
        assert result.score <= 100

    def test_worst_case_grade_f(self):
        result = _score(
            is_synced=False, sync_pct=10.0,
            peer_count=0, min_peers=8,
            knots=False,
            template_spam_pct=50.0,
            tip_spam_score=80,
            violation_pct=30.0,
        )
        assert result.grade == "F"
