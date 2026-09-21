"""The control that should have run BEFORE the lift ranking shipped into the engine.

The A/B rows in this directory all carry a counterfeit arm — same form, the decision rule replaced
by a coin — because a margin that a coin also earns is the shape of the exercise, not the advice.
The lift ranking went into `analyze_interrogate` with no such control and with no interval on its
0.49-vs-0.41 headline. This is that control, run late.

COUNTERFEIT: same retrieved analogues, the SAME support floor of 2, ranked by a coin instead of by
lift. Lift at support>=1 scores 0.44 and at support>=2 scores 0.49, so it was entirely possible that
the FLOOR was doing the work and the lift was decoration. It is not, but the margin is not large.

Each card's coin score is the mean of 20 shuffles, so the comparison is against the average coin
rather than one lucky one. The shuffle seeds come from crc32, not hash(): Python randomizes string
hashing per process, so a hash()-seeded baseline moves between runs and its record does not
reproduce. loo_signatures.py still seeds its weighted-random baseline from hash() and its CHECK 1
margin drifts by a few tenths for that reason.

TWO THINGS THIS IS NOT.
  - The absolute numbers here are NOT the shipped engine's. This reimplements the ranking to swap
    one sort key, and it drops the priority tiebreak and the engine's habit of topping up from
    `defended`/`good_means` when fewer than k rows are open. It reads 0.453 where the shipped engine
    reads 0.49. The lift-vs-coin CONTRAST is internally valid because both modes run the identical
    code path; the levels are not comparable to eval/loo_signatures_run.txt.
  - Not external validation. 30 tail cards, and the same person wrote the cards' axes and their
    signatures. That limit was stated when the row was built and it still binds.

The degenerate frequency constant (the three most common REPORTED signatures) is deliberately NOT
reported: the tail is DEFINED as signatures outside that triple, so it scores 0.00 by construction
and comparing to it flatters everything. The honest constant is the leave-one-out best triple at
0.41 in loo_signatures.py, a different computation.
"""
import collections, copy, os, random, statistics, sys, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
sys.path.insert(0, HERE)
import engine
import loo_signatures as L

K = 3
idx = engine.load_index()
cards = idx["cards"]
key = {cid: L.reported(c) for cid, c in cards.items()}
tail = [cid for cid, s in key.items() if set(s) - set(L.TOP3)]


def ranked(idx_minus, stub, mode, rng):
    near, far = engine._near_far(idx_minus, stub)
    ids = [c for _, c in near] + [c for _, c, _ in far]
    cnt = engine.risk_counter(idx_minus, ids)
    n = len(ids) or 1
    base = collections.Counter()
    for c in idx_minus["cards"].values():
        for sg in c["failure_signatures"]:
            base[sg] += 1
    N = len(idx_minus["cards"]) or 1
    have = engine.defended(idx_minus, stub)
    out = []
    for sig, c in cnt.items():
        if sig in have or c < 2:          # the support floor, identical in both modes
            continue
        br = base.get(sig, 0) / N
        lift = ((c / n) / br) if br else 0.0
        out.append((sig, lift if mode == "lift" else rng.random()))
    out.sort(key=lambda r: (-r[1], r[0]))
    return [r[0] for r in out][:K]


def recall(named, k):
    k = set(k)
    return len(k & set(named)) / len(k) if k else None


per_card = {"lift": [], "coin": []}
rng = random.Random(5)
for cid in tail:
    minus = copy.deepcopy(idx)
    del minus["cards"][cid]
    stub = L.stub_from(cards[cid])
    tk = set(key[cid]) - set(L.TOP3)
    per_card["lift"].append(recall(ranked(minus, stub, "lift", rng), tk))
    # the coin gets 20 draws per card, averaged, so it is not one lucky shuffle
    per_card["coin"].append(statistics.mean(
        recall(ranked(minus, stub, "coin", random.Random(zlib.crc32(cid.encode()) + i)), tk)
        for i in range(20)))

m = lambda k: statistics.mean(per_card[k])
print(f"  tail cards: {len(tail)}")
print(f"  LIFT order, support>=2        {m('lift'):.3f}")
print(f"  COIN order, support>=2        {m('coin'):.3f}   <- the counterfeit")

br = random.Random(1)
for lab, a_, b_ in (("lift - coin ", "lift", "coin"),):
    d = [x - y for x, y in zip(per_card[a_], per_card[b_])]
    boots = sorted(statistics.mean(br.choices(d, k=len(d))) for _ in range(4000))
    lo, hi = boots[int(.025 * len(boots))], boots[int(.975 * len(boots)) - 1]
    print(f"  {lab}  {100*statistics.mean(d):+6.1f} pts  95% CI [{100*lo:+.1f}, {100*hi:+.1f}]"
          f"   {'CLEARS 0' if lo > 0 else 'INCLUDES 0'}")
