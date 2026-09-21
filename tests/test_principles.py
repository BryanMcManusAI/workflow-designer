"""Tests for the principles tier (the intellectual backbone) and its wiring into backwards-from-good.

The discipline that keeps the backbone honest: every construct must point at real signatures, real
patterns, and (where claimed) real corpus cards — and the literature evidence must carry a source.
Plus a COVERAGE test: every validity signature has a principle; `bottleneck` is the one signature
deliberately left out (it's an operational/throughput concern, not a 'good data' construct).
"""
from conftest import SIGNATURE_VOCAB

import engine


def test_principles_loaded(idx):
    assert idx.get("principles"), "principles tier should be compiled into index.json"


def test_protects_against_are_real_signatures(idx):
    for pid, p in idx["principles"].items():
        for s in p["protects_against"]:
            assert s in SIGNATURE_VOCAB, f"{pid} protects unknown signature {s!r}"


def test_operationalized_by_are_real_patterns(idx):
    for pid, p in idx["principles"].items():
        for pat in p["operationalized_by"]:
            assert pat in idx["patterns"], f"{pid} operationalized_by unknown pattern {pat!r}"


def test_seen_in_are_real_cards(idx):
    for pid, p in idx["principles"].items():
        for e in p["evidence"]:
            if e.get("seen_in"):
                assert e["seen_in"] in idx["cards"], f"{pid} evidence seen_in unknown card {e['seen_in']!r}"


def test_every_principle_has_a_cited_source(idx):
    for pid, p in idx["principles"].items():
        assert p["evidence"], f"{pid} has no evidence"
        assert any(e.get("source") for e in p["evidence"]), f"{pid} evidence carries no source citation"


def test_backbone_covers_the_validity_signatures(idx):
    """Robustness: every signature that names a measurement-validity failure must have a principle.
    Only `bottleneck` is allowed to be uncovered — it's operational, not a definition-of-good construct."""
    covered = set()
    for p in idx["principles"].values():
        covered |= set(p["protects_against"])
    operational = {"bottleneck"}
    for s in SIGNATURE_VOCAB - operational:
        assert s in covered, f"signature {s!r} has no principle in the backbone (coverage gap)"


def test_principles_for_lookup(idx):
    assert "construct-validity" in engine.principles_for(idx, "label_leakage")
    assert "external-validity" in engine.principles_for(idx, "sampling_frame")


def test_backwards_surfaces_the_backbone(idx, stubs):
    bw = engine.analyze_backwards(idx, stubs["image_preference"])
    assert bw["principles"], "backwards-from-good should surface the principle backbone"
    for row in bw["principles"]:
        # every cited principle must protect at least one of THIS workflow's applicable signatures
        assert set(row["protects"]) & set(bw["good_means"]), row["id"]
        assert row["name"] and row["tenet"]


def test_spec_threats_cite_the_literature(idx, stubs):
    bw = engine.analyze_backwards(idx, stubs["marketing_copy"])
    cited = [s for s in bw["spec_threats"] if s.get("cite") and s["cite"].get("source")]
    assert cited, "the spec stress-test should cite the principle + paper behind each probe"


def test_declared_signature_routes_its_defense(idx):
    """A customer-declared high-cost signature must enter the risk set and receive its library
    defense even when NO corpus analogue logged it (the retrospective->designer bridge case).
    assumption_laundering has no exemplar card, only the control-attestation pattern + the
    provenance-documentation principle; declaring it must still surface both."""
    from conftest import make_stub
    stub = make_stub(
        goal="Rebuild a completed workflow so an assumed-away control can't recur",
        modality="multimodal", task_structure="demonstration", annotator_structure="expert",
        high_cost_signatures=["assumption_laundering"])
    bw = engine.analyze_backwards(idx, stub)
    assert "assumption_laundering" in bw["good_means"], "declared signature dropped from the risk set"
    assert any(n["for"] == "assumption_laundering" and n["id"] == "control-attestation"
               for n in bw["needed_patterns"]), "control-attestation not routed for the declared signature"
    assert "provenance-documentation" in {row["id"] for row in bw["principles"]}, \
        "provenance-documentation principle should surface for assumption_laundering"
