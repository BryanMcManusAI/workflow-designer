#!/usr/bin/env python3
"""A/B one workflow-designer pattern against the path not taken, on a REAL crossed rater pool.

The engine can now name the right risks (eval/loo_signatures.py) and attach a defense to them. It
has never been shown that TAKING the defense produces better data than not taking it. This row is
the first half of that test, for one pattern: `tiered-adjudication` — "auto-accept high-agreement
items; escalate only genuine disagreements to a scarce senior adjudicator who sets gold."

NO SIMULATED ANNOTATORS. The substrate is a fully crossed pool of real human ratings (DICES-350 is
350 items x 123 raters = 43,050 real ratings). Because every rater rated every item, a design that
spends ~4 raters per item uses ~3% of the pool, so both arms are real people and hundreds of
independent panels can be drawn for an interval instead of a point.

  TRUTH PANEL      61 raters held out, never drawn by either arm. Their majority is the answer key.
                   A disjoint 61 reproduces the full 123-rater majority on 98.6% of items, so this
                   costs almost nothing in key quality and removes leakage entirely.
  WORKING POOL     the other 62. Both arms draw from here and only here.
  QUALIFICATION    the senior tier is the top --seniors working raters by leave-one-out agreement
                   with the REST OF THE WORKING POOL. The truth panel is never consulted.
  ARM A (tiered)   --tier1 raters per item from the non-senior working raters; unanimous -> accept;
                   split -> escalate to --tier2 seniors whose plurality SETS gold, overriding tier 1.
  ARM B (flat)     no routing: the same total pass budget spread evenly over all items, drawn
                   uniformly from the whole working pool (seniors included — same labour, no tiers).

WHY NOT PLAIN ACCURACY. 88.2% of the truth panel's golds are "No", and a constant that answers "No"
to everything scores 88.2% while a flat 3-rater panel of real humans scores 86.9% — the constant
WINS. Plain accuracy would have shown both arms near 87% and declared no difference while neither
arm beat a constant. This is the same failure the interrogation ranking had against corpus base
rates. The scorers below all have a constant that cannot win, and the constant is printed on every
row so it can never quietly take the lead again.

CHECKS STATED BEFORE THE ROW RAN (thresholds are not moved; a miss is recorded):
  1. HARNESS: the two arms spend an identical number of passes. Not a finding, a precondition —
     an unequal-budget win is not a win. Exact equality or the row does not report.
  2. PRIMARY: on the contested tail (truth-panel margin < 50%), tiered beats flat by >= 3.0 points
     AND the 95% interval on the MEAN paired difference (bootstrapped over panels) excludes 0.
     The spread of single-panel differences is reported beside it and gates nothing: it answers
     "would one run of this design have won", which is not the question the pattern makes.
  3. Both arms beat the constant on the primary scorer.
  4. SECONDARY (reported, not gating): balanced accuracy, and accuracy on the minority class.

A win here is still not evidence the pattern works. The counterfeit arm — same machinery, pattern
drawn at random — has never been run, and until it has, any difference may be the shape of the
exercise rather than the advice.

  python3 eval/ab_tiered_adjudication.py --pool <crossed_pool.json>
"""
import argparse, collections, json, random, statistics


def plurality(vals):
    """The modal label, or None when the top two tie. None is never scored as correct."""
    c = collections.Counter(vals).most_common()
    return None if not c or (len(c) > 1 and c[0][1] == c[1][1]) else c[0][0]


def split_raters(raters, n_truth, seed):
    r = random.Random(seed)
    truth = set(r.sample(sorted(raters), n_truth))
    return truth, [x for x in sorted(raters) if x not in truth]


def qualify(items, working, n_seniors):
    """Rank working raters by leave-one-out agreement with the rest of the WORKING pool.

    This is what a real qualification round can see: rater-vs-rater agreement, never the answer key.
    Note what it therefore selects for — TYPICALITY, not correctness. A 'senior' here is a rater who
    answers like the crowd answers. That is the honest reading of any agreement-based qualification,
    and it is the reason this arm cannot be called evidence that expertise helps.
    """
    ws = set(working)
    score = collections.Counter()
    for it in items:
        for r in working:
            rest = [v for q, v in it["passes"].items() if q in ws and q != r]
            if plurality(rest) == it["passes"][r]:
                score[r] += 1
    ranked = sorted(working, key=lambda r: (-score[r], r))
    return ranked[:n_seniors], ranked[n_seniors:]


def arm_tiered(items, juniors, seniors, n1, n2, rng, rng2=None):
    """Spend n1 junior passes everywhere; where they split, n2 adjudicator passes set gold.

    `rng` draws tier 1, `rng2` draws tier 2. Splitting the streams lets two arms share one tier-1
    draw — so they escalate the SAME items on the SAME evidence for the SAME budget — and differ
    only in who adjudicates. Without that, the arms escalate different items and the comparison
    carries a budget difference it cannot separate from the effect.
    """
    rng2 = rng2 or rng
    gold, passes, spent = {}, {}, 0
    for it in items:
        j = rng.sample(juniors, n1)
        vals = [it["passes"][r] for r in j]
        used = {r: it["passes"][r] for r in j}
        spent += n1
        if len(set(vals)) == 1:
            gold[it["id"]] = vals[0]
        else:
            s = rng2.sample(seniors, n2)
            used.update({r: it["passes"][r] for r in s})
            spent += n2
            g = plurality([it["passes"][r] for r in s])
            # A senior tier that ties has not decided; fall back to everything the item bought.
            gold[it["id"]] = g if g is not None else plurality(vals + [it["passes"][r] for r in s])
        passes[it["id"]] = used
    return gold, passes, spent


def arm_flat(items, working, budget, rng):
    """No routing: `budget` total passes spread as evenly as the budget divides."""
    n, extra = divmod(budget, len(items))
    bumped = set(rng.sample([it["id"] for it in items], extra))
    gold, passes = {}, {}
    for it in items:
        k = n + (1 if it["id"] in bumped else 0)
        sel = rng.sample(working, min(k, len(working)))
        passes[it["id"]] = {r: it["passes"][r] for r in sel}
        gold[it["id"]] = plurality([it["passes"][r] for r in sel])
    return gold, passes, sum(len(p) for p in passes.values())


def score(gold, truth, ids):
    ids = [i for i in ids if truth.get(i) is not None]
    return (sum(gold.get(i) == truth[i] for i in ids) / len(ids)) if ids else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True, help="a fully crossed pool in judgelab's pool.json shape")
    ap.add_argument("--truth", type=int, default=61)
    ap.add_argument("--seniors", type=int, default=15)
    ap.add_argument("--tier1", type=int, default=3)
    ap.add_argument("--tier2", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=200)
    ap.add_argument("--seed", type=int, default=22)
    ap.add_argument("--write-pools", help="directory to write arm_a/arm_b pool.json for judgelab")
    a = ap.parse_args()

    D = json.load(open(a.pool))
    items = D["items"]
    raters = sorted(items[0]["passes"])
    per = {len(it["passes"]) for it in items}
    if per != {len(raters)}:
        raise SystemExit(f"pool is not fully crossed: raters per item {sorted(per)[:5]}")

    truth_ids, working = split_raters(raters, a.truth, a.seed)
    truth = {it["id"]: plurality([v for r, v in it["passes"].items() if r in truth_ids])
             for it in items}
    seniors, juniors = qualify(items, working, a.seniors)

    def margin(it):
        c = collections.Counter(v for r, v in it["passes"].items() if r in truth_ids).most_common()
        return (c[0][1] - (c[1][1] if len(c) > 1 else 0)) / a.truth

    scored = [it["id"] for it in items if truth[it["id"]] is not None]
    contested = [it["id"] for it in items if truth[it["id"]] is not None and margin(it) < 0.5]
    labels = collections.Counter(truth[i] for i in scored)
    major = labels.most_common(1)[0][0]
    minority = [i for i in scored if truth[i] != major]

    print(f"pool: {a.pool}")
    print(f"  {len(items)} items x {len(raters)} raters, fully crossed = {len(items)*len(raters):,} real ratings")
    print(f"  truth panel {a.truth} (held out) | working pool {len(working)} "
          f"= {len(seniors)} senior + {len(juniors)} junior")
    print(f"  scored {len(scored)} items | contested tail {len(contested)} | minority class {len(minority)}")
    print(f"  arm A: {a.tier1} junior, escalate to {a.tier2} senior | arm B: flat, matched budget\n")

    rows, budgets = [], []
    for i in range(a.repeats):
        rng = random.Random(a.seed * 1000 + i)
        ga, _, spent = arm_tiered(items, juniors, seniors, a.tier1, a.tier2, rng,
                                  random.Random(a.seed * 1000 + i + 700000))
        gb, _, spent_b = arm_flat(items, working, spent, random.Random(a.seed * 1000 + i + 500000))
        # ARM C isolates the confound. Seniors were qualified for agreeing with the crowd, and the
        # answer key IS a crowd majority, so arm A may win merely by routing to raters selected to
        # agree with what it is scored against. Arm C keeps the routing and drops the seniority:
        # identical structure and budget, tier 2 drawn at random from the working pool. If the win
        # survives here it is the routing; if it collapses, arm A's margin was the circularity.
        gc, _, spent_c = arm_tiered(items, juniors, [r for r in working if r not in set(seniors)],
                                    a.tier1, a.tier2, random.Random(a.seed * 1000 + i),
                                    random.Random(a.seed * 1000 + i + 900000))
        budgets.append((spent, spent_b, spent_c))
        rows.append({
            "a_con": score(ga, truth, contested), "b_con": score(gb, truth, contested),
            "c_con": score(gc, truth, contested),
            "a_all": score(ga, truth, scored), "b_all": score(gb, truth, scored),
            "c_all": score(gc, truth, scored),
            "a_min": score(ga, truth, minority), "b_min": score(gb, truth, minority),
            "c_min": score(gc, truth, minority),
        })

    m = lambda k: statistics.mean(r[k] for r in rows)
    diffs = [r["a_con"] - r["b_con"] for r in rows]

    # Two different questions, and conflating them is how a design-level win gets talked out of.
    #   SPREAD  — where a SINGLE panel's difference lands. Wide by nature: one panel scores 80
    #             contested items with ~4.5 raters each, so a single draw is noisy.
    #   MEAN CI — where the DESIGN's average difference lands, bootstrapped over the panels. This
    #             is what "tiered beats flat" claims, and it is the one check 2 gates on.
    sd = sorted(diffs)
    slo, shi = sd[int(.025 * len(sd))], sd[int(.975 * len(sd)) - 1]
    br = random.Random(a.seed)
    boots = sorted(statistics.mean(br.choices(diffs, k=len(diffs))) for _ in range(2000))
    lo, hi = boots[int(.025 * len(boots))], boots[int(.975 * len(boots)) - 1]
    winrate = sum(d > 0 for d in diffs) / len(diffs)
    const_all = labels[major] / len(scored)
    const_con = sum(truth[i] == major for i in contested) / len(contested)

    print(f"  {'':<26}{'A tiered':>11}{'B flat':>10}{'C route-only':>14}{'constant':>11}")
    print(f"  {'contested tail (PRIMARY)':<26}{m('a_con'):>10.1%}{m('b_con'):>10.1%}{m('c_con'):>13.1%}{const_con:>11.1%}")
    print(f"  {'all scored items':<26}{m('a_all'):>10.1%}{m('b_all'):>10.1%}{m('c_all'):>13.1%}{const_all:>11.1%}")
    print(f"  {'minority class':<26}{m('a_min'):>10.1%}{m('b_min'):>10.1%}{m('c_min'):>13.1%}{0.0:>11.1%}")
    print(f"\n  paired difference on the tail: {100*m('a_con')-100*m('b_con'):+.1f} pts")
    print(f"    mean, 95% CI  [{100*lo:+.1f}, {100*hi:+.1f}]   <- the DESIGN-level claim")
    print(f"    single panel  [{100*slo:+.1f}, {100*shi:+.1f}]   <- where one draw lands; "
          f"tiered wins {winrate:.0%} of {a.repeats} panels")
    print(f"  passes spent: arm A {budgets[0][0]:,} | arm B {budgets[0][1]:,} "
          f"({budgets[0][0]/len(items):.2f} per item)")

    cd_ = [r["c_con"] - r["b_con"] for r in rows]
    cb = sorted(statistics.mean(br.choices(cd_, k=len(cd_))) for _ in range(2000))
    clo, chi = cb[int(.025 * len(cb))], cb[int(.975 * len(cb)) - 1]
    print(f"  routing alone (C - B):        {100*statistics.mean(cd_):+.1f} pts  "
          f"95% CI [{100*clo:+.1f}, {100*chi:+.1f}]")
    print(f"  seniority adds (A - C):       {100*(m('a_con')-m('c_con')):+.1f} pts")
    eq = all(x == y == z for x, y, z in budgets)
    d = 100 * (m("a_con") - m("b_con"))
    checks = [
        ("1 HARNESS", eq, "the two arms spend an identical number of passes"),
        ("2 PRIMARY", d >= 3.0 and lo > 0, "tiered beats flat on the tail by >= 3.0 pts, CI excludes 0"),
        ("3 CONSTANT", m("a_con") > const_con and m("b_con") > const_con, "both arms beat the constant"),
    ]
    print()
    for name, ok, what in checks:
        print(f"  CHECK {name:<12}{'MET   ' if ok else 'MISSED'}  {what}")

    if a.write_pools:
        import os
        os.makedirs(a.write_pools, exist_ok=True)
        rng = random.Random(a.seed * 1000)
        _, pa, spent = arm_tiered(items, juniors, seniors, a.tier1, a.tier2, rng)
        _, pb, _ = arm_flat(items, working, spent, random.Random(a.seed * 1000 + 500000))
        for nm, p in (("arm_a_tiered", pa), ("arm_b_flat", pb)):
            out = {"items": [{"id": i["id"], "passes": p[i["id"]],
                              "when": {r: i["when"][r] for r in p[i["id"]] if r in (i.get("when") or {})}}
                             for i in items],
                   "source": f"{D.get('source','')} | {nm}, seed {a.seed}, "
                             f"arm of ab_tiered_adjudication.py",
                   "task": D.get("task", {"kind": "value", "ordinal": False})}
            with open(os.path.join(a.write_pools, f"{nm}.json"), "w") as f:
                json.dump(out, f)
            print(f"  wrote {os.path.join(a.write_pools, nm + '.json')}")


if __name__ == "__main__":
    main()
