"""Composite Sovereignty Score — single headline metric for node health.

Formula (0–100, higher = more sovereign):

    score = 100 – penalties

Penalties:
  - Not fully synced           : up to 25 pts  (25 if ibd, less if > 50 %)
  - Peer deficit               : min(20, (min_peers – actual_peers) * 5)
  - Not running Bitcoin Knots  : 10 pts
  - Template spam weight       :  > 30 % → 20 pts | 15–30 % → 10 pts | 5–15 % → 5 pts
  - Tip block spam score       :  > 60 → 15 pts  | 40–60 → 8 pts
  - Chain health violation %   :  > 20 % → 10 pts | 10–20 % → 5 pts (optional)

Grade thresholds:
  A+ 96–100 | A 90–95 | B 80–89 | C 70–79 | D 60–69 | F < 60
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SovereigntyScoreResult:
    score: int
    grade: str
    penalties: dict[str, int]


def compute_sovereignty_score(
    *,
    is_synced: bool,
    sync_pct: float,
    peer_count: int,
    min_peers: int,
    knots: bool,
    template_spam_pct: float = 0.0,
    tip_spam_score: int | None = None,
    violation_pct: float = 0.0,
) -> SovereigntyScoreResult:
    """Return a 0-100 sovereignty score and letter grade.

    All parameters must be non-negative.  Pass only the data you have;
    optional parameters default to neutral (no penalty).
    """
    penalties: dict[str, int] = {}

    # Sync penalty
    if not is_synced:
        if sync_pct < 50.0:
            penalties["sync"] = 25
        else:
            penalties["sync"] = max(1, int(25 * (1 - sync_pct / 100)))

    # Peer penalty
    peer_deficit = max(0, min_peers - peer_count)
    if peer_deficit > 0:
        penalties["peers"] = min(20, peer_deficit * 5)

    # Knots penalty
    if not knots:
        penalties["no_knots"] = 10

    # Template spam penalty
    if template_spam_pct > 30:
        penalties["template_spam"] = 20
    elif template_spam_pct > 15:
        penalties["template_spam"] = 10
    elif template_spam_pct > 5:
        penalties["template_spam"] = 5

    # Tip block spam penalty
    if tip_spam_score is not None:
        if tip_spam_score > 60:
            penalties["tip_spam"] = 15
        elif tip_spam_score > 40:
            penalties["tip_spam"] = 8

    # Chain health penalty (violation % of recent blocks)
    if violation_pct > 20:
        penalties["chain_health"] = 10
    elif violation_pct > 10:
        penalties["chain_health"] = 5

    total_penalty = sum(penalties.values())
    score = max(0, min(100, 100 - total_penalty))
    grade = _grade(score)

    return SovereigntyScoreResult(score=score, grade=grade, penalties=penalties)


def _grade(score: int) -> str:
    if score >= 96:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
