#!/usr/bin/env python3
"""The INFORMER — the advisory front door over the same engine as the designer.

Where the designer PRESCRIBES a workflow (steps, fields, conventions, audit), the informer ADVISES
the customer on what good data means for THEIR goal: the constructs that define it, what quietly
wrecks each one, the five-minute check that would catch it, and one way to secure it. It asks the
customer to cede nothing — no pipeline handover, no adopted design — which is why it fits the
quality-org posture (upstream advisory partner) where a designer can read as territorial.

Same corpus, same principles tier, same failure-mode graph, same deterministic engine. Two products,
two front doors, ONE engine: analyze_inform() is a composition of the existing analyze_* passes with
a customer-facing shape. The designer remains the deeper opt-in the brief hands off to.

Anti-decoration rule (the tool's own discipline): every line in the brief is load-bearing — a check
the customer can run, a defense they can adopt, a war story that really happened. No validity seminar.

  python3 engine/inform.py --stub customer.yaml            # render the brief (markdown)
"""
import argparse
import sys

try:
    from . import engine
except ImportError:
    import engine

# How many principles / spec-threats the brief leads with. An advisory doc that lists everything is
# a doc nobody acts on; the cost-ranking picks what to defend hardest and the tail is summarized.
BRIEF_PRINCIPLES = 5
BRIEF_THREATS = 3


def _war_story(idx, sig, analogue_ids, stub, used):
    """A REPORTED failure description for this signature — 'if you skip it, here is what actually
    happened to someone'. Advisory credibility lives on the examples reading apt, so prefer cards
    that share the customer's task/modality and never reuse a card across principles (a brief that
    cites the same case three times reads canned). Returns (card_id, description) or (None, '')."""
    def rank(cid):
        c = idx["cards"][cid]
        return (cid in used,                                   # fresh cards first
                c["task_structure"] != stub.get("task_structure"),
                c["modality"] != stub.get("modality"))
    ordered = sorted(analogue_ids, key=rank)
    cid, desc = engine.example_card_for(idx, sig, ordered)
    if cid:
        used.add(cid)
    return cid, desc


def _one_defense(idx, g, analogue_ids):
    """The single suggested defense for an open risk: the backwards pass's top pattern, grounded in
    how a real analogue used it. A suggestion with a price, not a build instruction."""
    if not g["patterns"]:
        return None
    p = g["patterns"][0]
    insp = engine._inspirations(idx, p["id"], analogue_ids)
    return {"id": p["id"], "name": p["name"], "cost": p["cost"],
            "seen_in": insp["seen_in"][:1], "as_done": insp["as_done"]}


def analyze_inform(idx, stub):
    """Compose the customer-facing Good Data Brief from the existing engine passes."""
    bw = engine.analyze_backwards(idx, stub)
    near, far = engine._near_far(idx, stub)
    analogue_ids = [cid for _, cid in near] + [cid for _, cid, _ in far]
    by_sig = {g["signature"]: g for g in bw["guarantees"]}

    principles, used_stories = [], set()
    for p in bw["principles"][:BRIEF_PRINCIPLES]:
        # the costliest still-open signature this principle protects — what the customer defends first
        open_sigs = [s for s in p["protects"] if not by_sig.get(s, {}).get("defended")]
        lead = open_sigs[0] if open_sigs else (p["protects"][0] if p["protects"] else None)
        story_card, story = (_war_story(idx, lead, analogue_ids, stub, used_stories)
                             if lead else (None, ""))
        defense = _one_defense(idx, by_sig[lead], analogue_ids) if lead and lead in by_sig else None
        ev = (p.get("evidence") or [{}])[0]
        principles.append({
            "name": p["name"], "tenet": p["tenet"], "secured": not open_sigs,
            "risks": p["protects"], "lead_risk": lead,
            "severity": by_sig.get(lead, {}).get("severity", "med") if lead else "med",
            "check": p.get("probe", ""),
            "war_story": {"card": story_card, "desc": story} if story else None,
            "defense": defense,
            "source": ev.get("source", ""),
        })
    # what to defend hardest: open risks in the backwards pass's cost order
    priorities = [{"signature": g["signature"], "severity": g["severity"]}
                  for g in bw["guarantees"] if not g["defended"]]
    threats = bw["spec_threats"][:BRIEF_THREATS]
    covered = [g["signature"] for g in bw["guarantees"] if g["defended"]]

    # REVIEWER MENTAL MODEL ("think of this task as…"): the closest precedent's own one-line
    # purpose — the analogical frame a reviewer holds while judging items. The frame lives or dies
    # on aptness, so prefer a precedent that shares the TASK SHAPE and modality over one that merely
    # scores high structurally (a red-team card is a bad frame for a rating task).
    ranked = engine.near_analogues(idx, stub, n=len(idx["cards"]))
    precedent = next((cid for _, cid in ranked
                      if idx["cards"][cid]["task_structure"] == stub.get("task_structure")
                      and idx["cards"][cid]["modality"] == stub.get("modality")), None)
    if precedent is None:
        precedent = next((cid for _, cid in ranked
                          if idx["cards"][cid]["task_structure"] == stub.get("task_structure")),
                         ranked[0][1] if ranked else None)
    mental_model = None
    if precedent:
        mental_model = {"card": precedent,
                        "frame": idx["cards"][precedent].get("decision", "").strip()}

    # DECISION GUIDELINES ("in ambiguous cases, prioritize X over Y"): the customer's edge-case and
    # process answers resolved into rules, plus any real tension among the suggested defenses —
    # emitted only when an answer or a conflict actually exists (load-bearing, never decorative).
    guidelines = []
    ep = engine.edge_pref(stub)
    if ep:
        guidelines.append(ep["guideline"])
    ap = engine.agent_pref(stub)
    if ap:
        guidelines.append(f"Process: run it {ap['label']}. {ap['note']}")
    needed_ids = [p["id"] for p in bw["needed_patterns"]] + list(stub.get("uses_patterns", []))
    for a, b in engine.conflict_pairs(idx, needed_ids, needed_ids):
        side = (a if ap and a in ap["prefer"] else b if ap and b in ap["prefer"] else None)
        res = (f" Your process answer favors `{side}`." if side
               else " A real design tension — choose deliberately, don't drift into both.")
        guidelines.append(f"`{a}` pulls against `{b}`.{res}")

    # STARTER CONVENTIONS (the condensed set — core principles, not a 40-rule catalog): the suggested
    # defenses phrased as the imperative house rules they become, each still tied to its pattern.
    conventions = []
    for p in bw["needed_patterns"][:6]:
        _, play = engine._play_for(idx, p["id"])
        conventions.append({"id": p["id"], "rule": play, "closes": p["for"]})

    return {"goal": stub.get("goal", ""), "task": stub.get("task_structure", ""),
            "modality": stub.get("modality", ""), "annotator": stub.get("annotator_structure", ""),
            "principles": principles, "spec_threats": threats,
            "priorities": priorities, "already_covered": covered,
            "mental_model": mental_model, "guidelines": guidelines, "conventions": conventions,
            "n_principles_total": len(bw["principles"])}


def render_inform_md(res):
    """The brief as a customer-facing markdown document."""
    L = []
    w = L.append
    w(f"# Good Data Brief")
    w(f"\n**Your goal:** {res['goal']}")
    w(f"*{res['modality']} · {res['task']} · {res['annotator']}*\n")
    names = [p["name"].split(" (")[0] for p in res["principles"][:3]]
    w(f"**In one line:** for this data to be good, it has to have "
      f"{', '.join(names[:-1])} and {names[-1]} — each is defined below, with the check that "
      f"tells you whether you have it and one way to get it.\n")

    w("## What “good” means for your data\n")
    for i, p in enumerate(res["principles"], 1):
        sev = {"high": "▲ costly to get wrong", "med": "● moderate", "low": "○ cheap to fix later"}
        w(f"### {i}. {p['name']}" + ("  ✓ (your plan already covers this)" if p["secured"] else ""))
        w(f"{p['tenet']}")
        if p["war_story"]:
            w(f"\n> **If you skip it:** {p['war_story']['desc']}  \n"
              f"> *(a real case: `{p['war_story']['card']}`)*")
        if p["check"]:
            w(f"\n**The five-minute check:** {p['check']}")
        if p["defense"] and not p["secured"]:
            d = p["defense"]
            done = (f" — as `{d['as_done']['card']}` does: {d['as_done']['checks']}"
                    if d.get("as_done") else (f" — see `{d['seen_in'][0]}`" if d["seen_in"] else ""))
            w(f"\n**One way to get it:** {d['name']} (cost: {d['cost']}){done}")
        if p["lead_risk"]:
            w(f"\n<sub>guards against `{p['lead_risk']}` · {sev.get(p['severity'],'')} · "
              f"established by {p['source']}</sub>")
        w("")

    if res["spec_threats"]:
        w("## Before any of that: is your “good” actually good?\n")
        w("The most expensive failure isn't missing a check — it's certifying data against a "
          "definition that was quietly measuring something else. Three tests of the definition itself:\n")
        for t in res["spec_threats"]:
            w(f"- **{t['question']}**  \n  *Run:* {t['probe']}"
              + (f"  · <sub>{t['cite']['source']}</sub>" if t.get("cite") else ""))
        w("")

    if res["mental_model"] and res["mental_model"]["frame"]:
        w("## How to think about this task\n")
        w(f"Think of it as: *{res['mental_model']['frame']}*  \n"
          f"<sub>(the closest real precedent: `{res['mental_model']['card']}` — worth reading "
          f"before you write a guideline)</sub>\n")

    if res["guidelines"]:
        w("## Decision guidelines\n")
        for g in res["guidelines"]:
            w(f"- {g}")
        w("")

    if res["conventions"]:
        w("## Starter conventions — the condensed set\n")
        w("Six core rules beat forty edge cases. These are the house rules your open risks imply, "
          "each one a real pattern with a track record:\n")
        for c in res["conventions"]:
            w(f"- {c['rule']}  <sub>(`{c['id']}` · closes `{c['closes']}`)</sub>")
        w("")

    if res["priorities"]:
        order = ", ".join(f"`{p['signature']}` ({p['severity']})" for p in res["priorities"][:6])
        w(f"## What to defend hardest, in order\n\n{order}\n")
    if res["already_covered"]:
        w(f"<sub>Already covered by your plan: {', '.join(res['already_covered'])}</sub>\n")

    w("---\n\n*This brief tells you what good data is for your goal and how to check you're getting "
      "it — how you build toward it is yours. If you want the full buildable workflow (labeling "
      "steps, per-item fields, conventions, audit plan), the designer assembles it from the same "
      "evidence base.*")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="The informer — a Good Data Brief for a customer goal.")
    ap.add_argument("--stub", required=True)
    args = ap.parse_args()
    idx = engine.load_index()
    stub = engine.load_stub(args.stub)
    for warn in engine.stub_warnings(idx, stub):
        print(f"warning: {warn}", file=sys.stderr)
    print(render_inform_md(analyze_inform(idx, stub)))


if __name__ == "__main__":
    main()
