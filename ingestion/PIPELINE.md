# Ingestion Pipeline — from seed corpus to big corpus

The bridge between the hand-built seed and the large corpus. Designed as the `corpus-ingestion`
workflow card; this is the operational layer. **No code required for v1** — it runs on the
extraction prompt + human judgment.

## Why this exists / the ordering
The schema had to stabilize first (it changed twice: v0.1 → v0.2 → universe pivot). Ingesting at
scale before that would have meant re-extracting everything. Now the schema has survived a real
modality-shift stress test, so it is safe to extract into.

## The gold set
The four hand-built cards (`judge-eval-study`, `image-bbox-adjudicated`, `text-preference-rlhf`,
`synthetic-with-audit`) are the **gold standard** for ingestion QA. Extracted cards are judged for
structure and quality against them. They are real (own-program + well-documented practice), so
they anchor the extractor.

## The seven stages (= corpus-ingestion.yaml steps)
1. **Intake & triage** — collect candidate sources; drop anything that describes only a model/result,
   not a data workflow. (The extraction prompt's STEP 0 does this.)
2. **Extract** — run `EXTRACTION_PROMPT` per source → a draft card, provenance: extracted.
3. **Pattern-link** — map gates to library patterns; novel ones → CANDIDATE-PATTERN queue.
4. **Dedup/merge** — near-duplicate skeleton → file as an EXEMPLAR of the existing card, not a new
   card. (Coverage is measured in signatures, not card count, so duplicates are bloat.)
5. **Human audit** — verify REPORTED failure modes; cut/hold INFERRED ones; promote scaffolding →
   war-story only on a confirmed REPORTED mode.
6. **Coverage routing** — recompute the coverage map; pull next sources to fill the thinnest
   `signature x modality x task` cells (active learning over sources).
7. **Commit** — card enters the corpus with its provenance flag.

## v1 manual recipe (do this first, before any automation)
- Pick ~5 sources that fill known gaps: a red-teaming data paper, a transcription/ASR annotation
  doc, a relevance-judgment (search) methodology, and one audio + one video labeling source.
- Run the extraction prompt on each by hand.
- Audit each against the gold set; promote or hold.
- Log results. If the drafts are faithful and need light editing → the schema + prompt are good,
  and automation is just scaling the same loop. If they're systematically wrong → fix the schema
  or prompt before scaling. (This pilot IS the validation.)

## Coverage map (what to track)
A grid of `failure_signature x modality x task_structure`, target ≥2 REPORTED examples per
signature. Drives stage 6. Current thin cells: red_team, transcription_translation, relevance
task structures; video/audio modalities (no card yet).

## The honest boundary (this pipeline's own failure mode)
`sampling_frame`: ingesting from arXiv/HF over-represents *published* academic workflows and
under-represents *practiced* real-world vendor workflows. Coverage routing fixes modality/task
gaps but not the published-vs-practiced bias — that needs deliberate non-academic sources
(platform docs, practitioner write-ups, and Bryan's own work knowledge, scrubbed of proprietary
detail). Flagged, not solved.
