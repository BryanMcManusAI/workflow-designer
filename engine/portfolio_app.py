"""Workflow Designer — public portfolio demo (a guided showcase, not the working tool).

A separate, polished, deployable Streamlit app for an audience (recruiters / peers). It reuses the
same engine + committed index.json (no keys, no private corpus), and WALKS a visitor through what
the creative partner does on a curated example — read-mostly, narrative, ~60 seconds to "get it".

Deploy: push the workflow-designer repo, point Streamlit Community Cloud at engine/portfolio_app.py
(requirements: engine/requirements.txt). Publishing is Bryan's call.
"""
import streamlit as st

import engine

st.set_page_config(page_title="Workflow Designer — a creative partner for ML data workflows",
                   layout="wide", page_icon="🧬")

idx = engine.load_index()
n_domains = len({c["domain"] for c in idx["cards"].values()})

# ── Hero ──────────────────────────────────────────────────────────────────
st.title("🧬 Workflow Designer")
st.subheader("A creative partner for designing ML data workflows")
st.markdown(
    "Describe a data workflow you want to build. The partner finds **analogous prior workflows**, "
    "**interrogates** your design against the failure modes they hit, and suggests **creative moves** — "
    "and every single suggestion is grounded in a real prior workflow with a real cost. "
    "It's deterministic: no LLM in the loop, nothing it can't trace back to a source. It can't bluff."
)
s1, s2, s3, s4 = st.columns(4)
s1.metric("Recipes", len(idx["cards"]))
s2.metric("Reusable patterns", len(idx["patterns"]))
s3.metric("Domains", n_domains)
s4.metric("Grounding", "published methods")

with st.expander("How it works"):
    st.markdown(
        "- The corpus is a graph: **workflows ↔ patterns ↔ failure signatures**. Each workflow is a real, "
        "documented way of producing ML training/eval data, decomposed the same way so they're comparable.\n"
        "- **Near** analogues share your modality / task / annotator structure; **far** analogues share a "
        "*failure signature* across distant domains — the source of surprising-but-valid ideas.\n"
        "- Interrogation collects the risks your analogues hit, subtracts what your design already defends, and "
        "for each open risk asks the methods-reviewer question + names the pattern that catches it and its cost.\n"
        "- The guardrail: every suggestion cites a **pattern**, the **failure signature** it inherits, and the "
        "**cost** it adds — legible back to a real prior workflow, never a confident fabrication."
    )

st.divider()

# ── Curated examples ──────────────────────────────────────────────────────
EXAMPLES = {
    "Collect preference data for an image-generation reward model": {
        "goal": "Collect pairwise preference data to train a reward model for an image generator",
        "modality": "image", "task_structure": "preference_ranking", "annotator_structure": "crowd",
        "qa_mechanism": ["gold_honeypots", "agreement"],
        "uses_patterns": ["multi-annotator-aggregate", "gold-honeypots"],
    },
    "Evaluate AI-generated marketing copy with an LLM judge": {
        "goal": "Evaluate AI-generated marketing copy at scale with an LLM judge",
        "modality": "text", "task_structure": "rubric_rating", "annotator_structure": "model_as_annotator",
        "qa_mechanism": [], "uses_patterns": ["human-gold-anchor"],
    },
    "Build a code-generation evaluation set": {
        "goal": "Build an eval set that measures whether generated code is functionally correct",
        "modality": "code", "task_structure": "freeform_generation", "annotator_structure": "expert",
        "qa_mechanism": ["execution_check"], "uses_patterns": ["execution-verification"],
    },
}
SHIFT_TARGET = {"image": "video", "text": "image", "code": "text", "audio": "text"}

choice = st.selectbox("Pick a workflow to design:", list(EXAMPLES))
stub = dict(EXAMPLES[choice])
stub.setdefault("addressed_signatures", [])
stub.setdefault("failure_signatures", [])
st.caption(f"**{stub['goal']}** — `{stub['modality']}` / `{stub['task_structure']}` / "
           f"`{stub['annotator_structure']}` · starting patterns: "
           + (", ".join(f"`{p}`" for p in stub['uses_patterns']) or "none"))

# ── Step 1 — Retrieve ─────────────────────────────────────────────────────
st.header("1 · It finds analogous prior workflows")
near, far = engine.analyze_retrieve(idx, stub)
cn, cf = st.columns(2)
with cn:
    st.markdown("**Near** — share your modality / task / annotator")
    for r in near[:4]:
        st.markdown(f"- `{r['id']}`  ({r['modality']}/{r['task']}) — shares {', '.join(r['why'])}")
with cf:
    st.markdown("**Far** — distant domain, *same risk* (the creative pulls)")
    for r in far[:4]:
        st.markdown(f"- `{r['id']}`  ({r['modality']}/{r['task']}) — shares: {', '.join(r['shared'])}")

# ── Step 2 — Interrogate ──────────────────────────────────────────────────
st.header("2 · It interrogates your design against their failure modes")
st.caption("Each suggestion names the pattern that defends the risk, the cost it adds, and a real workflow that hit it. That traceability is the point.")
res = engine.analyze_interrogate(idx, stub)
if res["defended"]:
    st.success("Already defended by your starting patterns: " + ", ".join(res["defended"]))
for r in res["open"][:6]:
    with st.container(border=True):
        st.markdown(f"**`{r['signature']}`**  ·  {r['question']}")
        for p in r["patterns"][:3]:
            st.markdown(f"- borrow **`{p['id']}`** — {p['name']}  \n"
                        f"<span style='color:#888'>defends {r['signature']} · cost: {p['cost']}</span>",
                        unsafe_allow_html=True)
        if r["example"]["card"]:
            st.caption(f"a real workflow that hit this: `{r['example']['card']}`")
if len(res["open"]) > 6:
    st.caption(f"…and {len(res['open']) - 6} more open risks.")

# ── Step 3 — A creative move (modality-shift) ─────────────────────────────
to = SHIFT_TARGET.get(stub["modality"], "text")
st.header(f"3 · It makes creative moves — e.g. “what would this become for {to}?”")
ms = engine.analyze_modality_shift(idx, stub, to)
if ms["kept"]:
    st.markdown("**Keeps your skeleton, re-derives what changes:**")
    for k in ms["kept"]:
        st.markdown(f"- `{k['id']}` → <span style='color:#888'>{k['notes'][:160]}</span>", unsafe_allow_html=True)
if ms["new_risks"]:
    st.markdown(f"**New risks `{to}` introduces:** "
                + ", ".join(f"`{nr['signature']}`" for nr in ms["new_risks"]))

# ── Step 4 — Compare how leading labs did it ──────────────────────────────
if stub["task_structure"] in engine.tasks_with_variants(idx):
    st.header("4 · It shows how leading labs solved the same problem differently")
    comp = engine.analyze_compare(idx, stub["task_structure"])
    for v in comp["variants"]:
        if v["distinctive"]:
            st.markdown(f"**{v['lineage']}** — {v['distinctive'][:220]}")

st.divider()
st.markdown(
    "**Why this matters.** Designing data workflows is where most ML quality is won or lost, and the knowledge "
    "is scattered across papers and practice. This turns it into something you can *consult* — broad coverage, "
    "grounded in published methods, and auditable down to the cost of every suggestion. Built as a study in "
    "cognitive-workflow design: a partner that's generative because it's legible, not despite it."
)
