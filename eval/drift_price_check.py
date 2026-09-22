#!/usr/bin/env python3
"""A SIGNATURE-MATCHED price check: does the screen catch DRIFT, the thing it is priced against?

price_check.py compared the corpus's per-signature record to a signature-agnostic load/error number,
which is a category error — those are different questions and can disagree with neither being wrong.
That is why "two of three prices are wrong" was withdrawn. This asks the matched question instead.

THE PRICE UNDER TEST. The corpus records `gold-honeypots` against `drift` at 5 adopted, 0 failed —
a Wilson floor of 0.566, which the engine sorts on and quotes as sound. SCHEMA.md defines drift as
"guidelines / acceptance bar move over a campaign", so per rater it is their bar shifting between
early and late work. The pattern's own claim is that honeypots "score each annotator continuously
and catch bad actors and DRIFT".

THE MATCHED QUESTION: does an agreement-based honeypot screen preferentially remove the raters who
drift? If it does, the price holds. If it is blind to drift — dropping low-agreement raters who are
perfectly stable while keeping high-agreement raters whose bar moves — then a record of 5-and-0
against drift is quoting a defense that does not defend.

DICES-350 is the only pool to hand with a clock: 43,050 timestamped passes over 33 days, every one
of 123 raters rating all 350 items.

⚠️ THE ORDER CONFOUND, AND WHY THIS SURVIVES IT. 212 of 300 rater pairs saw the items in the SAME
order (position correlation +0.74), so a rater's early half is largely the same items as everyone
else's early half. An early/late shift in raw Yes-rate would therefore be item difficulty, not time,
and is NOT used. What is used is agreement with the item's own consensus, compared ACROSS raters:
the item effect is common to everyone and cancels in a cross-rater comparison, which is the only
comparison this file makes. Absolute drift levels here mean little; the contrast between dropped and
kept raters is the measurement.

⚠️ WHAT IT CANNOT TEST. The real mechanism is CONTINUOUS scoring that catches drift as it happens
and intervenes. Resampling fixed historical ratings can only test the SELECTION half — whether the
screen picks out drifters. That is, however, the half the corpus record itself measures (did cards
adopting it still report drift), so the comparison is fair.

HOW THE SCREEN CATCHES DRIFT, which is not how the pattern says it does. |drift| against a rater's
mean agreement is rho -0.45: drifters have lower overall agreement, so an agreement screen removes
them as a SIDE EFFECT of removing low agreement. It is not detecting change. The association is not
a one-split artifact — inside the high-agreement half alone, dropping its lowest fifteen by
agreement still separates drifters 0.056 to 0.026 — but two things follow. A rater who drifts
SYMMETRICALLY, wrong in both directions and averaging to high agreement, would be missed entirely.
And the honeypots need not be continuous for this to work, which is the half of the mechanism
resampling cannot test anyway.

  python3 eval/drift_price_check.py --pool <pool with a clock>.json
"""
import argparse, collections, json, random, statistics


def plurality(vals):
    c = collections.Counter(vals).most_common()
    return None if not c or (len(c) > 1 and c[0][1] == c[1][1]) else c[0][0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True)
    ap.add_argument("--bank", type=int, default=40)
    ap.add_argument("--drop", type=int, default=15)
    ap.add_argument("--seeds", type=int, default=60)
    a = ap.parse_args()

    D = json.load(open(a.pool))
    items = D["items"]
    raters = sorted(items[0]["passes"])
    if not (items[0].get("when")):
        raise SystemExit("  this pool has no clock; drift is not measurable on it.")

    consensus = {it["id"]: plurality(list(it["passes"].values())) for it in items}

    # Per-rater drift: agreement with each item's consensus, late half minus early half, split at
    # the rater's OWN median timestamp. Signed shift is the bar moving; magnitude is what matters.
    drift = {}
    for r in raters:
        seq = sorted(((it["when"][r], it["id"]) for it in items), key=lambda z: z[0])
        half = len(seq) // 2
        by_id = {it["id"]: it for it in items}
        def agree(chunk):
            hits = [by_id[i]["passes"][r] == consensus[i] for _, i in chunk if consensus[i]]
            return sum(hits) / len(hits) if hits else float("nan")
        drift[r] = agree(seq[half:]) - agree(seq[:half])

    mags = sorted(abs(v) for v in drift.values())
    print(f"  {len(items)} items x {len(raters)} raters, all timestamped")
    print(f"  per-rater bar shift |late - early| : median {statistics.median(mags):.3f}, "
          f"p90 {mags[int(.9*len(mags))]:.3f}, max {max(mags):.3f}\n")

    def screen(rng):
        bank = set(rng.sample([it["id"] for it in items], a.bank))
        ans = {it["id"]: plurality(list(it["passes"].values())) for it in items if it["id"] in bank}
        hp = {r: sum(1 for it in items if it["id"] in bank and it["passes"][r] == ans[it["id"]])
              for r in raters}
        ranked = sorted(raters, key=lambda r: (hp[r], r))
        return ranked[:a.drop], ranked[a.drop:]

    rows = {"honeypot screen": [], "random drop (coin)": [], "oracle (drops top drifters)": []}
    for s in range(a.seeds):
        rng = random.Random(4000 + s)
        dropped, kept = screen(rng)
        rows["honeypot screen"].append((statistics.mean(abs(drift[r]) for r in dropped),
                                        statistics.mean(abs(drift[r]) for r in kept)))
        rd = rng.sample(raters, a.drop)
        rk = [r for r in raters if r not in set(rd)]
        rows["random drop (coin)"].append((statistics.mean(abs(drift[r]) for r in rd),
                                           statistics.mean(abs(drift[r]) for r in rk)))
        od = sorted(raters, key=lambda r: -abs(drift[r]))[:a.drop]
        ok = [r for r in raters if r not in set(od)]
        rows["oracle (drops top drifters)"].append((statistics.mean(abs(drift[r]) for r in od),
                                                    statistics.mean(abs(drift[r]) for r in ok)))

    print(f"  {'selector':<30}{'drift of DROPPED':>18}{'of KEPT':>10}{'gap':>9}")
    gaps = {}
    for name, rs in rows.items():
        d = statistics.mean(x[0] for x in rs)
        k = statistics.mean(x[1] for x in rs)
        gaps[name] = d - k
        print(f"  {name:<30}{d:>18.3f}{k:>10.3f}{d-k:>+9.3f}")

    br = random.Random(7)
    dd = [x[0] - x[1] for x in rows["honeypot screen"]]
    boots = sorted(statistics.mean(br.choices(dd, k=len(dd))) for _ in range(2000))
    lo, hi = boots[int(.025 * len(boots))], boots[int(.975 * len(boots)) - 1]
    print(f"\n  screen's gap: {statistics.mean(dd):+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    share = (gaps["honeypot screen"] / gaps["oracle (drops top drifters)"]
             if gaps["oracle (drops top drifters)"] else float("nan"))
    print(f"  as a share of what an oracle drop achieves: {share:.0%}")
    verdict = ("PRICE HOLDS — the screen does preferentially remove drifters"
               if lo > 0 else
               "PRICE WRONG — the screen is blind to drift, yet is quoted 5-of-5 against it")
    print(f"\n  corpus quotes gold-honeypots vs drift at 5 adopted / 0 failed, floor 0.566 (sound)")
    print(f"  -> {verdict}")


if __name__ == "__main__":
    main()
