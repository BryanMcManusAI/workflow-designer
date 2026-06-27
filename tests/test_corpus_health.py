"""Provenance-discipline regression guards. The corpus promises observed (REPORTED) grounding, not
imagined failure modes — these lock the gains from the 2026-06-27 audit so a new card can't quietly
reintroduce the gap (every failure mode must carry a REPORTED/INFERRED tag).

We deliberately do NOT gate on `zero_reported == 0`: a handful of METHOD cards (Dawid-Skene,
phi/Textbooks, Something-Something) describe a technique whose failure modes are analytically derived,
not empirically measured in the source. Forcing REPORTED tags onto them to hit a number would be the
"costume of grounding" the tool exists to catch. The ratchet keeps that set from growing.
"""
import corpus_health


def test_no_untagged_failure_modes(idx):
    """Every failure mode must declare REPORTED or INFERRED — the discipline, now enforced."""
    h = corpus_health.report(idx)
    assert h["totals"]["untagged"] == 0, \
        f"untagged failure modes in: {[r['id'] for r in h['untagged_cards']]}"


def test_reported_ratio_floor(idx):
    """Most failure modes should be observed, not inferred — guards against inference-padding."""
    assert corpus_health.report(idx)["overall_ratio"] >= 0.55


def test_zero_reported_cards_do_not_grow(idx):
    """Ratchet: the method-card set with no REPORTED mode must not expand (it should shrink as sources
    are verified, never grow)."""
    assert len(corpus_health.report(idx)["zero_reported"]) <= 3
