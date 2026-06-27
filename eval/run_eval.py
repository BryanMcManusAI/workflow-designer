#!/usr/bin/env python3
"""Evaluate the engine's RECOMMENDATIONS against the gold set — the missing piece for a tool built by
an evals person: not "does the code run" (the pytest suite) but "is the advice any good".

Two things are scored per gold item, against INDEPENDENT expert labels (eval/gold.yaml):
  RETRIEVAL — do the engine's surfaced analogues include the cards a human judged relevant?
              measured separately for the STRUCTURAL channel (axis-match near-analogues) and the
              SEMANTIC channel (goal-text topical ranking), so we can see whether semantic actually
              helps — recall@k.
  RISK      — does interrogate/backwards name the failure signatures that genuinely apply? recall.

Honest framing: the scores are only as good as the gold, which is DRAFT (audit-pending). Read them as
a diagnostic of where the engine is weak, not a leaderboard number. Stdlib + PyYAML (dev-time) to load
gold; the scoring core takes plain dicts so it's unit-testable without YAML.
"""
import argparse
import os
import statistics

import engine
import semantic

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "gold.yaml")


def _stub(item):
    return {"goal": item["goal"], "modality": item["modality"],
            "task_structure": item["task_structure"],
            "annotator_structure": item["annotator_structure"],
            "qa_mechanism": [], "uses_patterns": [], "addressed_signatures": []}


def _recall(found, expected):
    expected = set(expected)
    return (len(expected & set(found)) / len(expected)) if expected else 1.0


def score_item(idx, item, k=5, use_llm=False):
    stub = _stub(item)
    relevant = set(item["relevant_cards"])

    near = [cid for _, cid in engine.near_analogues(idx, stub, n=k)]
    sem = [r["id"] for r in semantic.analyze_semantic(idx, stub, use_llm=False, top=k)["ranked"]]
    combined = list(dict.fromkeys(near + sem))[:k]

    llm_recall = None
    if use_llm:
        res = semantic.analyze_semantic(idx, stub, use_llm=True, top=k)
        # only counts as an LLM result if the rerank actually ran (else it's Tier-1 and == sem)
        llm_ids = [r["id"] for r in res["ranked"]]
        llm_recall = _recall(llm_ids, relevant) if res["tier"].startswith("llm") else None

    # Risk channel: what the engine flags as applicable / open.
    inter = engine.analyze_interrogate(idx, stub)
    flagged_risks = {r["signature"] for r in inter["open"]} | set(inter["defended"])
    flagged_risks |= set(engine.analyze_backwards(idx, stub)["good_means"])

    return {
        "id": item["id"],
        "recall_structural": _recall(near, relevant),
        "recall_semantic": _recall(sem, relevant),
        "recall_combined": _recall(combined, relevant),
        "recall_llm": llm_recall,
        "missed_cards": sorted(relevant - set(combined)),
        "risk_recall": _recall(flagged_risks, item["expected_risks"]),
        "missed_risks": sorted(set(item["expected_risks"]) - flagged_risks),
    }


def run(idx, items, k=5, use_llm=False):
    rows = [score_item(idx, it, k, use_llm) for it in items]
    metrics = ["recall_structural", "recall_semantic", "recall_combined", "risk_recall"]
    agg = {m: statistics.mean(r[m] for r in rows) for m in metrics}
    llm_vals = [r["recall_llm"] for r in rows if r["recall_llm"] is not None]
    if llm_vals:
        agg["recall_llm"] = statistics.mean(llm_vals)
    return {"rows": rows, "aggregate": agg, "k": k, "n": len(rows), "llm_n": len(llm_vals)}


def render(res):
    print(f"ENGINE RECOMMENDATION EVAL  (n={res['n']}, k={res['k']}, gold = DRAFT/audit-pending)")
    print("-" * 78)
    has_llm = "recall_llm" in res["aggregate"]
    llm_h = f"{'llm':>7}" if has_llm else ""
    print(f"  {'item':<22} {'near':>7} {'seman':>7} {'comb':>7}{llm_h} {'risk':>7}   misses")
    for r in res["rows"]:
        miss = []
        if r["missed_cards"]:
            miss.append("cards:" + ",".join(r["missed_cards"]))
        if r["missed_risks"]:
            miss.append("risks:" + ",".join(r["missed_risks"]))
        llm_c = (f"{r['recall_llm']:>7.2f}" if r.get("recall_llm") is not None else f"{'—':>7}") if has_llm else ""
        print(f"  {r['id']:<22} {r['recall_structural']:>7.2f} {r['recall_semantic']:>7.2f} "
              f"{r['recall_combined']:>7.2f}{llm_c} {r['risk_recall']:>7.2f}   {'; '.join(miss)}")
    a = res["aggregate"]
    print("-" * 78)
    llm_m = f"{a['recall_llm']:>7.2f}" if has_llm else ""
    print(f"  {'MEAN recall':<22} {a['recall_structural']:>7.2f} {a['recall_semantic']:>7.2f} "
          f"{a['recall_combined']:>7.2f}{llm_m} {a['risk_recall']:>7.2f}")
    print("\n  near = hybrid axis+goal-topical · seman = pure goal-topical · comb = top-k union"
          + (" · llm = Tier-2 rerank" if has_llm else "") + " · risk = signatures flagged")


def load_gold(path=GOLD):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)["items"]


def main():
    ap = argparse.ArgumentParser(description="Evaluate engine recommendations against the gold set.")
    ap.add_argument("--k", type=int, default=5, help="top-k retrieved cards to score recall at")
    ap.add_argument("--llm", action="store_true", help="also score the Tier-2 LLM rerank channel (needs a key)")
    args = ap.parse_args()
    render(run(engine.load_index(), load_gold(), k=args.k, use_llm=args.llm))


if __name__ == "__main__":
    main()
