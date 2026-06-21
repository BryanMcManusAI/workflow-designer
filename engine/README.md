# Workflow Designer — Engine

A **deterministic creative partner** for ML-data-workflow design. You describe a new workflow as a
small YAML stub; the engine retrieves analogous prior workflows from the corpus, interrogates your
design against their failure modes, and applies creative operators (modality-shift, transplant,
flip, actor-substitute) — all over the 45-card corpus in this repo. Drive it one-shot from the CLI,
or interactively from the REPL (`repl.py`); both share the same `analyze_*` / `render_*` core.

**No LLM, no network.** Every suggestion is templated from the corpus and CITES the pattern it
borrows, the failure signature it inherits, and that pattern's cost — so a recommendation is always
legible back to a real prior workflow with a real price. That legibility is the whole point: the
partner is generative *and* auditable.

## Setup

```bash
# Build the corpus index (dev-time; needs PyYAML). Commit index.json so the engine runs cold.
python3 build_index.py        # -> index.json (45 cards)
```

The engine itself (`engine.py`) is **stdlib-only** — once `index.json` exists, a cold clone runs
every command with no third-party dependencies. The small input stub is flat YAML, parsed by a
~15-line stdlib reader.

## Commands

```bash
python3 engine.py list                                   # corpus summary + signature coverage
python3 engine.py workflow     --stub S                  # ★ assemble the sample workflow: labeling steps + fields + conventions + audit
python3 engine.py backwards    --stub S                  # good = free of these failures -> the workflow that guarantees it + a spec stress-test
python3 engine.py retrieve     --stub S                  # near + far analogues
python3 engine.py interrogate  --stub S                  # mode 3: open risks + patterns that catch them
python3 engine.py modality-shift --stub S --to video     # re-instantiate the skeleton in another modality
python3 engine.py transplant   --stub S                  # distant patterns that defend your open risks
python3 engine.py flip         --stub S --axis A --to V  # change a constraint; see what survives/breaks
python3 engine.py actor-substitute --stub S --to V       # swap the annotator structure; see what changes
```

`--stub` defaults to `examples/new_workflow.yaml`. Two examples ship:
`new_workflow.yaml` (an LLM-judged marketing-copy eval, nothing defended → maximal interrogation)
and `preference_stub.yaml` (an RLHF-like skeleton with patterns filled → exercises the operators).

## Interactive REPL (the working tool)

```bash
python3 repl.py [--stub S]
```

Builds a design and lets you iterate: `workflow` (the assembled sample workflow — steps, fields,
conventions, audit), `interrogate`, `adopt <pattern|N>` (open risks shrink and the **coverage** bar
rises), `shift <modality>`, `flip <axis> <value>`, `transplant`, `compare <task>`, `show <id>`,
`set <axis> <value>`, `save <path>` (writes the session back to a reusable stub).
Adopting also surfaces **complementary** patterns (`pairs_with`) and warns on real design **conflicts**
(`conflicts_with`, e.g. lock-then-score ⟂ active-learning-loop).

## Interactive web app (browser, local)

```bash
python3 serve.py [--port 8011]      # then open http://localhost:8011
```

A tiny stdlib `http.server` that exposes the same `analyze_*` functions as a JSON API, with a
vanilla-JS page: pick modality / task / annotator / QA, adopt patterns from the Interrogate tab, and
watch the assembled workflow, backwards-from-good, and the **coverage bar** update live. No Streamlit,
no build step, no dependencies — the engine logic stays in Python; the browser only renders the JSON.

## Stub format (flat YAML)

```yaml
goal: Evaluate AI-generated marketing copy at scale
modality: text                       # text|image|video|audio|3d_pointcloud|code|tabular|multimodal
task_structure: rubric_rating        # see SCHEMA.md controlled vocab
annotator_structure: model_as_annotator
qa_mechanism: []                     # mechanisms already in place
uses_patterns: []                    # patterns already in your design (these get credited as 'defended')
addressed_signatures: []             # risks you've already handled some other way
```

As you add patterns to `uses_patterns`, the risks they defend drop out of `interrogate` — the
loop is: interrogate → adopt a suggested pattern → interrogate again, until the open risks are
ones you've consciously accepted. The REPL does this loop live; the CLI does it by editing the stub.

## How it works

The corpus is a graph: **workflow cards ↔ patterns ↔ failure signatures** (see `../SCHEMA.md`).
- **Near analogues** match on modality / task / annotator structure.
- **Far analogues** match on a shared failure *signature* across distant modality/task — the source
  of surprising-but-valid transplants. They're ranked by the *rarity* (IDF) of the shared signature,
  so a distant workflow sharing a rare risk (e.g. `self_affinity`, `gaming`) outranks one sharing the
  near-universal `under_specification`.
- **Interrogate** collects the union of analogues' signatures, subtracts what your patterns already
  defend, and asks the methods-reviewer question for each open risk + the pattern(s) that catch it.
- **Operators** are disciplined traversals of the graph; `modality-shift` keeps your patterns and
  re-derives modality-specific risks from each pattern's `modality_notes`.
