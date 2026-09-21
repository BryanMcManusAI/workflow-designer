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
    ap.add_argument("--seed", type=int, default=22)
    a = ap.parse_args()

    idx = engine.load_index()
    stub = engine.load_stub(a.stub)
    inter = engine.analyze_interrogate(idx, stub)
    order = []
    for r in inter["open"]:
        for p in r["patterns"]:
            if p["id"] not in order:
                order.append(p["id"])
    pick = next((p for p in order if p in REALIZABLE), None)
    print(f"  the engine's ranked patterns: {', '.join(order[:8])}")
    print(f"  its top REALIZABLE pick: {pick}")
    if pick is None:
        raise SystemExit("  nothing the engine recommends can be realized by subsampling.")
    if pick != "human-audit-sample":
        print(f"  NOTE: this file only realizes human-audit-sample; {pick} needs its own arm.")

    D = json.load(open(a.pool))
    raters = sorted({r for it in D["items"] for r in it["passes"]})
    items = [it for it in D["items"] if len(it["passes"]) == len(raters)]
    rng = random.Random(a.seed)
    audit = set(rng.sample([it["id"] for it in items], int(a.audit_frac * len(items))))

    pa, spend = {}, 0
    for it in items:
        sel = rng.sample(raters, a.base)
        if it["id"] in audit:
            sel += [r for r in rng.sample(raters, a.audit_extra) if r not in sel]
        pa[it["id"]] = {r: it["passes"][r] for r in sel}
        spend += len(sel)
    base, extra = divmod(spend, len(items))
    bump = set(rng.sample([it["id"] for it in items], extra))
    pb = {it["id"]: {r: it["passes"][r] for r in
                     rng.sample(raters, min(base + (1 if it["id"] in bump else 0), len(raters)))}
          for it in items}

    os.makedirs(a.out, exist_ok=True)
    ctx = [k for k in items[0] if k not in ("id", "passes", "when")]
    for nm, p in (("arm_a_" + pick.replace("-", "_"), pa), ("arm_b_flat", pb)):
        out = {"items": [{"id": it["id"], "passes": p[it["id"]],
                          **{k: it[k] for k in ctx}} for it in items],
               "source": f"{D.get('source','')} | {nm} | engine-recommended arm vs path not taken",
               "task": D.get("task", {"kind": "value", "ordinal": True, "tolerance": 1.0,
                                      "span_labels": []})}
        with open(os.path.join(a.out, nm + ".json"), "w") as f:
            json.dump(out, f)
        print(f"  wrote {nm}.json  ({sum(len(x['passes']) for x in out['items']):,} passes)")

    print("\n  then, per arm, judgelab delivers the verdict:")
    print("    python3 -m judgelab.agreement queue   ARM.json --shape json --pages P.json --key K.json")
    print("    python3 -m judgelab.agreement answer  --pages P.json --key K.json --majority 3 --out A.csv")
    print("    python3 -m judgelab.agreement record  --pages P.json --key K.json --answers A.csv --out R.json")
    print("    python3 -m judgelab.agreement release ARM.json --shape json --pages P.json --key K.json \\")
    print("                --answers A.csv --name ARM --check 'DIFFERENT_VALUE: value >= 2' --out REL.json")
    print("  the verdict: does the release EARN AUTHORITY, and what does it do to the human load?")


if __name__ == "__main__":
    main()
