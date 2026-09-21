#!/usr/bin/env python3
"""Leave-one-out, second half of step 1: when the engine names a risk correctly, is the DEFENSE it
attaches any good?

loo_signatures.py checked which failures the engine names. This checks what it proposes to do about
them. Same setup: hide a card, show only its setup, rank by lift (the ranking that row left), and look
at the patterns the engine attaches to each signature it got right.

The answer key is the card itself:
  - uses_patterns  — what that workflow actually ran. A REPORTED failure is BY DEFINITION one those
                     patterns did not prevent, so proposing one of them as the defense is proposing a
                     defense known to have failed there.
  - caught_by      — free text (81 distinct values over 92 modes), so it cannot be matched to the 25
                     pattern ids. But 30 of the 92 start with UNGUARDED, and that IS a clean binary:
                     did anything catch this failure at all.

CHECKS STATED BEFORE THE ROW RAN (thresholds are not moved; a miss is recorded):
  A. of the defenses proposed for correctly-named signatures, <= 25% were already adopted by the
     failing card
  B. the engine's guarded/unguarded call beats the better constant by >= 5 points
  C. the engine proposes at least one defense for >= 70% of the signatures it names

  python3 eval/loo_patterns.py
"""
import collections, copy, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
sys.path.insert(0, HERE)
import engine  # noqa: E402
from loo_signatures import reported, stub_from, engine_named_lift, K, TOP3  # noqa: E402


def main():
    idx = engine.load_index()
    cards = idx["cards"]

    # answer key: per card, per REPORTED signature, was anything recorded as catching it
    key = {}
    for cid, c in cards.items():
        rows = {}
        for fm in (c.get("failure_modes") or []):
            if (fm.get("evidence") or "").upper().startswith("REPORTED"):
                rows[fm["signature"]] = not (fm.get("caught_by") or "").upper().startswith("UNGUARD")
        key[cid] = rows

    tail = [cid for cid, r in key.items() if set(r) - set(TOP3)]

    proposed_total = proposed_already = 0
    cov_named = cov_with_defense = 0
    guard_rows = []
    detail = []
    for cid in tail:
        card = cards[cid]
        minus = copy.deepcopy(idx)
        del minus["cards"][cid]
        stub = stub_from(card)
        stub["uses_patterns"] = list(card.get("uses_patterns") or [])   # realistic: it knows what you run
        named, _ = engine_named_lift(minus, stub, K, min_support=2)
        adopted = set(card.get("uses_patterns") or [])
        # the ENGINE'S OWN verdict, not merely whether a pattern exists
        verdict = {r["signature"]: r["unguarded"] for r in engine.analyze_interrogate(minus, stub)["open"]}
        for sig in named:
            cov_named += 1
            defs = [p for p in engine.patterns_defending(minus, sig)]
            if defs and not verdict.get(sig, False):
                cov_with_defense += 1
            if sig in key[cid]:                       # a signature the engine got RIGHT
                proposed_total += len(defs)
                already = [p for p in defs if p in adopted]
                proposed_already += len(already)
                guard_rows.append((key[cid][sig], not verdict.get(sig, False)))
                if already:
                    detail.append((cid, sig, already))

    print(f"LEAVE-ONE-OUT, the DEFENSE attached to a correctly-named risk   (k={K}, n={len(tail)} cards)")
    print("-" * 92)

    a = (100 * proposed_already / proposed_total) if proposed_total else 0.0
    print(f"  A  proposed defenses on correctly-named signatures : {proposed_total}")
    print(f"     of those, already adopted by the failing card   : {proposed_already}  ({a:.1f}%)")
    for cid, sig, ps in detail[:8]:
        print(f"       {cid:<34} {sig:<20} {', '.join(ps)}")
    if len(detail) > 8:
        print(f"       ... and {len(detail)-8} more")

    n = len(guard_rows)
    if n:
        truth_guarded = sum(t for t, _ in guard_rows)
        acc = sum(t == p for t, p in guard_rows) / n
        const = max(truth_guarded, n - truth_guarded) / n
        print(f"\n  B  guarded/unguarded call on {n} correctly-named signatures")
        print(f"     record says something caught it : {truth_guarded}/{n} ({100*truth_guarded/n:.0f}%)")
        print(f"     engine accuracy                 : {100*acc:.1f}%   better constant {100*const:.1f}%")
        tp = sum(t and p for t, p in guard_rows); fp = sum((not t) and p for t, p in guard_rows)
        fn = sum(t and not p for t, p in guard_rows); tn = sum((not t) and (not p) for t, p in guard_rows)
        print(f"     both guarded {tp} · engine guarded, record UNGUARDED {fp} · "
              f"engine unguarded, record guarded {fn} · both unguarded {tn}")
    else:
        acc = const = 0.0

    cov = (100 * cov_with_defense / cov_named) if cov_named else 0.0
    print(f"\n  C  signatures named with at least one defense attached : "
          f"{cov_with_defense}/{cov_named}  ({cov:.1f}%)")

    print("-" * 92)
    for nm, txt, got, ok in (
            ("A", "already-adopted defenses <= 25%", f"{a:.1f}%", a <= 25),
            ("B", "guarded call beats the constant by >= 5 pts",
             f"{100*(acc-const):+.1f} pts", (acc - const) >= 0.05),
            ("C", "a defense attached on >= 70% of named signatures", f"{cov:.1f}%", cov >= 70)):
        print(f"  CHECK {nm}  {'MET    ' if ok else 'NOT MET'}  {txt:<48} {got}")


if __name__ == "__main__":
    main()
