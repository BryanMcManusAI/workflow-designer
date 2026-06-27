# Principles — the third tier (the intellectual backbone)

> **Status: seed / proposal.** `library.yaml` holds 6 fully-distilled principles + 4 stubs.
> The engine/UI wiring below is designed but not yet built — it's the next step pending a nod on
> the tier's *shape*.

## Why this tier exists

The cards are the **how** (45 buildable recipes). The patterns are the reusable **how-pieces** (24).
This tier is the **why**: the methodology constructs that define *good data in an AI experiment*,
each grounded in the paper that establishes it.

Today the tool's definition of good is **negative and self-referential** — `analyze_backwards`
reads "good = free of the failure signatures," and the signatures are an in-house vocabulary. The
spec stress-test probes are hardcoded prose with no citation. This tier supplies the **positive,
literature-grounded** definition the backwards move was missing.

The key economy: the backbone is **not a new vocabulary**. Each principle is the construct whose
*absence* is a signature you already have:

| Principle | = absence of | secured by patterns | established by |
|-----------|--------------|---------------------|----------------|
| Construct validity | confounded · label_leakage · unanchored | partial-input-baseline, cross-family-judges | Gururangan 2018; Jacobs & Wallach 2021 |
| Internal validity | confounded · priming | order-randomization | Geirhos 2020; Torralba & Efros 2011 |
| Reliability | under/over_specification | inter-annotator-agreement, edge-case-guidelines | Krippendorff; Dawid–Skene 1979 |
| External validity | sampling_frame · class_imbalance | coverage-routing, split-isolation | nuScenes 2020; Datasheets 2021 |
| Ground-truth anchoring | unanchored · self_affinity | human-gold-anchor, tamper-to-ground-truth | Northcutt 2021; Zheng 2023 |
| Contamination control | label_leakage | split-isolation | SWE-Bench+ 2024 |
| Statistical power | underpowered | powered-eval-split | Card et al. 2020 |
| Incentive alignment | gaming | gold-honeypots, engagement-gate | Kennedy 2020 |
| Construct stability | drift · inflation | lock-then-score | (drift practice) |
| Provenance/documentation | *(cross-cutting)* | → motivates `provenance-datasheet` | Datasheets 2021; Bender & Friedman 2018 |

`bottleneck` and `priming` are **operational**, not validity constructs — that boundary is a
finding to surface, not a gap.

## The graph it joins

```
principle ──protects_against──▶ failure_signature   (negative-of)
principle ──operationalized_by─▶ pattern             (how to secure it)
principle.evidence[].seen_in ──▶ workflow card        (where it played out)
principle.evidence[].source ───▶ the paper            (what proves it — the "academic trace")
```

No new matching logic. Build-time extraction only (like authoring a card). Runtime stays
stdlib + deterministic — **the no-LLM-in-the-loop guarantee is intact.**

## What changes in `backwards-from-good`

**Before** (signatures → patterns, no why):

```
"GOOD preference_ranking DATA MEANS FREE OF
  confounded, label_leakage, unanchored, self_affinity, ...
TO GUARANTEE THAT, THE WORKFLOW NEEDS
  [confounded]  -> cross-family-judges
  ...
```

**After** (principle → signature → pattern → paper):

```
"GOOD preference_ranking DATA HAS
  • Construct validity — the preference measures quality, not length/style
      (absence of: confounded, label_leakage) secured by cross-family-judges, partial-input-baseline
      established by Gururangan 2018 (hypothesis-only ~67% on SNLI) — seen in nli-snli-artifacts
  • Ground-truth anchoring — a validated gold the judge is checked against
      (absence of: unanchored, self_affinity) secured by human-gold-anchor, cross-family-judges
      established by Zheng 2023 (LLM-judge self-enhancement bias) — seen in eval-chatbot-arena
  ...
BUT FIRST — IS YOUR 'GOOD' ACTUALLY GOOD?
  Construct validity probe: can a partial-input baseline predict the label? (Gururangan 2018)
```

The spec stress-test stops being house prose and starts **citing the study** behind each probe.

## Engine wiring (designed, small, deterministic)

1. `build_index.py`: read `principles/library.yaml` → `index["principles"]` (one block, mirrors the
   patterns block). Build a reverse map `signature → [principle ids]`.
2. `engine.py`: a `principles_for(idx, signatures)` lookup. `analyze_backwards` groups its
   `good_means` signatures under the principle that protects them and attaches `evidence` (paper +
   seen_in). `SPEC_THREATS` probes gain a `source:` pulled from the principle's evidence.
3. Renderers / `serve.py` step 4 ("The rationale"): lead with the principles + citations instead of
   the bare signature list. The static site gets a "What good data means" panel.
4. Tests: every `protects_against` is a real signature; every `operationalized_by` is a real
   pattern; every `seen_in` is a real card (the guard that keeps the backbone honest).

## Growth loop (Bryan's "sample traces of academic papers")

The knowledge-vault (211 papers / 34.7k chunks) + `ingestion/EXTRACTION_PROMPT.md` is the substrate.
A principle-extraction prompt distills, from a methods paper: the construct, the signatures it
protects, the finding + numbers, and the citation — REPORTED/INFERRED tagged, audited against the
existing cards before it earns a `seen_in`. New principles surface candidate patterns to promote
(as `provenance-documentation` already did).
