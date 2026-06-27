# Quickstart — test it yourself & grow the corpus

Runtime is pure stdlib (no install). Only the build-time steps (compiling the corpus, LLM ingestion)
need extras. From the repo root:

```bash
python3 engine/build_index.py          # compile cards + patterns + principles -> engine/index.json
                                        # (needs PyYAML: pip install pyyaml)
```

## Drive the three faces

```bash
# 1) Interactive web UI (recommended) — stdlib http.server, no Streamlit
python3 engine/serve.py                 # open http://localhost:8011
#    Forward mode: Describe -> Find & close risks -> Your recipe -> The rationale
#    Reverse mode: Describe -> Define good -> Reverse-engineer -> Your recipe
#    Step 4 now shows the PRINCIPLE BACKBONE (what good data IS + citations) and the
#    "Closest to what you described" panel (your goal text driving retrieval).

# 2) Interactive terminal REPL
python3 engine/repl.py                   # then: help / workflow / interrogate / adopt <pattern|N>
                                         #       backwards / shift <modality> / show / save

# 3) Static public page (what ships to GitHub Pages /docs)
python3 engine/build_site.py             # writes docs/index.html ; open it in a browser
```

## One-shot CLI (drive a design from a stub file)

A stub is flat YAML — `goal`, `modality`, `task_structure`, `annotator_structure`, optional
`qa_mechanism` / `uses_patterns`. Examples live in `engine/examples/`.

```bash
python3 engine/engine.py backwards   --stub engine/examples/preference_stub.yaml   # backbone + build list
python3 engine/engine.py workflow    --stub engine/examples/preference_stub.yaml   # the assembled recipe
python3 engine/engine.py semantic    --stub engine/examples/preference_stub.yaml   # goal-driven retrieval (LLM if key present)
python3 engine/engine.py semantic    --stub ... --no-llm                           # force deterministic topical tier
python3 engine/engine.py interrogate --stub ...        # open risks + the patterns that close them
python3 engine/engine.py list                          # corpus + signature coverage
python3 engine/engine.py compare --task preference_ranking   # how labs did the same workflow
python3 -m pytest -q                                   # the suite (86 tests)
```

## Grow the corpus — the loop

Two tiers grow the same way: **ingest → audit → fold → rebuild.** Ingestion needs `ANTHROPIC_API_KEY`
(or it in `~/.config/llm-keys.env`) + `pip install anthropic`. It is a BUILD-TIME act — runtime stays
deterministic.

```bash
# A WORKFLOW CARD from a dataset paper / a report:
python3 engine/ingest.py --source path/to/paper.txt --out drafts/        # -> drafts/<id>.yaml

# A PRINCIPLE (backbone) from a METHODOLOGY paper (Krippendorff, Card, Gebru, ...):
python3 engine/ingest.py --kind principle --source path/to/methods.txt   # -> draft YAML (stdout)
```

**Audit checklist before a draft joins the corpus** (this is what keeps provenance-over-volume):
- Every `failure_mode` tagged `REPORTED` actually states/measures it in the source (quote the number);
  downgrade anything you inferred to `INFERRED`.
- `failure_signatures` / `protects_against` reuse the existing vocab (don't invent a signature for a
  one-off); `uses_patterns` / `operationalized_by` point at real patterns.
- For a principle: the `source` is real and the claim is verified against it (not paraphrased loosely);
  `seen_in` only if a corpus card truly exhibits it.

Then fold the audited card into `cards/` (or the principle into `principles/library.yaml`) and:

```bash
python3 engine/build_index.py && python3 -m pytest -q   # recompile + confirm green
```

## Internal deployment (firewall side — same engine, private corpus)

```bash
# Point at a directory of private workflows/reports; writes a SEPARATE index OUTSIDE the repo.
python3 engine/build_corpus.py --sources /private/internal-sources \
    --out-index /private/wd-internal/index.json --drafts /private/wd-internal/drafts

# Run ANY face against that corpus with one env var — no code fork:
WD_INDEX=/private/wd-internal/index.json python3 engine/serve.py
WD_INDEX=/private/wd-internal/index.json python3 engine/engine.py list
```

`build_corpus` refuses to write inside this repo, and `.gitignore` blocks `drafts/` / `*.internal.json`
/ `wd-internal*/`, so private data can't land in the public repo.

## Growth queue (candidates, when you want to extend)

- **Patterns to promote** (the principles/cards already hint at these): `provenance-datasheet`
  (2 exemplars exist: datasheets-documentation + corpus-ingestion), plus `scan-aggregation`,
  `peer-review-gate`, `pseudo-labeling`.
- **Depth**: more lineage variants per `compare` cluster (red-team, preference, instruction);
  a 2nd/3rd exemplar in any thin modality×task cell.
- **Backbone**: a new principle only when a methodology construct isn't yet covered (the validity
  space is covered today; `bottleneck`/operational concerns are deliberately not principles).
