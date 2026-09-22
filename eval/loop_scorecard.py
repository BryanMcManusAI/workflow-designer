#!/usr/bin/env python3
"""Score the loop on what a design COSTS A PERSON and what it SHIPS WRONG when nobody looks.

judgelab's gate returned `withheld` for every arm on this pool, so it cannot rank designs here — an
instrument that gives the same verdict to everything is not measuring the things. Adjudication load
does separate them, so that becomes the scorecard.

LOAD ALONE IS GAMEABLE and must never be quoted by itself. A design that buys one pass per item has
no disagreement, so it has zero load and worthless data. The scorecard is therefore a PAIR:

  HUMAN LOAD     share of items where no strict majority of the item's own passes exists, so a
                 person must settle it. This is what the design costs in human time.
  SHIPPED ERROR  share of the items it DID decide whose answer is wrong against the held-out key.
                 These ship with nobody looking. This is what the design costs in quality.

A design is better only if it moves one without giving the other back. Buying fewer passes drives
load down and error up; buying more does the reverse. The pair makes that trade visible instead of
letting either number stand alone.

The decision rule matches eval/proportional_answer.py, and the ROUTING half of it was validated
against judgelab in eval/judgelab_handoff.py, where judgelab queued exactly the items this rule
selects. The key is used only to score, never to decide.

  python3 eval/loop_scorecard.py --arms <dir> --gold-key "ground truth"
"""
import argparse, collections, glob, json, os


def decide(passes):
    """The reading strictly more than half this item's passes share, or None -> a person decides."""
    c = collections.Counter(passes.values())
    if not c:
        return None
    val, n = c.most_common(1)[0]
    return val if n * 2 > len(passes) else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms", required=True, help="directory of arm pools from close_the_loop.py")
    ap.add_argument("--gold-key", default="ground truth")
    a = ap.parse_args()

    print(f"  {'arm':<34}{'human load':>12}{'shipped error':>15}{'decided':>10}{'passes':>9}")
    seen = []
    for path in sorted(glob.glob(os.path.join(a.arms, "arm_*.json"))):
        name = os.path.basename(path)[:-5]
        if name.endswith(("_P", "_K", "_REL", "_REL2", "_RELP")):
            continue
        pool = json.load(open(path))
        items = pool["items"]
        if a.gold_key not in items[0]:
            raise SystemExit(f"  {name}: no {a.gold_key!r} on the items — this needs a pool whose "
                             f"key is independent of the raters.")
        load = wrong = decided = passes = 0
        for it in items:
            passes += len(it["passes"])
            g = decide(it["passes"])
            if g is None:
                load += 1
            else:
                decided += 1
                if int(g) != int(it[a.gold_key]):
                    wrong += 1
        n = len(items)
        seen.append((name, load / n, wrong / decided if decided else float("nan")))
        print(f"  {name:<34}{load/n:>11.1%}{wrong/decided if decided else float('nan'):>15.1%}"
              f"{decided:>10}{passes:>9,}")

    print("\n  NB the passes column counts COLLECTED passes only. A screening arm also pays for its"
          "\n     bank up front (gold-honeypots: 280 passes), which close_the_loop.py matches against"
          "\n     the flat arm's total. Equal budgets can therefore show unequal columns here."
          "\n     Arms in different directories also cover different item counts (a bank is reserved"
          "\n     out of the pool), so compare WITHIN a pair, never across two.")
    print("\n  human load     items no strict majority settles, so a person must  (the human cost)")
    print("  shipped error  of the items it DID decide, the share that are wrong  (the quality cost)")
    print("  Quote them together. Either alone can be bought with the other.")
    if len(seen) == 2:
        (na, la, ea), (nb, lb, eb) = seen
        dl, de = 100 * (la - lb), 100 * (ea - eb)
        better = ("moves both the right way" if dl < 0 and de < 0 else
                  "moves both the wrong way" if dl > 0 and de > 0 else
                  "a TRADE, not a win: it buys one with the other")
        print(f"\n  {na} vs {nb}: load {dl:+.1f} pts, error {de:+.1f} pts -> {better}")


if __name__ == "__main__":
    main()
