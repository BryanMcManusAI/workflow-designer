"""The recommendation eval as a quality GATE: a corpus or engine change that tanks the advice should
fail CI, not slip through. Floors are conservative (well below current scores) so normal corpus growth
doesn't trip them — they catch regressions, not fluctuations. Gold is draft/audit-pending, so these
are ratchets, not a leaderboard.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
import run_eval


def test_eval_runs_and_metrics_well_formed(idx):
    res = run_eval.run(idx, run_eval.load_gold())
    assert res["n"] >= 8
    for r in res["rows"]:
        for m in ("recall_structural", "recall_semantic", "recall_combined", "risk_recall"):
            assert 0.0 <= r[m] <= 1.0


def test_risk_detection_floor(idx):
    """The engine should name (nearly) all genuinely-applicable risks — its strongest channel.
    Floor ratcheted to 0.90 after the hybrid-retrieval change pushed risk recall to 1.0."""
    assert run_eval.run(idx, run_eval.load_gold())["aggregate"]["risk_recall"] >= 0.90


def test_retrieval_floor(idx):
    """Hybrid near-analogue retrieval (axes + goal-text topical) should surface most relevant cards.
    Floor 0.85 ratchets in the hybrid-retrieval lift (0.80 -> 0.90 mean combined recall)."""
    agg = run_eval.run(idx, run_eval.load_gold())["aggregate"]
    assert agg["recall_combined"] >= 0.90   # ratcheted after domain-coherence (0.90 -> 0.93)
    assert agg["recall_semantic"] >= 0.75
