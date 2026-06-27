#!/usr/bin/env python3
"""Generate a rater kit so a human can AUDIT the eval gold — the step that turns the recommendation
eval's numbers from Claude-drafted to trustworthy.

The gold (eval/gold.yaml) was drafted by Claude as a stand-in; until a human confirms which prior
recipes are genuinely analogous and which risks genuinely apply, the eval scores rest on unvalidated
gold (the tool's own ground-truth-anchoring warning). This emits a single self-contained markdown
sheet: per prompt, the drafted candidates with a clear Y/N, room to add, and reference appendices of
the full option space (all recipes + the signature glossary) so the rater isn't guessing blind.

Polarity is uniform and explicit: Y = relevant / applies, N = not. (No A/B, no shuffle — this is gold
confirmation, not a blind preference task.)

  python3 eval/make_rater_kit.py > eval/rater_kit.md
"""
import os

import engine
import run_eval

HERE = os.path.dirname(os.path.abspath(__file__))

# Plain-language gloss of each failure signature, so a rater judges meaning, not jargon.
SIGNATURE_GLOSS = {
    "confounded": "a spurious cue (length, source, tier) rides along with the real signal",
    "unanchored": "no gold / ground truth to check labels against",
    "self_affinity": "a model judge favors its own family's outputs",
    "inflation": "the bar creeps up; everything starts passing",
    "underpowered": "too few items/reps to support the claim",
    "priming": "item order or position contaminates the label",
    "sampling_frame": "the labeled set isn't representative of deployment",
    "drift": "guidelines / acceptance bar move over the campaign",
    "bottleneck": "one stage (adjudication, expert review) gates throughput",
    "over_specification": "guidelines so rigid they break on edge cases",
    "under_specification": "so loose competent annotators disagree (low IAA)",
    "label_leakage": "the label is derivable from a feature it shouldn't be / eval contaminated by training",
    "class_imbalance": "rare-but-important classes under-sampled",
    "gaming": "annotators optimize the pay/quota, not quality (Goodhart)",
}


def main():
    idx = engine.load_index()
    items = run_eval.load_gold()
    out = []
    w = out.append

    w("# Workflow Designer — Gold Audit Kit\n")
    w("You're confirming the answer key for the recommendation eval. For each workflow below, judge:\n")
    w("1. **Analogous recipes** — is each drafted recipe a genuinely useful prior example for this "
      "workflow? Mark **Y** (yes, relevant) or **N** (no). Add any the draft missed.\n")
    w("2. **Risks** — does each drafted failure risk genuinely apply to this kind of workflow? "
      "**Y** / **N**. Add any missed.\n")
    w("Polarity is uniform: **Y = relevant / applies, N = not.** Appendices list the full option "
      "space (every recipe, every risk) so you can add from a known menu.\n")
    w("\n---\n")

    for i, it in enumerate(items, 1):
        w(f"\n## {i}. {it['id']}\n")
        w(f"> **Goal:** {it['goal']}  ")
        w(f"\n> {it['modality']} / {it['task_structure']} / {it['annotator_structure']}\n")
        w("\n**Analogous recipes** (mark Y/N, strike-through to drop):\n")
        for cid in it["relevant_cards"]:
            title = idx["cards"].get(cid, {}).get("title", "")
            w(f"- [ ] `{cid}` — {title}   **Y / N**")
        w("- _Add others:_ ______________________________________________\n")
        w("\n**Risks that genuinely apply** (mark Y/N):\n")
        for s in it["expected_risks"]:
            w(f"- [ ] `{s}` — {SIGNATURE_GLOSS.get(s, '')}   **Y / N**")
        w("- _Add others:_ ______________________________________________\n")
        w("\n---\n")

    w("\n## Appendix A — every recipe (the menu for 'add others')\n")
    for cid in sorted(idx["cards"]):
        w(f"- `{cid}` — {idx['cards'][cid].get('title','')} "
          f"[{idx['cards'][cid]['modality']}/{idx['cards'][cid]['task_structure']}]")
    w("\n## Appendix B — every risk signature\n")
    for s, g in SIGNATURE_GLOSS.items():
        w(f"- `{s}` — {g}")

    print("\n".join(out))


if __name__ == "__main__":
    main()
