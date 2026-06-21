"""Invariants on the engine's analyze_* functions — properties that must hold across scoring
tweaks, so Phase-2 intelligence changes can't silently break the contract the UIs rely on.
"""
import pytest

from conftest import REPRESENTATIVE_STUBS, SIGNATURE_VOCAB, make_stub

ALL_STUBS = list(REPRESENTATIVE_STUBS.items())


def _pattern_ids(idx):
    return set(idx["patterns"].keys())


def _card_ids(idx):
    return set(idx["cards"].keys())


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_interrogate_invariants(eng, idx, name, stub):
    res = eng.analyze_interrogate(idx, stub)
    pids = _pattern_ids(idx)
    open_sigs = {r["signature"] for r in res["open"]}

    # A defended signature is never re-asked as an open risk.
    assert open_sigs.isdisjoint(set(res["defended"])), name

    for r in res["open"]:
        # Every cited pattern is real and actually defends the signature it's offered for.
        for p in r["patterns"]:
            assert p["id"] in pids, (name, p["id"])
            assert r["signature"] in idx["patterns"][p["id"]]["defends"], (name, r["signature"])
        # unguarded <=> no defending pattern.
        assert r["unguarded"] == (len(r["patterns"]) == 0), (name, r["signature"])
        # The example card (when present) really exhibits the signature.
        ex = r["example"]
        if ex["card"]:
            assert r["signature"] in idx["cards"][ex["card"]]["failure_signatures"], name


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_backwards_invariants(eng, idx, name, stub):
    res = eng.analyze_backwards(idx, stub)
    pids = _pattern_ids(idx)

    # The build list is deduped, names one defense per still-open risk, and skips the defended.
    needed_ids = [p["id"] for p in res["needed_patterns"]]
    assert len(needed_ids) == len(set(needed_ids)), name
    for p in res["needed_patterns"]:
        assert p["id"] in pids, (name, p["id"])
        assert p["for"] in {g["signature"] for g in res["guarantees"]}, name
    defended = set(res["already_have"])
    assert {p["for"] for p in res["needed_patterns"]}.isdisjoint(defended), name

    # spec_threats are a subset of what "good" means here.
    assert {s["signature"] for s in res["spec_threats"]}.issubset(set(res["good_means"])), name

    # Every guarantee's patterns are real; defended flag is consistent with already_have.
    for g in res["guarantees"]:
        for p in g["patterns"]:
            assert p["id"] in pids, (name, p["id"])
        assert g["defended"] == (g["signature"] in defended), (name, g["signature"])


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_far_analogues_are_distant(eng, idx, name, stub):
    near, far = eng.analyze_retrieve(idx, stub)
    for r in far:
        c = idx["cards"][r["id"]]
        # "Far" means it differs on modality OR task — a genuinely distant pull.
        assert (c["modality"] != stub.get("modality")
                or c["task_structure"] != stub.get("task_structure")), (name, r["id"])
        # The shared signatures it's surfaced for really are shared with the stub's risk set.
        assert r["shared"], (name, r["id"])


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_near_analogues_deterministic_and_scored(eng, idx, name, stub):
    near1, _ = eng.analyze_retrieve(idx, stub)
    near2, _ = eng.analyze_retrieve(idx, stub)
    assert [r["id"] for r in near1] == [r["id"] for r in near2], name  # deterministic
    scores = [r["score"] for r in near1]
    assert scores == sorted(scores, reverse=True), name  # ranked best-first
    assert all(s > 0 for s in scores), name
    for r in near1:
        assert r["id"] in idx["cards"], (name, r["id"])


def test_load_stub_parsing(eng, tmp_path):
    p = tmp_path / "stub.yaml"
    p.write_text(
        "goal: Test parsing  # trailing comment\n"
        "modality: text\n"
        "task_structure: classification\n"
        "annotator_structure: crowd\n"
        "qa_mechanism: [agreement, gold_honeypots]\n"
        "uses_patterns: []\n"
        "# a full-line comment\n"
        'addressed_signatures: ["drift"]\n'
    )
    stub = eng.load_stub(str(p))
    assert stub["goal"] == "Test parsing"
    assert stub["modality"] == "text"
    assert stub["qa_mechanism"] == ["agreement", "gold_honeypots"]
    assert stub["uses_patterns"] == []
    assert stub["addressed_signatures"] == ["drift"]
    # The four keys are always lists, even when absent from the file.
    for k in ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures"):
        assert isinstance(stub[k], list), k


def test_severity_defaults_and_overrides(eng, idx):
    assert eng.signature_priority("label_leakage", make_stub()) > eng.signature_priority("priming", make_stub())
    assert eng.severity_label(3) == "high" and eng.severity_label(2) == "med" and eng.severity_label(1) == "low"
    # customer failure-sensitivity moves a signature's cost
    boosted = make_stub(high_cost_signatures=["priming"])
    assert eng.signature_priority("priming", boosted) > eng.signature_priority("priming", make_stub())
    toler = make_stub(tolerable_signatures=["label_leakage"])
    assert eng.signature_priority("label_leakage", toler) < eng.signature_priority("label_leakage", make_stub())


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_build_list_is_cost_ordered(eng, idx, name, stub):
    bw = eng.analyze_backwards(idx, stub)
    sev_rank = {"high": 3, "med": 2, "low": 1}
    scores = [sev_rank[g["severity"]] for g in bw["guarantees"]]
    assert scores == sorted(scores, reverse=True), name  # costliest first
    for p in bw["needed_patterns"]:
        assert p["severity"] in sev_rank, (name, p)
    for r in eng.analyze_interrogate(idx, stub)["open"]:
        assert r["severity"] in sev_rank, name


def test_high_cost_override_reprioritizes(eng, idx):
    # flagging a normally-low-cost risk as high-cost should pull it toward the front of the build list
    base = make_stub(modality="text", task_structure="rubric_rating", annotator_structure="model_as_annotator")
    if "priming" not in eng.analyze_backwards(idx, base)["good_means"]:
        pytest.skip("priming not applicable to this stub")
    boosted = dict(base); boosted["high_cost_signatures"] = ["priming"]
    gm0 = eng.analyze_backwards(idx, base)["good_means"]
    gm1 = eng.analyze_backwards(idx, boosted)["good_means"]
    assert gm1.index("priming") <= gm0.index("priming")


def test_meta_tooling_cards_demoted_in_near(eng, idx):
    # A process/meta card (datasheets-documentation) must not outrank a thematic extraction
    # workflow as the precedent for an extraction task.
    stub = make_stub(modality="text", task_structure="extraction", annotator_structure="expert")
    wf = eng.analyze_workflow(idx, stub)
    assert idx["cards"][wf["precedent"]]["domain"] not in eng.META_TOOLING_DOMAINS, wf["precedent"]
    # but if the stub itself targets meta-tooling, the penalty is dropped
    meta = make_stub(modality="text", task_structure="extraction", annotator_structure="expert")
    meta["domain"] = "meta-tooling"
    near = eng.near_analogues(idx, meta)
    assert any(idx["cards"][c]["domain"] == "meta-tooling" for _, c in near)


def _has_welfare(eng, idx, stub):
    return "annotator-welfare-protocol" in [p["id"] for p in eng.analyze_workflow(idx, stub)["conventions"]]


def test_precedent_prefers_shared_modality(eng, idx):
    # Audio classification has no exact audio+classification card; the precedent must still be an
    # audio card, not a text card that merely shares the task.
    wf = eng.analyze_workflow(idx, make_stub(modality="audio", task_structure="classification",
                                             annotator_structure="crowd"))
    assert idx["cards"][wf["precedent"]]["modality"] == "audio", wf["precedent"]
    # When a same-modality+task card exists, it's still the precedent.
    wf2 = eng.analyze_workflow(idx, make_stub(modality="image", task_structure="structured_output",
                                              annotator_structure="tiered_review"))
    assert idx["cards"][wf2["precedent"]]["modality"] == "image", wf2["precedent"]


def test_welfare_surfaces_for_harmful_only(eng, idx):
    # by task
    assert _has_welfare(eng, idx, make_stub(modality="text", task_structure="red_team", annotator_structure="crowd"))
    # by goal keyword, even in a modality with no domain-tagged harmful neighbors (video moderation)
    assert _has_welfare(eng, idx, make_stub(goal="Video moderation for policy violations",
                                            modality="video", task_structure="classification", annotator_structure="tiered_review"))
    # harmful work caught even without a keyword neighbor, via more goal words
    assert _has_welfare(eng, idx, make_stub(goal="Flag self-harm posts", modality="text", task_structure="classification", annotator_structure="crowd"))
    assert _has_welfare(eng, idx, make_stub(goal="Review traumatic testimony", modality="text", task_structure="classification", annotator_structure="expert"))
    # benign work doesn't get it — incl. dual-meaning words that must NOT trip it
    for benign in ["Label support tickets by intent", "Pharma trial data extraction",
                   "Rate answers with moderate confidence", "Pet grooming photo classification",
                   "Harmless small-talk quality"]:
        assert not _has_welfare(eng, idx, make_stub(goal=benign, modality="text",
                                                    task_structure="classification", annotator_structure="crowd")), benign


def test_nonhuman_label_step_leads_with_mechanism(eng, idx):
    wf = eng.analyze_workflow(idx, make_stub(modality="tabular", task_structure="classification", annotator_structure="programmatic"))
    label = [s["do"] for s in wf["steps"] if s["phase"] == "Label"][0]
    assert label.startswith("Labeling functions")  # mechanism first, not "Assign each item…"
    assert "Target per item:" in label


def test_stub_warnings(eng, idx):
    assert eng.stub_warnings(idx, make_stub(modality="text", task_structure="classification", annotator_structure="crowd")) == []
    warns = eng.stub_warnings(idx, make_stub(modality="hologram", task_structure="vibes",
                                             annotator_structure="crowd", uses_patterns=["nope"]))
    assert len(warns) == 3


def test_modality_shift_same_modality_is_noop(eng, idx):
    stub = dict(REPRESENTATIVE_STUBS["marketing_copy"])  # modality=text
    res = eng.analyze_modality_shift(idx, stub, "text")
    assert res["same"] is True
    assert res["new_risks"] == [] and res["transplants"] == []
    # a genuine shift still produces change
    other = eng.analyze_modality_shift(idx, stub, "image")
    assert other["same"] is False


def test_flip_same_value_is_noop(eng, idx):
    stub = dict(REPRESENTATIVE_STUBS["image_preference"])  # annotator=crowd
    res = eng.analyze_flip(idx, stub, "annotator_structure", "crowd")
    assert res["same"] is True
    assert res["new_sig"] == [] and res["survive"] == [] and res["at_risk"] == []
    other = eng.analyze_flip(idx, stub, "annotator_structure", "expert")
    assert other["same"] is False


def test_compare_shape(eng, idx):
    res = eng.analyze_compare(idx, "preference_ranking")
    assert not res["few"]
    assert len(res["variants"]) >= 2
    for v in res["variants"]:
        assert v["id"] in idx["cards"]


def test_compare_too_few(eng, idx):
    # critique_rationale has a single card -> the "few" branch.
    res = eng.analyze_compare(idx, "critique_rationale")
    assert res["few"]


def test_cookbook_partitions_every_card(eng, idx):
    for angle in eng.COOKBOOK_ANGLES:
        res = eng.analyze_cookbook(idx, angle)
        total = sum(len(items) for items in res["groups"].values())
        assert total == len(idx["cards"]), angle


def test_vocab_within_known_values(eng, idx):
    v = eng.vocab(idx)
    assert set(v["modality"])
    assert set(v["failure_signature"]).issubset(SIGNATURE_VOCAB), \
        set(v["failure_signature"]) - SIGNATURE_VOCAB


def test_signature_idf_rewards_rarity(eng, idx):
    idf = eng.signature_idf(idx)
    # The near-universal signature must score below a rare one.
    assert idf["under_specification"] < idf["self_affinity"], idf
    assert all(w >= 0 for w in idf.values())


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_coverage_partitions_applicable(eng, idx, name, stub):
    cov = eng.analyze_coverage(idx, stub)
    assert set(cov["covered"]).isdisjoint(set(cov["open"])), name
    assert cov["n_covered"] == len(cov["covered"]), name
    assert cov["n_covered"] + len(cov["open"]) == cov["n_applicable"], name
    assert 0.0 <= cov["pct"] <= 1.0, name


def test_coverage_rises_when_adopting(eng, idx, stubs):
    # Adopting a pattern that defends an open risk must not lower coverage.
    stub = dict(stubs["marketing_copy"])
    before = eng.analyze_coverage(idx, stub)
    open_sig = before["open"][0]
    defenders = eng.patterns_defending(idx, open_sig)
    assert defenders, open_sig
    stub["uses_patterns"] = stub["uses_patterns"] + [defenders[0]]
    after = eng.analyze_coverage(idx, stub)
    assert after["n_covered"] >= before["n_covered"]
    assert open_sig in after["covered"]


def test_conflict_pairs_symmetric_dedup(eng, idx):
    # lock-then-score ⟂ active-learning-loop is the canonical design tension; surface it once.
    pair = ("lock-then-score", "active-learning-loop")
    if "active-learning-loop" in idx["patterns"].get("lock-then-score", {}).get("conflicts_with", []) \
            or "lock-then-score" in idx["patterns"].get("active-learning-loop", {}).get("conflicts_with", []):
        pairs = eng.conflict_pairs(idx, pair, pair)
        assert len(pairs) == 1
        assert set(pairs[0]) == set(pair)
    # No design conflicts when there's nothing to conflict.
    assert eng.conflict_pairs(idx, ["gold-honeypots"], ["gold-honeypots"]) == []


def test_suggested_complements_excludes_adopted(eng, idx):
    comp = eng.suggested_complements(idx, ["multi-annotator-aggregate"])
    ids = {c["id"] for c in comp}
    assert "multi-annotator-aggregate" not in ids
    for c in comp:
        assert c["id"] in idx["patterns"]


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_workflow_is_assembled(eng, idx, name, stub):
    wf = eng.analyze_workflow(idx, stub)
    # Six labeling steps, each with a phase + description.
    assert [s["phase"] for s in wf["steps"]][:1] == ["Source & sample"]
    assert len(wf["steps"]) == 6
    for s in wf["steps"]:
        assert s["phase"] and s["do"]
    # Fields are concrete and non-empty.
    assert wf["fields"]
    # Every play (in steps / conventions / audit) is a chosen, real pattern, tagged have/add.
    chosen = set(wf["chosen"])
    plays = wf["conventions"] + wf["audit"] + [p for s in wf["steps"] for p in s["patterns"]]
    for p in plays:
        assert p["id"] in idx["patterns"], (name, p["id"])
        assert p["id"] in chosen, (name, p["id"])
        assert p["have"] == (p["id"] in wf["adopted"]), (name, p["id"])
    # to_add = chosen minus the starting design; disjoint from adopted.
    assert set(wf["to_add"]).isdisjoint(set(wf["adopted"])), name
    assert set(wf["to_add"]).issubset(chosen), name
    if wf["precedent"]:
        assert wf["precedent"] in idx["cards"], name


def test_workflow_build_list_matches_backwards(eng, idx):
    # The "add" patterns are exactly the backwards-from-good build list (the recipe completes the design).
    stub = dict(REPRESENTATIVE_STUBS["marketing_copy"])
    wf = eng.analyze_workflow(idx, stub)
    needed = [p["id"] for p in eng.analyze_backwards(idx, stub)["needed_patterns"]]
    assert set(wf["to_add"]) == set(needed)


@pytest.mark.parametrize("name,stub", ALL_STUBS)
def test_workflow_grounded_in_inspirations(eng, idx, name, stub):
    wf = eng.analyze_workflow(idx, stub)
    plays = wf["conventions"] + wf["audit"] + [p for s in wf["steps"] for p in s["patterns"]]
    for p in plays:
        # seen_in cards are real
        for cid in p["seen_in"]:
            assert cid in idx["cards"], (name, cid)
        a = p.get("as_done")
        if a:
            # the quoted gate is a REAL gate on a REAL card, and it catches a risk this pattern defends
            assert a["card"] in idx["cards"], (name, a["card"])
            defends = set(idx["patterns"][p["id"]]["defends"])
            gates = idx["cards"][a["card"]]["quality_gates"]
            match = [g for g in gates if g["gate"] == a["gate"]]
            assert match, (name, a["gate"])
            assert set(match[0]["catches"]) & defends, (name, p["id"], a["gate"])


def test_workflow_adopting_moves_add_to_have(eng, idx):
    stub = dict(REPRESENTATIVE_STUBS["marketing_copy"])
    wf = eng.analyze_workflow(idx, stub)
    assert wf["to_add"], "expected an open build list to start"
    pick = wf["to_add"][0]
    stub["uses_patterns"] = stub["uses_patterns"] + [pick]
    wf2 = eng.analyze_workflow(idx, stub)
    assert pick not in wf2["to_add"]
    assert pick in wf2["adopted"]
