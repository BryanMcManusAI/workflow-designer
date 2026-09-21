#!/usr/bin/env python3
"""Second pattern on the same harness: does `gold-honeypots` beat the path not taken?

tiered-adjudication works by ROUTING ITEMS. gold-honeypots works by SELECTING RATERS — "seed
known-answer honeypots invisibly into the stream to score each annotator and catch bad actors and
drift". Different mechanism, different declared signatures (inflation, drift vs under_specification,
bottleneck). If the shape of the first result repeats here, it is a property of the program; if it
does not, the first result was about that pattern.

THE BANK IS NOT THE ANSWER KEY. Honeypot answers are the WORKING pool's consensus on a reserved
set of items — what an authored bank approximates. The 61-rater truth panel is never consulted for
screening, so a rater is never selected for agreeing with what scores them. Honeypot items are
excluded from scoring; they are the cost, not the measurement.

POSITIVE CONTROL, checked before believing any null: the pool must contain raters worth dropping.
It does — against the truth panel the 62 working raters run 12.9% to 92.5%, the bottom 15 averaging
59.9% against the top 47's 85.9%. A null here would mean the screen cannot find them, not that
there is nothing to find.

  ARM A  screened     pay 62 x H screening passes, drop the worst --drop raters, then k per item
                      from the survivors
  ARM B  unscreened   no screen; the entire budget goes into ratings, drawn from everyone
  ARM D  counterfeit  pay the IDENTICAL screening cost, then drop the same NUMBER of raters AT
                      RANDOM. Same form, the rule replaced by a coin.
  ARM E  evidence     no screen, k per item from everyone. Spends less; matches A's per-item
                      evidence instead of its budget.

BOTH CONTROLS, because the matched-evidence row established that budget and evidence cannot both be
held fixed against a design that spends part of its money on something other than ratings. B answers
"was the screen worth the money", E answers "was it the screen or the smaller pool".

CHECKS STATED BEFORE THE ROW RAN:
  1. HARNESS: A, B and D spend an identical number of passes.
  2. POSITIVE CONTROL: the screen drops raters whose truth agreement is below those it keeps.
     If this fails the instrument is broken and nothing below is interpretable.
  3. PRIMARY: A beats B on the contested tail by >= 3.0 pts, 95% mean CI excluding 0.
  4. COUNTERFEIT: A beats D by >= 3.0 pts, 95% mean CI excluding 0.
  5. CONSTANT: A beats the majority-label constant on the contested tail.

  python3 eval/ab_gold_honeypots.py --pool <crossed>.json
"""
import argparse, collections, json, random, statistics

import ab_tiered_adjudication as ab


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True)
    ap.add_argument("--truth", type=int, default=61)
    ap.add_argument("--honeypots", type=int, default=10)
    ap.add_argument("--drop", type=int, default=15)
    ap.add_argument("--per-item", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=100)
    ap.add_argument("--seed", type=int, default=22)
    a = ap.parse_args()

    D = json.load(open(a.pool))
    items = D["items"]
    raters = sorted(items[0]["passes"])
    truth_ids, working = ab.split_raters(raters, a.truth, a.seed)
    truth = {it["id"]: ab.plurality([v for r, v in it["passes"].items() if r in truth_ids])
             for it in items}

    def margin(it):
        c = collections.Counter(v for r, v in it["passes"].items() if r in truth_ids).most_common()
        return (c[0][1] - (c[1][1] if len(c) > 1 else 0)) / a.truth

    # Each rater's true quality — used ONLY to report the positive control, never to screen.
    quality = {r: sum(1 for it in items if truth[it["id"]] is not None
                      and it["passes"][r] == truth[it["id"]])
                  / sum(1 for it in items if truth[it["id"]] is not None) for r in working}

    rows, budgets, ctrl = [], [], []
    for i in range(a.repeats):
        sd = a.seed * 1000 + i
        rng = random.Random(sd)
        bank_ids = set(rng.sample([it["id"] for it in items], a.honeypots))
        bank = {it["id"]: ab.plurality([it["passes"][r] for r in working])
                for it in items if it["id"] in bank_ids}
        live = [it for it in items if it["id"] not in bank_ids and truth[it["id"]] is not None]
        contested = [it["id"] for it in live if margin(it) < 0.5]
        minority = [it["id"] for it in live
                    if truth[it["id"]] != collections.Counter(
                        truth[x["id"]] for x in live).most_common(1)[0][0]]

        screen_cost = len(working) * a.honeypots
        hp = {r: sum(1 for cid in bank_ids
                     if next(x for x in items if x["id"] == cid)["passes"][r] == bank[cid])
              for r in working}
        kept = sorted(working, key=lambda r: (-hp[r], r))[:len(working) - a.drop]
        dropped = [r for r in working if r not in set(kept)]
        ctrl.append((statistics.mean(quality[r] for r in dropped),
                     statistics.mean(quality[r] for r in kept)))

        fake_kept = rng.sample(working, len(kept))
        budget = screen_cost + a.per_item * len(live)

        def collect(pool_, seed_off, k=None, total=None):
            """k raters on every item, or `total` passes spread as evenly as it divides.

            The spread matters: a budget that buys a flat EVEN panel ties 2-2 over three labels and
            the tie scores wrong, so a fixed 4 lands below a fixed 3. Spreading the remainder mixes
            4s and 5s and averages over that artifact instead of sitting on it.
            """
            r_ = random.Random(sd + seed_off)
            gold, load, silent, spent = {}, 0, 0, 0
            base, extra = (k, 0) if k else divmod(total, len(live))
            bumped = set(r_.sample([x["id"] for x in live], extra)) if extra else set()
            for it in live:
                n = base + (1 if it["id"] in bumped else 0)
                sel = r_.sample(pool_, n)
                spent += n
                vals = [it["passes"][r] for r in sel]
                split = len(set(vals)) > 1
                load += split
                gold[it["id"]] = ab.plurality(vals)
                if not split and gold[it["id"]] != truth[it["id"]]:
                    silent += 1
            return gold, load / len(live), silent, spent

        ga, la, sa, spa = collect(kept, 1, k=a.per_item)
        gd, ld, sdl, spd = collect(fake_kept, 2, k=a.per_item)
        ge, le, se, spe = collect(working, 3, k=a.per_item)
        # Arm B spends A's WHOLE budget on ratings — screen cost included, since not screening is
        # exactly what frees that money. Spread, not a fixed panel, for the reason in collect().
        gb, lb, sb, spb = collect(working, 4, total=budget)
        budgets.append((spa + screen_cost, spb, spd + screen_cost, spe))
        r = {}
        for k_, g, ld_, sl_ in (("a", ga, la, sa), ("b", gb, lb, sb),
                                ("d", gd, ld, sdl), ("e", ge, le, se)):
            r[k_ + "_con"] = ab.score(g, truth, contested)
            r[k_ + "_min"] = ab.score(g, truth, minority)
            r[k_ + "_load"], r[k_ + "_sil"] = ld_, sl_
        r["const"] = sum(truth[i2] == "No" for i2 in contested) / len(contested)
        rows.append(r)

    m = lambda k: statistics.mean(x[k] for x in rows)
    br = random.Random(a.seed)

    def ci(x, y):
        d = [p[x] - p[y] for p in rows]
        b = sorted(statistics.mean(br.choices(d, k=len(d))) for _ in range(2000))
        return statistics.mean(d), b[int(.025 * len(b))], b[int(.975 * len(b)) - 1]

    print(f"pool {len(items)} items | truth panel {a.truth} | bank {a.honeypots} items "
          f"(excluded from scoring) | drop {a.drop} of {len(working)} | {a.repeats} panels")
    nlive = len(items) - a.honeypots
    lo_, hi_ = divmod(budgets[0][0], nlive)[0], divmod(budgets[0][0], nlive)[0] + 1
    print(f"screening costs {len(working) * a.honeypots} passes; arm A then buys {a.per_item}/item "
          f"from survivors, arm B spends the same total on {lo_}-{hi_}/item with no screen\n")
    print(f"  {'arm':<28}{'tail acc':>10}{'minority':>10}{'adj load':>10}{'silent':>8}{'spend':>8}")
    for lab, k_, sp in (("A screened (3/item)", "a", 0), ("B unscreened, same budget", "b", 1),
                        ("D counterfeit, random drop", "d", 2),
                        ("E unscreened, same evidence", "e", 3)):
        print(f"  {lab:<28}{m(k_+'_con'):>9.1%}{m(k_+'_min'):>10.1%}{m(k_+'_load'):>10.1%}"
              f"{m(k_+'_sil'):>8.1f}{statistics.mean(b[sp] for b in budgets):>8.0f}")
    print(f"  {'constant':<28}{m('const'):>9.1%}")

    print()
    for lab, x, y in (("A - B  screen vs the money   ", "a_con", "b_con"),
                      ("A - E  screen, evidence held ", "a_con", "e_con"),
                      ("A - D  screen vs a coin      ", "a_con", "d_con")):
        d_, lo, hi = ci(x, y)
        print(f"  {lab} {100*d_:+6.1f} pts  95% CI [{100*lo:+.1f}, {100*hi:+.1f}]")

    dq, kq = statistics.mean(c[0] for c in ctrl), statistics.mean(c[1] for c in ctrl)
    print(f"\n  positive control: screen drops raters at {dq:.1%} truth agreement, "
          f"keeps raters at {kq:.1%}")
    checks = [
        # Compare what the arms ACTUALLY spent. An earlier version compared three copies of the
        # intended budget and reported MET while arm B was 282 passes short.
        ("1 HARNESS", all(b[0] == b[1] == b[2] for b in budgets),
         "A, B and D spend the same (actual, not intended)"),
        ("2 CONTROL", dq < kq, "the screen drops worse raters than it keeps"),
        ("3 PRIMARY", ci("a_con", "b_con")[0] * 100 >= 3.0 and ci("a_con", "b_con")[1] > 0,
         "A beats B by >= 3.0 pts, CI excludes 0"),
        ("4 COUNTERFEIT", ci("a_con", "d_con")[0] * 100 >= 3.0 and ci("a_con", "d_con")[1] > 0,
         "A beats the coin by >= 3.0 pts, CI excludes 0"),
        ("5 CONSTANT", m("a_con") > m("const"), "A beats the constant"),
    ]
    print()
    for n_, ok, what in checks:
        print(f"  CHECK {n_:<14}{'MET   ' if ok else 'MISSED'}  {what}")


if __name__ == "__main__":
    main()
