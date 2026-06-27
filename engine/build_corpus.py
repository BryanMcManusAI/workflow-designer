#!/usr/bin/env python3
"""Build an INTERNAL corpus index from a directory of source documents — the firewall-side half of
the two-track design.

The public tool ships one committed `index.json` (papers/public sources). An internal deployment runs
THIS over a private directory of old workflows + post-mortem reports: each source is LLM-ingested into a
draft (ingest.py), merged onto the public seed corpus, and compiled to a SEPARATE index.json that the
same engine reads via `WD_INDEX=/path engine.py ...` — zero code fork.

Clean-room wall, enforced in code:
  - This file is generic MECHANISM (no company specifics) and is public-safe to ship.
  - The SOURCES, DRAFTS, and OUTPUT INDEX are private data — they must live OUTSIDE this git repo.
  - The tool REFUSES to write the index or drafts inside the repo root (use --allow-in-repo only for a
    public demo with public sources). So internal data cannot accidentally land in the public repo.

Drafts are exactly that — machine-extracted, awaiting human audit (post-mortems = REPORTED war-story
provenance). build_corpus merges them so you can EXERCISE the internal corpus immediately; the audit
gate is yours before any draft is treated as ground truth.

Usage:
  python3 engine/build_corpus.py --sources /private/internal-sources \\
      --out-index /private/wd-internal/index.json --drafts /private/wd-internal/drafts [--kind card]
  WD_INDEX=/private/wd-internal/index.json python3 engine/engine.py list   # same engine, internal corpus
"""
import argparse
import copy
import glob
import os
import sys

try:
    from . import engine, ingest, llm
    from . import build_index as bi
except ImportError:
    import engine
    import ingest
    import llm
    import build_index as bi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the public repo root


def _to_index_card(d):
    """Map an ingest draft (card schema) into the compiled index-card shape build_index produces."""
    ann = d.get("annotator_structure", "")
    return {
        "id": d["id"], "title": d.get("title", ""),
        "modality": d.get("modality", ""), "task_structure": d.get("task_structure", ""),
        "annotator_structure": ann,
        "scale": bi.SCALE_BY_ANNOTATOR.get(ann, "unspecified"),
        "domain": d.get("domain") or "general", "lineage": d.get("lineage", ""),
        "distinctive": d.get("distinctive", ""),
        "qa_mechanism": d.get("qa_mechanism") or [],
        "failure_signatures": d.get("failure_signatures") or [],
        "uses_patterns": d.get("uses_patterns") or [],
        "decision": d.get("decision", ""),
        "failure_modes": [{"signature": f.get("signature", ""), "evidence": f.get("evidence", ""),
                           "description": f.get("description", ""), "caught_by": f.get("caught_by", "")}
                          for f in (d.get("failure_modes") or [])],
        "quality_gates": [{"gate": g.get("gate", ""), "checks": g.get("checks", ""),
                           "catches": g.get("catches") or []} for g in (d.get("quality_gates") or [])],
        "cost_profile": d.get("cost_profile") or {},
    }


def _to_index_principle(d):
    return {
        "id": d["id"], "name": d.get("name", ""), "tenet": d.get("tenet", ""),
        "protects_against": d.get("protects_against") or [],
        "operationalized_by": d.get("operationalized_by") or [],
        "probe": d.get("probe", ""),
        "evidence": [{"claim": e.get("claim", ""), "source": e.get("source", ""),
                      "seen_in": e.get("seen_in", ""), "provenance": e.get("provenance", "")}
                     for e in (d.get("evidence") or [])],
    }


def _in_repo(path):
    return os.path.abspath(path).startswith(ROOT + os.sep)


def main():
    ap = argparse.ArgumentParser(description="Build an internal corpus index from a directory of sources.")
    ap.add_argument("--sources", required=True, help="directory of source .txt/.md docs (workflows / reports)")
    ap.add_argument("--out-index", required=True, help="where to write the merged internal index.json")
    ap.add_argument("--drafts", help="directory to write per-source draft YAML into (for audit)")
    ap.add_argument("--kind", choices=["card", "principle"], default="card")
    ap.add_argument("--allow-in-repo", action="store_true",
                    help="permit writing inside the repo (PUBLIC demo only — never for internal data)")
    args = ap.parse_args()

    for label, p in (("--out-index", args.out_index), ("--drafts", args.drafts)):
        if p and _in_repo(p) and not args.allow_in_repo:
            sys.exit(f"refusing to write {label} inside the public repo ({p}). Internal corpora live "
                     f"OUTSIDE the repo (clean-room wall). Use a path outside {ROOT}, or --allow-in-repo "
                     f"only for a public demo.")
    if not llm.available():
        sys.exit("LLM unavailable: set ANTHROPIC_API_KEY (or ~/.config/llm-keys.env) + pip install anthropic.")

    base = engine.load_index()  # extend the public seed corpus
    idx = copy.deepcopy(base)
    bucket = "principles" if args.kind == "principle" else "cards"
    idx.setdefault(bucket, {})
    transform = _to_index_principle if args.kind == "principle" else _to_index_card

    sources = sorted(glob.glob(os.path.join(args.sources, "*.txt"))
                     + glob.glob(os.path.join(args.sources, "*.md")))
    if not sources:
        sys.exit(f"no .txt/.md sources in {args.sources}")
    if args.drafts:
        os.makedirs(args.drafts, exist_ok=True)

    added, failed = [], []
    for path in sources:
        text = open(path).read()
        draft = ingest.ingest(base, text, kind=args.kind)
        if not draft or "id" not in draft:
            failed.append(os.path.basename(path))
            continue
        idx[bucket][draft["id"]] = transform(draft)
        added.append(draft["id"])
        if args.drafts:
            with open(os.path.join(args.drafts, f"{draft['id']}.yaml"), "w") as f:
                f.write(f"# DRAFT {args.kind} from {os.path.basename(path)} — awaiting human audit.\n")
                f.write(ingest.to_yaml(draft))
        print(f"  ingested {os.path.basename(path)} -> {draft['id']}", file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(args.out_index)) or ".", exist_ok=True)
    import json
    with open(args.out_index, "w") as f:
        json.dump(idx, f, indent=1, ensure_ascii=False)

    print(f"\nwrote {args.out_index}: {len(idx['cards'])} cards, {len(idx['patterns'])} patterns, "
          f"{len(idx.get('principles', {}))} principles "
          f"(+{len(added)} draft {args.kind}s merged onto the public seed)")
    if failed:
        print(f"  extraction failed: {', '.join(failed)}", file=sys.stderr)
    print(f"run it:  WD_INDEX={args.out_index} python3 engine/engine.py list")


if __name__ == "__main__":
    main()
