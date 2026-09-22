#!/usr/bin/env python3
"""Are the tool's PRICES true? The question an idea tool actually has to answer.

The workflow designer is a partner for building a workflow, not an oracle that names the one right
answer. So "does its top pick win an A/B" is the wrong bar. What a person relies on when they are
the one choosing is the PRICE on each option: the corpus says this pattern was adopted five times
and failed once, so plan accordingly. If those prices are fiction, every option it offers is
mispriced and the guardrail NOTES.md sets — "each suggestion is legible back to a real pattern with
a real price" — is not being met.

So: for each pattern this harness can realize, put the corpus's recorded price beside what the
pattern actually does on a real crossed pool, and see whether they agree.

THREE PATTERNS, THREE SEPARATE CHECKS, NOT A CORRELATION. Only three distinct designs are realizable
on this pool — the others either collapse into each other under resampling (qualification-calibration
is the same operation as gold-honeypots here), need item metadata the pool has no column for
(coverage-routing), or would change what a rating IS and are out of scope by declaration
(human-gold-anchor shows raters the gold). A rank correlation on n=3 would be theatre. Each row is
read on its own.

The pool's verdict is the pair from loop_scorecard.py — human load and shipped error against a flat
arm on an identical budget — averaged over seeds. The corpus's price is the Wilson floor from
engine.defense_rank, the same number the engine now sorts defenses by.

SEEDS. The default is 60 because 8 was not enough and said so the hard way. eval/loop_replication.py
reported gold-honeypots improving both numbers in 31 of 40 runs; those 40 were 5 settings over the
SAME 8 seeds, with the honeypot block drawing from an RNG the audit block had already consumed, so
they were not 40 independent draws. Re-run here on 60 independent seeds, its error advantage is
+0.2 points and both-right is 30 of 60 — a coin. The 31/40 was noise. Anything below ~30 seeds on
this pool should not be quoted.

⚠️ READ THIS BEFORE QUOTING THE VERDICTS. The two sides may not be commensurable, and if they are
not then a disagreement is this file's fault rather than the corpus's.

  the corpus record asks   of the cards that adopted pattern P, how many still REPORTED failure
                           signature S in their published account?
  this pool measure asks   does design P lower human load and shipped error against a flat arm?

Those are different questions. A pattern can cut error on a pool while the papers that adopted it
still report the signature — adopting a detection pattern is exactly what makes a team find and
report the thing. And a 0-of-5 record can mean the five cards never looked for S, not that P
prevented it. Worse, the record is PER SIGNATURE while the pool measure is signature-agnostic:
gold-honeypots is priced here against `inflation` and `drift`, but the pool number is overall
load/error on an ordinal grading task, which is nearer to rater quality than to either. So the
verdicts below should be read as "the record does not predict this pool outcome", never as "the
corpus price is false". A fair test would measure the SAME signature on the pool, which for drift
needs a clock (DICES has one, CrowdGleason does not) and for inflation may not be realizable at all.

TWO STRUCTURAL PROBLEMS IN THE RECORD ARE REAL WHATEVER THIS FILE MEASURES, both checked 2026-09-21:
  - `caught` is non-zero on 2 of 40 records. The record is almost purely a failure count, so a
    pattern can lose points and essentially never gain them. What it calls a survival rate is a
    rate of not-being-blamed.
  - the median record rests on 5 adoptions. Wilson bounds that honestly, which is why the engine
    sorts on the floor, but it cannot manufacture evidence that is not there.
A COLLECTIVE-BLAME HYPOTHESIS WAS TESTED AND REJECTED: a card reporting S blames every pattern it
ran that declares S, so patterns in busy workflows should accumulate blame. They do not — failure
rate against co-adoption count is rho -0.19, and patterns in busy workflows fail LESS (0.35) than
those in lean ones (0.41). Reporting verbosity is weakly positive (rho +0.28, n=32) and is the only
survivor of the three mechanisms tried.

  python3 eval/price_check.py --pool <crossed>.json
"""
import argparse, collections, json, os, random, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
import engine  # noqa: E402


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
    return load / len(arm), (wrong / decided if decided else float("nan"))


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
    ap.add_argument("--seeds", type=int, default=60)  # 8 was not enough; see the header
    a = ap.parse_args()

    D = json.load(open(a.pool))
    raters = sorted({r for it in D["items"] for r in it["passes"]})
    items = [it for it in D["items"] if len(it["passes"]) == len(raters)]
    truth = {it["id"]: it[a.gold_key] for it in items}
    idx = engine.load_index()

    def corpus_price(pid):
        """What the tool would quote: the record and Wilson floor per signature it claims to defend."""
        out = []
        for sig in idx["patterns"][pid].get("defends", []):
            rec = engine.defense_record(idx, pid, sig)
            out.append((sig, rec, engine.defense_rank(rec)[0]))
        return sorted(out, key=lambda r: -r[2])

    def run(kind):
        deltas = []
        for s in range(a.seeds):
            rng = random.Random(1000 + s)
            if kind == "human-audit-sample":
                audit = set(rng.sample([it["id"] for it in items], int(.30 * len(items))))
                arm, spend, live = {}, 0, items
                for it in items:
                    sel = rng.sample(raters, a.base)
                    if it["id"] in audit:
                        sel += [r for r in rng.sample(raters, 2) if r not in sel]
                    arm[it["id"]] = {r: it["passes"][r] for r in sel}
                    spend += len(sel)
            elif kind == "gold-honeypots":
                bank = set(rng.sample([it["id"] for it in items], 40))
                ans = {it["id"]: decide(it["passes"]) or list(it["passes"].values())[0]
                       for it in items if it["id"] in bank}
                hp = {r: sum(1 for it in items if it["id"] in bank
                             and it["passes"][r] == ans[it["id"]]) for r in raters}
                kept = sorted(raters, key=lambda r: (-hp[r], r))[:len(raters) - 2]
                live = [it for it in items if it["id"] not in bank]
                arm, spend = {}, len(raters) * 40
                for it in live:
                    arm[it["id"]] = {r: it["passes"][r] for r in rng.sample(kept, a.base)}
                    spend += a.base
            else:  # tiered-adjudication: base panel, escalate only where it splits
                arm, spend, live = {}, 0, items
                for it in items:
                    sel = rng.sample(raters, a.base)
                    vals = [it["passes"][r] for r in sel]
                    if len(set(vals)) > 1:
                        sel += [r for r in rng.sample(raters, 2) if r not in sel]
                    arm[it["id"]] = {r: it["passes"][r] for r in sel}
                    spend += len(sel)
            f = flat(live, raters, spend, random.Random(2000 + s))
            la, ea = score(arm, truth)
            lb, eb = score(f, truth)
            deltas.append((la - lb, ea - eb))
        return (statistics.mean(d[0] for d in deltas) * 100,
                statistics.mean(d[1] for d in deltas) * 100,
                sum(1 for d in deltas if d[0] < 0 and d[1] < 0))

    print(f"  pool {len(items)} items, {len(raters)} raters, key {a.gold_key!r}, "
          f"{a.seeds} seeds, {a.base} passes/item base\n")
    for pid in ("gold-honeypots", "human-audit-sample", "tiered-adjudication"):
        dl, de, both = run(pid)
        print(f"  {pid}")
        for sig, rec, w in corpus_price(pid)[:3]:
            print(f"      corpus price   {sig:<22} adopted {rec['adopted']:>2} failed "
                  f"{rec['failed']:>2}  -> floor {w:.3f}")
        print(f"      pool says      load {dl:+.1f} pts, error {de:+.1f} pts vs flat, "
              f"both-right {both}/{a.seeds}")
        best = corpus_price(pid)[0][2] if corpus_price(pid) else 0.0
        verdict = ("PRICE HOLDS — quoted as sound, and it is" if best >= 0.4 and de < 0 else
                   "PRICE OPTIMISTIC — quoted as sound, but it trades quality for load" if best >= 0.4
                   else "PRICE HONEST — quoted as weak, and it is weak" if de >= 0
                   else "PRICE PESSIMISTIC — quoted as weak, does better than that")
        print(f"      -> {verdict}\n")
    print("  A price HOLDS when the corpus's record and the pool's behaviour agree. That is what an")
    print("  idea tool owes the person choosing: not the right answer, an honest cost on each option.")


if __name__ == "__main__":
    main()
