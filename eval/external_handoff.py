#!/usr/bin/env python3
"""Score the A/B arms with the agreement layer deciding what ships, instead of the harness grading itself.

ab_tiered_adjudication.py builds the arms AND scores them. That is one script marking its own
homework. This hands each arm to an external agreement layer, lets IT route every item, and scores
only what it says can ship without an adjudicator.

  python3 -m <layer> queue <arm>.json --pages <arm>_pages.json --key <arm>_key.json

`<layer>` is a separate inter-annotator-agreement tool, not part of this repo and not released. What
matters here is the SHAPE of the contract, not the tool: it reads a pool of passes, routes every
item to auto-accept or adjudicate, and will not hand back a verdict it cannot stand behind. Any
layer with those three properties can take its place.

Every item the layer queues is one a human or model must be paid to settle; every item it does not
queue, it is willing to auto-accept on consensus. So an arm has two numbers that matter operationally
and that the internal scorer never showed:

  ADJUDICATION LOAD  the share of items it sends to a person. The pattern's whole promise is that
                     this is small and well-chosen.
  SILENT ERROR       the items the layer auto-accepts where the consensus is WRONG against the
                     held-out truth panel. These are the ones that ship broken with nobody looking.

Silent error is the number that decides a workflow, and it is invisible to the tail accuracy the
internal harness reports: an arm can win the contested tail and still ship more quiet mistakes.

  python3 eval/external_handoff.py --pool <crossed>.json --arms <dir written by --write-pools>
"""
import argparse, collections, glob, json, os

import ab_tiered_adjudication as ab


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True, help="the full crossed pool the truth panel comes from")
    ap.add_argument("--arms", required=True, help="directory of arm pools + the layer's *_pages.json")
    ap.add_argument("--truth", type=int, default=61)
    ap.add_argument("--seed", type=int, default=22)
    a = ap.parse_args()

    full = json.load(open(a.pool))
    raters = sorted(full["items"][0]["passes"])
    truth_ids, _ = ab.split_raters(raters, a.truth, a.seed)
    truth = {it["id"]: ab.plurality([v for r, v in it["passes"].items() if r in truth_ids])
             for it in full["items"]}
    majority = collections.Counter(v for v in truth.values() if v).most_common(1)[0][0]

    print(f"truth panel: {a.truth} held-out raters, majority label {majority!r}")
    print(f"{'arm':<20}{'adjudication load':>19}{'auto-accepted':>15}{'silent errors':>15}"
          f"{'auto-accept acc':>17}")

    for pool_path in sorted(glob.glob(os.path.join(a.arms, "arm_*.json"))):
        name = os.path.basename(pool_path)[:-5]
        if name.endswith("_pages") or name.endswith("_key"):
            continue
        pages_path = os.path.join(a.arms, f"{name}_pages.json")
        if not os.path.exists(pages_path):
            print(f"{name:<20}  no pages — run the agreement layer queue on it first")
            continue
        pool = json.load(open(pool_path))
        queued = {p["item_id"] for p in json.load(open(pages_path))["pages"]
                  if p.get("route") == "adjudicate"}

        auto, wrong, scored = 0, 0, 0
        for it in pool["items"]:
            if it["id"] in queued or truth.get(it["id"]) is None:
                continue
            auto += 1
            scored += 1
            # the layer auto-accepts on consensus, so the shipped label is what its passes agree on.
            g = ab.plurality(list(it["passes"].values()))
            if g != truth[it["id"]]:
                wrong += 1
        n = len(pool["items"])
        # On how much evidence did it decide to ship? A low adjudication load is only a virtue if
        # the arm is not simply deciding on fewer raters — three who agree is a weaker signal than
        # five, and the difference shows up as silent error, not as load.
        ev = collections.Counter(len(it["passes"]) for it in pool["items"]
                                 if it["id"] not in queued and truth.get(it["id"]) is not None)
        print(f"{name:<20}{len(queued)/n:>18.1%}{auto:>15}{wrong:>15}"
              f"{(scored-wrong)/scored if scored else float('nan'):>17.1%}"
              f"   on {'/'.join(f'{k}x{v}' for k, v in sorted(ev.items()))}")

    print("\n  adjudication load = items the agreement layer sends to a person (the arm's human cost)")
    print("  silent errors     = auto-accepted items whose consensus is wrong; these ship unseen")
    print("  on NxM            = M auto-accepts were decided by N agreeing raters. Compare these")
    print("                      before reading a low load as routing skill: an arm that decides on")
    print("                      a smaller panel agrees more often and ships more silent error.")


if __name__ == "__main__":
    main()
