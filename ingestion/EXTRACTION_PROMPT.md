# Extraction Prompt — Source Document → Draft Workflow Card

Operational, no code. Paste this prompt + one source document (a paper, datasheet, dataset card,
or annotation-guideline doc) into a fresh Claude chat. You get back a draft card to audit and
commit. This is the `extract` step of the corpus-ingestion workflow.

The discipline that protects the corpus: **every failure mode must be tagged `[REPORTED]`
(the source states it) or `[INFERRED]` (you added it from general knowledge).** Only REPORTED
modes earn a war-story card; INFERRED modes are hypotheses the human curator verifies or cuts.

---

## THE PROMPT

```
You are extracting a WORKFLOW CARD from a source document about ML data work
(annotation, preference/RLHF collection, eval-data, red-teaming, or synthetic-data-with-audit).

STEP 0 — TRIAGE. First decide: does this document actually describe a DATA WORKFLOW (how the
data was produced/labeled/judged), or only a model/result? If it does not describe a workflow,
reply exactly: "NO WORKFLOW — <one-line reason>" and stop.

STEP 1 — LOCATE in the space. Choose from the controlled vocabularies (pick the closest; note
if multiple apply):
- modality: text | image | video | audio | 3d_pointcloud | code | tabular | multimodal
- task_structure: classification | extraction | structured_output | transcription_translation |
  preference_ranking | rubric_rating | demonstration | critique_rationale | relevance | red_team |
  freeform_generation
- annotator_structure: single | multi_aggregate | tiered_review | expert | crowd |
  model_assisted | model_as_annotator
- qa_mechanism (list any present): gold_honeypots | agreement | qualification_calibration |
  adjudication | audit_sampling | consensus_threshold | guideline_freeze

STEP 2 — EXTRACT the eight facets from the SOURCE ONLY:
decision, inputs (source/provenance/assumption), actors (role/does/type), steps,
quality_gates (gate/checks/catches), output (shape/consumed_by), failure_modes, cost_profile.

STEP 3 — FAILURE MODES with provenance. For each, give: signature (from the list below),
description, caught_by, and a TAG:
  [REPORTED]  the source explicitly observed/measured this failure — quote or cite the line.
  [INFERRED]  you are adding this from general knowledge; the source does not state it.
Failure signatures: confounded | unanchored | self_affinity | inflation | underpowered |
priming | sampling_frame | drift | bottleneck | over_specification | under_specification |
label_leakage | class_imbalance. Propose a new signature only if none fits; mark it NEW-SIGNATURE.

STEP 4 — PATTERN LINKING. Map each quality_gate to a known pattern id:
multi-annotator-aggregate | tiered-adjudication | gold-honeypots | qualification-calibration |
inter-annotator-agreement | human-gold-anchor | cross-family-judges | human-audit-sample |
lock-then-score | active-learning-loop. If a gate matches none, label it CANDIDATE-PATTERN: <name>.

STEP 5 — OUTPUT. Emit:
(a) a HEADER block: source citation, your confidence (high/med/low) that this is faithful to the
    source, provenance: extracted, and a DEDUP HINT (which of these existing cards is the closest
    skeleton, if any: judge-eval-study, image-bbox-adjudicated, text-preference-rlhf,
    synthetic-with-audit, corpus-ingestion — or "none").
(b) the card as valid YAML in the schema's card format, with uses_patterns filled from STEP 4.

Do not invent specifics the source doesn't contain. If a facet is absent in the source, write
"NOT STATED" rather than guessing.
```

---

## After extraction (human curator, the `audit` step)
1. Read the source against the draft. Confirm each `[REPORTED]` mode is real; cut or hold each
   `[INFERRED]` mode unless you can confirm it.
2. If the DEDUP HINT names a close card, file this as an EXEMPLAR of that card (add to its
   `exemplified_by` / notes) instead of creating a new card.
3. Promote to a war-story card only when ≥1 failure mode is confirmed REPORTED. Otherwise it stays
   a scaffolding card (provenance: extracted, unverified) and does not feed the creative partner's
   failure-mode interrogation.
4. Add any CANDIDATE-PATTERN to the review queue in NOTES.md.
