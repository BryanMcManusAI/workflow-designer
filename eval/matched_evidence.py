#!/usr/bin/env python3
"""Separate "routes better" from "decides on a smaller panel".

The the agreement layer hand-off found arm A sending 4 points fewer items to a person than flat, and shipping
3 silent errors where flat shipped 0 — but every one of A's auto-accepts rested on 3 agreeing
raters against flat's 4 or 5. A was not necessarily routing better; it was deciding on less
evidence. This row separates the two.

IT CANNOT BE DONE WITH ONE CONTROL, and that is the finding rather than a limitation. At equal
budget a tiered design MUST carry a smaller tier 1, because it holds spend back to afford the
escalation. Budget and evidence cannot both be matched. So each tier-1 size k is run against two
flats, and the pair of answers is the honest result:

  FLAT @ SAME BUDGET    what the money would have bought spread evenly. Tiered decides on less
                        evidence here, so any load/silent-error gap is confounded — this is the
                        comparison the earlier rows reported.
  FLAT @ SAME PANEL k   auto-accepts rest on identical evidence, so load and silent error are
                        comparable. Tiered spends MORE (it adds the escalation on top), so a win
                        here says the escalation was worth buying, not that it was free.

Read together: if tiered beats flat@panel on the tail, routing earns its extra spend. If tiered's
load advantage over flat@budget disappears at flat@panel, that advantage was panel size all along.

Routing is computed here as "the shipped passes disagree", which is what an external agreement layer
does; it was validated against the real thing in eval/external_handoff.py, where the layer queued
exactly the 178 items this rule selects.

READING THE TABLE. Two things in it are properties of the substrate, not of the pattern:
  - tiered's tier 1 draws from JUNIORS (the 47 lower-agreement raters), while a flat arm draws from
    all 62. So tiered's tier 1 splits more often than a flat panel of the same size. That makes the
    evidence-matched contrast conservative for tiered on the tier-1 side, and it means the contrast
    measures "routing plus senior escalation", not routing alone. Routing alone was isolated in
    eval/ab_tiered_adjudication.py against the counterfeit arm (+7.1 pts).
  - an EVEN flat panel ties (2-2 over three labels), and a tie is scored wrong. That is why
    flat @ same panel (4) dips below both its neighbours. Real property of even panels under
    plurality, not a harness fault.

  python3 eval/matched_evidence.py --pool <crossed>.json
"""
import argparse, collections, json, random, statistics

import ab_tiered_adjudication as ab


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool", required=True)
    ap.add_argument("--truth", type=int, default=61)
    ap.add_argument("--seniors", type=int, default=15)
    ap.add_argument("--tier2", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=100)
    ap.add_argument("--seed", type=int, default=22)
    a = ap.parse_args()

    D = json.load(open(a.pool))
    items = D["items"]
    raters = sorted(items[0]["passes"])
    truth_ids, working = ab.split_raters(raters, a.truth, a.seed)
    truth = {it["id"]: ab.plurality([v for r, v in it["passes"].items() if r in truth_ids])
             for it in items}
    seniors, juniors = ab.qualify(items, working, a.seniors)
    others = [r for r in working if r not in set(seniors)]

    def margin(it):
        c = collections.Counter(v for r, v in it["passes"].items() if r in truth_ids).most_common()
        return (c[0][1] - (c[1][1] if len(c) > 1 else 0)) / a.truth

    contested = [it["id"] for it in items if truth[it["id"]] is not None and margin(it) < 0.5]
    scored = [it["id"] for it in items if truth[it["id"]] is not None]

    print(f"pool {len(items)} items | truth panel {a.truth} | seniors {a.seniors} | "
          f"escalate to {a.tier2} | {a.repeats} panels\n")
    print(f"  {'arm':<26}{'tail acc':>10}{'adj load':>10}{'silent':>8}{'spend':>8}{'decided on':>13}")

    def summarize(label, accs, loads, silents, spends, ev):
        print(f"  {label:<26}{statistics.mean(accs):>9.1%}{statistics.mean(loads):>10.1%}"
              f"{statistics.mean(silents):>8.1f}{statistics.mean(spends):>8.0f}{ev:>13}")
        return statistics.mean(accs)

    results = {}
    for k in (3, 4, 5):
        rowsets = {"tiered": ([], [], [], []), "flat_budget": ([], [], [], []),
                   "flat_panel": ([], [], [], [])}
        for i in range(a.repeats):
            sd = a.seed * 1000 + i
            t1 = ab.tier1_draw(items, juniors, k, random.Random(sd))
            esc = ab.split_items(items, t1)
            spend = len(items) * k + len(esc) * a.tier2
            r2 = random.Random(sd + 700000)
            gold = {}
            for it in items:
                used = list(t1[it["id"]]) + (r2.sample(seniors, a.tier2) if it["id"] in esc else [])
                vals = [it["passes"][r] for r in used]
                if it["id"] in esc:
                    g = ab.plurality([it["passes"][r] for r in used[k:]])
                    gold[it["id"]] = g if g is not None else ab.plurality(vals)
                else:
                    gold[it["id"]] = vals[0]
            sil = sum(1 for i2 in scored if i2 not in esc and gold[i2] != truth[i2])
            rowsets["tiered"][0].append(ab.score(gold, truth, contested))
            rowsets["tiered"][1].append(len(esc) / len(items))
            rowsets["tiered"][2].append(sil)
            rowsets["tiered"][3].append(spend)

            for name, budget in (("flat_budget", spend), ("flat_panel", len(items) * k)):
                rf = random.Random(sd + (500000 if name == "flat_budget" else 600000))
                n, extra = divmod(budget, len(items))
                bumped = set(rf.sample([x["id"] for x in items], extra))
                g2, load, sil2 = {}, 0, 0
                for it in items:
                    sel = rf.sample(working, n + (1 if it["id"] in bumped else 0))
                    vals = [it["passes"][r] for r in sel]
                    split = len(set(vals)) > 1
                    load += split
                    g2[it["id"]] = ab.plurality(vals)
                    if not split and truth[it["id"]] is not None and g2[it["id"]] != truth[it["id"]]:
                        sil2 += 1
                rowsets[name][0].append(ab.score(g2, truth, contested))
                rowsets[name][1].append(load / len(items))
                rowsets[name][2].append(sil2)
                rowsets[name][3].append(budget)

        print(f"\n  tier-1 = {k}")
        results[k] = {}
        for nm, ev in (("tiered", f"{k}x auto"), ("flat_budget", "varies"), ("flat_panel", f"{k}x all")):
            lab = {"tiered": f"tiered (tier-1={k})", "flat_budget": "  flat @ same budget",
                   "flat_panel": f"  flat @ same panel ({k})"}[nm]
            results[k][nm] = summarize(lab, *rowsets[nm], ev)
        br = random.Random(a.seed)
        for x, y, lab in (("tiered", "flat_panel", "routing, evidence matched"),
                          ("tiered", "flat_budget", "routing, budget matched  ")):
            d = [p - q for p, q in zip(rowsets[x][0], rowsets[y][0])]
            b = sorted(statistics.mean(br.choices(d, k=len(d))) for _ in range(2000))
            print(f"    {lab}  {100*statistics.mean(d):+6.1f} pts  "
                  f"95% CI [{100*b[int(.025*len(b))]:+.1f}, {100*b[int(.975*len(b))-1]:+.1f}]")


if __name__ == "__main__":
    main()
