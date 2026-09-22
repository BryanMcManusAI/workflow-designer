#!/usr/bin/env python3
"""Piece 6: A/B what the ENGINE recommends, and let judgelab deliver the verdict.

Every earlier row picked its pattern by hand off the realizable list, so they tested PATTERNS. This
one asks the engine what to adopt for a stub, realizes its top realizable pick against the path not
taken at identical budget, and hands both to judgelab. The engine is in the loop and the verdict is
judgelab's gate, not this file's arithmetic. That is what the six-piece design was for.

  1. engine.analyze_interrogate(stub) -> its ranked patterns (the SUGGESTION)
  2. realize the top realizable pick as arm A; the same budget spread evenly as arm B
  3. judgelab: read -> queue -> answer --majority 3 -> record -> release
  4. the verdict is whether the release EARNS AUTHORITY, and what it does to the human load

Only 10 of the 25 patterns can be realized by subsampling a crossed pool at all (aggregation,
overlap, routing, adjudication). The engine's true top pick is often outside that set — for the
DICES stub it is `engagement-gate`, which no resampling can touch — so this tests the engine on its
most measurable quarter, never on the whole recommendation.

⚠️ THE STUB MUST BE FILLED IN, AND THE FIRST RUNS OF THIS FILE WERE NOT. The engine reads fifteen
fields — goal, domain, modality, task_structure, annotator_structure, qa_mechanism, uses_patterns,
addressed_signatures, failure_signatures, high_cost_signatures, tolerable_signatures, downstream,
edge_case_mode, process_mode, observed_failures. The stubs used on 2026-09-21 carried four. That is
not a thin version of the tool's advice, it is a different one:

  - `high_cost_signatures` and `downstream` feed signature_priority, so with both empty the COST half
    of the ranking is inert and every signature carries its default severity.
  - `uses_patterns` and `addressed_signatures` feed defended(), so with both empty the engine
    believes the workflow has no QA at all — while the pool it is being tested on runs a seven-rater
    panel.

Filled to nine fields, the CrowdGleason stub's advice changes: drift goes from third at lift 2.0 to
first at 4.0, inflation appears at 2.86 where it was absent, class_imbalance drops a place but rises
to high severity, and unanchored and under_specification are struck as already covered. The top
realizable pick happens to survive, so the arms those runs built still stand — but nothing about the
QUALITY of the tool's advice should be read off a four-field stub.

The deeper version: this tool is a guided traversal that elicits those fifteen answers one decision
at a time. Calling analyze_interrogate on a YAML file is its batch-mode shadow, and that is what
every harness in this directory drives. A judgement about the partner is not available from here.

⚠️ THE LOOP NEVER TESTS THE ADVICE ON ITS OWN TERMS, and no substrate to hand can fix it. The engine
names a RISK and recommends a pattern FOR THAT RISK. This file then measures the pattern's effect on
overall human load and shipped error, which is a different question. For the filled Gleason stub the
engine's first risk is `drift` at lift 4.0 and gold-honeypots is recommended against drift — and:

  CrowdGleason   key YES, clock NO    outcome measurable, drift is not
  DICES-350      key NO,  clock YES   drift visible, nothing to score it against

So the pattern is validated generically and never against the failure the advice actually named. A
signature-matched check needs one pool with both a clock and an independent key, and neither of
these has both.

  python3 eval/close_the_loop.py --pool <crossed>.json --stub <stub>.yaml --out <dir>
  then the printed judgelab chain.
"""
import argparse, json, os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
import engine  # noqa: E402

REALIZABLE = {"multi-annotator-aggregate", "tiered-adjudication", "inter-annotator-agreement",
              "gold-honeypots", "qualification-calibration", "human-audit-sample",
              "human-gold-anchor", "coverage-routing", "powered-eval-split", "split-isolation"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True)
    ap.add_argument("--stub", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", type=int, default=3, help="passes on every item")
    ap.add_argument("--audit-frac", type=float, default=0.30)
    ap.add_argument("--audit-extra", type=int, default=2)
    ap.add_argument("--honeypots", type=int, default=40)
    ap.add_argument("--drop", type=int, default=2)
    ap.add_argument("--seed", type=int, default=22)
    a = ap.parse_args()

    idx = engine.load_index()
    stub = engine.load_stub(a.stub)
    inter = engine.analyze_interrogate(idx, stub)
    def ranked(rows):
        out = []
        for r in rows:
            for p in r["patterns"]:
                if p["id"] not in out:
                    out.append(p["id"])
        return out

    order = ranked(inter["open"])
    # Take the first pattern the engine can STAND BEHIND. A row it marks `unproven` has declared
    # defenders and not one with a record the corpus supports, so recommending from it is offering
    # an untested option with the confidence of a tested one.
    proven = ranked([r for r in inter["open"] if not r.get("unproven")])
    pick = next((p for p in proven if p in REALIZABLE), None)
    naive = next((p for p in order if p in REALIZABLE), None)
    print(f"  the engine's ranked patterns: {', '.join(order[:8])}")
    print(f"  unproven rows skipped: "
          f"{', '.join(r['signature'] for r in inter['open'] if r.get('unproven')) or '(none)'}")
    print(f"  top realizable pick ignoring proof: {naive}")
    print(f"  TOP REALIZABLE PICK IT CAN STAND BEHIND: {pick}")
    if pick is None:
        raise SystemExit("  nothing the engine recommends can be realized by subsampling.")
    if pick not in ("human-audit-sample", "gold-honeypots"):
        raise SystemExit(f"  this file realizes human-audit-sample and gold-honeypots; "
                         f"{pick} needs its own arm.")

    D = json.load(open(a.pool))
    raters = sorted({r for it in D["items"] for r in it["passes"]})
    items = [it for it in D["items"] if len(it["passes"]) == len(raters)]
    rng = random.Random(a.seed)

    # Each arm realizes the pattern it is NAMED for. An earlier version named the arm after the
    # engine's pick and then built an audit sample regardless, which would have tested the wrong
    # design under the right label.
    if pick == "human-audit-sample":
        audit = set(rng.sample([it["id"] for it in items], int(a.audit_frac * len(items))))
        live, pa, spend = items, {}, 0
        for it in items:
            sel = rng.sample(raters, a.base)
            if it["id"] in audit:
                sel += [r for r in rng.sample(raters, a.audit_extra) if r not in sel]
            pa[it["id"]] = {r: it["passes"][r] for r in sel}
            spend += len(sel)
    else:  # gold-honeypots: pay to screen raters on a reserved bank, then collect from survivors.
        bank = set(rng.sample([it["id"] for it in items], a.honeypots))
        ans = {it["id"]: max(set(it["passes"].values()), key=list(it["passes"].values()).count)
               for it in items if it["id"] in bank}
        # The bank's answers are the pool's own consensus, never any held-out key.
        hp = {r: sum(1 for it in items if it["id"] in bank and it["passes"][r] == ans[it["id"]])
              for r in raters}
        kept = sorted(raters, key=lambda r: (-hp[r], r))[:len(raters) - a.drop]
        print(f"  screened {len(raters)} raters on {a.honeypots} bank items, kept {len(kept)}: "
              f"{', '.join(kept)}")
        live = [it for it in items if it["id"] not in bank]
        pa, spend = {}, len(raters) * a.honeypots
        for it in live:
            sel = rng.sample(kept, a.base)
            pa[it["id"]] = {r: it["passes"][r] for r in sel}
            spend += len(sel)

    base, extra = divmod(spend, len(live))
    bump = set(rng.sample([it["id"] for it in live], extra))
    pb = {it["id"]: {r: it["passes"][r] for r in
                     rng.sample(raters, min(base + (1 if it["id"] in bump else 0), len(raters)))}
          for it in live}

    os.makedirs(a.out, exist_ok=True)
    ctx = [k for k in items[0] if k not in ("id", "passes", "when")]
    for nm, p in (("arm_a_" + pick.replace("-", "_"), pa), ("arm_b_flat", pb)):
        out = {"items": [{"id": it["id"], "passes": p[it["id"]],
                          **{k: it[k] for k in ctx}} for it in live],
               "source": f"{D.get('source','')} | {nm} | engine-recommended arm vs path not taken",
               "task": D.get("task", {"kind": "value", "ordinal": True, "tolerance": 1.0,
                                      "span_labels": []})}
        with open(os.path.join(a.out, nm + ".json"), "w") as f:
            json.dump(out, f)
        collected = sum(len(x["passes"]) for x in out["items"])
        screen = spend - collected if nm.startswith("arm_a") else 0
        note = f" + {screen:,} screening" if screen else ""
        print(f"  wrote {nm}.json  ({collected:,} collected{note} = {collected + screen:,} total)")

    print("\n  then, per arm, judgelab delivers the verdict:")
    print("    python3 -m judgelab.agreement queue   ARM.json --shape json --pages P.json --key K.json")
    print("    python3 -m judgelab.agreement answer  --pages P.json --key K.json --majority 3 --out A.csv")
    print("    python3 -m judgelab.agreement record  --pages P.json --key K.json --answers A.csv --out R.json")
    print("    python3 -m judgelab.agreement release ARM.json --shape json --pages P.json --key K.json \\")
    print("                --answers A.csv --name ARM --check 'DIFFERENT_VALUE: value >= 2' --out REL.json")
    print("  the verdict: does the release EARN AUTHORITY, and what does it do to the human load?")


if __name__ == "__main__":
    main()
