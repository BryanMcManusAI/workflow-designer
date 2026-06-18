# Workflow Card Schema (v0.2)

A creative partner for **ML data-workflow design** — the universe of human annotation,
preference/RLHF collection, eval-data generation, red-teaming, and synthetic-data-with-audit,
across every modality. The corpus has **two tiers**:

- **Workflow cards** — a concrete data workflow, a skeleton instantiated in a modality.
- **Pattern cards** — the reusable, modality-independent sub-structures distilled out of the
  workflows. Patterns are the units that transfer and recombine.

The intelligence is in the **decomposition**. A data workflow is a point in a product space, and
chunking it along independent axes is what lets the partner *recombine* instead of merely retrieve.

---

## The space a workflow lives in

Every workflow card is located by four axes plus its failure signatures. The skeleton
(task x annotator x QA) is largely **modality-independent and portable**; modality is a
permutation that swaps tooling and adds modality-specific failure modes but preserves the skeleton.

### `modality`
`text` · `image` · `video` · `audio` · `3d_pointcloud` · `code` · `tabular` · `multimodal`

### `task_structure`  (the output the workflow produces)
`classification` · `extraction` (spans/entities) · `structured_output` (boxes/segmentation/keypoints) ·
`transcription_translation` · `preference_ranking` · `rubric_rating` · `demonstration` (SFT) ·
`critique_rationale` · `relevance` · `red_team` · `freeform_generation`

### `annotator_structure`  (who acts)
`single` · `multi_aggregate` · `tiered_review` (annotate→review→adjudicate) · `expert` · `crowd` ·
`model_assisted` (pre-label / active learning) · `model_as_annotator` (synthetic + human audit) ·
`programmatic` (weak supervision / labeling functions + a learned label model)

### `qa_mechanism`
`gold_honeypots` · `agreement` (IAA, κ/α) · `qualification_calibration` · `adjudication` ·
`audit_sampling` · `consensus_threshold` · `guideline_freeze` · `input_pooling` · `order_randomization` · `execution_check`

### Derived cookbook angles (for browsing)
Beyond the four axes, every recipe is also indexed by **`scale`** (cost/throughput regime — derived from
annotator_structure: solo / expert / crowd / hybrid / automated / programmatic) and **`domain`** (the vertical,
e.g. vision / alignment-rlhf / clinical / code / search-ir). A card may set these explicitly; otherwise they're
derived at build time. `cookbook --by <angle>` (and the Cookbook-index UI tab) group recipes by any angle
(domain / scale / modality / task_structure / annotator_structure / lineage) — the cookbook's multiple indexes,
so a designer can enter from whatever direction they're thinking.

---

## `failure_signature` — the cross-domain key

Domain-agnostic vocabulary. Two workflows that share a signature are far-analogues even across
modality and task; the shared signature is what the partner uses to interrogate a new design.

| Signature | In data-workflow terms |
|-----------|------------------------|
| `confounded` | A spurious cue rides along with the real signal (priority correlates with customer tier; style with quality) |
| `unanchored` | No gold / ground truth to check labels against |
| `self_affinity` | A model-annotator/judge favors its own family's outputs |
| `inflation` | Annotator leniency creeps up; everything passes |
| `underpowered` | Too few items/reps to support the claim or train reliably |
| `priming` | Item order or context contaminates the label |
| `sampling_frame` | The labeled set isn't representative of deployment (only easy cases get the full treatment) |
| `drift` | Guidelines / acceptance bar move over a campaign |
| `bottleneck` | One stage (adjudication, expert review) gates throughput |
| `over_specification` | Guidelines so rigid they break on edge cases |
| `under_specification` | So loose that competent annotators disagree → low IAA |
| `label_leakage` | The label is derivable from a feature it shouldn't be / answer visible in the prompt |
| `class_imbalance` | Rare classes under-sampled, so the model never learns them |
| `gaming` | Annotators optimize the incentive (pay/quota), not quality — Goodhart | Template-farming, redundant low-value items to maximize earnings |

Prefer reusing a signature over inventing one. New ones earn their place by recurring across ≥2
task structures.

**Scope.** Signatures name *systematic data-quality* failures — ways the data or the judgments are
biased, noisy, unrepresentative, or unanchored. They deliberately do **not** cover
implementation/instrumentation bugs (a broken vote counter, a crashed pipeline stage, a mislabeled
export field). Those are real and may be logged on a card's `failure_modes` with the literal
signature `instrumentation-bug`, but they are code defects — not transferable workflow-design
lessons — so they get no signature row and never drive far-analogy.

---

## Workflow card format (YAML)

```yaml
id: kebab-case-id
title: Human Readable Title
modality: image
task_structure: structured_output
annotator_structure: tiered_review
lineage: deepmind / Sparrow          # optional — the org/house-style this card represents (feeds `compare`)
qa_mechanism: [agreement, adjudication]
failure_signatures: [under_specification, bottleneck]
uses_patterns: [multi-annotator-aggregate, tiered-adjudication]   # link to the pattern tier

decision: >          # what data this workflow exists to produce, and for what model behavior
inputs:              # source / provenance / the assumption that is the hidden risk
actors:              # role / does / type (human|model|hybrid)
steps:               # the control flow incl. decision points
quality_gates:       # gate / checks / catches (signature); optional `induces:` — a signature this gate CREATES
output:              # shape + consumed_by
failure_modes:       # signature / description / caught_by (or UNGUARDED)
cost_profile:        # throughput / bottleneck / human_cost (note annotator welfare / content-exposure risk here when relevant)
provenance: >        # real program | canonical practice | synthesized (flag which)
```

## Pattern card format (YAML)

```yaml
id: kebab-case-id
name: Human Name
does: >                  # the structural move, in one or two lines
defends: [unanchored]    # failure_signature(s) it guards against
pairs_with: [pattern-ids]      # composes cleanly with
conflicts_with: [pattern-ids]  # fights / double-counts with
cost: >                  # what it adds (human time, latency, $)
modality_notes: >        # how it changes across modalities — the hook for modality-shift
exemplified_by: [workflow-card-ids]
```

The corpus is a graph: **workflows ↔ patterns ↔ failure_signatures**. The creative operators are
disciplined traversals of that graph.

---

## How the partner uses the corpus

**Near-analogy** — match on `modality` + `task_structure` + `annotator_structure`.
**Far-analogy** — match on `failure_signatures` *across* modality/task; the source of surprising,
still-valid transplants.

**Creative operators** (see NOTES.md for the full table with corpus costs). The signature move of
this universe is **modality-shift**: take a workflow skeleton and re-instantiate it in another
modality — "what does our text-preference pipeline become for video?" — keeping the patterns and
re-deriving the modality-specific failure modes. The other cheap-at-small-corpus moves are
*transplant*, *constraint-flip*, and *actor-substitution*.

The **compare** operator is different in kind: it contrasts the org/house-style variants (the
`lineage` facet) of *one* task type side by side — the same workflow done the Anthropic vs OpenAI vs
Meta vs DeepMind way — surfacing the invariant core they share and the distinctive choice each made.
That's the "how have others done versions of this same workflow" view.

**Mode 3 — interrogation (the learning engine).** Given a new workflow in these facets, the
partner retrieves near + far analogues, collects the union of their `failure_signatures`, and for
each one *not already defended by a gate in your design* asks the question that signature implies
and offers the pattern that catches it. Because data-workflow QA *is* applied experimental design
(sampling frame, gold, IAA, calibration, bias control), mode 3 doubles as a methods tutor.

**The guardrail.** Every creative move cites the pattern it borrows, the failure signature it
inherits, and the cost it adds — so a suggestion is legible back to a real pattern with a real
price, never a confident fabrication.
