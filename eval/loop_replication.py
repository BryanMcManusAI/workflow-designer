#!/usr/bin/env python3
"""Does the abstention arc hold, or was it one draw?

close_the_loop.py + loop_scorecard.py showed one before/after: the engine's pick without abstention
(human-audit-sample) merely TRADED human load for error against flat, while its pick with abstention
(gold-honeypots) improved BOTH. One comparison is one comparison, and this repo has already had to
retract a headline that rested on a single measurement.

VARYING THE STUB DOES NOT REPLICATE IT. The arms are realized from the PATTERN, not the stub, so any
stub that yields the same pick produces byte-identical arms. A sweep over image/classification/expert,
image/rubric_rating/crowd and image/classification/crowd gives the same swap and the same numbers.
What can actually vary is the draw and the pattern's own parameters, so that is what this sweeps:

  seeds          different rater draws for every arm
  audit-frac     how much of the pool the audit sample covers
  bank/drop      how big the honeypot bank is and how many raters the screen removes

Each row re-asks the same question: against a flat arm on the same budget, does the design move
BOTH human load and shipped error the right way, or does it buy one with the other?
"""
import argparse, collections, json, random, statistics


def decide(passes):
    c = collections.Counter(passes.values())
    if not c:
        return None
    val, n = c.most_common(1)[0]
    return val if n * 2 > len(passes) else None


def score(arm, truth):
    load = wrong = decided = 0
    for iid, passes in arm.items():
        g = decide(passes)
        if g is None:
            load += 1
        else:
            decided += 1
            wrong += int(g) != int(truth[iid])
    n = len(arm)
    return load / n, (wrong / decided if decided else float("nan"))


def flat(live, raters, budget, rng):
    base, extra = divmod(budget, len(live))
    bump = set(rng.sample([it["id"] for it in live], extra)) if extra else set()
    return {it["id"]: {r: it["passes"][r] for r in
                       rng.sample(raters, min(base + (1 if it["id"] in bump else 0), len(raters)))}
            for it in live}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True)
    ap.add_argument("--gold-key", default="ground truth")
    ap.add_argument("--base", type=int, default=3)
    ap.add_argument("--seeds", type=int, default=8)
    a = ap.parse_args()

    D = json.load(open(a.pool))
    raters = sorted({r for it in D["items"] for r in it["passes"]})
    items = [it for it in D["items"] if len(it["passes"]) == len(raters)]
    truth = {it["id"]: it[a.gold_key] for it in items}

    settings = [(0.30, 40, 2), (0.50, 40, 2), (0.30, 80, 2), (0.30, 40, 1), (0.50, 80, 3)]
    print(f"  pool {len(items)} items, {len(raters)} raters, {a.base} passes/item base, "
          f"{a.seeds} seeds x {len(settings)} settings\n")
    print(f"  {'design':<22}{'audit/bank/drop':>17}{'load vs flat':>15}{'error vs flat':>16}"
          f"{'both right?':>13}")

    tallies = {"human-audit-sample": [], "gold-honeypots": []}
    for frac, bank_n, drop in settings:
        agg = {k: [] for k in tallies}
        for s in range(a.seeds):
            rng = random.Random(1000 + s)
            # --- human-audit-sample: base everywhere, extra passes on a random slice
            audit = set(rng.sample([it["id"] for it in items], int(frac * len(items))))
            arm, spend = {}, 0
            for it in items:
                sel = rng.sample(raters, a.base)
                if it["id"] in audit:
                    sel += [r for r in rng.sample(raters, 2) if r not in sel]
                arm[it["id"]] = {r: it["passes"][r] for r in sel}
                spend += len(sel)
            fa = flat(items, raters, spend, random.Random(2000 + s))
            la, ea = score(arm, truth)
            lb, eb = score(fa, truth)
            agg["human-audit-sample"].append((la - lb, ea - eb))

            # --- gold-honeypots: pay to screen on a reserved bank, then collect from survivors
            bank = set(rng.sample([it["id"] for it in items], bank_n))
            ans = {it["id"]: decide(it["passes"]) or list(it["passes"].values())[0]
                   for it in items if it["id"] in bank}
            hp = {r: sum(1 for it in items if it["id"] in bank and it["passes"][r] == ans[it["id"]])
                  for r in raters}
            kept = sorted(raters, key=lambda r: (-hp[r], r))[:len(raters) - drop]
            live = [it for it in items if it["id"] not in bank]
            arm2, spend2 = {}, len(raters) * bank_n
            for it in live:
                sel = rng.sample(kept, a.base)
                arm2[it["id"]] = {r: it["passes"][r] for r in sel}
                spend2 += len(sel)
            fb = flat(live, raters, spend2, random.Random(3000 + s))
            la2, ea2 = score(arm2, truth)
            lb2, eb2 = score(fb, truth)
            agg["gold-honeypots"].append((la2 - lb2, ea2 - eb2))

        for name, rows in agg.items():
            dl = statistics.mean(r[0] for r in rows) * 100
            de = statistics.mean(r[1] for r in rows) * 100
            both = sum(1 for r in rows if r[0] < 0 and r[1] < 0)
            tallies[name].append((dl, de, both, len(rows)))
            verdict = f"{both}/{len(rows)} seeds"
            print(f"  {name:<22}{f'{frac}/{bank_n}/{drop}':>17}{dl:>+14.1f}{de:>+15.1f}{verdict:>13}")
        print()

    print("  across every setting and seed")
    for name, rows in tallies.items():
        dl = statistics.mean(r[0] for r in rows)
        de = statistics.mean(r[1] for r in rows)
        both = sum(r[2] for r in rows)
        tot = sum(r[3] for r in rows)
        call = ("IMPROVES BOTH" if dl < 0 and de < 0 else
                "a trade, not a win" if (dl < 0) != (de < 0) else "worse on both")
        print(f"    {name:<22} load {dl:+6.1f}  error {de:+6.1f}  "
              f"both-right on {both}/{tot} runs  -> {call}")


if __name__ == "__main__":
    main()
