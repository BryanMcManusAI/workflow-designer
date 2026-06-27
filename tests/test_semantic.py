"""Tests for the deterministic (Tier-1) topical retrieval.

The LLM tiers (semantic Tier-2, ingest) can't be unit-tested without a key/network, but the offline
GUARANTEE must hold: with use_llm=False the topical layer ranks by the goal text, deterministically,
and resolves the structural-blindness case the four-axis engine can't (toxicity vs NLI, both
text/classification). These tests pin that guarantee.
"""
from conftest import make_stub

import semantic


TOX = make_stub(
    goal="Label user comments as toxic or hateful to train a content-moderation classifier",
    modality="text", task_structure="classification", annotator_structure="crowd")


def test_topical_scores_are_deterministic(idx):
    a = semantic.topical_scores(idx, TOX["goal"])
    b = semantic.topical_scores(idx, TOX["goal"])
    assert a == b  # pure function of goal + corpus, no randomness


def test_topical_beats_structural_on_topic(idx):
    """The fix: goal-driven topical ranking puts content-moderation above NLI, where the four-axis
    structural near-set (which can't read the goal) ranks the NLI cards equal-or-higher."""
    scores = semantic.topical_scores(idx, TOX["goal"])
    assert scores["content-moderation-abuse"][0] > scores.get("nli-snli-artifacts", (0, []))[0]
    assert scores["content-moderation-abuse"][0] > scores.get("adversarial-nli-anli", (0, []))[0]


def test_analyze_semantic_offline_returns_real_cards(idx):
    res = semantic.analyze_semantic(idx, TOX, use_llm=False)
    assert res["tier"] == "topical (deterministic)"
    assert res["ranked"], "expected a non-empty ranking"
    assert res["ranked"][0]["id"] == "content-moderation-abuse"
    for r in res["ranked"]:
        assert r["id"] in idx["cards"]  # every suggestion is a real corpus card (no fabrication)


def test_empty_goal_degrades_gracefully(idx):
    res = semantic.analyze_semantic(idx, make_stub(goal="", modality="text",
                                                   task_structure="classification"), use_llm=False)
    assert res["tier"] == "topical (deterministic)"
    for r in res["ranked"]:
        assert r["id"] in idx["cards"]


def test_stopwords_dropped(idx):
    # generic workflow words carry no topical signal
    assert semantic.tokens("the data labeling workflow for our model") == []
