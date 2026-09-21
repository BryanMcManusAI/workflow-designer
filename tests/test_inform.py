"""The informer (advisory front door). Invariants: it reuses the engine's passes (no second source of
truth), every brief item is load-bearing (check/defense/story present), and its war stories diversify
across principles instead of citing one card three times."""
import inform


CUSTOMER = {"goal": "Collect human ratings of AI-generated product descriptions to fine-tune our generation model",
            "modality": "text", "task_structure": "rubric_rating", "annotator_structure": "crowd",
            "qa_mechanism": [], "uses_patterns": [], "addressed_signatures": []}


def test_brief_structure(idx):
    res = inform.analyze_inform(idx, dict(CUSTOMER))
    assert res["principles"], "brief must lead with the backbone"
    for p in res["principles"]:
        assert p["name"] and p["tenet"] and p["check"], "every principle must carry a runnable check"
        if not p["secured"]:
            assert p["defense"], "every open principle must offer one concrete defense"
    assert res["spec_threats"], "the is-your-good-good stress test is the informer's signature"
    assert res["priorities"], "the cost-ranked defend-hardest list must be present"


def test_war_stories_diversify(idx):
    res = inform.analyze_inform(idx, dict(CUSTOMER))
    cards = [p["war_story"]["card"] for p in res["principles"] if p["war_story"]]
    assert len(set(cards)) >= min(3, len(cards)), f"war stories too repetitive: {cards}"


def test_render_is_customer_facing(idx):
    md = inform.render_inform_md(inform.analyze_inform(idx, dict(CUSTOMER)))
    assert "Good Data Brief" in md and "five-minute check" in md
    assert "the designer assembles it" in md, "the brief must end with the designer funnel"
    assert "uses_patterns" not in md, "no internal vocabulary in a customer artifact"


def test_adopted_defenses_show_secured(idx):
    stub = dict(CUSTOMER, uses_patterns=["human-gold-anchor", "cross-family-judges",
                                         "order-randomization", "partial-input-baseline"])
    res = inform.analyze_inform(idx, stub)
    assert any(p["secured"] for p in res["principles"]), \
        "adopting the defenses must flip principles to secured (the brief reacts to the plan)"


# ---- the good-data questionnaire hooks: every answer must CHANGE the output (load-bearing) ----

def test_edge_case_answer_flips_the_ambiguity_defense(idx):
    import engine
    def defense(mode):
        bw = engine.analyze_backwards(idx, dict(CUSTOMER, edge_case_mode=mode))
        return next((p["id"] for p in bw["needed_patterns"] if p["for"] == "under_specification"), None)
    assert defense("escalate") == "tiered-adjudication"
    assert defense("rule") == "edge-case-guidelines"


def test_downstream_answer_reweights_priorities(idx):
    import engine
    def first(ds):
        return engine.analyze_backwards(idx, dict(CUSTOMER, downstream=ds))["guarantees"][0]["signature"]
    assert first("training") == "sampling_frame"    # training data dies on coverage
    assert first("evaluation") == "unanchored"      # eval data dies on contamination / no anchor


def test_stake_extraction():
    assert inform._stake("hypothesis-only reaches ~67% (SNLI) vs 33% chance").startswith("hypothesis")
    # a later decimal must not truncate the clause
    assert inform._stake("a GPT-4o judge showed +0.74 self-affinity; a Claude judge ran -0.26") \
        == "a GPT-4o judge showed +0.74 self-affinity"
    assert "threefold" in inform._stake("dropped resolution roughly threefold after decontamination")
    assert inform._stake("raters prefer the longer response regardless of substance") is None


def test_brief_leads_with_a_documented_number(idx):
    """Concrete stakes: at least one principle's war story should carry a real magnitude, and the
    numbers are never fabricated — every stake is a substring of the real card description."""
    res = inform.analyze_inform(idx, dict(CUSTOMER))
    staked = [p for p in res["principles"] if p["war_story"] and p["war_story"].get("stake")]
    assert staked, "the corpus has quantified failures; the brief should surface at least one"
    for p in staked:
        assert p["war_story"]["stake"] in p["war_story"]["desc"], "stake must be real, not synthesized"
    assert "What it cost, documented" in inform.render_inform_md(res)


def test_support_signal_is_honest(idx):
    strong = inform.analyze_inform(idx, dict(CUSTOMER))["support"]          # rubric_rating / text
    assert strong["level"] == "strong"
    cross_modality = inform.analyze_inform(idx, dict(CUSTOMER, modality="audio"))["support"]
    assert cross_modality["level"] == "moderate" and cross_modality["note"]
    novel = inform.analyze_inform(idx, dict(CUSTOMER, task_structure="unheard_of_task"))["support"]
    assert novel["level"] == "weak" and "directional" in novel["note"]
    # the caveat renders for non-strong support, and is absent when support is strong
    assert "How far to trust" in inform.render_inform_md(inform.analyze_inform(idx, dict(CUSTOMER, modality="audio")))
    assert "How far to trust" not in inform.render_inform_md(inform.analyze_inform(idx, dict(CUSTOMER)))


def test_probes_are_real_and_reactive(idx):
    """The Calibrate step's elicitation ladder: probes are real corpus failures, they skip what the
    customer already answered, and a reaction changes the brief (nothing decorative)."""
    res = inform.analyze_probes(idx, dict(CUSTOMER))
    assert res["failure_probes"], "an unanswered stub must yield failure probes"
    sigs = [p["signature"] for p in res["failure_probes"]]
    assert len(set(sigs)) == len(sigs), "one probe per signature"
    for p in res["failure_probes"]:
        assert p["card"] in idx["cards"] and p["story"], "every probe is a real corpus case"
    assert res["edge_options"] and len(res["edge_options"]) == 3
    assert res["mirror"] and res["mirror"]["frame"]

    # answering removes the probe (the ladder only offers open rungs)…
    first = sigs[0]
    res2 = inform.analyze_probes(idx, dict(CUSTOMER, high_cost_signatures=[first]))
    assert first not in [p["signature"] for p in res2["failure_probes"]]
    res3 = inform.analyze_probes(idx, dict(CUSTOMER, edge_case_mode="rule"))
    assert res3["edge_options"] is None

    # …and the reaction genuinely reorders the brief's priorities.
    base_first = inform.analyze_inform(idx, dict(CUSTOMER))["priorities"][0]["signature"]
    probe_sig = next(s for s in sigs if s != base_first)
    bumped = inform.analyze_inform(idx, dict(CUSTOMER, high_cost_signatures=[probe_sig]))
    assert bumped["priorities"][0]["signature"] == probe_sig, \
        "marking a probed failure costly must move it to defend-first"


def test_brief_carries_the_questionnaire_outputs(idx):
    stub = dict(CUSTOMER, edge_case_mode="signal", downstream="evaluation", process_mode="strict")
    res = inform.analyze_inform(idx, stub)
    mm = res["mental_model"]
    import engine as eng
    assert mm and mm["frame"], "reviewer mental model must be present"
    assert idx["cards"][mm["card"]]["task_structure"] == "rubric_rating", \
        "the mental-model precedent must share the task shape (the frame lives on aptness)"
    assert any("ambiguous" in g for g in res["guidelines"]), "edge answer becomes a decision guideline"
    assert res["conventions"] and len(res["conventions"]) <= 6, "condensed conventions, not a catalog"
    md = inform.render_inform_md(res)
    assert "Decision guidelines" in md and "Starter conventions" in md and "think about this task" in md


# ---- the retrospective bridge: observed failures make the brief personal ----
# A retrospective diagnosis arrives as observed_failures — the customer's own documented
# incidents. Contract: they fold into high-cost (defend-first), the
# brief cites the customer's own case above any corpus example, and an absent/empty field
# changes nothing.

OBSERVED = [
    {"signature": "drift",
     "description": "acceptance bar moved mid-campaign; 24% of Q3 defects predate the guideline change",
     "source": "retrospective:catalog_enrichment_q3_2025 (Q3 2025)"},
    {"signature": "under_specification",
     "description": "annotators disagreed on brand attribution for 412 records (49% of defects)",
     "source": "retrospective:catalog_enrichment_q3_2025 (Q3 2025)"},
]


def test_observed_failures_fold_into_high_cost(idx):
    res = inform.analyze_inform(idx, dict(CUSTOMER, observed_failures=[dict(o) for o in OBSERVED]))
    assert len(res["observed"]) == 2
    # semantics: observed signatures behave exactly as if the customer declared them high-cost
    manual = inform.analyze_inform(idx, dict(CUSTOMER,
                                             high_cost_signatures=["drift", "under_specification"]))
    assert [p["signature"] for p in res["priorities"]] == \
           [p["signature"] for p in manual["priorities"]], \
        "observed failures must reprioritize like declared high-cost signatures"


def test_observed_story_cited_above_corpus(idx):
    res = inform.analyze_inform(idx, dict(CUSTOMER, observed_failures=[dict(o) for o in OBSERVED]))
    own = [p for p in res["principles"] if p.get("own_story")]
    assert own, "a principle protecting an observed signature must cite the customer's own case"
    for p in own:
        assert p["own_story"]["description"]
        assert p["own_story"]["source"].startswith("retrospective:")
    assert any(p["own_story"].get("stake") for p in own), \
        "stake extraction must work on the customer's own words too"
    md = inform.render_inform_md(res)
    assert "This already happened in your workflow" in md
    assert "Grounded in your own history" in md


def test_json_stub_round_trip(tmp_path, idx):
    import json
    import engine
    stub_path = tmp_path / "bridged_stub.json"
    stub_path.write_text(json.dumps(dict(
        CUSTOMER, observed_failures=OBSERVED, high_cost_signatures="drift")))
    stub = engine.load_stub(str(stub_path))
    assert stub["observed_failures"][0]["signature"] == "drift", \
        "structured fields must survive a JSON stub"
    assert stub["high_cost_signatures"] == ["drift"], "list normalization applies to JSON stubs too"
    assert inform.analyze_inform(idx, stub)["observed"]


def test_absent_observed_changes_nothing(idx):
    a = inform.analyze_inform(idx, dict(CUSTOMER))
    b = inform.analyze_inform(idx, dict(CUSTOMER, observed_failures=[]))
    assert a == b, "an empty bridge field must be a no-op (existing briefs unchanged)"
