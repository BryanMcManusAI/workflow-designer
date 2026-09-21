#!/usr/bin/env python3
"""Leave-one-out: from a card's SETUP alone, with that card removed from the corpus, does the engine
name the failures that workflow actually had?

The existing run_eval.py scores retrieval and risk against gold.yaml — hand-drafted labels. This row
uses the corpus's own answer key instead: each card's failure_modes carry evidence=REPORTED (documented
in the published account of that workflow) or INFERRED (the corpus author's reasoning). Only REPORTED
is scored.

Why the tail. Across the 45 cards, REPORTED signatures run sampling_frame 42%, under_specification 38%,
confounded 36%. Naming those three costs nothing and scores well, so raw recall measures the prior, not
the engine. The row is scored on the TAIL: REPORTED signatures outside that top three. 30 cards have at
least one.

CHECKS STATED BEFORE THE ROW RAN (thresholds are not moved; a miss is recorded):
  1. tail recall @k=3 beats the frequency-weighted random baseline by >= 15 points
  2. tail recall @k=3 beats the single-axis (modality-only) baseline by >= 5 points
  3. the engine names >= 1 REPORTED tail signature on >= 10 of the 30 tail cards @k=3
  4. every signature emitted or keyed resolves against one declared vocabulary; off-vocabulary values
     are counted and printed, never dropped. Expect exactly 1 (instrumentation-bug).

ALL FOUR WERE MET AND THE ROW STILL FAILS. Added after the first run, and the reason the row is kept:
the BEST FIXED TRIPLE control — the same three signatures named for every card, no analysis at all —
scores 0.53 tail recall against the engine's 0.34. None of the four stated checks was the right
control; weighted-random (0.15), single-axis (0.23) and constant-top-3 (0.00 by construction, since
the tail is defined as outside it) are all weaker than the engine and all weaker than a good constant.
The thresholds are not moved and checks 1-4 are recorded as met. The row records that the engine loses
to a constant, and why: its ordering is dominated by corpus frequency, so sampling_frame and confounded
(REPORTED on 42% and 36% of cards) take two of the three slots on nearly every card and neither can
score, the top-3 takes only 5 distinct values across 30 cards, and 9 of the 12 tail signatures are
unreachable at k=3 — including class_imbalance (keyed on 7 cards), drift (4) and priming (4).
NEXT STEP THE ROW LEAVES: rank by lift over base rate, not by raw analogue count.

TAKEN 2026-09-21. analyze_interrogate now ranks by lift at a support floor of 2, with cost
demoted to a tiebreak. The engine's own ordering went 0.34 -> 0.49 and its distinct top-3 sets
5 -> 18, so it now beats the honest leave-one-out constant (0.41) instead of losing to it. The
paragraph above is left as written: it is the record of the row that failed, and the reason the
change was made. The engine and reference rows below should now agree — they are the same
ranking reached two ways, and a gap between them means the port drifted.

  PYTHONPATH=engine python3 eval/loo_signatures.py
"""
import collections, copy, os, random, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
import engine  # noqa: E402

K = 3
RANDOM_REPEATS = 200
TOP3 = ("sampling_frame", "under_specification", "confounded")


def reported(card):
    return [fm["signature"] for fm in (card.get("failure_modes") or [])
            if (fm.get("evidence") or "").upper().startswith("REPORTED")]


def stub_from(card):
    """The setup a designer would type. Signatures and failure modes are withheld."""
    return {"goal": card.get("title", ""), "modality": card.get("modality"),
            "task_structure": card.get("task_structure"),
            "annotator_structure": card.get("annotator_structure"),
            "qa_mechanism": list(card.get("qa_mechanism") or []),
            "uses_patterns": [], "addressed_signatures": []}


def engine_named(idx_minus, stub, k):
    """The engine's own ordering: open rows first (since 2026-09-21 it sorts by lift, support floor 2,
    cost as tiebreak — so this now tracks engine_named_lift below rather than contrasting with it), then
    defended, then what backwards calls good. Capped at k, because an advisor that names everything
    has said nothing."""
    inter = engine.analyze_interrogate(idx_minus, stub)
    ordered = [r["signature"] for r in inter["open"]]
    for s in list(inter["defended"]) + list(engine.analyze_backwards(idx_minus, stub)["good_means"]):
        if s not in ordered:
            ordered.append(s)
    return ordered[:k], len(ordered)


def engine_named_lift(idx_minus, stub, k, priority_first=False, min_support=1):
    """Same retrieved analogues, ranked by LIFT instead of raw count.

    lift = (share of the retrieved analogues carrying this signature)
           / (share of the whole corpus carrying it)

    Lift 1.0 means the signature is no more common here than everywhere, so it says nothing about
    this setup. Lift 3.0 means it is three times as concentrated in the analogues as in the corpus.
    min_support is the floor on how many analogues must carry a signature before its lift is trusted;
    without it a signature on one corpus card can top the list off a single analogue.
    """
    near, far = engine._near_far(idx_minus, stub)
    ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
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
        if sig in have or c < min_support:
            continue
        br = base.get(sig, 0) / N
        out.append((sig, ((c / n) / br) if br else 0.0, engine.signature_priority(sig, stub)))
    if not out:
        return [], 0
    out.sort(key=(lambda r: (-r[2], -r[1], r[0])) if priority_first else (lambda r: (-r[1], -r[2], r[0])))
    return [r[0] for r in out][:k], len(out)


def recall(named, key):
    key = set(key)
    return (len(key & set(named)) / len(key)) if key else None


def main():
    idx = engine.load_index()
    cards = idx["cards"]
    key = {cid: reported(c) for cid, c in cards.items()}
    tail_cards = [cid for cid, sigs in key.items() if set(sigs) - set(TOP3)]

    vocab = {s for sigs in key.values() for s in sigs}
    offvocab = sorted(s for s in vocab if not s.replace("_", "").isalpha() or "-" in s)

    rows = []
    for cid in tail_cards:
        card = cards[cid]
        minus = copy.deepcopy(idx)
        del minus["cards"][cid]
        stub = stub_from(card)
        named, n_named = engine_named(minus, stub, K)
        lift1, _ = engine_named_lift(minus, stub, K, min_support=1)
        lift2, _ = engine_named_lift(minus, stub, K, min_support=2)
        liftp, _ = engine_named_lift(minus, stub, K, priority_first=True, min_support=2)

        rest = {c: s for c, s in key.items() if c != cid}
        freq = collections.Counter(s for sigs in rest.values() for s in sigs)
        const = [s for s, _ in freq.most_common(K)]

        pool, weights = zip(*freq.items())
        rng = random.Random(hash(cid) & 0xFFFF)
        tailkey = sorted(set(key[cid]) - set(TOP3))
        rand_scores = []
        for _ in range(RANDOM_REPEATS):
            draw = set()
            while len(draw) < K:
                draw.add(rng.choices(pool, weights=weights, k=1)[0])
            rand_scores.append(recall(draw, tailkey))
        same_mod = [c for c, cc in cards.items() if c != cid and cc.get("modality") == card.get("modality")]
        mfreq = collections.Counter(s for c in same_mod for s in key[c])
        one_axis = [s for s, _ in mfreq.most_common(K)]

        rows.append(dict(id=cid, key=sorted(key[cid]), tailkey=tailkey, named=named, n_named=n_named,
                         eng=recall(named, tailkey), const=recall(const, tailkey),
                         lift1=recall(lift1, tailkey), lift2=recall(lift2, tailkey),
                         liftp=recall(liftp, tailkey), lift_named=lift2,
                         rand=statistics.mean(rand_scores), axis=recall(one_axis, tailkey),
                         hit=bool(set(named) & set(tailkey))))

    print(f"LEAVE-ONE-OUT, REPORTED signatures, scored on the TAIL   (k={K}, n={len(rows)} cards)")
    print("-" * 96)
    print(f"  {'card':<34} {'eng':>5} {'const':>6} {'rand':>6} {'axis':>6}  named@k")
    for r in sorted(rows, key=lambda r: -r["eng"]):
        print(f"  {r['id']:<34} {r['eng']:>5.2f} {r['const']:>6.2f} {r['rand']:>6.2f} {r['axis']:>6.2f}"
              f"  {','.join(r['named'])}")
    m = {k2: statistics.mean(r[k2] for r in rows) for k2 in ("eng", "const", "rand", "axis",
                                                             "lift1", "lift2", "liftp")}
    hits = sum(r["hit"] for r in rows)
    print("-" * 96)
    print(f"  {'MEAN tail recall':<34} {m['eng']:>5.2f} {m['const']:>6.2f} {m['rand']:>6.2f} {m['axis']:>6.2f}")
    print(f"  {'  ranked by LIFT (support>=1)':<34} {m['lift1']:>5.2f}")
    print(f"  {'  ranked by LIFT (support>=2)':<34} {m['lift2']:>5.2f}")
    print(f"  {'  cost first, then LIFT':<34} {m['liftp']:>5.2f}")
    print(f"  engine names {statistics.mean(r['n_named'] for r in rows):.1f} signatures before the cap")
    print()
    import itertools
    tk = {r["id"]: r["tailkey"] for r in rows}
    allsigs = sorted({s for sigs in key.values() for s in sigs})
    ids = list(tk)

    def sc(t, cids):
        return statistics.mean(len(set(t) & set(tk[c])) / len(tk[c]) for c in cids)

    # The ORACLE: the best single triple, chosen knowing every answer. Nobody could pick this in
    # advance; it is the ceiling a constant could reach, not a control.
    oracle = max(itertools.combinations(allsigs, K), key=lambda t: sc(t, ids))
    oracle_score = sc(oracle, ids)
    # The HONEST CONSTANT: for each card, the best triple chosen from the OTHER cards only. This is
    # what someone could actually pick in advance, and it is the control the engine has to beat.
    fixed_score = statistics.mean(
        len(set(max(itertools.combinations(allsigs, K), key=lambda t: sc(t, [c for c in ids if c != cid])))
            & set(tk[cid])) / len(tk[cid]) for cid in ids)
    print(f"  {'HONEST CONSTANT (leave-one-out)':<34} {fixed_score:>5.2f}")
    print(f"  {'ORACLE ceiling (knows the answers)':<34} {oracle_score:>5.2f}         "
          f"        {', '.join(oracle)}")
    for label, val in (("engine, as shipped", m["eng"]), ("reference impl, LIFT order", m["lift2"])):
        print(f"  -> {label:<28} {val:.2f}  "
              f"{'BEATS' if val > fixed_score else 'loses to'} the honest constant by "
              f"{abs(100*(val-fixed_score)):.1f} pts")
    print(f"  -> {len(set(tuple(sorted(r['named'])) for r in rows))} distinct top-{K} sets across {len(rows)} cards"
          f"  (lift: {len(set(tuple(sorted(r['lift_named'])) for r in rows))})")
    best_lift = max(("lift1", "lift2", "liftp"), key=lambda kk: m[kk])
    print(f"  -> best lift variant {best_lift} = {m[best_lift]:.2f}; "
          f"{'BEATS' if m[best_lift] > fixed_score else 'still loses to'} the fixed triple "
          f"({fixed_score:.2f}) by {abs(100*(m[best_lift]-fixed_score)):.1f} pts")
    print()
    c1 = 100 * (m["eng"] - m["rand"]); c2 = 100 * (m["eng"] - m["axis"])
    for n, txt, got, bar, ok in (
            (1, "tail recall beats weighted-random by >= 15 pts", f"{c1:+.1f} pts", 15, c1 >= 15),
            (2, "tail recall beats single-axis by >= 5 pts", f"{c2:+.1f} pts", 5, c2 >= 5),
            (3, ">= 1 tail signature named on >= 10 of 30 cards", f"{hits} of {len(rows)}", 10, hits >= 10),
            (4, "off-vocabulary signatures counted, expect 1", f"{len(offvocab)} {offvocab}", 1, len(offvocab) == 1)):
        print(f"  CHECK {n}  {'MET    ' if ok else 'NOT MET'}  {txt:<48} {got}")


if __name__ == "__main__":
    main()
