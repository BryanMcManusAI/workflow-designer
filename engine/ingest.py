#!/usr/bin/env python3
"""LLM ingestion — turn a messy source (a paper, or a workflow/post-mortem report) into a DRAFT card.

This is `ingestion/EXTRACTION_PROMPT.md` automated: paste a source, get a structured draft card in the
corpus schema, with REPORTED vs INFERRED provenance tagging preserved. It is a BUILD-TIME act (like
hand-authoring a card) — the runtime engine still reads frozen YAML with stdlib only, so the
deterministic / no-LLM-at-runtime guarantee is untouched.

The output is a DRAFT: it lands in `drafts/` (never `cards/`) and must be human-audited before it
joins the corpus — exactly the provenance discipline the corpus already requires. Extraction is
constrained to the controlled vocabulary (the schema enums the axes/signatures/patterns from the
current index), so a draft can't invent off-vocab values.

Public-source demo of the internal story: point this at a repository of old workflows + reports and it
builds the corpus from the org's own accumulated experience (post-mortems are REPORTED failure modes —
the war-story provenance the corpus wants). Here we run it on published papers; no proprietary data.

Usage:
  python3 engine/ingest.py --source path/to/source.txt        # → prints draft YAML
  python3 engine/ingest.py --source - --id my-card --out drafts/   # read stdin, write a file
"""
import argparse
import os
import sys

try:
    from . import engine, llm
except ImportError:
    import engine
    import llm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _schema(idx):
    v = engine.vocab(idx)
    sig = sorted(set(v["failure_signature"]) | set(engine.SIGNATURE_SEVERITY))
    str_ = {"type": "string"}
    enum = lambda vals: {"type": "string", "enum": vals}
    arr = lambda items: {"type": "array", "items": items}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["id", "title", "modality", "task_structure", "annotator_structure",
                     "qa_mechanism", "failure_signatures", "uses_patterns", "distinctive",
                     "decision", "quality_gates", "failure_modes", "cost_profile", "provenance"],
        "properties": {
            "id": str_, "title": str_,
            "modality": enum(v["modality"]),
            "task_structure": enum(v["task_structure"]),
            "annotator_structure": enum(v["annotator_structure"]),
            "lineage": str_,
            "qa_mechanism": arr(enum(v["qa_mechanism"])),
            "failure_signatures": arr(enum(sig)),
            "uses_patterns": arr(enum(sorted(idx["patterns"]))),
            "distinctive": str_,
            "decision": str_,
            "quality_gates": arr({
                "type": "object", "additionalProperties": False,
                "required": ["gate", "checks", "catches"],
                "properties": {"gate": str_, "checks": str_, "catches": arr(enum(sig))}}),
            "failure_modes": arr({
                "type": "object", "additionalProperties": False,
                "required": ["signature", "evidence", "description"],
                "properties": {"signature": enum(sig),
                               "evidence": enum(["REPORTED", "INFERRED"]),
                               "description": str_, "caught_by": str_}}),
            "cost_profile": {
                "type": "object", "additionalProperties": False,
                "required": ["throughput"],
                "properties": {"throughput": str_, "bottleneck": str_, "human_cost": str_}},
            "provenance": str_,
        },
    }


def _principle_schema(idx):
    """Schema for a PRINCIPLES-tier entry — distinct from a card. A methodology paper (Krippendorff,
    Card et al., Gebru) isn't a workflow; it's a claim about a construct that defines good data."""
    v = engine.vocab(idx)
    sig = sorted(set(v["failure_signature"]) | set(engine.SIGNATURE_SEVERITY))
    str_ = {"type": "string"}
    enum = lambda vals: {"type": "string", "enum": vals}
    arr = lambda items: {"type": "array", "items": items}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["id", "name", "tenet", "protects_against", "operationalized_by", "probe",
                     "evidence"],
        "properties": {
            "id": str_, "name": str_, "tenet": str_, "probe": str_,
            "protects_against": arr(enum(sig)),
            "operationalized_by": arr(enum(sorted(idx["patterns"]))),
            "evidence": arr({
                "type": "object", "additionalProperties": False,
                "required": ["claim", "source", "provenance"],
                "properties": {
                    "claim": str_, "source": str_,
                    "seen_in": enum([""] + sorted(idx["cards"])),  # optional corpus exemplar
                    "provenance": enum(["extracted-then-audited", "stub-to-extract"])}}),
        },
    }


PRINCIPLE_SYSTEM = """You extract a PRINCIPLES-tier entry — a methodology construct that defines what
"good data" IS in an ML experiment — from a measurement / experimental-design / data-documentation
paper (e.g. inter-annotator reliability, statistical power, construct validity, dataset documentation).

This is the intellectual BACKBONE: it must be grounded in independent academic work, not in any one
team's projects. Decompose:
- `protects_against`: the failure_signatures whose ABSENCE this construct IS (good = free of them).
  Construct validity ↔ confounded/label_leakage; reliability ↔ under/over_specification; external
  validity ↔ sampling_frame/class_imbalance; power ↔ underpowered; etc. Use ONLY vocab signatures.
- `operationalized_by`: the corpus patterns that secure it (vocab pattern ids only; [] if none fit).
- `tenet`: one or two sentences stating the construct as the definition of good.
- `probe`: the question that tests whether your 'good' actually has it.
- `evidence`: the paper's specific finding (quote the number) + the citation in `source`. Set
  `provenance` = "extracted-then-audited". Leave `seen_in` empty unless a listed corpus card clearly
  exhibits it. Be faithful to the source — this is a DRAFT for human audit."""


SYSTEM = """You extract a structured ML-data-workflow recipe card from a source document (a paper or
an internal workflow/post-mortem report). You decompose the workflow along four axes — modality,
task_structure (the output produced), annotator_structure (who acts), qa_mechanism — and record its
failure_signatures (systematic data-quality failures, NOT code bugs) and the patterns it uses.

Discipline (non-negotiable):
- Use ONLY the controlled vocabulary the schema enumerates; never invent values.
- Tag each failure_mode's `evidence` REPORTED (the source states/measures it, ideally with numbers in
  the description) vs INFERRED (you reasonably infer it). Prefer REPORTED; quote the number.
- quality_gates.catches and failure_modes.signature must be real signatures from the vocab.
- `decision` = what data this workflow produces and for what model behavior. `distinctive` = the one
  thing that sets it apart (the house-style / the cautionary lesson).
- This is a DRAFT for human audit — be faithful to the source, do not embellish."""


def ingest(idx, text, kind="card", forced_id=None):
    schema = _principle_schema(idx) if kind == "principle" else _schema(idx)
    system = PRINCIPLE_SYSTEM if kind == "principle" else SYSTEM
    user = f"SOURCE DOCUMENT:\n\n{text.strip()[:20000]}"
    out = llm.json_complete(system, user, schema, max_tokens=4096)
    if out and forced_id:
        out["id"] = forced_id
    return out


def to_yaml(card):
    try:
        import yaml
    except ImportError:
        import json
        return json.dumps(card, indent=2, ensure_ascii=False)
    return yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=100)


def main():
    ap = argparse.ArgumentParser(description="LLM ingestion: source → draft workflow card (build-time).")
    ap.add_argument("--source", required=True, help="path to a source text file, or - for stdin")
    ap.add_argument("--kind", choices=["card", "principle"], default="card",
                    help="card = a workflow (from a dataset paper/report); principle = a backbone "
                         "construct (from a methodology paper)")
    ap.add_argument("--id", help="force the id (else the model proposes one)")
    ap.add_argument("--out", help="directory to write <id>.yaml into (else print to stdout)")
    args = ap.parse_args()

    if not llm.available():
        sys.exit("LLM unavailable: set ANTHROPIC_API_KEY (or add it to ~/.config/llm-keys.env) "
                 "and `pip install anthropic`. Ingestion is the one build-time step that needs a key.")

    text = sys.stdin.read() if args.source == "-" else open(args.source).read()
    idx = engine.load_index()
    out = ingest(idx, text, kind=args.kind, forced_id=args.id)
    if not out:
        sys.exit("extraction failed (nothing returned).")

    y = to_yaml(out)
    dest = "principles/library.yaml" if args.kind == "principle" else "cards/"
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, f"{out['id']}.yaml")
        with open(path, "w") as f:
            f.write(f"# DRAFT {args.kind} — machine-extracted, awaiting human audit before joining the corpus.\n")
            f.write(y)
        print(f"wrote draft: {path}\n(audit it, then fold into {dest} and re-run build_index.py)",
              file=sys.stderr)
    else:
        print("# DRAFT — machine-extracted, awaiting human audit.\n" + y)


if __name__ == "__main__":
    main()
