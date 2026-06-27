#!/usr/bin/env python3
"""Topical (semantic) retrieval — what makes the free-text `goal` finally drive the match.

The structural engine (engine.near_analogues) matches on the four controlled-vocab axes only, so it
can't tell that a toxicity-moderation workflow and an NLI workflow — both text/classification — are
about different SUBJECTS. The `goal` prose was dead weight. This module fixes that in two tiers, both
ADDITIVE (engine.py and its goldens are untouched; this is opt-in):

  TIER 1 — deterministic, always available, no key, no network.
    A stdlib token-IDF overlap between the stub's `goal` and each card's text (title + decision +
    distinctive + failure-mode descriptions). Rare shared terms ("toxic", "adjudication") score
    higher than common ones. This alone resolves the topical-mismatch ceiling Bryan punted as
    "out of scope", and it runs with zero dependencies.

  TIER 2 — optional LLM rerank (claude-opus-4-8 via llm.py), used only when a key is present.
    Asks the model to score each candidate card's topical relevance to the goal with a one-line
    reason. Strictly improves Tier 1; never replaces the grounding. Falls back to Tier 1 on any
    failure, so behavior degrades gracefully.

Either way the RESULT is a reordering of real corpus cards — every suggestion still traces to a card,
so the no-counterfeit guarantee holds. The LLM ranks; engine.py still assembles and cites.
"""
try:
    from . import llm, engine
except ImportError:  # run as a plain script, not a package
    import llm
    import engine

# The topical primitives now live in engine.py (near_analogues uses them as a primary signal); reuse
# them here so the Tier-1 ranking and the engine's hybrid retrieval share one source of truth.
topical_scores = engine.topical_scores
tokens = engine.topical_tokens


def _llm_rerank(idx, goal, candidate_ids):
    """Tier-2: ask claude-opus-4-8 to score each candidate's topical relevance to the goal.
    Returns {cid: {"score": int, "why": str}} or None if the LLM is unavailable / failed."""
    cards = "\n".join(
        f"- {cid}: {idx['cards'][cid].get('title','')} "
        f"[{idx['cards'][cid]['modality']}/{idx['cards'][cid]['task_structure']}] "
        f"{idx['cards'][cid].get('decision','')[:200]}"
        for cid in candidate_ids)
    schema = {
        "type": "object", "additionalProperties": False, "required": ["rankings"],
        "properties": {"rankings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "score", "why"],
            "properties": {
                "id": {"type": "string"},
                "score": {"type": "integer"},
                "why": {"type": "string"},
            }}}},
    }
    system = (
        "You rank prior ML-data-workflow recipes by how TOPICALLY analogous they are to a new "
        "workflow a designer described — same subject matter / domain / kind of data, not just the "
        "same structural axes. Score 0-100 (100 = same subject). Be terse in `why` (one clause). "
        "Only use ids from the candidate list.")
    user = f"NEW WORKFLOW GOAL:\n{goal}\n\nCANDIDATE PRIOR RECIPES:\n{cards}"
    out = llm.json_complete(system, user, schema, max_tokens=2048)
    if not out or "rankings" not in out:
        return None
    valid = set(candidate_ids)
    return {r["id"]: {"score": int(r["score"]), "why": (r.get("why") or "").strip()}
            for r in out["rankings"] if r.get("id") in valid}


def analyze_semantic(idx, stub, use_llm=True, top=8):
    """Topical ranking of the corpus for the stub's goal. Tier 2 (LLM) when use_llm and a key are
    available, else Tier 1 (deterministic). Always returns ranked real cards + which tier ran."""
    goal = stub.get("goal", "")
    base = topical_scores(idx, goal)
    # Candidates = anything with topical overlap, plus the structural near set (so a same-axes card
    # with no shared words still gets considered). Cap before any LLM call to keep it cheap.
    try:
        from . import engine
    except ImportError:
        import engine
    near_ids = [cid for _, cid in engine.near_analogues(idx, stub, n=8)]
    cand = list(dict.fromkeys([cid for cid, _ in sorted(
        base.items(), key=lambda kv: -kv[1][0])] + near_ids))[:16]

    tier, llm_scores = "topical (deterministic)", None
    # Only spend an LLM call when there's a real goal AND candidates to rerank (an empty/garbage stub
    # shouldn't burn a call).
    if use_llm and cand and goal.strip() and llm.available():
        llm_scores = _llm_rerank(idx, goal, cand)
        if llm_scores:
            tier = "llm (claude-opus-4-8)"

    rows = []
    for cid in cand:
        c = idx["cards"][cid]
        row = {"id": cid, "title": c.get("title", ""),
               "modality": c["modality"], "task": c["task_structure"],
               "topical": base.get(cid, (0.0, []))[0],
               "shared_terms": base.get(cid, (0.0, []))[1]}
        if llm_scores and cid in llm_scores:
            row["llm_score"], row["why"] = llm_scores[cid]["score"], llm_scores[cid]["why"]
        rows.append(row)

    key = ((lambda r: (-r.get("llm_score", -1), -r["topical"])) if llm_scores
           else (lambda r: -r["topical"]))
    rows.sort(key=key)
    return {"goal": goal, "tier": tier, "ranked": rows[:top]}


def render_semantic(res):
    print(f"\n>>> SEMANTIC retrieval — ranked by topical relevance to the goal")
    print(f"    goal: {res['goal']}")
    print(f"    tier: {res['tier']}\n")
    for i, r in enumerate(res["ranked"], 1):
        score = (f"llm {r['llm_score']:>3}" if "llm_score" in r else f"idf {r['topical']:.2f}")
        print(f"  {i:>2}. [{score}] {r['id']}  ({r['modality']}/{r['task']})")
        if r.get("why"):
            print(f"        {r['why']}")
        elif r["shared_terms"]:
            print(f"        shares: {', '.join(r['shared_terms'])}")
