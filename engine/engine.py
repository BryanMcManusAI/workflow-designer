#!/usr/bin/env python3
"""Workflow Designer — a deterministic creative partner over the ML-data-workflow corpus.

Stdlib only. Reads index.json (built by build_index.py) and a small YAML 'stub' describing the
new workflow you want to design. No LLM, no network: every suggestion is templated from the
corpus and CITES the pattern it borrows, the failure signature it inherits, and its cost — so a
recommendation is always legible back to a real prior workflow with a real price.

Commands:
  list                          summarize the corpus + signature coverage
  retrieve     --stub S         near + far analogues for the stub workflow
  interrogate  --stub S         mode 3: the unguarded risks + the patterns that catch them
  modality-shift --stub S --to M   re-instantiate the stub's skeleton in modality M
  transplant   --stub S         patterns from distant workflows that defend your open risks
  flip         --stub S --axis A --to V   change a constraint; see what survives/breaks
  actor-substitute --stub S --to V        swap the annotator structure; see what changes

Stub format (flat YAML), e.g.:
  goal: Evaluate AI-generated marketing copy at scale
  modality: text
  task_structure: rubric_rating
  annotator_structure: model_as_annotator
  qa_mechanism: []
  uses_patterns: []
  addressed_signatures: []
"""
import argparse
import json
import os
import textwrap
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.json")
DEFAULT_STUB = os.path.join(HERE, "examples", "new_workflow.yaml")

QUESTIONS = {
    "unanchored": "Do you have a gold / ground-truth set to validate against, or are you trusting raw outputs?",
    "self_affinity": "Is the model that PRODUCES the data the same family as the one that JUDGES it? You may be measuring self-preference.",
    "inflation": "Absolute rubric with anchor exemplars, or relative scoring that will drift upward over time?",
    "drift": "Will your guidelines / acceptance bar stay fixed, or shift across the campaign — and how would you detect it?",
    "sampling_frame": "Is your labeled data representative of deployment, or only the easy cases that already look good?",
    "priming": "Could item order or A/B position leak into the labels? Are you randomizing presentation?",
    "confounded": "Is a spurious cue (length, author, source, tier) riding along with the signal you actually want?",
    "under_specification": "Will two competent annotators agree? Have you written edge-case examples for the boundary?",
    "over_specification": "Is your taxonomy so rich that annotators can't apply it consistently, or that categories are starved of data?",
    "bottleneck": "Which single stage gates throughput (adjudication, expert review)? What happens at peak load?",
    "class_imbalance": "Are the rare-but-important classes represented enough for the model to learn them?",
    "label_leakage": "Could the label be derivable from a feature absent at deployment — or is your eval contaminated by training data?",
    "gaming": "How are annotators paid / incentivized? Could they optimize the metric (templates, speed) instead of quality?",
}

# The subset of failure signatures that threaten the DEFINITION of good itself — the detector's
# lesson: the gold is the thing most likely to be wrong. Each is a "is your 'good' a proxy?" probe.
SPEC_THREATS = {
    "unanchored": (
        "You have no ground truth — is 'good' just whatever your producer emitted? Without a gold reference you can't tell good from confident-and-wrong.",
        "build a small expert gold set; measure producer-vs-gold agreement"),
    "label_leakage": (
        "Could 'good' be predicted from PART of the input — a length/format/position cue, or eval data the model already trained on? Then the label leaks a proxy.",
        "partial-input baseline: predict the label from a fragment of the input"),
    "self_affinity": (
        "If a model defines or judges 'good', is it perceiving quality or recalling its own family's style? Re-label a slice with a different model family.",
        "cross-family re-label a slice; measure divergence"),
    "confounded": (
        "Is a spurious cue — length, formatting, author, fluency — standing in for 'good'? Hold it fixed and see if the judgment survives.",
        "length/style-control a slice; check 'good' still holds"),
    "gaming": (
        "Can an annotator hit 'good' by templating or speed without producing quality? Then you're capturing the metric, not the good.",
        "seed honeypots; test whether 'good' is reachable by gaming"),
    "inflation": (
        "Does the bar for 'good' creep upward over time? Re-score frozen anchor exemplars and watch the standard drift.",
        "re-score fixed anchor exemplars across the campaign"),
    "drift": (
        "Is your definition of 'good' moving under you as the data/model changes?",
        "periodic re-score of a held-out gold set"),
    "under_specification": (
        "Would two competent people agree 'good' applies? Low agreement means 'good' isn't actually defined yet.",
        "two raters on the same items; measure IAA"),
    "over_specification": (
        "Is 'good' so rigid it mislabels genuinely novel-but-good cases? Test it against the hard tail, not the easy bulk.",
        "apply the spec to the hard/novel tail"),
    "sampling_frame": (
        "Are you only certifying 'good' on the easy cases? 'Good' on a biased sample isn't good at deployment.",
        "stratified audit across the full distribution, not a random sample"),
}

W = 96


def load_index():
    with open(INDEX) as f:
        return json.load(f)


def load_stub(path):
    stub = {}
    with open(path) as f:
        for line in f:
            line = line.split("#", 1)[0].rstrip()
            if not line.strip() or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                stub[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
            elif val:
                stub[key] = val.strip("\"'")
            else:
                stub[key] = []
    for k in ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures"):
        v = stub.get(k, [])
        stub[k] = [v] if isinstance(v, str) else (v or [])
    return stub


# ---- helpers -------------------------------------------------------------

def wrap(text, indent="    "):
    return textwrap.fill(text, width=W, initial_indent=indent, subsequent_indent=indent)


def header(title):
    print("\n" + title)
    print("-" * min(len(title), W))


def patterns_defending(idx, sig):
    return [pid for pid, p in idx["patterns"].items() if sig in p.get("defends", [])]


def near_analogues(idx, stub, n=5):
    scored = []
    for cid, c in idx["cards"].items():
        s = 0
        if c["task_structure"] == stub.get("task_structure"):
            s += 3
        if c["annotator_structure"] == stub.get("annotator_structure"):
            s += 2
        if c["modality"] == stub.get("modality"):
            s += 2
        s += len(set(c["qa_mechanism"]) & set(stub.get("qa_mechanism", [])))
        s += len(set(c["uses_patterns"]) & set(stub.get("uses_patterns", [])))
        if s > 0:
            scored.append((s, cid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:n]


def far_analogues(idx, stub, risk, n=4):
    out = []
    for cid, c in idx["cards"].items():
        same_mod = c["modality"] == stub.get("modality")
        same_task = c["task_structure"] == stub.get("task_structure")
        if same_mod and same_task:
            continue  # not distant enough
        shared = sorted(set(c["failure_signatures"]) & set(risk))
        if shared and (not same_mod or not same_task):
            out.append((len(shared), cid, shared))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out[:n]


def risk_counter(idx, cids):
    sigs = Counter()
    for cid in cids:
        for sg in idx["cards"][cid]["failure_signatures"]:
            sigs[sg] += 1
    return sigs


def defended(idx, stub):
    d = set(stub.get("addressed_signatures", []))
    for pid in stub.get("uses_patterns", []):
        p = idx["patterns"].get(pid)
        if p:
            d |= set(p.get("defends", []))
    return d


def example_card_for(idx, sig, cids):
    fallback = None
    for cid in cids:
        c = idx["cards"][cid]
        if sig not in c["failure_signatures"]:
            continue
        for fm in c["failure_modes"]:
            if fm["signature"].startswith(sig):
                if fm["evidence"].upper().startswith("REPORTED"):
                    return cid, fm["description"]
                fallback = fallback or (cid, fm["description"])
        fallback = fallback or (cid, "")
    return fallback or (None, "")


def cite_patterns(idx, sig):
    out = []
    for pid in patterns_defending(idx, sig):
        p = idx["patterns"][pid]
        out.append(f"      borrow `{pid}` — {p['name']} (defends {sig}; cost: {p['cost']})")
    return out


def stub_banner(stub):
    print(f"stub: {stub.get('goal','(no goal)')}")
    print(f"      {stub.get('modality','?')} / {stub.get('task_structure','?')} / "
          f"{stub.get('annotator_structure','?')} / qa={stub.get('qa_mechanism') or '[]'} / "
          f"patterns={stub.get('uses_patterns') or '[]'}")


# ---- structured analysis (shared by the CLI and the Streamlit UI) --------
# These return plain data; cmd_* (below) and wd_app.py (Streamlit) both render them.

def _near_far(idx, stub):
    near = near_analogues(idx, stub)
    risk = risk_counter(idx, [cid for _, cid in near[:3]])
    far = far_analogues(idx, stub, set(risk))
    return near, far


def analyze_retrieve(idx, stub):
    near, far = _near_far(idx, stub)
    near_rows = []
    for s, cid in near:
        c = idx["cards"][cid]
        why = [k for k, axis in (("task", "task_structure"), ("annotator", "annotator_structure"),
                                 ("modality", "modality")) if c[axis] == stub.get(axis)]
        near_rows.append({"score": s, "id": cid, "modality": c["modality"],
                          "task": c["task_structure"], "why": why or ["qa/patterns"]})
    far_rows = [{"id": cid, "modality": idx["cards"][cid]["modality"],
                 "task": idx["cards"][cid]["task_structure"], "shared": shared}
                for _, cid, shared in far]
    return near_rows, far_rows


def analyze_interrogate(idx, stub):
    near, far = _near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    full = risk_counter(idx, analogue_ids)
    have = defended(idx, stub)
    rows = []
    for sig, n in full.most_common():
        if sig in have:
            continue
        defs = [{"id": pid, "name": idx["patterns"][pid]["name"], "cost": idx["patterns"][pid]["cost"]}
                for pid in patterns_defending(idx, sig)]
        ex_cid, ex_desc = example_card_for(idx, sig, analogue_ids)
        rows.append({"signature": sig, "count": n,
                     "question": QUESTIONS.get(sig, f"How will you handle `{sig}`?"),
                     "patterns": defs, "unguarded": not defs,
                     "example": {"card": ex_cid, "desc": ex_desc}})
    return {"defended": sorted(have), "open": rows}


def analyze_backwards(idx, stub):
    """Run the engine in REVERSE — from the definition of good back to the workflow that produces it.

    'Good data' = data free of the ways it goes bad for this kind of capture (the applicable failure
    signatures). For each, the gate/pattern that guarantees against it -> a backwards-assembled build
    list. Plus a spec stress-test: the subset of threats that mean your *definition* of good may be a proxy.
    """
    near, far = _near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    full = risk_counter(idx, analogue_ids)
    have = defended(idx, stub)
    good_means, guarantees = [], []
    for sig, n in full.most_common():
        good_means.append(sig)
        defs = patterns_defending(idx, sig)
        ex_cid, _ = example_card_for(idx, sig, analogue_ids)
        guarantees.append({
            "signature": sig, "count": n, "defended": sig in have, "unguarded": not defs,
            "patterns": [{"id": p, "name": idx["patterns"][p]["name"], "cost": idx["patterns"][p]["cost"]}
                         for p in defs],
            "example": ex_cid,
        })
    # Tight build list: ONE primary pattern per still-OPEN failure mode (dedup; skip already-defended).
    needed, seen = [], set(stub.get("uses_patterns", []))
    for g in guarantees:
        if g["defended"] or not g["patterns"]:
            continue
        p = g["patterns"][0]
        if p["id"] not in seen:
            seen.add(p["id"])
            needed.append({"id": p["id"], "name": p["name"], "for": g["signature"]})
    spec_threats = [{"signature": s, "question": SPEC_THREATS[s][0], "probe": SPEC_THREATS[s][1]}
                    for s in good_means if s in SPEC_THREATS]
    return {"good_means": good_means, "guarantees": guarantees,
            "needed_patterns": needed, "spec_threats": spec_threats, "already_have": sorted(have)}


def analyze_modality_shift(idx, stub, to):
    kept = []
    for pid in stub.get("uses_patterns", []):
        p = idx["patterns"].get(pid)
        kept.append({"id": pid, "name": p["name"] if p else "(unknown)",
                     "notes": p["modality_notes"] if p else ""})
    target_cards = [cid for cid, c in idx["cards"].items() if c["modality"] == to]
    if not target_cards:
        return {"kept": kept, "no_target": True, "new_risks": [], "transplants": []}
    near_ids = [cid for _, cid in near_analogues(idx, stub)][:3]
    current = set(risk_counter(idx, near_ids)) | defended(idx, stub)
    new_risks = []
    for s, _ in risk_counter(idx, target_cards).most_common():
        if s in current:
            continue
        defs = patterns_defending(idx, s)
        ex_cid, _ = example_card_for(idx, s, target_cards)
        new_risks.append({"signature": s, "defender": defs[0] if defs else None, "example": ex_cid})
    kept_set = set(stub.get("uses_patterns", []))
    tcount = Counter()
    for cid in target_cards:
        for pid in idx["cards"][cid]["uses_patterns"]:
            if pid not in kept_set and pid in idx["patterns"]:
                tcount[pid] += 1
    transplants = [{"id": pid, "name": idx["patterns"][pid]["name"], "cost": idx["patterns"][pid]["cost"]}
                   for pid, _ in tcount.most_common(8)]
    return {"kept": kept, "no_target": False, "new_risks": new_risks, "transplants": transplants}


def analyze_transplant(idx, stub):
    near, far = _near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    full = risk_counter(idx, analogue_ids)
    have = defended(idx, stub)
    open_risks = [s for s, _ in full.most_common() if s not in have]
    stub_mod, stub_task = stub.get("modality"), stub.get("task_structure")
    rows, shown = [], set()
    for sig in open_risks:
        for pid in patterns_defending(idx, sig):
            if pid in shown:
                continue
            p = idx["patterns"][pid]
            distant = [c for c in p["exemplified_by"] if c in idx["cards"]
                       and (idx["cards"][c]["modality"] != stub_mod
                            or idx["cards"][c]["task_structure"] != stub_task)]
            if not distant:
                continue
            shown.add(pid)
            rows.append({"id": pid, "name": p["name"], "signature": sig, "from": distant[0],
                         "from_mod": idx["cards"][distant[0]]["modality"],
                         "from_task": idx["cards"][distant[0]]["task_structure"], "cost": p["cost"]})
    return rows


def analyze_flip(idx, stub, axis, to):
    flipped = [cid for cid, c in idx["cards"].items() if c.get(axis) == to]
    if not flipped:
        return {"empty": True, "survive": [], "at_risk": [], "conflicts": [], "new_sig": []}
    flipped_patterns = set()
    for cid in flipped:
        flipped_patterns |= set(idx["cards"][cid]["uses_patterns"])
    kept = stub.get("uses_patterns", [])
    survive = [p for p in kept if p in flipped_patterns]
    at_risk = [p for p in kept if p not in flipped_patterns]
    conflicts = []
    for p in kept:
        for other in set(idx["patterns"].get(p, {}).get("conflicts_with", [])) & flipped_patterns:
            conflicts.append((p, other))
    near_ids = [cid for _, cid in near_analogues(idx, stub)][:3]
    current = set(risk_counter(idx, near_ids)) | defended(idx, stub)
    new_sig = []
    for s, _ in risk_counter(idx, flipped).most_common():
        if s in current:
            continue
        defs = patterns_defending(idx, s)
        new_sig.append({"signature": s, "defender": defs[0] if defs else None})
    return {"empty": False, "survive": survive, "at_risk": at_risk,
            "conflicts": conflicts, "new_sig": new_sig}


def analyze_compare(idx, task):
    cards = [c for c in idx["cards"].values() if c["task_structure"] == task]
    if len(cards) < 2:
        return {"task": task, "few": True, "variants": [], "shared_patterns": [], "shared_sigs": []}
    n = len(cards)
    pat_count, sig_count = Counter(), Counter()
    for c in cards:
        pat_count.update(set(c["uses_patterns"]))
        sig_count.update(set(c["failure_signatures"]))
    shared_p = sorted(p for p, k in pat_count.items() if k == n)
    shared_s = sorted(s for s, k in sig_count.items() if k == n)
    variants = []
    for c in sorted(cards, key=lambda x: x.get("lineage") or x["id"]):
        variants.append({
            "id": c["id"], "lineage": c.get("lineage") or "(unspecified)",
            "annotator": c["annotator_structure"],
            "distinctive": c.get("distinctive", ""),
            "distinct_patterns": sorted(p for p in set(c["uses_patterns"]) if pat_count[p] == 1),
            "distinct_sigs": sorted(s for s in set(c["failure_signatures"]) if sig_count[s] == 1),
            "decision": c.get("decision", ""),
        })
    return {"task": task, "few": False, "variants": variants,
            "shared_patterns": sorted(shared_p), "shared_sigs": sorted(shared_s)}


def tasks_with_variants(idx, minimum=2):
    counts = Counter(c["task_structure"] for c in idx["cards"].values())
    return sorted(t for t, n in counts.items() if n >= minimum)


COOKBOOK_ANGLES = ["domain", "scale", "modality", "task_structure", "annotator_structure", "lineage"]


def analyze_cookbook(idx, by):
    """Group every recipe by one angle — the cookbook's by-<angle> index."""
    groups = {}
    for cid, c in idx["cards"].items():
        key = c.get(by) or "(unspecified)"
        groups.setdefault(key, []).append({
            "id": cid, "title": c.get("title", ""), "modality": c["modality"],
            "task": c["task_structure"], "lineage": c.get("lineage", ""),
        })
    ordered = dict(sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    return {"by": by, "groups": ordered}


def vocab(idx):
    """Controlled-vocab values present in the corpus, for UI dropdowns."""
    out = {"modality": set(), "task_structure": set(), "annotator_structure": set(),
           "qa_mechanism": set(), "failure_signature": set()}
    for c in idx["cards"].values():
        out["modality"].add(c["modality"])
        out["task_structure"].add(c["task_structure"])
        out["annotator_structure"].add(c["annotator_structure"])
        out["qa_mechanism"].update(c["qa_mechanism"])
        out["failure_signature"].update(c["failure_signatures"])
    for p in idx["patterns"].values():
        out["failure_signature"].update(p["defends"])
    return {k: sorted(v) for k, v in out.items()}


# ---- commands ------------------------------------------------------------

def cmd_list(idx, args):
    cards, pats = idx["cards"], idx["patterns"]
    print(f"corpus: {len(cards)} workflow cards, {len(pats)} patterns")
    for axis in ("modality", "task_structure", "annotator_structure"):
        vals = Counter(c[axis] for c in cards.values())
        print(f"\n{axis}:")
        for v, n in vals.most_common():
            print(f"  {v:<22} {n}")
    sigcov = Counter()
    for c in cards.values():
        for s in c["failure_signatures"]:
            sigcov[s] += 1
    header("failure-signature coverage")
    for s, n in sigcov.most_common():
        print(f"  {s:<22} {n}")


def _analogues(idx, stub):
    near = near_analogues(idx, stub)
    near_ids = [cid for _, cid in near]
    risk = risk_counter(idx, near_ids[:3])
    far = far_analogues(idx, stub, set(risk))
    return near, far, risk


def cmd_retrieve(idx, stub, args):
    stub_banner(stub)
    near, far, _ = _analogues(idx, stub)
    header("NEAR analogues (shared modality / task / annotator)")
    if not near:
        print("  (none)")
    for s, cid in near:
        c = idx["cards"][cid]
        why = []
        if c["task_structure"] == stub.get("task_structure"):
            why.append("task")
        if c["annotator_structure"] == stub.get("annotator_structure"):
            why.append("annotator")
        if c["modality"] == stub.get("modality"):
            why.append("modality")
        print(f"  [{s}] {cid}  ({c['modality']}/{c['task_structure']}) — shares: {', '.join(why) or 'qa/patterns'}")
    header("FAR analogues (distant modality/task, shared RISK — the creative pulls)")
    if not far:
        print("  (none)")
    for n, cid, shared in far:
        c = idx["cards"][cid]
        print(f"  {cid}  ({c['modality']}/{c['task_structure']}) — shares signatures: {', '.join(shared)}")


def cmd_interrogate(idx, stub, args):
    stub_banner(stub)
    near, far, risk = _analogues(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    full_risk = risk_counter(idx, analogue_ids)
    have = defended(idx, stub)
    open_risks = [(s, n) for s, n in full_risk.most_common() if s not in have]
    header("MODE 3 — interrogation (answer these before you build)")
    if have:
        print(f"  already defended by your patterns/addressed: {', '.join(sorted(have))}\n")
    if not open_risks:
        print("  No open risks among your analogues — your patterns cover them. (Rare; double-check coverage.)")
        return
    for i, (sig, n) in enumerate(open_risks, 1):
        q = QUESTIONS.get(sig, f"How will you handle `{sig}`?")
        print(f"  {i}. [{sig}]  (seen in {n} analogue{'s' if n > 1 else ''})")
        print(wrap(q, "     "))
        cites = cite_patterns(idx, sig)
        if cites:
            for line in cites:
                print(line)
        else:
            print(f"      UNGUARDED — no pattern in the library defends `{sig}` (a corpus gap).")
        ex_cid, ex_desc = example_card_for(idx, sig, analogue_ids)
        if ex_cid:
            tag = "" if not ex_desc else f": {ex_desc[:120]}"
            print(f"      seen in `{ex_cid}`{tag}")
        print()


def cmd_backwards(idx, stub, args):
    stub_banner(stub)
    res = analyze_backwards(idx, stub)
    task = stub.get("task_structure", "this")
    header(f'"GOOD" {task} DATA MEANS FREE OF')
    print("  " + (", ".join(res["good_means"]) or "(no analogues — fill the stub axes)"))
    header("TO GUARANTEE THAT, THE WORKFLOW NEEDS")
    for g in res["guarantees"]:
        tag = "  ✓ already in your design" if g["defended"] else ""
        print(f"  [{g['signature']}]{tag}")
        if g["unguarded"]:
            print("      UNGUARDED — no pattern defends this (a corpus gap)")
        for p in g["patterns"][:3]:
            print(f"      -> {p['id']} — {p['name']} (cost: {p['cost']})")
        if g["example"]:
            print(f"      seen in `{g['example']}`")
    header("BACKWARDS-ASSEMBLED BUILD LIST (one defense per open risk)")
    if res["needed_patterns"]:
        for p in res["needed_patterns"]:
            print(f"  + {p['id']} — {p['name']}  (closes: {p['for']})")
    else:
        print("  (your design already covers every applicable failure mode)")
    header("BUT FIRST — IS YOUR 'GOOD' ACTUALLY GOOD?  (stress-test the spec)")
    for s in res["spec_threats"]:
        print(f"  [{s['signature']}]")
        print(wrap(s["question"], "     "))
        print(f"      probe: {s['probe']}")


def cmd_modality_shift(idx, stub, args):
    to = args.to
    stub_banner(stub)
    print(f"\n>>> MODALITY-SHIFT to: {to}\n")
    kept = stub.get("uses_patterns", [])
    header("KEEP (modality-independent skeleton) — and what swaps for " + to)
    if not kept:
        print("  (stub lists no patterns — fill uses_patterns to carry a skeleton across)")
    for pid in kept:
        p = idx["patterns"].get(pid)
        if not p:
            print(f"  {pid}  (unknown pattern)")
            continue
        print(f"  {pid} — {p['name']}")
        print(wrap("swaps: " + (p["modality_notes"] or "(no modality notes)"), "      "))
    target_cards = [cid for cid, c in idx["cards"].items() if c["modality"] == to]
    if not target_cards:
        print(f"\n  (no {to} cards in the corpus yet — can't derive modality-specific risks)")
        return
    near_ids = [cid for _, cid in near_analogues(idx, stub)][:3]
    current = set(risk_counter(idx, near_ids)) | defended(idx, stub)
    target_sigs = risk_counter(idx, target_cards)
    new_risks = [s for s, _ in target_sigs.most_common() if s not in current]
    header(f"NEW failure modes {to} introduces (re-derive these)")
    for s in new_risks:
        ex_cid, ex_desc = example_card_for(idx, s, target_cards)
        defs = patterns_defending(idx, s)
        guard = (f"borrow `{defs[0]}`" if defs else "UNGUARDED — corpus gap")
        print(f"  [{s}] {guard}" + (f" — e.g. {ex_cid}" if ex_cid else ""))
    kept_set = set(kept)
    transplants = []
    for cid in target_cards:
        for pid in idx["cards"][cid]["uses_patterns"]:
            if pid not in kept_set and pid in idx["patterns"]:
                transplants.append(pid)
    header(f"TRANSPLANT candidates ({to} workflows use these; your stub doesn't)")
    for pid in [p for p, _ in Counter(transplants).most_common(8)]:
        p = idx["patterns"][pid]
        print(f"  `{pid}` — {p['name']} (cost: {p['cost']})")


def cmd_transplant(idx, stub, args):
    stub_banner(stub)
    near, far, risk = _analogues(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    full_risk = risk_counter(idx, analogue_ids)
    have = defended(idx, stub)
    open_risks = [s for s, _ in full_risk.most_common() if s not in have]
    header("TRANSPLANT — patterns from DISTANT workflows that defend your open risks")
    stub_mod, stub_task = stub.get("modality"), stub.get("task_structure")
    shown = set()
    for sig in open_risks:
        for pid in patterns_defending(idx, sig):
            if pid in shown:
                continue
            p = idx["patterns"][pid]
            distant = [c for c in p["exemplified_by"]
                       if c in idx["cards"]
                       and (idx["cards"][c]["modality"] != stub_mod
                            or idx["cards"][c]["task_structure"] != stub_task)]
            if not distant:
                continue
            shown.add(pid)
            print(f"  `{pid}` — {p['name']}")
            print(wrap(f"imports a defense for `{sig}` from {distant[0]} "
                       f"({idx['cards'][distant[0]]['modality']}/{idx['cards'][distant[0]]['task_structure']}); "
                       f"cost: {p['cost']}", "      "))
    if not shown:
        print("  (no distant transplants found — your open risks may need new patterns)")


def cmd_flip(idx, stub, args, actor=False):
    axis = "annotator_structure" if actor else args.axis
    to = args.to
    stub_banner(stub)
    label = "ACTOR-SUBSTITUTE" if actor else "FLIP"
    print(f"\n>>> {label}: {axis} -> {to}\n")
    flipped = [cid for cid, c in idx["cards"].items() if c[axis] == to]
    if not flipped:
        print(f"  (no cards with {axis}={to} — can't derive the flipped regime)")
        return
    flipped_patterns = set()
    for cid in flipped:
        flipped_patterns |= set(idx["cards"][cid]["uses_patterns"])
    kept = stub.get("uses_patterns", [])
    survive = [p for p in kept if p in flipped_patterns]
    at_risk = [p for p in kept if p not in flipped_patterns]
    conflicts = []
    for p in kept:
        cw = set(idx["patterns"].get(p, {}).get("conflicts_with", []))
        for other in cw & flipped_patterns:
            conflicts.append((p, other))
    near_ids = [cid for _, cid in near_analogues(idx, stub)][:3]
    current = set(risk_counter(idx, near_ids)) | defended(idx, stub)
    new_sig = [s for s, _ in risk_counter(idx, flipped).most_common() if s not in current]
    header("patterns that SURVIVE (also used by the flipped regime)")
    print("  " + (", ".join(survive) if survive else "(none of your patterns)"))
    header("patterns that may NOT carry over (not seen in the flipped regime)")
    print("  " + (", ".join(at_risk) if at_risk else "(none)"))
    if conflicts:
        header("CONFLICTS introduced")
        for a, b in conflicts:
            print(f"  `{a}` conflicts_with `{b}` (which the {to} regime uses)")
    header(f"NEW signatures the {to} regime tends to hit")
    for s in new_sig:
        defs = patterns_defending(idx, s)
        print(f"  [{s}] " + (f"borrow `{defs[0]}`" if defs else "UNGUARDED"))


def cmd_cookbook(idx, args):
    if args.by not in COOKBOOK_ANGLES:
        print(f"  --by must be one of: {', '.join(COOKBOOK_ANGLES)}")
        return
    res = analyze_cookbook(idx, args.by)
    print(f"\n>>> COOKBOOK index — recipes by {args.by}\n")
    for val, items in res["groups"].items():
        header(f"{val}  ({len(items)})")
        for it in items:
            extra = f"  · {it['lineage']}" if it["lineage"] else ""
            print(f"  {it['id']}  ({it['modality']}/{it['task']}){extra}")


def cmd_compare(idx, args):
    res = analyze_compare(idx, args.task)
    print(f"\n>>> COMPARE org / house-style approaches to: {args.task}\n")
    if res["few"]:
        print(f"  (need >=2 cards with task_structure={args.task}; "
              f"types with variants: {', '.join(tasks_with_variants(idx))})")
        return
    header("shared across ALL approaches (the invariant core)")
    print("  patterns:   " + (", ".join(res["shared_patterns"]) or "(none)"))
    print("  signatures: " + (", ".join(res["shared_sigs"]) or "(none)"))
    for v in res["variants"]:
        header(f"{v['lineage']}   [{v['id']}]")
        if v["distinctive"]:
            print(wrap("DISTINCTIVE: " + v["distinctive"], "  "))
        print(f"  annotator: {v['annotator']}")
        print(f"  patterns only this lab uses: {', '.join(v['distinct_patterns']) or '(none unique)'}")
        print(f"  risks only this lab carries: {', '.join(v['distinct_sigs']) or '(none unique)'}")


def main():
    ap = argparse.ArgumentParser(description="Workflow Designer engine (deterministic, stdlib).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sp = sub.add_parser("cookbook")
    sp.add_argument("--by", default="domain")
    sp = sub.add_parser("compare")
    sp.add_argument("--task", required=True)
    for name in ("retrieve", "interrogate", "transplant", "backwards"):
        sp = sub.add_parser(name)
        sp.add_argument("--stub", default=DEFAULT_STUB)
    sp = sub.add_parser("modality-shift")
    sp.add_argument("--stub", default=DEFAULT_STUB)
    sp.add_argument("--to", required=True)
    sp = sub.add_parser("flip")
    sp.add_argument("--stub", default=DEFAULT_STUB)
    sp.add_argument("--axis", default="annotator_structure")
    sp.add_argument("--to", required=True)
    sp = sub.add_parser("actor-substitute")
    sp.add_argument("--stub", default=DEFAULT_STUB)
    sp.add_argument("--to", required=True)
    args = ap.parse_args()

    idx = load_index()
    if args.cmd == "list":
        cmd_list(idx, args)
        return
    if args.cmd == "compare":
        cmd_compare(idx, args)
        return
    if args.cmd == "cookbook":
        cmd_cookbook(idx, args)
        return
    stub = load_stub(args.stub)
    if args.cmd == "retrieve":
        cmd_retrieve(idx, stub, args)
    elif args.cmd == "interrogate":
        cmd_interrogate(idx, stub, args)
    elif args.cmd == "backwards":
        cmd_backwards(idx, stub, args)
    elif args.cmd == "modality-shift":
        cmd_modality_shift(idx, stub, args)
    elif args.cmd == "transplant":
        cmd_transplant(idx, stub, args)
    elif args.cmd == "flip":
        cmd_flip(idx, stub, args)
    elif args.cmd == "actor-substitute":
        cmd_flip(idx, stub, args, actor=True)


if __name__ == "__main__":
    main()
