#!/usr/bin/env python3
"""Both patterns again, on a pool whose answer key is INDEPENDENT of the raters.

Everything measured on DICES was scored against a 61-rater crowd-majority truth panel. Both
patterns that were run there work by selecting for agreement, so they were being scored against the
very thing they select for, and the strongest cross-pattern finding — that selecting for typicality
costs minority-class recall — could be circular by construction.

CrowdGleason breaks the circle: 2,812 fully crossed items (of 2,926; the rest are filtered), 7
raters, and a `ground truth` column that no rater voted on. If the typicality cost survives here it
is a finding. If it vanishes, it was the crowd-majority key all along, which retroactively qualifies
both DICES rows and is worth just as much.

The pool is also a better instrument than DICES in three ways, all verified before the row ran:
  - a flat 3-rater panel scores 83.3% exact against a 73.0% constant, so plain accuracy is USABLE
    here. On DICES the panel lost to the constant and only a contested-tail scorer worked.
  - the rater spread is enormous: 33.8% to 91.7% against ground truth. Two of the seven are plainly
    bad, so an agreement-based screen has something unambiguous to find.
  - 8x the items, so the intervals are much tighter.

⭐ THE DECISIVE CHECK, only possible with an independent key: does agreement-based qualification
actually pick the GOOD raters? On DICES that could not be asked, because the key was agreement.
Here the answer is checkable, and if a screen that selects on agreement picks raters who are bad
against ground truth, that is the typicality mechanism caught in the act.

SCORERS, FIXED BEFORE THE ROW RAN. Gleason grades are ordinal, so both are reported and neither is
chosen after the fact: EXACT match is primary (strictest, hardest to flatter), WITHIN-1 secondary.
The tail is items the full 7-rater pool does not agree on. Minority = ground truth above grade 0.

  python3 eval/crossed_pool_replication.py --pool <crowdgleason>.json
"""
import argparse, collections, json, random, statistics

import ab_tiered_adjudication as ab


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True)
    ap.add_argument("--gold-key", default="ground truth")
    ap.add_argument("--seniors", type=int, default=3)
    ap.add_argument("--tier1", type=int, default=3)
    ap.add_argument("--tier2", type=int, default=2)
    ap.add_argument("--drop", type=int, default=2)
    ap.add_argument("--honeypots", type=int, default=40)
    ap.add_argument("--repeats", type=int, default=60)
    ap.add_argument("--seed", type=int, default=22)
    a = ap.parse_args()

    D = json.load(open(a.pool))
    raters = sorted({r for it in D["items"] for r in it["passes"]})
    items = [it for it in D["items"] if len(it["passes"]) == len(raters)]
    truth = {it["id"]: int(it[a.gold_key]) for it in items}
    for it in items:
        it["passes"] = {r: int(v) for r, v in it["passes"].items()}

    tail = [it["id"] for it in items if len(set(it["passes"].values())) > 1]
    minority = [it["id"] for it in items if truth[it["id"]] != 0]
    const = collections.Counter(truth.values()).most_common(1)[0]
    print(f"pool: {len(items)} fully crossed of {len(D['items'])} | {len(raters)} raters | "
          f"key = {a.gold_key!r}, independent of every rater")
    print(f"  tail {len(tail)} items ({len(tail)/len(items):.0%}) | minority {len(minority)} "
          f"({len(minority)/len(items):.0%}) | constant {const[1]/len(items):.1%}\n")

    # --- the decisive check: does agreement-qualification pick raters who are good vs GROUND TRUTH?
    truthacc = {r: sum(it["passes"][r] == truth[it["id"]] for it in items) / len(items)
                for r in raters}
    seniors, juniors = ab.qualify(items, raters, a.seniors)
    print("  agreement-based qualification vs the independent key")
    for r in sorted(raters, key=lambda x: -truthacc[x]):
        print(f"    {r:<10}{truthacc[r]:>7.1%} vs ground truth   "
              f"{'<- picked as SENIOR' if r in seniors else ''}")
    picked = statistics.mean(truthacc[r] for r in seniors)
    rest = statistics.mean(truthacc[r] for r in juniors)
    print(f"    seniors average {picked:.1%} against ground truth; the rest {rest:.1%}\n")

    def exact(g, ids):
        ids = [i for i in ids if g.get(i) is not None]
        return sum(g[i] == truth[i] for i in ids) / len(ids) if ids else float("nan")

    def within1(g, ids):
        ids = [i for i in ids if g.get(i) is not None]
        return sum(abs(g[i] - truth[i]) <= 1 for i in ids) / len(ids) if ids else float("nan")

    def collect(pool_, k, rng):
        return {it["id"]: ab.plurality([it["passes"][r] for r in rng.sample(pool_, k)])
                for it in items}

    rows = []
    for i in range(a.repeats):
        sd = a.seed * 1000 + i
        t1 = ab.tier1_draw(items, juniors, a.tier1, random.Random(sd))
        split = ab.split_items(items, t1)
        fake = set(random.Random(sd + 3).sample([it["id"] for it in items], len(split)))
        ga, _, spend = ab.arm_routed(items, t1, split, seniors, a.tier2, random.Random(sd + 7))
        gc, _, _ = ab.arm_routed(items, t1, split, juniors, a.tier2, random.Random(sd + 9))
        gd, _, _ = ab.arm_routed(items, t1, fake, seniors, a.tier2, random.Random(sd + 11))
        gb, _, _ = ab.arm_flat(items, raters, spend, random.Random(sd + 5))
        # honeypots: bank answers are POOL CONSENSUS on reserved items, never the key
        rng = random.Random(sd + 13)
        bank = set(rng.sample([it["id"] for it in items], a.honeypots))
        ans = {it["id"]: ab.plurality(list(it["passes"].values())) for it in items if it["id"] in bank}
        hp = {r: sum(1 for it in items if it["id"] in bank and it["passes"][r] == ans[it["id"]])
              for r in raters}
        kept = sorted(raters, key=lambda r: (-hp[r], r))[:len(raters) - a.drop]
        gh = collect(kept, a.tier1, random.Random(sd + 17))
        gu = collect(raters, a.tier1, random.Random(sd + 19))
        r = {"hp_kept": tuple(sorted(kept))}
        for k_, g in (("a", ga), ("b", gb), ("c", gc), ("d", gd), ("h", gh), ("u", gu)):
            r[k_ + "_tail"] = exact(g, tail)
            r[k_ + "_min"] = exact(g, minority)
            r[k_ + "_w1"] = within1(g, tail)
        rows.append(r)

    m = lambda k: statistics.mean(x[k] for x in rows)
    br = random.Random(a.seed)

    def ci(x, y):
        d = [p[x] - p[y] for p in rows]
        b = sorted(statistics.mean(br.choices(d, k=len(d))) for _ in range(2000))
        return statistics.mean(d), b[int(.025 * len(b))], b[int(.975 * len(b)) - 1]

    print(f"  {'arm':<34}{'tail exact':>12}{'tail w/in-1':>13}{'minority':>11}")
    for lab, k_ in (("A tiered (senior tier)", "a"), ("B flat, same budget", "b"),
                    ("C route-only (no senior tier)", "c"), ("D counterfeit (random items)", "d"),
                    ("H honeypot-screened", "h"), ("U unscreened, same evidence", "u")):
        print(f"  {lab:<34}{m(k_+'_tail'):>11.1%}{m(k_+'_w1'):>13.1%}{m(k_+'_min'):>11.1%}")

    print("\n  does the agreement-selected tier cost the minority class, as it did on DICES?")
    for lab, x, y in (("A - C  senior tier, minority  ", "a_min", "c_min"),
                      ("H - U  honeypot screen, minority", "h_min", "u_min")):
        d_, lo, hi = ci(x, y)
        verdict = "COSTS it" if hi < 0 else ("HELPS it" if lo > 0 else "no effect")
        print(f"    {lab} {100*d_:+6.1f} pts  95% CI [{100*lo:+.1f}, {100*hi:+.1f}]  {verdict}")
    print("\n  and on the tail, for comparison with the DICES row")
    for lab, x, y in (("A - B  tiered over flat       ", "a_tail", "b_tail"),
                      ("A - D  vs the counterfeit     ", "a_tail", "d_tail"),
                      ("H - U  screen over no screen  ", "h_tail", "u_tail")):
        d_, lo, hi = ci(x, y)
        print(f"    {lab} {100*d_:+6.1f} pts  95% CI [{100*lo:+.1f}, {100*hi:+.1f}]")


if __name__ == "__main__":
    main()
