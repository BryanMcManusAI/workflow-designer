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
