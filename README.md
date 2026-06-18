# Workflow Designer

A deterministic **creative partner for designing ML data workflows.** Describe a workflow you want to
build; it finds analogous prior workflows, interrogates your design against the failure modes they hit,
and suggests creative moves — and every suggestion is traceable to a real prior workflow with a real
cost. No LLM in the loop, no API key.

It reasons over a corpus of **45 grounded recipes** (annotation, RLHF, eval, red-teaming, synthetic data)
spanning every modality (text, image, video, audio, 3D, code, tabular) and task type, plus **23 reusable
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
python3 engine/engine.py interrogate                      # mode 3 on the example workflow stub
python3 engine/engine.py modality-shift --to video
python3 engine/engine.py compare --task preference_ranking
python3 engine/engine.py cookbook --by domain

# Guided Streamlit demo
pip install -r engine/requirements.txt
streamlit run engine/portfolio_app.py
```

The engine reads a compiled `engine/index.json`. To regenerate it from the YAML corpus:
`python3 engine/build_index.py` (the only step that needs PyYAML).

## Layout

- `cards/` — workflow recipes (YAML); `patterns/library.yaml` — the reusable patterns
- `engine/` — the deterministic engine (`engine.py`), the index compiler, and the Streamlit demo (`portfolio_app.py`)
- `ingestion/` — the extraction prompt + pipeline for growing the corpus from published sources
- `SCHEMA.md` — the card / pattern schema and the failure-signature vocabulary
- `examples/` — a worked modality-shift walkthrough

## Scope & grounding

Every recipe is grounded in published methods; the corpus is synthetic/public only, with no proprietary or
confidential content. Provenance is tracked per card, and inferred failure modes are flagged as such.

MIT licensed.
