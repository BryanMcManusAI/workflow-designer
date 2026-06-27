#!/usr/bin/env python3
"""Corpus-health report — make provenance a VISIBLE, re-runnable metric.

The corpus promises "every card carries >=1 OBSERVED (REPORTED) failure mode, not imagined." This
checks that promise against the compiled index and surfaces where it's thin: untagged failure modes
(no REPORTED/INFERRED at all), cards with zero REPORTED grounding, and the overall REPORTED ratio.

This is the tool's own `ground-truth-anchoring` principle turned on itself — the gold is the thing
most likely to be quietly wrong, so we measure it. Stdlib only; reads index.json.

  python3 engine/corpus_health.py            # the report
  python3 engine/corpus_health.py --gate     # exit non-zero if any card is untagged or 0-REPORTED
"""
import argparse
import sys

import engine


def classify(fm):
    ev = (fm.get("evidence") or "").upper()
    if ev.startswith("REPORTED"):
        return "reported"
    if ev.startswith("INFERRED"):
        return "inferred"
    return "untagged"


def card_health(card):
    counts = {"reported": 0, "inferred": 0, "untagged": 0}
    for fm in card.get("failure_modes", []):
        counts[classify(fm)] += 1
    total = sum(counts.values())
    return {"id": card["id"], "total": total, **counts,
            "ratio": (counts["reported"] / total) if total else 0.0}


def report(idx):
    rows = [card_health(c) for c in idx["cards"].values()]
    tot = {k: sum(r[k] for r in rows) for k in ("total", "reported", "inferred", "untagged")}
    overall = (tot["reported"] / tot["total"]) if tot["total"] else 0.0
    untagged_cards = sorted([r for r in rows if r["untagged"]], key=lambda r: -r["untagged"])
    zero_reported = sorted([r for r in rows if r["reported"] == 0], key=lambda r: r["id"])
    return {"rows": rows, "totals": tot, "overall_ratio": overall,
            "untagged_cards": untagged_cards, "zero_reported": zero_reported}


def render(h):
    t = h["totals"]
    print("CORPUS PROVENANCE HEALTH")
    print("-" * 40)
    print(f"  failure modes: {t['total']}  |  REPORTED {t['reported']}  "
          f"INFERRED {t['inferred']}  UNTAGGED {t['untagged']}")
    bar = round(24 * h["overall_ratio"])
    print(f"  REPORTED ratio: [{'#'*bar}{'.'*(24-bar)}] {h['overall_ratio']*100:.0f}%")
    print(f"\n  UNTAGGED cards ({len(h['untagged_cards'])}) — no provenance tag, the discipline's own gap:")
    for r in h["untagged_cards"]:
        print(f"    {r['untagged']:>2} untagged / {r['total']} modes — {r['id']}")
    print(f"\n  ZERO-REPORTED cards ({len(h['zero_reported'])}) — no OBSERVED failure mode (claim says >=1):")
    for r in h["zero_reported"]:
        print(f"    {r['id']}  ({r['inferred']} inferred, {r['untagged']} untagged)")


def main():
    ap = argparse.ArgumentParser(description="Corpus provenance-health report.")
    ap.add_argument("--gate", action="store_true",
                    help="exit non-zero if any card is untagged or has zero REPORTED modes")
    args = ap.parse_args()
    h = report(engine.load_index())
    render(h)
    if args.gate and (h["untagged_cards"] or h["zero_reported"]):
        print("\nGATE FAILED: untagged or zero-REPORTED cards remain.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
