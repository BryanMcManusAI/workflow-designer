#!/usr/bin/env python3
"""An adjudicator whose standard does not change with how deep an arm bought.

judgelab's `answer --majority N` resolves a disputed unit when N passes share a reading. N is
absolute, so across arms of different depth it is not one standard:

  --majority 2  on a 3-pass item wants 67% of the evidence; on a 6-pass item it wants 33%.
  --majority 3  on a 6-pass item wants 50%; on a 3-pass item it is UNSATISFIABLE, because three
                passes that disagree can never have three sharing a reading.

That is why the loop's gate verdicts were not comparable: a tiered or audit design spends unevenly
BY CONSTRUCTION, so any fixed N either flatters the deep arm or cannot resolve the shallow one. The
first run used 3, the second had to use 2, and neither verdict could be read against the other.

This writes the same answers CSV under a PROPORTIONAL rule: a reading holds when strictly more than
half of THAT ITEM'S passes share it. Three passes need 2, four need 3, six need 4. The evidentiary
standard is identical at every depth, so an arm that buys more passes gets more resolution only when
those passes actually agree — which is the thing being measured, not an artifact of the setting.

Units with no such majority are written as `none of the readings`, exactly as a human adjudicator
who could not call it would leave them, so their cost stays visible instead of vanishing.

  python3 eval/proportional_answer.py --pages P.json --out A.csv
"""
import argparse, collections, csv, json


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pages = json.load(open(a.pages))["pages"]
    rows, held, unresolved = [], 0, 0
    depths = collections.Counter()
    for pg in pages:
        n = len(pg["passes"])
        depths[n] += 1
        for unit in pg.get("disputed", []):
            counts = collections.Counter()
            labels = {}
            for reading in unit["readings"]:
                sig = json.dumps(reading["spans"], sort_keys=True)
                counts[sig] += 1
                labels.setdefault(sig, []).append(reading["label"])
            sig, c = counts.most_common(1)[0]
            # Strictly more than half of this item's passes, so a 2-2 split never resolves.
            if c * 2 > n:
                verdict = sorted(labels[sig])[0]
                held += 1
            else:
                verdict = "none of the readings"
                unresolved += 1
            rows.append({"item": pg["item_id"], "start": unit["unit"][0], "end": unit["unit"][1],
                         "holds": verdict, "rubric_open": "no", "note": ""})

    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item", "start", "end", "holds", "rubric_open", "note"])
        w.writeheader()
        w.writerows(rows)
    print(f"  {held} of {held + unresolved} disputed units held by a strict majority of the item's "
          f"own passes; {unresolved} left uncalled")
    print(f"  page depths: {dict(sorted(depths.items()))} -> threshold is per-item, not fixed")
    print(f"  written to {a.out}")


if __name__ == "__main__":
    main()
