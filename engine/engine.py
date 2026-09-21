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
import math
import os
import re
import sys
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

# Failure SENSITIVITY — how costly each failure is by default (the "what errors are most costly"
# axis of a good-data brief). Failures that corrupt the ground truth itself score highest; ones
# that add measurable/correctable noise are medium; cheaply-fixable or operational ones are low.
# The customer can override per workflow via the stub's `high_cost_signatures` / `tolerable_signatures`.
# This turns a flat build list ("what to defend") into a prioritized one ("what to defend hardest").
SIGNATURE_SEVERITY = {
    "unanchored": 3, "label_leakage": 3, "self_affinity": 3, "confounded": 3, "sampling_frame": 3,
    "class_imbalance": 2, "gaming": 2, "drift": 2, "under_specification": 2, "inflation": 2,
    "underpowered": 2,
    "bottleneck": 1, "over_specification": 1, "priming": 1,
}
DEFAULT_SEVERITY = 2


def _as_list(v):
    return [v] if isinstance(v, str) else list(v or [])


# Workflow Context (the good-data brief's "where does this sit in the larger system" question):
# what the data FEEDS changes which failures are catastrophic. Evaluation data is worthless if
# contaminated or unanchored (the claim rests on it); training data fails on coverage (the model
# learns whatever the sample under-represents). A real severity hook, not a decorative field.
DOWNSTREAM_WEIGHTS = {
    "evaluation": {"label_leakage": 1, "unanchored": 1, "underpowered": 1},
    "training": {"class_imbalance": 1, "sampling_frame": 1},
}


def signature_priority(sig, stub):
    """Cost weight for a failure signature: the default severity, raised for signatures the customer
    flagged as high-cost and lowered for ones they called tolerable (their failure-sensitivity answer),
    then reweighted by what the data feeds (their workflow-context answer)."""
    score = SIGNATURE_SEVERITY.get(sig, DEFAULT_SEVERITY)
    if sig in set(_as_list(stub.get("high_cost_signatures"))):
        score += 2
    if sig in set(_as_list(stub.get("tolerable_signatures"))):
        score -= 2
    score += DOWNSTREAM_WEIGHTS.get(stub.get("downstream") or "", {}).get(sig, 0)
    return score


def severity_label(score):
    return "high" if score >= 3 else ("low" if score <= 1 else "med")


# Agent / autonomous behavior — "strict steps vs adapt dynamically" resolves the freeze-vs-iterate
# tension (lock-then-score ⟂ active-learning-loop / edge-case-guidelines). The chosen side biases
# the build list: prefer its patterns, avoid the other's. Set via the stub's `process_mode`.
STRICT_PATTERNS = {"lock-then-score"}
ADAPTIVE_PATTERNS = {"active-learning-loop", "edge-case-guidelines"}
PROCESS_MODES = {
    "strict": {"prefer": STRICT_PATTERNS, "avoid": ADAPTIVE_PATTERNS, "label": "strict / frozen",
               "note": "Freeze the guideline before scoring (lock-then-score): reproducible and "
               "auditable, but it won't adapt as the data drifts. For autonomous systems, strict "
               "steps keep the reasoning legible and monitorable."},
    "adaptive": {"prefer": ADAPTIVE_PATTERNS, "avoid": STRICT_PATTERNS, "label": "adaptive / dynamic",
                 "note": "Let the process adapt (active-learning, iterated guidelines): responsive to "
                 "new failure modes, but harder to reproduce and audit — and for autonomous systems "
                 "the reasoning can launder, so budget extra monitoring."},
}


def agent_pref(stub):
    """The strict/adaptive preference for this workflow (or None for 'either')."""
    return PROCESS_MODES.get(stub.get("process_mode") or "")


# Edge-Case Philosophy (the good-data brief's "how should ambiguous cases be handled" question).
# Ambiguity failures (under/over_specification) have three genuinely different cures, and which one
# is RIGHT is the customer's call, not the corpus's: route the hard case to a human, legislate it
# into the guideline, or keep the disagreement as signal. The answer biases which defense the
# backwards pass suggests for those signatures — and becomes the brief's decision guideline.
AMBIGUITY_SIGS = {"under_specification", "over_specification"}
EDGE_MODES = {
    "escalate": {"prefer": {"tiered-adjudication", "human-audit-sample"},
                 "guideline": "In ambiguous cases, don't force a call: escalate to a senior "
                              "reviewer and let adjudication set the precedent."},
    "rule": {"prefer": {"edge-case-guidelines", "lock-then-score"},
             "guideline": "In ambiguous cases, resolve by the written rule: extend the guideline "
                          "with a worked example so the same case never surprises twice."},
    "signal": {"prefer": {"multi-annotator-aggregate", "inter-annotator-agreement"},
               "guideline": "In ambiguous cases, keep the disagreement: collect independent labels "
                            "and treat divergence as information, not noise to be forced flat."},
}


def edge_pref(stub):
    """The escalate/rule/signal preference for ambiguous cases (or None for unspecified)."""
    return EDGE_MODES.get(stub.get("edge_case_mode") or "")


W = 96


def load_index(path=None):
    """Read the compiled corpus. Defaults to the committed public index.json, but honors a `path`
    arg or the WD_INDEX env var so an INTERNAL deployment can point the SAME engine at a different,
    firewall-only corpus (built by build_corpus.py from a private repo) with zero code fork. The
    public repo never sees that file — only the path is configured. This is the two-track wall in
    one line: code is shared, data is swapped."""
    src = path or os.environ.get("WD_INDEX") or INDEX
    with open(src) as f:
        return json.load(f)


def load_stub(path):
    if str(path).endswith(".json"):
        # Machine-authored stubs (e.g. the retrospective bridge): JSON keeps structured
        # fields like observed_failures intact. The flat format below stays the human path.
        with open(path) as f:
            stub = json.load(f) or {}
    else:
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
    for k in ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures",
              "high_cost_signatures", "tolerable_signatures"):
        v = stub.get(k, [])
        stub[k] = [v] if isinstance(v, str) else (v or [])
    return stub


def stub_warnings(idx, stub):
    """Flag stub values outside the corpus vocabulary so a typo in a hand-written stub doesn't
    silently produce a degraded (generic-fallback) result. Returns a list of human-readable warnings."""
    v = vocab(idx)
    warns = []
    for axis in ("modality", "task_structure", "annotator_structure"):
        val = stub.get(axis)
        if val and val not in v.get(axis, []):
            warns.append(f"{axis}={val!r} is not in the corpus vocab {v.get(axis, [])}")
    for qa in stub.get("qa_mechanism", []):
        if qa not in v["qa_mechanism"]:
            warns.append(f"qa_mechanism {qa!r} is not a known mechanism")
    for pid in stub.get("uses_patterns", []):
        if pid not in idx["patterns"]:
            warns.append(f"uses_patterns {pid!r} is not a known pattern")
    return warns


# ---- helpers -------------------------------------------------------------

def wrap(text, indent="    "):
    return textwrap.fill(text, width=W, initial_indent=indent, subsequent_indent=indent)


def header(title):
    print("\n" + title)
    print("-" * min(len(title), W))


def patterns_defending(idx, sig):
    return [pid for pid, p in idx["patterns"].items() if sig in p.get("defends", [])]


def principles_for(idx, sig):
    """The principle(s) whose absence-of IS this failure signature — the backbone behind the gap."""
    return [pid for pid, p in idx.get("principles", {}).items()
            if sig in p.get("protects_against", [])]


def principle_cite(idx, sig):
    """The principle + its first cited source for a signature — so a spec probe names the study
    that established the threat, not just house prose. None if no principle covers the signature."""
    for pid in principles_for(idx, sig):
        p = idx["principles"][pid]
        if p.get("evidence"):
            return {"principle": p["name"], "source": p["evidence"][0].get("source", "")}
    return None


def backbone(idx, stub, good_means, have):
    """The positive definition of good for this workflow: the principles whose absence is one of the
    applicable failure signatures. Each carries the construct it protects, whether the design already
    secures it, and the literature that establishes it — the third tier wired into backwards-from-good.
    Ordered so the principle guarding the costliest risk leads.
    """
    rows = []
    for pid, p in idx.get("principles", {}).items():
        covered = [s for s in good_means if s in p.get("protects_against", [])]  # keep cost order
        if not covered:
            continue
        rows.append({
            "id": pid, "name": p["name"], "tenet": p.get("tenet", ""),
            "protects": covered, "defended": all(s in have for s in covered),
            "probe": p.get("probe", ""), "evidence": p.get("evidence", []),
        })
    rows.sort(key=lambda r: (-max(signature_priority(s, stub) for s in r["protects"]), r["name"]))
    return rows


def signature_idf(idx):
    """Inverse document frequency of each failure signature across the corpus.

    A signature on few cards (e.g. `gaming`, `self_affinity`) is rare and discriminating; one on
    many (e.g. `under_specification`) is near-universal. IDF lets far-analogy reward the surprising,
    high-information shared risk over the banal one.
    """
    cards = idx["cards"]
    n = len(cards) or 1
    df = Counter()
    for c in cards.values():
        for s in set(c["failure_signatures"]):
            df[s] += 1
    return {s: math.log(n / k) for s, k in df.items()}


# ---- topical (semantic Tier-1) primitives ---------------------------------
# Deterministic, stdlib token-IDF over the free-text goal vs each card's text. Lives in the engine
# (not semantic.py) because near_analogues now uses it as a PRIMARY retrieval signal — the eval showed
# the goal text catches relevant cards that axis-matching misses (e.g. llm-judge → critique-criticgpt).
# semantic.py imports these for its LLM-rerank path; keeping them here avoids a circular import.
_STOP = {
    "the", "and", "for", "with", "that", "this", "are", "from", "into", "your", "you", "our",
    "data", "workflow", "model", "models", "label", "labels", "labeling", "annotation", "annotate",
    "task", "tasks", "build", "building", "produce", "producing", "set", "sets", "use", "using",
    "via", "per", "each", "every", "want", "need", "make", "given", "across", "over", "under",
    "how", "what", "which", "when", "where", "they", "them", "its", "out", "not", "but", "all",
}


def topical_tokens(text):
    return [t for t in re.findall(r"[a-z]+", (text or "").lower())
            if len(t) >= 3 and t not in _STOP]


def card_text(card):
    parts = [card.get("title", ""), card.get("decision", ""), card.get("distinctive", ""),
             card.get("domain", "")]
    parts += [fm.get("description", "") for fm in card.get("failure_modes", [])]
    return " ".join(parts)


def card_idf(idx):
    """IDF of each token across card texts — rare topical terms carry more signal than common ones."""
    cards = idx["cards"]
    n = len(cards) or 1
    df = Counter()
    for c in cards.values():
        for t in set(topical_tokens(card_text(c))):
            df[t] += 1
    return {t: math.log(n / k) for t, k in df.items()}


def topical_scores(idx, goal):
    """{cid: (idf_sum, shared_terms)} — a card's topical relevance to the goal text. Deterministic."""
    idf = card_idf(idx)
    g = set(topical_tokens(goal))
    out = {}
    for cid, c in idx["cards"].items():
        shared = g & set(topical_tokens(card_text(c)))
        if shared:
            out[cid] = (round(sum(idf.get(t, 0.0) for t in shared), 4),
                        sorted(shared, key=lambda t: -idf.get(t, 0.0))[:6])
    return out


# How much the topical signal can add to a near-analogue's structural score. Capped so a strong
# topical match is worth ~1.5 axes (enough to pull in a topically-relevant card that misses an axis),
# never enough to swamp a genuine structural match. Tuned against eval/run_eval.py.
TOPICAL_CAP = 6.0
TOPICAL_WEIGHT = 0.5
# Bonus for a card sharing the workflow's (inferred) domain — domain coherence as a retrieval signal.
DOMAIN_COHERENCE_BONUS = 1.5


# Domains that document/tool the data process rather than BEING an annotation workflow; they make
# weak analogues for a concrete design, so they're demoted below any thematic match (else e.g. the
# datasheets card outranks ner-conll2003 as the precedent for an NER task). Unless the stub itself
# targets one of these, in which case the penalty is dropped.
META_TOOLING_DOMAINS = {"meta-tooling"}
META_TOOLING_PENALTY = 3


def near_analogues(idx, stub, n=5):
    stub_qa = set(stub.get("qa_mechanism", []))
    stub_pat = set(stub.get("uses_patterns", []))
    stub_domain = stub.get("domain")
    demote_meta = stub_domain not in META_TOOLING_DOMAINS
    # HYBRID: the structural axes PLUS a bounded topical signal from the goal text, so a card that's
    # clearly on-subject but misses an axis (the eval's llm-judge→critique-criticgpt case) still ranks.
    topical = topical_scores(idx, stub.get("goal", ""))
    prov = {}
    for cid, c in idx["cards"].items():
        s = 0.0
        if c["task_structure"] == stub.get("task_structure"):
            s += 3
        if c["annotator_structure"] == stub.get("annotator_structure"):
            s += 2
        if c["modality"] == stub.get("modality"):
            s += 2
        if stub_domain and c.get("domain") == stub_domain:
            s += 1
        # Shared skeleton PATTERNS are a stronger structural signal than shared raw QA tokens.
        s += 2 * len(set(c["uses_patterns"]) & stub_pat)
        s += len(set(c["qa_mechanism"]) & stub_qa)
        s += min(topical.get(cid, (0.0,))[0], TOPICAL_CAP) * TOPICAL_WEIGHT
        if demote_meta and c.get("domain") in META_TOOLING_DOMAINS:
            s -= META_TOOLING_PENALTY
        prov[cid] = s

    # DOMAIN COHERENCE: workflows in the same domain are analogous even when axes/words diverge (the
    # eval's welfare-ops / external-gpt4 misses share a domain with cards that DID surface). The stub
    # rarely sets `domain`, so infer it from the top provisional match and give its domain-siblings a
    # modest bonus — enough to pull a same-domain card into view, not to override a real structural hit.
    target = stub_domain
    if not target:
        top = max(prov, key=lambda c: prov[c], default=None)
        if top is not None and prov[top] > 0:
            target = idx["cards"][top].get("domain")
    if target and target not in META_TOOLING_DOMAINS:
        for cid in prov:
            if idx["cards"][cid].get("domain") == target:
                prov[cid] += DOMAIN_COHERENCE_BONUS

    scored = [(s, cid) for cid, s in prov.items() if s > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:n]


def far_analogues(idx, stub, risk, n=4):
    idf = signature_idf(idx)
    out = []
    for cid, c in idx["cards"].items():
        same_mod = c["modality"] == stub.get("modality")
        same_task = c["task_structure"] == stub.get("task_structure")
        if same_mod and same_task:
            continue  # not distant enough
        shared = set(c["failure_signatures"]) & set(risk)
        if not shared:
            continue
        # Rank by the RARITY of the shared risk (sum of IDF), not raw count: a distant card that
        # shares a rare signature is a more surprising, more valuable creative pull. List the
        # shared signatures rarest-first too, so the headline reason is the most informative one.
        score = sum(idf.get(s, 0.0) for s in shared)
        shared_sorted = sorted(shared, key=lambda s: (-idf.get(s, 0.0), s))
        out.append((score, cid, shared_sorted))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out[:n]


_DEFENSE_CACHE = {}

def defense_record(idx, pattern, signature):
    """How a pattern has actually FARED against a signature, from the corpus, not from its declaration.

      adopted — cards that ran this pattern and for which this signature is declared defended by it
      failed  — of those, the ones that REPORTED that failure anyway
      caught  — cards whose failure_modes record this pattern as what caught it

    The declaration in `patterns[].defends` is an intention. This is the record. They disagree often:
    edge-case-guidelines is declared to defend under_specification and failed on 6 of the 6 cards that
    adopted it.
    """
    k = id(idx)
    if k not in _DEFENSE_CACHE:
        adopted, failed, caught = Counter(), Counter(), Counter()
        names = {pid: {pid.replace("-", " ").lower(), (pp.get("name") or "").lower()}
                 for pid, pp in idx["patterns"].items()}
        for card in idx["cards"].values():
            rep = {fm["signature"] for fm in (card.get("failure_modes") or [])
                   if (fm.get("evidence") or "").upper().startswith("REPORTED")}
            for fm in (card.get("failure_modes") or []):
                cb = (fm.get("caught_by") or "").lower()
                for pid, ns in names.items():
                    if any(n and n in cb for n in ns):
                        caught[(pid, fm["signature"])] += 1
            for pid in (card.get("uses_patterns") or []):
                for sg in (idx["patterns"].get(pid, {}).get("defends") or []):
                    adopted[(pid, sg)] += 1
                    if sg in rep:
                        failed[(pid, sg)] += 1
        _DEFENSE_CACHE.clear()
        _DEFENSE_CACHE[k] = (adopted, failed, caught)
    adopted, failed, caught = _DEFENSE_CACHE[k]
    key = (pattern, signature)
    return {"adopted": adopted[key], "failed": failed[key], "caught": caught[key]}


# NOTE: an evidence-grounded `unguarded` verdict was built here and REVERTED 2026-09-21. It asked a
# corpus-wide question (do all declared defenders of this signature have a failure record and none a
# catch record), which is a property of the SIGNATURE, not of the workflow, so it fired on the same six
# signatures every time and scored 46.7% against the per-card record where always-guarded scores 73.3%.
# The records below are kept; the verdict needs to be conditioned on the retrieved analogues, and on
# more ground truth than the 15 cases it was measured against. See eval/loo_patterns.py.


def risk_counter(idx, cids):
    sigs = Counter()
    for cid in cids:
        for sg in idx["cards"][cid]["failure_signatures"]:
            sigs[sg] += 1
    return sigs


MIN_SUPPORT = 2


def base_rate(idx):
    """Share of the whole corpus carrying each failure signature — the denominator for lift.

    Deliberately uncached: it is a pass over 45 cards, and the single-entry id()-keyed caches
    elsewhere in this module are only safe because their callers keep the old index alive while
    building the next one. Not worth inheriting that constraint for a loop this cheap.
    """
    n = len(idx["cards"]) or 1
    c = Counter()
    for card in idx["cards"].values():
        for sg in card["failure_signatures"]:
            c[sg] += 1
    return {sg: v / n for sg, v in c.items()}


def defended(idx, stub):
    d = set(stub.get("addressed_signatures", []))
    for pid in stub.get("uses_patterns", []):
        p = idx["patterns"].get(pid)
        if p:
            d |= set(p.get("defends", []))
    return d


def conflict_pairs(idx, left, right):
    """Pairs (a, b) where pattern a (in `left`) conflicts_with pattern b (in `right`).

    Symmetric pairs are de-duplicated. With left == right this surfaces the tensions WITHIN a
    design (e.g. lock-then-score ⟂ active-learning-loop); with right = a target regime it surfaces
    tensions a flip would introduce.
    """
    left, right = set(left), set(right)
    out, seen = [], set()
    for p in left:
        for other in idx["patterns"].get(p, {}).get("conflicts_with", []):
            if other in right and p != other:
                key = tuple(sorted((p, other)))
                if key not in seen:
                    seen.add(key)
                    out.append((p, other))
    return out


def suggested_complements(idx, pattern_ids):
    """Patterns that `pairs_with` what's already adopted but aren't in the design yet —
    the synergy half of the adopt-loop (the conflict half is conflict_pairs)."""
    pids = set(pattern_ids)
    rec = Counter()
    for p in pids:
        for other in idx["patterns"].get(p, {}).get("pairs_with", []):
            if other not in pids and other in idx["patterns"]:
                rec[other] += 1
    return [{"id": pid, "name": idx["patterns"][pid]["name"],
             "cost": idx["patterns"][pid]["cost"], "by": cnt} for pid, cnt in rec.most_common()]


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


def stub_banner(stub):
    print(f"stub: {stub.get('goal','(no goal)')}")
    print(f"      {stub.get('modality','?')} / {stub.get('task_structure','?')} / "
          f"{stub.get('annotator_structure','?')} / qa={stub.get('qa_mechanism') or '[]'} / "
          f"patterns={stub.get('uses_patterns') or '[]'}")


# ---- structured analysis (shared by the CLI, the REPL, and the static site) --------
# These return plain data; the render_* helpers (CLI + REPL) and build_site.py all consume them.

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
    base = base_rate(idx)
    n_analogues = len(analogue_ids) or 1

    # Order by LIFT — how concentrated a signature is in THESE analogues against how common it is
    # in the corpus — not by raw analogue count, and not by cost.
    #
    # Raw count ranks the prior, not the setup: sampling_frame and confounded are REPORTED on 42%
    # and 36% of cards, so they took two of the top three slots on nearly every stub and the top-3
    # held only 5 distinct values across 30 cards. Lift at a support floor of 2 spreads that to 18
    # and lifts leave-one-out tail recall from 0.34 to 0.49, against an honest leave-one-out
    # constant of 0.41 (oracle ceiling 0.53). Cost-first scored 0.38 — it was pinning the same
    # expensive signatures to the top regardless of situation — so priority is now a tiebreak.
    #
    # Below MIN_SUPPORT a lift is computed off one analogue and is noise, so those rows sort last
    # rather than being dropped: they are still real risks the corpus raised, they have just not
    # earned a ranking claim.
    ranked = []
    for sig, n in full.items():
        if sig in have:
            continue
        br = base.get(sig, 0.0)
        ranked.append((sig, n, ((n / n_analogues) / br) if br else 0.0))
    ranked.sort(key=lambda r: (-(r[1] >= MIN_SUPPORT), -r[2], -signature_priority(r[0], stub), r[0]))

    rows = []
    for sig, n, lift in ranked:
        defs = [{"id": pid, "name": idx["patterns"][pid]["name"], "cost": idx["patterns"][pid]["cost"]}
                for pid in patterns_defending(idx, sig)]
        ex_cid, ex_desc = example_card_for(idx, sig, analogue_ids)
        for d in defs:
            d["record"] = defense_record(idx, d["id"], sig)
        rows.append({"signature": sig, "count": n,
                     "lift": round(lift, 2), "trusted": n >= MIN_SUPPORT,
                     "severity": severity_label(signature_priority(sig, stub)),
                     "question": QUESTIONS.get(sig, f"How will you handle `{sig}`?"),
                     "patterns": defs, "unguarded": not defs,
                     "example": {"card": ex_cid, "desc": ex_desc}})
    adopted = stub.get("uses_patterns", [])
    return {"defended": sorted(have), "open": rows,
            "complements": suggested_complements(idx, adopted),
            "conflicts": conflict_pairs(idx, adopted, adopted)}


def analyze_coverage(idx, stub):
    """How much of the applicable failure space the current design defends — the adopt-loop's
    score. Applicable = the union of signatures across the stub's near+far analogues (what 'good'
    must be free of); covered = those a pattern/addressed_signature in the design already guards.
    """
    near, far = _near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    applicable = set(risk_counter(idx, analogue_ids))
    have = defended(idx, stub)
    covered = sorted(applicable & have)
    open_ = sorted(applicable - have)
    total = len(applicable)
    adopted = stub.get("uses_patterns", [])
    return {"applicable": sorted(applicable), "covered": covered, "open": open_,
            "n_applicable": total, "n_covered": len(covered),
            "pct": (len(covered) / total) if total else 1.0,
            "conflicts": conflict_pairs(idx, adopted, adopted)}


# ---- assembling a concrete sample workflow -------------------------------
# These tables turn the abstract axes + chosen patterns into a buildable spec: the fields each
# annotator fills (by task), the action they take, the actor structure, and how each pattern slots
# into the pipeline as a step / convention / audit move.

# Per-item FIELDS the annotator produces, keyed by task_structure.
TASK_FIELDS = {
    "classification": ["label (one value from the taxonomy)", "confidence (low/med/high)",
                       "notes / why (optional)"],
    "extraction": ["span_text", "char_start", "char_end", "entity_type"],
    "structured_output": ["region (box / polygon / mask)", "class", "attributes",
                          "occlusion / truncation flags"],
    "transcription_translation": ["transcript / translation", "language or dialect",
                                  "inaudible / uncertain flags", "confidence"],
    "preference_ranking": ["choice (A / B / tie)", "strength (slight / clear / strong)",
                           "rationale", "policy-violation flag"],
    "rubric_rating": ["per-criterion score (vs anchor exemplars)", "overall score",
                      "evidence span / quote"],
    "demonstration": ["prompt", "ideal_response", "refuse-if-appropriate flag", "notes"],
    "critique_rationale": ["critique_text", "defect_severity", "located_span", "suggested_fix"],
    "relevance": ["relevance_grade (0–3)", "query_id", "doc_id", "justification"],
    "red_team": ["attack_prompt", "technique / harm_category", "model_response",
                 "success (y/n)", "severity"],
    "freeform_generation": ["prompt", "produced_output", "pass / fail",
                            "failing case or test", "notes"],
}
GENERIC_FIELDS = ["item_id", "label / judgment", "confidence", "notes"]

# One-line description of the core labeling ACTION, keyed by task_structure.
TASK_ACTION = {
    "classification": "Assign each item exactly one label from the taxonomy (plus confidence).",
    "extraction": "Mark the spans/entities in each item and tag each with its type.",
    "structured_output": "Draw the region(s) for each item and label class + attributes.",
    "transcription_translation": "Transcribe/translate each clip and flag the uncertain parts.",
    "preference_ranking": "Shown two outputs for one input, pick the better, say how much better and why.",
    "rubric_rating": "Score each item on every rubric criterion against the anchors, then overall.",
    "demonstration": "Write the ideal response for each prompt (the SFT demonstration).",
    "critique_rationale": "Find the defect in each item, locate it, and explain it.",
    "relevance": "Grade how relevant each document is to the query (0–3).",
    "red_team": "Craft inputs that elicit the harmful behavior; label success and category.",
    "freeform_generation": "Produce the output and decide pass/fail against an objective check.",
}

# How the actor structure runs the LABEL step.
ANNOTATOR_LABEL = {
    "crowd": "Crowd annotators label each item, several per item for redundancy.",
    "multi_aggregate": "Several annotators label each item independently; aggregate into one label.",
    "tiered_review": "First-pass annotators label; reviewers check; a senior adjudicator sets gold on conflicts.",
    "expert": "Domain experts label (low throughput, high skill); lighter redundancy.",
    "model_as_annotator": "A model labels every item; humans audit a sample instead of labeling all.",
    "model_assisted": "A model pre-labels; humans accept or correct (correct-the-machine).",
    "programmatic": "Labeling functions emit noisy labels; a learned label model resolves them — no per-item human.",
    "single": "A single annotator labels each item.",
}
# Annotator structures where no human labels each item — the Label step leads with the mechanism.
NONHUMAN_ANNOTATORS = {"model_as_annotator", "programmatic"}
# Domains whose work exposes annotators to harmful/distressing content (welfare duty-of-care applies).
HARMFUL_DOMAINS = {"safety-redteam", "content-moderation"}
# Goal/title words that signal harmful-content exposure — catches harmful work in a modality whose
# nearest analogues aren't domain-tagged harmful (e.g. video moderation, where the neighbors are
# generic video cards). Matched as WHOLE TOKENS, so "pharma"/"charm" don't trip "harm" and
# "moderate confidence" doesn't trip moderation. Excludes dual-meaning words (moderate, grooming).
HARMFUL_KEYWORDS = {"moderation", "abuse", "abusive", "toxic", "toxicity", "harm", "harmful",
                    "harassment", "hate", "hateful", "nsfw", "csam", "violence", "violent",
                    "suicide", "jailbreak", "extremist", "extremism", "traumatic", "disturbing",
                    "gore", "gory"}

# Each pattern's role in an assembled workflow — a pipeline phase (source/qualify/label/resolve),
# a labeling CONVENTION, or part of the AUDIT strategy — plus an imperative instruction, both now
# live ON THE PATTERN in patterns/library.yaml (`phase:` / `play:`), so the recipe is grounded in
# the corpus like everything else rather than in a parallel table here. _play_for reads them;
# _generic_play is the fallback for any pattern that hasn't declared them yet.
VALID_PHASES = {"source", "qualify", "label", "resolve", "convention", "audit"}


PHASE_BASE = [
    ("Source & sample", "Assemble candidate inputs and sample them to mirror deployment — not just the easy cases."),
    ("Write & freeze the guideline", "Draft the labeling guideline with worked examples; freeze it before scoring (see conventions)."),
    ("Qualify & calibrate", "Train and gate annotators on a calibration set so everyone shares the bar."),
    ("Label", None),  # filled from task action + annotator structure
    ("Resolve", "Measure agreement and adjudicate disagreements into final labels."),
    ("Audit & sign-off", "Run the audit strategy below before any data is accepted."),
]
PHASE_KEYS = {"Source & sample": "source", "Qualify & calibrate": "qualify",
              "Label": "label", "Resolve": "resolve"}


def _generic_play(idx, pid):
    """Fallback (phase, instruction) for a pattern whose library entry hasn't declared `phase`/`play`
    yet — derived from what it defends, so the assembler stays robust as the corpus grows."""
    p = idx["patterns"].get(pid, {})
    defends = set(p.get("defends", []))
    if defends & {"inflation", "drift", "gaming", "unanchored", "self_affinity", "label_leakage"}:
        phase = "audit"
    elif defends & {"under_specification", "over_specification"}:
        phase = "convention"
    else:
        phase = "label"
    instr = (p.get("does") or "").strip()
    return phase, (instr[:140] + "…" if len(instr) > 140 else instr) or "(see pattern detail)"


def _play_for(idx, pid):
    """A pattern's role + instruction, read from the corpus (library.yaml `phase`/`play`) with a
    derived fallback. This is what grounds conventions/audit in the corpus, not a hardcoded table."""
    p = idx["patterns"].get(pid, {})
    phase, play = p.get("phase"), p.get("play")
    if phase in VALID_PHASES and play:
        return phase, play
    return _generic_play(idx, pid)


def _inspirations(idx, pid, analogue_ids):
    """Ground a pattern's convention/audit in the actual workflow inspirations: the analogue cards
    that really use it (`seen_in`), and — where one exists — a concrete quality_gate from such a card
    that catches a risk this pattern defends (`as_done`), so the recipe quotes how a real workflow did
    it instead of only a generic instruction. Falls back to the pattern's own exemplar cards."""
    defends = set(idx["patterns"][pid].get("defends", []))
    ptoks = set(pid.replace("-", " ").split())
    insp = [cid for cid in analogue_ids if pid in idx["cards"][cid]["uses_patterns"]]
    if not insp:
        insp = [c for c in idx["patterns"][pid].get("exemplified_by", []) if c in idx["cards"]]
    # Pick the inspiration gate that best matches this pattern: most overlap with what it defends,
    # tie-broken by name affinity (so gold-honeypots quotes the honeypot gate, not just any gate).
    best = None  # (score, card, gate)
    for cid in insp:
        for g in idx["cards"][cid].get("quality_gates", []):
            overlap = len(set(g.get("catches", [])) & defends)
            if not overlap or not g.get("checks"):
                continue
            gtoks = set(g.get("gate", "").lower().replace("/", " ").replace("+", " ").split())
            score = (overlap, len(ptoks & gtoks))
            if best is None or score > best[0]:
                best = (score, cid, g)
    as_done = {"card": best[1], "gate": best[2]["gate"], "checks": best[2]["checks"]} if best else None
    # de-dup while preserving order, cap to keep the output legible
    seen, ordered = set(), []
    for cid in insp:
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)
    return {"seen_in": ordered[:3], "as_done": as_done}


def analyze_workflow(idx, stub):
    """Assemble a concrete, buildable sample workflow from the stub + its patterns: the ordered
    labeling steps, the per-item fields, the suggested conventions, and the audit strategy. The
    'chosen' patterns are what the design already has PLUS the backwards-from-good build list, so
    the output is a complete recipe, not just a critique. Each pattern's convention/audit is grounded
    in the actual inspiration cards (`seen_in` / `as_done`)."""
    bw = analyze_backwards(idx, stub)
    near, far = _near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    adopted = list(stub.get("uses_patterns", []))
    chosen, seen = [], set()
    for pid in adopted + [p["id"] for p in bw["needed_patterns"]]:
        if pid in idx["patterns"] and pid not in seen:
            seen.add(pid)
            chosen.append(pid)

    # Welfare is a duty-of-care, not a data-quality signature, so it never enters the signature-driven
    # build list — but harmful-content work demands it. Surface it for red-teaming / moderation.
    goal_toks = set(re.findall(r"[a-z]+", (stub.get("goal") or "").lower()))
    harmful = (stub.get("task_structure") == "red_team"
               or bool(goal_toks & HARMFUL_KEYWORDS)
               or any(idx["cards"][cid].get("domain") in HARMFUL_DOMAINS for _, cid in near[:3]))
    if harmful and "annotator-welfare-protocol" in idx["patterns"] and "annotator-welfare-protocol" not in seen:
        seen.add("annotator-welfare-protocol")
        chosen.append("annotator-welfare-protocol")

    plays = {}
    for pid in chosen:
        role, instr = _play_for(idx, pid)
        insp = _inspirations(idx, pid, analogue_ids)
        plays.setdefault(role, []).append({
            "id": pid, "name": idx["patterns"][pid]["name"], "instruction": instr,
            "have": pid in adopted, "cost": idx["patterns"][pid]["cost"],
            "seen_in": insp["seen_in"], "as_done": insp["as_done"]})

    task = stub.get("task_structure")
    annot = stub.get("annotator_structure")
    steps = []
    for i, (phase, base) in enumerate(PHASE_BASE, 1):
        if phase == "Label":
            action = TASK_ACTION.get(task, f"produce the {task} label for each item.")
            who = ANNOTATOR_LABEL.get(annot, "Annotators label each item.")
            if annot in NONHUMAN_ANNOTATORS:
                # No human labels each item, so lead with the mechanism and frame the task as the
                # target output (avoids "assign each item a label … no per-item human").
                base = f"{who} Target per item: {action[0].lower() + action[1:]}"
            else:
                base = f"{action} {who}"
        steps.append({"n": i, "phase": phase, "do": base,
                      "patterns": plays.get(PHASE_KEYS.get(phase, ""), [])})

    # Prefer a precedent that shares the MODALITY — an audio task should cite an audio card, not a
    # text card that merely shares the task. Scan the FULL ranking (the top-5 `near` may not include
    # a same-modality card when it scores low); fall back to the top analogue when none match.
    ranked = near_analogues(idx, stub, n=len(idx["cards"]))
    precedent = next((cid for _, cid in ranked
                      if idx["cards"][cid]["modality"] == stub.get("modality")), None)
    if precedent is None:
        precedent = ranked[0][1] if ranked else None

    return {
        "goal": stub.get("goal", ""), "modality": stub.get("modality"),
        "task": task, "annotator": annot,
        "precedent": precedent,
        "steps": steps,
        "fields": TASK_FIELDS.get(task, GENERIC_FIELDS),
        "conventions": plays.get("convention", []),
        "audit": plays.get("audit", []),
        "spec_threats": bw["spec_threats"],
        "chosen": chosen, "adopted": adopted,
        "to_add": [p for p in chosen if p not in adopted],
        "agent": _agent_summary(idx, stub),
    }


def _agent_summary(idx, stub):
    pref = agent_pref(stub)
    if not pref:
        return None
    return {"mode": stub.get("process_mode"), "label": pref["label"], "note": pref["note"],
            "prefer": sorted(p for p in pref["prefer"] if p in idx["patterns"]),
            "avoid": sorted(p for p in pref["avoid"] if p in idx["patterns"])}


def analyze_backwards(idx, stub):
    """Run the engine in REVERSE — from the definition of good back to the workflow that produces it.

    'Good data' = data free of the ways it goes bad for this kind of capture (the applicable failure
    signatures). For each, the gate/pattern that guarantees against it -> a backwards-assembled build
    list. Plus a spec stress-test: the subset of threats that mean your *definition* of good may be a proxy.
    """
    near, far = _near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    full = risk_counter(idx, analogue_ids)
    # Seed the risk set with signatures the customer DECLARED (high-cost / observed / failure_signatures)
    # even when no corpus analogue logged them. A failure that already happened to the customer must
    # still receive its library defense — grounded in their own war story rather than a corpus example —
    # instead of being silently dropped because the public corpus never recorded that signature.
    declared = (set(_as_list(stub.get("high_cost_signatures")))
                | set(_as_list(stub.get("failure_signatures")))
                | {f.get("signature") for f in (stub.get("observed_failures") or [])
                   if isinstance(f, dict) and f.get("signature")})
    for sig in declared:
        if sig and sig not in full:
            full[sig] = 0  # count 0 = customer-declared, no corpus analogue; priority still ranks it
    have = defended(idx, stub)
    good_means, guarantees = [], []
    # Cost-first ordering: the build list leads with the most expensive failures to be free of.
    for sig, n in sorted(full.items(), key=lambda kv: (-signature_priority(kv[0], stub), -kv[1], kv[0])):
        good_means.append(sig)
        defs = patterns_defending(idx, sig)
        ex_cid, _ = example_card_for(idx, sig, analogue_ids)
        guarantees.append({
            "signature": sig, "count": n, "defended": sig in have, "unguarded": not defs,
            "severity": severity_label(signature_priority(sig, stub)),
            "patterns": [{"id": p, "name": idx["patterns"][p]["name"], "cost": idx["patterns"][p]["cost"]}
                         for p in defs],
            "example": ex_cid,
        })
    # Tight build list: ONE primary pattern per still-OPEN failure mode (dedup; skip already-defended).
    # Bias by the agent-behavior preference (favor the chosen side's patterns, avoid the other's) and,
    # for ambiguity signatures, by the customer's edge-case philosophy (escalate / rule / signal).
    pref = agent_pref(stub)
    epref = edge_pref(stub)
    needed, seen = [], set(stub.get("uses_patterns", []))
    for g in guarantees:
        if g["defended"] or not g["patterns"]:
            continue
        cands = g["patterns"]
        if pref:
            favored = [c for c in cands if c["id"] in pref["prefer"]]
            rest = [c for c in cands if c["id"] not in pref["avoid"] and c not in favored]
            cands = (favored + rest) or cands
        if epref and g["signature"] in AMBIGUITY_SIGS:
            # the edge-case answer is the SPECIFIC question about ambiguity — it outranks the
            # general process preference on these signatures, so it sorts last (wins).
            favored = [c for c in cands if c["id"] in epref["prefer"]]
            cands = (favored + [c for c in cands if c not in favored]) or cands
        p = cands[0]
        if p["id"] not in seen:
            seen.add(p["id"])
            needed.append({"id": p["id"], "name": p["name"], "for": g["signature"],
                           "severity": g["severity"]})
    spec_threats = [{"signature": s, "question": SPEC_THREATS[s][0], "probe": SPEC_THREATS[s][1],
                     "cite": principle_cite(idx, s)}
                    for s in good_means if s in SPEC_THREATS]
    return {"good_means": good_means, "guarantees": guarantees,
            "needed_patterns": needed, "spec_threats": spec_threats, "already_have": sorted(have),
            "principles": backbone(idx, stub, good_means, have)}


def analyze_modality_shift(idx, stub, to):
    kept = []
    for pid in stub.get("uses_patterns", []):
        p = idx["patterns"].get(pid)
        kept.append({"id": pid, "name": p["name"] if p else "(unknown)",
                     "notes": p["modality_notes"] if p else ""})
    if to and to == stub.get("modality"):
        # Shifting into your own modality is a no-op; emitting "new risks" would be misleading.
        return {"kept": kept, "same": True, "no_target": False, "new_risks": [], "transplants": []}
    target_cards = [cid for cid, c in idx["cards"].items() if c["modality"] == to]
    if not target_cards:
        return {"kept": kept, "same": False, "no_target": True, "new_risks": [], "transplants": []}
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
    return {"kept": kept, "same": False, "no_target": False,
            "new_risks": new_risks, "transplants": transplants}


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
    if to and to == stub.get(axis):
        # Flipping an axis to its current value is a no-op; don't report spurious "new" signatures.
        return {"empty": False, "same": True, "survive": [], "at_risk": [], "conflicts": [], "new_sig": []}
    flipped = [cid for cid, c in idx["cards"].items() if c.get(axis) == to]
    if not flipped:
        return {"empty": True, "same": False, "survive": [], "at_risk": [], "conflicts": [], "new_sig": []}
    flipped_patterns = set()
    for cid in flipped:
        flipped_patterns |= set(idx["cards"][cid]["uses_patterns"])
    kept = stub.get("uses_patterns", [])
    survive = [p for p in kept if p in flipped_patterns]
    at_risk = [p for p in kept if p not in flipped_patterns]
    conflicts = conflict_pairs(idx, kept, flipped_patterns)
    near_ids = [cid for _, cid in near_analogues(idx, stub)][:3]
    current = set(risk_counter(idx, near_ids)) | defended(idx, stub)
    new_sig = []
    for s, _ in risk_counter(idx, flipped).most_common():
        if s in current:
            continue
        defs = patterns_defending(idx, s)
        new_sig.append({"signature": s, "defender": defs[0] if defs else None})
    return {"empty": False, "same": False, "survive": survive, "at_risk": at_risk,
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


# ---- renderers (shared by the CLI and the REPL) --------------------------
# Each takes a structured analyze_* result and prints it. The REPL drives these directly, so the
# terminal output is identical whether you run a one-shot subcommand or the interactive loop.

def render_list(idx):
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


def render_retrieve(near, far):
    header("NEAR analogues (shared modality / task / annotator)")
    if not near:
        print("  (none)")
    for r in near:
        print(f"  [{r['score']}] {r['id']}  ({r['modality']}/{r['task']}) — "
              f"shares: {', '.join(r['why'])}")
    header("FAR analogues (distant modality/task, shared RISK — the creative pulls)")
    if not far:
        print("  (none)")
    for r in far:
        print(f"  {r['id']}  ({r['modality']}/{r['task']}) — "
              f"shares signatures: {', '.join(r['shared'])}")


def render_synergy(res):
    """Conflicts + complements among the adopted patterns — the adopt-loop's two halves."""
    if res.get("conflicts"):
        header("⟂ CONFLICTS in your current design")
        for a, b in res["conflicts"]:
            print(f"  `{a}` ⟂ `{b}` — a real design tension; choose one deliberately.")
    if res.get("complements"):
        header("+ COMPLEMENTS (pair cleanly with what you've adopted)")
        for c in res["complements"][:6]:
            print(f"  `{c['id']}` — {c['name']} (cost: {c['cost']})")


def render_interrogate(res):
    header("MODE 3 — interrogation (answer these before you build)")
    if res["defended"]:
        print(f"  already defended by your patterns/addressed: {', '.join(res['defended'])}\n")
    if not res["open"]:
        print("  No open risks among your analogues — your patterns cover them. "
              "(Rare; double-check coverage.)")
    for i, r in enumerate(res["open"], 1):
        sig, n = r["signature"], r["count"]
        sev = f"  ({r['severity']}-cost)" if r.get("severity") else ""
        # Show the lift, not just the count: the list is ORDERED by lift, so printing the raw
        # analogue count alone makes the order look arbitrary (4 above 5 above 2).
        if r.get("trusted"):
            why = (f"{n} analogue{'s' if n > 1 else ''}, {r['lift']}x its rate across the corpus"
                   if r.get("lift") else f"{n} analogue{'s' if n > 1 else ''}")
        else:
            why = f"{n} analogue{'s' if n > 1 else ''}, too few to rank"
        print(f"  {i}. [{sig}]{sev}  ({why})")
        print(wrap(r["question"], "     "))
        if r["unguarded"]:
            print(f"      UNGUARDED — no pattern in the library defends `{sig}` (a corpus gap).")
        for p in r["patterns"]:
            rc = p.get("record") or {}
            note = ""
            if rc.get("adopted"):
                note = f"; {rc['failed']} of {rc['adopted']} workflows that ran it still hit this"
                if rc.get("caught"):
                    note += f", {rc['caught']} record it catching this"
            print(f"      borrow `{p['id']}` — {p['name']} (defends {sig}; cost: {p['cost']}{note})")
        ex = r["example"]
        if ex["card"]:
            tag = "" if not ex["desc"] else f": {ex['desc'][:120]}"
            print(f"      seen in `{ex['card']}`{tag}")
        print()
    render_synergy(res)


def render_backwards(stub, res):
    task = stub.get("task_structure", "this")
    if res.get("principles"):
        header(f'"GOOD" {task} DATA HAS  (the backbone — what good data IS)')
        for p in res["principles"]:
            tag = "  ✓ secured" if p["defended"] else ""
            print(f"  • {p['name']}{tag}  (= absence of: {', '.join(p['protects'])})")
            if p.get("tenet"):
                print(wrap(p["tenet"], "      "))
            ev = p.get("evidence") or []
            if ev and ev[0].get("source"):
                seen = f"; seen in `{ev[0]['seen_in']}`" if ev[0].get("seen_in") else ""
                print(f"      established by: {ev[0]['source']}{seen}")
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
    header("BACKWARDS-ASSEMBLED BUILD LIST (costliest risks first)")
    if res["needed_patterns"]:
        for p in res["needed_patterns"]:
            sev = f"[{p['severity']}] " if p.get("severity") else ""
            print(f"  + {sev}{p['id']} — {p['name']}  (closes: {p['for']})")
    else:
        print("  (your design already covers every applicable failure mode)")
    header("BUT FIRST — IS YOUR 'GOOD' ACTUALLY GOOD?  (stress-test the spec)")
    for s in res["spec_threats"]:
        print(f"  [{s['signature']}]")
        print(wrap(s["question"], "     "))
        print(f"      probe: {s['probe']}")
        if s.get("cite"):
            print(f"      per {s['cite']['principle']} — {s['cite']['source']}")


def render_coverage(res):
    total = res["n_applicable"]
    bar_len = 24
    filled = round(bar_len * res["pct"]) if total else bar_len
    bar = "#" * filled + "." * (bar_len - filled)
    header("COVERAGE")
    print(f"  [{bar}] {res['n_covered']}/{total} applicable risks defended ({res['pct']*100:.0f}%)")
    if res["covered"]:
        print(f"  covered: {', '.join(res['covered'])}")
    if res["open"]:
        print(f"  open:    {', '.join(res['open'])}")
    for a, b in res.get("conflicts", []):
        print(f"  ⟂ conflict: `{a}` vs `{b}` — pick one.")


def _print_play(p):
    tag = "have" if p["have"] else "ADD"
    print(wrap(f"[{tag}] `{p['id']}` — {p['instruction']}", "  "))
    if p.get("as_done"):
        a = p["as_done"]
        print(wrap(f"as `{a['card']}` does — {a['gate']}: {a['checks']}", "      "))
    elif p.get("seen_in"):
        print(f"      seen in: {', '.join(p['seen_in'])}")


def render_workflow(res):
    print(f"\n>>> ASSEMBLED SAMPLE WORKFLOW")
    print(f"    {res['goal']}")
    print(f"    {res['modality']} / {res['task']} / {res['annotator']}"
          + (f"  ·  closest precedent: {res['precedent']}" if res["precedent"] else ""))
    header("LABELING STEPS")
    for s in res["steps"]:
        print(f"  {s['n']}. {s['phase']} — {s['do']}")
        for p in s["patterns"]:
            tag = "have" if p["have"] else "ADD"
            print(wrap(f"[{tag}] `{p['id']}`: {p['instruction']}", "       "))
    header("FIELDS the annotator fills per item")
    for f in res["fields"]:
        print(f"  - {f}")
    header("SUGGESTED CONVENTIONS")
    if not res["conventions"]:
        print("  (none beyond a frozen, example-driven guideline)")
    for p in res["conventions"]:
        _print_play(p)
    header("AUDIT STRATEGY")
    if not res["audit"]:
        print("  (add a gold anchor + a stratified human audit)")
    for p in res["audit"]:
        _print_play(p)
    if res["spec_threats"]:
        print("  — and stress-test that 'good' isn't a proxy:")
        for s in res["spec_threats"]:
            print(wrap(f"{s['signature']}: {s['probe']}", "      "))


def render_modality_shift(res, to):
    print(f"\n>>> MODALITY-SHIFT to: {to}\n")
    if res.get("same"):
        print(f"  (that's already your modality — pick a different one to shift into)")
        return
    header("KEEP (modality-independent skeleton) — and what swaps for " + to)
    if not res["kept"]:
        print("  (stub lists no patterns — fill uses_patterns to carry a skeleton across)")
    for k in res["kept"]:
        print(f"  {k['id']} — {k['name']}")
        print(wrap("swaps: " + (k["notes"] or "(no modality notes)"), "      "))
    if res["no_target"]:
        print(f"\n  (no {to} cards in the corpus yet — can't derive modality-specific risks)")
        return
    header(f"NEW failure modes {to} introduces (re-derive these)")
    for nr in res["new_risks"]:
        guard = (f"borrow `{nr['defender']}`" if nr["defender"] else "UNGUARDED — corpus gap")
        print(f"  [{nr['signature']}] {guard}" + (f" — e.g. {nr['example']}" if nr["example"] else ""))
    header(f"TRANSPLANT candidates ({to} workflows use these; your stub doesn't)")
    for t in res["transplants"]:
        print(f"  `{t['id']}` — {t['name']} (cost: {t['cost']})")


def render_transplant(rows):
    header("TRANSPLANT — patterns from DISTANT workflows that defend your open risks")
    if not rows:
        print("  (no distant transplants found — your open risks may need new patterns)")
    for t in rows:
        print(f"  `{t['id']}` — {t['name']}")
        print(wrap(f"imports a defense for `{t['signature']}` from {t['from']} "
                   f"({t['from_mod']}/{t['from_task']}); cost: {t['cost']}", "      "))


def render_flip(res, axis, to, actor=False):
    label = "ACTOR-SUBSTITUTE" if actor else "FLIP"
    print(f"\n>>> {label}: {axis} -> {to}\n")
    if res.get("same"):
        print(f"  (your {axis} is already {to} — pick a different value to flip into)")
        return
    if res["empty"]:
        print(f"  (no cards with {axis}={to} — can't derive the flipped regime)")
        return
    header("patterns that SURVIVE (also used by the flipped regime)")
    print("  " + (", ".join(res["survive"]) if res["survive"] else "(none of your patterns)"))
    header("patterns that may NOT carry over (not seen in the flipped regime)")
    print("  " + (", ".join(res["at_risk"]) if res["at_risk"] else "(none)"))
    if res["conflicts"]:
        header("CONFLICTS introduced")
        for a, b in res["conflicts"]:
            print(f"  `{a}` conflicts_with `{b}` (which the {to} regime uses)")
    header(f"NEW signatures the {to} regime tends to hit")
    for ns in res["new_sig"]:
        print(f"  [{ns['signature']}] "
              + (f"borrow `{ns['defender']}`" if ns["defender"] else "UNGUARDED"))


def render_cookbook(res):
    print(f"\n>>> COOKBOOK index — recipes by {res['by']}\n")
    for val, items in res["groups"].items():
        header(f"{val}  ({len(items)})")
        for it in items:
            extra = f"  · {it['lineage']}" if it["lineage"] else ""
            print(f"  {it['id']}  ({it['modality']}/{it['task']}){extra}")


def render_compare(idx, res):
    print(f"\n>>> COMPARE org / house-style approaches to: {res['task']}\n")
    if res["few"]:
        print(f"  (need >=2 cards with task_structure={res['task']}; "
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


# ---- commands (thin CLI wrappers: load -> analyze -> render) --------------

def cmd_list(idx, args):
    render_list(idx)


def cmd_retrieve(idx, stub, args):
    stub_banner(stub)
    near, far = analyze_retrieve(idx, stub)
    render_retrieve(near, far)


def cmd_interrogate(idx, stub, args):
    stub_banner(stub)
    render_interrogate(analyze_interrogate(idx, stub))


def cmd_backwards(idx, stub, args):
    stub_banner(stub)
    render_backwards(stub, analyze_backwards(idx, stub))


def cmd_modality_shift(idx, stub, args):
    stub_banner(stub)
    render_modality_shift(analyze_modality_shift(idx, stub, args.to), args.to)


def cmd_transplant(idx, stub, args):
    stub_banner(stub)
    render_transplant(analyze_transplant(idx, stub))


def cmd_flip(idx, stub, args, actor=False):
    axis = "annotator_structure" if actor else args.axis
    stub_banner(stub)
    render_flip(analyze_flip(idx, stub, axis, args.to), axis, args.to, actor)


def cmd_cookbook(idx, args):
    if args.by not in COOKBOOK_ANGLES:
        print(f"  --by must be one of: {', '.join(COOKBOOK_ANGLES)}")
        return
    render_cookbook(analyze_cookbook(idx, args.by))


def cmd_compare(idx, args):
    render_compare(idx, analyze_compare(idx, args.task))


def cmd_workflow(idx, stub, args):
    stub_banner(stub)
    render_workflow(analyze_workflow(idx, stub))


def main():
    ap = argparse.ArgumentParser(description="Workflow Designer engine (deterministic, stdlib).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sp = sub.add_parser("cookbook")
    sp.add_argument("--by", default="domain")
    sp = sub.add_parser("compare")
    sp.add_argument("--task", required=True)
    for name in ("retrieve", "interrogate", "transplant", "backwards", "workflow"):
        sp = sub.add_parser(name)
        sp.add_argument("--stub", default=DEFAULT_STUB)
    sp = sub.add_parser("semantic")  # opt-in topical retrieval (stdlib Tier 1; LLM Tier 2 if keyed)
    sp.add_argument("--stub", default=DEFAULT_STUB)
    sp.add_argument("--no-llm", action="store_true", help="force the deterministic topical tier")
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
    for w in stub_warnings(idx, stub):
        print(f"warning: {w}", file=sys.stderr)
    if args.cmd == "retrieve":
        cmd_retrieve(idx, stub, args)
    elif args.cmd == "interrogate":
        cmd_interrogate(idx, stub, args)
    elif args.cmd == "backwards":
        cmd_backwards(idx, stub, args)
    elif args.cmd == "workflow":
        cmd_workflow(idx, stub, args)
    elif args.cmd == "modality-shift":
        cmd_modality_shift(idx, stub, args)
    elif args.cmd == "transplant":
        cmd_transplant(idx, stub, args)
    elif args.cmd == "semantic":
        import semantic  # opt-in; imports llm only if a key is present
        stub_banner(stub)
        semantic.render_semantic(semantic.analyze_semantic(idx, stub, use_llm=not args.no_llm))
    elif args.cmd == "flip":
        cmd_flip(idx, stub, args)
    elif args.cmd == "actor-substitute":
        cmd_flip(idx, stub, args, actor=True)


if __name__ == "__main__":
    main()
