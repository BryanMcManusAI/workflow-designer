#!/usr/bin/env python3
"""Compile the workflow-designer YAML corpus into a stdlib-readable index.json.

Dev-time only; requires PyYAML. The engine itself (engine.py) reads index.json with
stdlib json, so a cold clone runs the engine with no third-party deps.
"""
import glob
import json
import os

import yaml  # dev-time dependency only

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # ~/workflow-designer
CARDS_DIR = os.path.join(ROOT, "cards")
PATTERNS_FILE = os.path.join(ROOT, "patterns", "library.yaml")
OUT = os.path.join(HERE, "index.json")


# Derived "cookbook" angles, so every recipe is findable from more directions.
# scale = cost/throughput regime (derived from annotator structure; a card may override with `scale:`).
SCALE_BY_ANNOTATOR = {
    "single": "solo",
    "expert": "expert (low-throughput / high-skill)",
    "tiered_review": "expert + review (tiered)",
    "crowd": "crowd (high-throughput)",
    "multi_aggregate": "crowd (aggregated)",
    "model_assisted": "hybrid (model + human)",
    "model_as_annotator": "automated (very-high-throughput)",
    "programmatic": "programmatic (weak supervision)",
}
# domain = the vertical a recipe lives in (a card may override with `domain:`).
DOMAIN_BY_ID = {
    "judge-eval-study": "research-eval",
    "image-bbox-adjudicated": "vision",
    "text-preference-rlhf": "alignment-rlhf",
    "synthetic-with-audit": "synthetic-data",
    "corpus-ingestion": "meta-tooling",
    "audio-transcription-commonvoice": "speech",
    "redteam-adversarial-dialogue": "safety-redteam",
    "relevance-pooling-trec": "search-ir",
    "demonstration-instructgpt": "alignment-rlhf",
    "content-moderation-abuse": "content-moderation",
    "video-action-kinetics": "vision-video",
    "code-humaneval": "code",
    "tabular-weak-supervision-snorkel": "weak-supervision",
    "pointcloud-detection-nuscenes": "autonomous-driving",
    "critique-criticgpt": "alignment-eval",
    "crowd-quality-mturk": "crowdsourcing-methods",
    "code-swebench": "code",
    "text-relation-distant-supervision": "nlp-extraction",
    "detector-planted-mislabels": "data-quality",
    "content-moderation-welfare-ops": "content-moderation",
    "adversarial-nli-anli": "nlp",
    "clinical-annotation-guidelines": "clinical",
    "preference-anthropic-hh": "alignment-rlhf",
    "preference-constitutional-cai": "alignment-rlhf",
    "preference-llama2-rlhf": "alignment-rlhf",
    "preference-sparrow": "alignment-rlhf",
    "redteam-automated-perez": "safety-redteam",
    "redteam-external-gpt4": "safety-redteam",
    "image-classification-imagenet": "vision",
    "search-msmarco": "search-ir",
    "instruction-openassistant": "instruction-tuning",
    "instruction-self-instruct": "instruction-tuning",
    "nli-snli-artifacts": "nlp",
    "speech-librispeech": "speech",
    "data-quality-cleanlab": "data-quality",
    "eval-chatbot-arena": "alignment-eval",
    "pointcloud-segmentation-semantickitti": "autonomous-driving",
    "clinical-chexpert-labeler": "clinical",
    "benchmark-bigbench": "research",
    "synthetic-textbooks-phi": "synthetic-data",
    "video-something-something": "vision-video",
    "crowd-aggregation-dawid-skene": "crowdsourcing-methods",
    "datasheets-documentation": "meta-tooling",
    "ner-conll2003": "nlp-extraction",
    "self-training-noisy-student": "weak-supervision",
}


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def flat(s):
    return " ".join(str(s or "").split())


def main():
    cards = {}
    for path in sorted(glob.glob(os.path.join(CARDS_DIR, "*.yaml"))):
        with open(path) as f:
            d = yaml.safe_load(f)
        if not d or "id" not in d:
            print("skip (no id):", path)
            continue
        fms = []
        for fm in as_list(d.get("failure_modes")):
            if not isinstance(fm, dict):
                continue
            fms.append({
                "signature": flat(fm.get("signature")),
                "evidence": flat(fm.get("evidence")),
                "description": flat(fm.get("description")),
                "caught_by": flat(fm.get("caught_by")),
            })
        # quality_gates: how this workflow actually defends each risk — the inspiration the assembled
        # workflow quotes so conventions/audit reflect the real cards, not a generic instruction.
        gates = []
        for g in as_list(d.get("quality_gates")):
            if not isinstance(g, dict):
                continue
            catches = g.get("catches")
            catches = [s.strip() for s in str(catches or "").replace(",", " ").split() if s.strip()]
            gates.append({"gate": flat(g.get("gate")), "checks": flat(g.get("checks")),
                          "catches": catches})
        cp = d.get("cost_profile")
        cost_profile = ({k: flat(v) for k, v in cp.items()} if isinstance(cp, dict)
                        else ({"note": flat(cp)} if cp else {}))
        cards[d["id"]] = {
            "id": d["id"],
            "title": d.get("title", ""),
            "modality": flat(d.get("modality")),
            "task_structure": flat(d.get("task_structure")),
            "annotator_structure": flat(d.get("annotator_structure")),
            "scale": flat(d.get("scale")) or SCALE_BY_ANNOTATOR.get(flat(d.get("annotator_structure")), "unspecified"),
            "domain": flat(d.get("domain")) or DOMAIN_BY_ID.get(d["id"], "general"),
            "lineage": flat(d.get("lineage")),
            "distinctive": flat(d.get("distinctive")),
            "qa_mechanism": as_list(d.get("qa_mechanism")),
            "failure_signatures": as_list(d.get("failure_signatures")),
            "uses_patterns": as_list(d.get("uses_patterns")),
            "decision": flat(d.get("decision")),
            "failure_modes": fms,
            "quality_gates": gates,
            "cost_profile": cost_profile,
        }

    with open(PATTERNS_FILE) as f:
        pdoc = yaml.safe_load(f)
    patterns = {}
    for p in as_list(pdoc.get("patterns")):
        if not isinstance(p, dict) or "id" not in p:
            continue
        patterns[p["id"]] = {
            "id": p["id"],
            "name": p.get("name", ""),
            "phase": flat(p.get("phase")),
            "play": flat(p.get("play")),
            "does": flat(p.get("does")),
            "defends": as_list(p.get("defends")),
            "pairs_with": as_list(p.get("pairs_with")),
            "conflicts_with": as_list(p.get("conflicts_with")),
            "cost": flat(p.get("cost")),
            "modality_notes": flat(p.get("modality_notes")),
            "exemplified_by": as_list(p.get("exemplified_by")),
        }

    with open(OUT, "w") as f:
        json.dump({"cards": cards, "patterns": patterns}, f, indent=1, ensure_ascii=False)
    print(f"wrote {OUT}: {len(cards)} cards, {len(patterns)} patterns")


if __name__ == "__main__":
    main()
