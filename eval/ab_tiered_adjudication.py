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

THE COUNTERFEIT ARMS (added 2026-09-21; the threshold was fixed before they were run). NOTES.md
states the guardrail as "so creativity != counterfeit": the risk is a glib recombination engine
handing you a plausible workflow with a fabricated rationale. This pattern's rationale is not
"spend unevenly", it is "spend where they DISAGREE". So the counterfeit holds the form fixed —
same tier-1 evidence, same number of items escalated, same tier-2 pool, same total budget — and
replaces only the decision rule with a coin:

  ARM D  escalate a RANDOM set of items, the same size as A's, to the senior tier
  ARM E  the same, to ordinary raters (the counterfeit of arm C)

  5. COUNTERFEIT: A beats D by >= 3.0 pts with the 95% mean CI excluding 0, and C beats E likewise.
     A counterfeit that matches the real arm means the advice is not doing the work — any uneven
     spend would have scored the same, and the margin is the shape of the exercise, not the advice.

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


def tier1_draw(items, juniors, n1, rng):
    """One junior panel per item, drawn once and shared by every routed arm, so the arms see
    identical evidence and differ only in which items they escalate and to whom."""
    return {it["id"]: rng.sample(juniors, n1) for it in items}


def split_items(items, t1):
    """The items whose junior panel did not agree — what tiered-adjudication routes on."""
    return {it["id"] for it in items if len({it["passes"][r] for r in t1[it["id"]]}) > 1}


def arm_routed(items, t1, escalate, tier2_pool, n2, rng2):
    """Accept the junior panel's answer; on `escalate`, n2 adjudicator passes set gold instead.

    `escalate` is the only thing separating the real arms from the counterfeits: the real ones pass
    the split set, the counterfeits a random set of the same size. Budget is therefore identical by
    construction rather than by matching.
    """
    gold, passes, spent = {}, {}, 0
    for it in items:
        j = t1[it["id"]]
        vals = [it["passes"][r] for r in j]
        used = {r: it["passes"][r] for r in j}
        spent += len(j)
        if it["id"] in escalate:
            sel = rng2.sample(tier2_pool, n2)
            used.update({r: it["passes"][r] for r in sel})
            spent += n2
            g = plurality([it["passes"][r] for r in sel])
            # An adjudicator tier that ties has not decided; fall back to all the item bought.
            gold[it["id"]] = g if g is not None else plurality(vals + [it["passes"][r] for r in sel])
        else:
            gold[it["id"]] = plurality(vals)
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
    print(f"  arm A: {a.tier1} junior, escalate the split to {a.tier2} senior | B: flat | "
          f"C: escalate to non-seniors | D,E: escalate a RANDOM set of the same size\n")

    juniors_l, seniors_l = list(juniors), list(seniors)
    others = [r for r in working if r not in set(seniors)]
    rows, budgets = [], []
    for i in range(a.repeats):
        sd_ = a.seed * 1000 + i
        t1 = tier1_draw(items, juniors_l, a.tier1, random.Random(sd_))
        split = split_items(items, t1)
        # The counterfeits escalate the SAME NUMBER of items, drawn at random instead of by
        # disagreement. Same evidence, same tier-2 pool, same budget: only the rule differs.
        fake = set(random.Random(sd_ + 300000).sample([it["id"] for it in items], len(split)))

        ga, _, sp = arm_routed(items, t1, split, seniors_l, a.tier2, random.Random(sd_ + 700000))
        gc, _, sc = arm_routed(items, t1, split, others, a.tier2, random.Random(sd_ + 900000))
        gd, _, sd2 = arm_routed(items, t1, fake, seniors_l, a.tier2, random.Random(sd_ + 110000))
        ge, _, se = arm_routed(items, t1, fake, others, a.tier2, random.Random(sd_ + 130000))
        gb, _, sb = arm_flat(items, working, sp, random.Random(sd_ + 500000))
        budgets.append((sp, sb, sc, sd2, se))
        r = {}
        for k, g in (("a", ga), ("b", gb), ("c", gc), ("d", gd), ("e", ge)):
            r[k + "_con"] = score(g, truth, contested)
            r[k + "_all"] = score(g, truth, scored)
            r[k + "_min"] = score(g, truth, minority)
        rows.append(r)

    m = lambda k: statistics.mean(r[k] for r in rows)
    br = random.Random(a.seed)

    def ci(x, y):
        """Bootstrapped 95% interval on the MEAN paired difference — the design-level claim."""
        d = [r[x] - r[y] for r in rows]
        b = sorted(statistics.mean(br.choices(d, k=len(d))) for _ in range(2000))
        return statistics.mean(d), b[int(.025 * len(b))], b[int(.975 * len(b)) - 1], d

    const_all = labels[major] / len(scored)
    const_con = sum(truth[i] == major for i in contested) / len(contested)
    cols = [("A tiered", "a"), ("B flat", "b"), ("C route-only", "c"),
            ("D counterfeit", "d"), ("E cf/no-snr", "e")]
    hdr = "".join(f"{n:>14}" for n, _ in cols)
    print(f"  {'':<26}{hdr}{'constant':>11}")
    for lab, suf, const in (("contested tail (PRIMARY)", "_con", const_con),
                            ("all scored items", "_all", const_all),
                            ("minority class", "_min", 0.0)):
        cells = "".join(f"{m(k + suf):>13.1%} " for _, k in cols)
        print(f"  {lab:<26}{cells}{const:>10.1%}")

    d_ab, lo, hi, diffs = ci("a_con", "b_con")
    sdd = sorted(diffs)
    print(f"\n  the pattern vs the path not taken")
    print(f"    A - B  tiered over flat        {100*d_ab:+6.1f}  95% CI [{100*lo:+.1f}, {100*hi:+.1f}]"
          f"   single panel [{100*sdd[int(.025*len(sdd))]:+.1f}, {100*sdd[int(.975*len(sdd))-1]:+.1f}]")
    for lab, x, y in (("C - B  routing alone         ", "c_con", "b_con"),
                      ("A - C  seniority adds        ", "a_con", "c_con")):
        d_, l_, h_, _ = ci(x, y)
        print(f"    {lab} {100*d_:+6.1f}  95% CI [{100*l_:+.1f}, {100*h_:+.1f}]")
    print(f"\n  the counterfeit: same form, escalation drawn at random")
    cf = {}
    for lab, x, y in (("A - D  real vs counterfeit   ", "a_con", "d_con"),
                      ("C - E  the same, no seniors  ", "c_con", "e_con")):
        d_, l_, h_, _ = ci(x, y)
        cf[x[0]] = (d_, l_, h_)
        print(f"    {lab} {100*d_:+6.1f}  95% CI [{100*l_:+.1f}, {100*h_:+.1f}]")
    d_db, ldb, hdb, _ = ci("d_con", "b_con")
    print(f"    D - B  counterfeit over flat  {100*d_db:+6.1f}  95% CI [{100*ldb:+.1f}, {100*hdb:+.1f}]"
          f"   <- what any uneven spend buys")
    print(f"\n  passes spent: {budgets[0][0]:,} in every arm ({budgets[0][0]/len(items):.2f} per item)")
    eq = all(len(set(b)) == 1 for b in budgets)
    d = 100 * (m("a_con") - m("b_con"))
    checks = [
        ("1 HARNESS", eq, "the two arms spend an identical number of passes"),
        ("2 PRIMARY", d >= 3.0 and lo > 0, "tiered beats flat on the tail by >= 3.0 pts, CI excludes 0"),
        ("3 CONSTANT", m("a_con") > const_con and m("b_con") > const_con, "both arms beat the constant"),
        ("5 COUNTERFEIT", cf["a"][0] * 100 >= 3.0 and cf["a"][1] > 0 and cf["c"][1] > 0,
         "the real rule beats the coin (A>D by >=3.0 CI-clear, and C>E)"),
    ]
    print()
    for name, ok, what in checks:
        print(f"  CHECK {name:<14}{'MET   ' if ok else 'MISSED'}  {what}")

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
