# Workflow Designer

A deterministic **creative partner for designing ML data workflows.** Describe a workflow you want to
build; it finds analogous prior workflows, interrogates your design against the failure modes they hit,
and suggests creative moves. From your selections it then **assembles a concrete sample workflow** — the
labeling steps, the fields each annotator fills, suggested conventions, and an audit strategy — with every
suggestion traceable to a real prior workflow with a real cost. No LLM in the loop, no API key.

Its core move is **backwards-from-good**: since "good data" is just data *free of the ways it goes bad*,
the engine runs in reverse — from what good means for your task, to the failure modes that threaten it, to
the one defense per risk that guarantees it — then stress-tests whether your definition of "good" is itself
a proxy (length, format, recalled consensus, a lenient label).

It reasons over a corpus of **45 grounded recipes** (annotation, RLHF, eval, red-teaming, synthetic data)
spanning every modality (text, image, video, audio, 3D, code, tabular) and task type, plus **25 reusable
patterns** distilled from them. Each recipe is built from published methods and carries failure modes that
were actually *reported* — not invented.

## Why deterministic

Every suggestion cites the **pattern** it borrows, the **failure signature** it inherits, and the **cost**
it adds — legible all the way back to a real prior workflow. Generative *because* it's legible, not despite
it. A recombination engine that free-associates produces confident nonsense; this one can't.

## Quickstart

```bash
# CLI — stdlib only, no dependencies, no API key
python3 engine/engine.py list
python3 engine/engine.py workflow                         # assemble the sample workflow: steps · fields · conventions · audit
python3 engine/engine.py backwards                        # backwards-from-good: derive the workflow + stress-test the spec
python3 engine/engine.py interrogate                      # mode 3 on the example workflow stub
python3 engine/engine.py modality-shift --to video
python3 engine/engine.py compare --task preference_ranking
python3 engine/engine.py cookbook --by domain

# Interactive web app — pick selections + adopt patterns live in the browser (stdlib server, no deps)
python3 engine/serve.py                                   # then open http://localhost:8011

# Interactive REPL — same thing in the terminal: build a design and iterate
python3 engine/repl.py                                    # then: workflow, interrogate, adopt <pattern>, shift video, save …

# Static portfolio site (pre-rendered, no server) -> docs/index.html
python3 engine/build_site.py && open docs/index.html
```

The engine reads a compiled `engine/index.json`. To regenerate it from the YAML corpus:
`python3 engine/build_index.py` (the only step that needs PyYAML). Run the tests with
`pip install -r engine/requirements.txt && pytest -q`.

## Layout

- `cards/` — workflow recipes (YAML); `patterns/library.yaml` — the reusable patterns
- `engine/` — the deterministic engine (`engine.py`), the interactive REPL (`repl.py`), the local
  web app (`serve.py`), the index compiler (`build_index.py`), and the static-site generator (`build_site.py`)
- `tests/` — pytest invariants, index round-trip checks, golden snapshots, and the REPL adopt-loop
- `docs/` — the pre-rendered static site (GitHub Pages)
- `ingestion/` — the extraction prompt + pipeline for growing the corpus from published sources
- `SCHEMA.md` — the card / pattern schema and the failure-signature vocabulary
- `examples/` — a worked modality-shift walkthrough

## Scope & grounding

Every recipe is grounded in published methods; the corpus is synthetic/public only, with no proprietary or
confidential content. Provenance is tracked per card, and inferred failure modes are flagged as such.

MIT licensed.
