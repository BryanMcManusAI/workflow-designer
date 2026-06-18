"""Streamlit UI for the Workflow Designer engine.

Imported by knowledge_lab.py as a tab. Builds a workflow 'stub' from form inputs and renders the
engine's analyze_* results. Deterministic: every suggestion is templated from the corpus and cites
the pattern + inherited signature + cost. Edit this file (or engine.py) and rerun to iterate.
"""
import streamlit as st

import engine


def _adopt(pid):
    cur = st.session_state.get("wd_patterns", [])
    if pid not in cur:
        st.session_state["wd_patterns"] = cur + [pid]


def _reset():
    st.session_state["wd_patterns"] = []


def _stub_summary(stub):
    st.caption(
        f"**{stub.get('goal') or '(no goal)'}** — "
        f"`{stub['modality']}` / `{stub['task_structure']}` / `{stub['annotator_structure']}` · "
        f"qa={stub['qa_mechanism'] or '[]'} · patterns={stub['uses_patterns'] or '[]'}"
    )


def render():
    st.subheader("🧬 Workflow Designer")
    st.caption("A deterministic creative partner over the ML-data-workflow corpus. "
               "Describe a new workflow; the engine finds analogues, interrogates it against their "
               "failure modes, and applies creative operators — every suggestion cites a pattern + cost.")

    idx = engine.load_index()
    v = engine.vocab(idx)
    pattern_ids = sorted(idx["patterns"].keys())
    st.caption(f"corpus: {len(idx['cards'])} workflow cards · {len(idx['patterns'])} patterns")

    # ---- build the stub from a form ----
    with st.expander("① Describe your new workflow", expanded=True):
        goal = st.text_input("Goal", "Evaluate AI-generated marketing copy at scale",
                             key="wd_goal")
        c1, c2, c3 = st.columns(3)
        modality = c1.selectbox("Modality", v["modality"],
                                index=v["modality"].index("text") if "text" in v["modality"] else 0,
                                key="wd_modality")
        task = c2.selectbox("Task structure", v["task_structure"], key="wd_task")
        annotator = c3.selectbox("Annotator structure", v["annotator_structure"], key="wd_annot")
        qa = st.multiselect("QA mechanisms already in place", v["qa_mechanism"], key="wd_qa")
        used = st.multiselect("Patterns already in your design (credited as 'defended')",
                              pattern_ids, key="wd_patterns")
        addressed = st.multiselect("Signatures you've already handled", v["failure_signature"],
                                   key="wd_addressed")

    stub = {"goal": goal, "modality": modality, "task_structure": task,
            "annotator_structure": annotator, "qa_mechanism": qa,
            "uses_patterns": used, "addressed_signatures": addressed, "failure_signatures": []}

    tabs = st.tabs(["🔎 Interrogate", "🧭 Retrieve", "🔀 Modality-shift",
                    "🧩 Transplant", "♻️ Flip / Substitute", "📚 Browse corpus",
                    "🏛️ Compare orgs", "📖 Cookbook index"])

    # ---- Interrogate (mode 3) — the iterative creative-partner loop ----
    with tabs[0]:
        adopted = st.session_state.get("wd_patterns", [])
        c0, c1 = st.columns([4, 1])
        c0.markdown("**Your design so far:** "
                    + (", ".join(f"`{p}`" for p in adopted) or "_(no patterns adopted yet)_"))
        c1.button("↺ Reset design", key="wd_reset", on_click=_reset)
        _stub_summary(stub)
        res = engine.analyze_interrogate(idx, stub)
        if res["defended"]:
            st.success("Defended by your design: " + ", ".join(res["defended"]))
        if not res["open"]:
            st.info("No open risks left among your analogues — your design covers them. 🎯")
        for r in res["open"]:
            with st.container(border=True):
                st.markdown(f"**`{r['signature']}`** · seen in {r['count']} analogue(s)")
                st.markdown(f"> {r['question']}")
                if r["unguarded"]:
                    st.warning(f"UNGUARDED — no pattern in the library defends `{r['signature']}` (a corpus gap).")
                for p in r["patterns"]:
                    pc0, pc1 = st.columns([5, 1])
                    pc0.markdown(f"borrow **`{p['id']}`** — {p['name']}  \n"
                                 f"<span style='color:#888'>defends {r['signature']} · cost: {p['cost']}</span>",
                                 unsafe_allow_html=True)
                    pc1.button("➕ Adopt", key=f"adopt_{r['signature']}_{p['id']}",
                               on_click=_adopt, args=(p["id"],))
                ex = r["example"]
                if ex["card"]:
                    st.caption(f"seen in `{ex['card']}`" + (f": {ex['desc'][:200]}" if ex["desc"] else ""))

    # ---- Retrieve ----
    with tabs[1]:
        _stub_summary(stub)
        near, far = engine.analyze_retrieve(idx, stub)
        st.markdown("**Near analogues** (shared modality / task / annotator)")
        if near:
            st.dataframe([{"score": r["score"], "card": r["id"],
                           "modality": r["modality"], "task": r["task"],
                           "shares": ", ".join(r["why"])} for r in near],
                         width="stretch", hide_index=True)
        else:
            st.caption("(none)")
        st.markdown("**Far analogues** (distant modality/task, shared risk — the creative pulls)")
        if far:
            st.dataframe([{"card": r["id"], "modality": r["modality"], "task": r["task"],
                           "shared signatures": ", ".join(r["shared"])} for r in far],
                         width="stretch", hide_index=True)
        else:
            st.caption("(none)")

    # ---- Modality-shift ----
    with tabs[2]:
        _stub_summary(stub)
        to = st.selectbox("Shift to modality", [m for m in v["modality"] if m != modality],
                          key="wd_shift_to")
        res = engine.analyze_modality_shift(idx, stub, to)
        st.markdown(f"**Keep** (modality-independent skeleton) — and what swaps for `{to}`")
        if not res["kept"]:
            st.caption("(your stub lists no patterns — add some under ① to carry a skeleton across)")
        for k in res["kept"]:
            st.markdown(f"- **`{k['id']}`** — {k['name']}  \n  <span style='color:#888'>swaps: "
                        f"{k['notes'] or '(no modality notes)'}</span>", unsafe_allow_html=True)
        if res["no_target"]:
            st.info(f"No `{to}` cards in the corpus yet — can't derive modality-specific risks.")
        else:
            st.markdown(f"**New failure modes `{to}` introduces**")
            for nr in res["new_risks"]:
                g = f"borrow `{nr['defender']}`" if nr["defender"] else "UNGUARDED — corpus gap"
                st.markdown(f"- `{nr['signature']}` → {g}" + (f" · e.g. {nr['example']}" if nr["example"] else ""))
            st.markdown(f"**Transplant candidates** (`{to}` workflows use these; your stub doesn't)")
            for t in res["transplants"]:
                st.markdown(f"- **`{t['id']}`** — {t['name']}  \n  <span style='color:#888'>cost: {t['cost']}</span>",
                            unsafe_allow_html=True)

    # ---- Transplant ----
    with tabs[3]:
        _stub_summary(stub)
        rows = engine.analyze_transplant(idx, stub)
        if not rows:
            st.caption("(no distant transplants found — your open risks may need new patterns)")
        for t in rows:
            st.markdown(f"- **`{t['id']}`** — {t['name']}  \n  <span style='color:#888'>imports a defense for "
                        f"`{t['signature']}` from {t['from']} ({t['from_mod']}/{t['from_task']}) · "
                        f"cost: {t['cost']}</span>", unsafe_allow_html=True)

    # ---- Flip / Actor-substitute ----
    with tabs[4]:
        _stub_summary(stub)
        c1, c2 = st.columns(2)
        axis = c1.selectbox("Flip which axis", ["annotator_structure", "task_structure",
                                                "modality", "qa_mechanism"], key="wd_flip_axis")
        opts = v.get(axis, [])
        to = c2.selectbox("To", [o for o in opts if o != stub.get(axis)], key="wd_flip_to")
        res = engine.analyze_flip(idx, stub, axis, to)
        if res["empty"]:
            st.info(f"No cards with `{axis}` = `{to}` — can't derive the flipped regime.")
        else:
            st.markdown("**Patterns that survive** (also used by the flipped regime): "
                        + (", ".join(f"`{p}`" for p in res["survive"]) or "(none of yours)"))
            st.markdown("**May not carry over** (unseen in the flipped regime): "
                        + (", ".join(f"`{p}`" for p in res["at_risk"]) or "(none)"))
            if res["conflicts"]:
                st.warning("Conflicts: " + "; ".join(f"`{a}` ⟂ `{b}`" for a, b in res["conflicts"]))
            st.markdown(f"**New signatures the `{to}` regime tends to hit**")
            for ns in res["new_sig"]:
                g = f"borrow `{ns['defender']}`" if ns["defender"] else "UNGUARDED"
                st.markdown(f"- `{ns['signature']}` → {g}")

    # ---- Browse corpus ----
    with tabs[5]:
        sub = st.radio("Show", ["Workflow cards", "Patterns"], horizontal=True, key="wd_browse")
        if sub == "Workflow cards":
            for cid, c in sorted(idx["cards"].items()):
                with st.expander(f"{cid} — {c['modality']}/{c['task_structure']}"):
                    meta = " · ".join(x for x in [c.get("lineage", ""),
                                                  f"scale: {c.get('scale', '')}",
                                                  f"domain: {c.get('domain', '')}"] if x and x.strip())
                    st.caption(meta)
                    if c.get("decision"):
                        st.markdown(f"**Decision:** {c['decision']}")
                    if c.get("distinctive"):
                        st.markdown(f"🔑 {c['distinctive']}")
                    st.markdown(f"**Patterns:** {', '.join(c['uses_patterns']) or '—'}")
                    if c.get("failure_modes"):
                        st.markdown("**Failure modes:**")
                        for fm in c["failure_modes"]:
                            st.markdown(f"- `{fm['signature']}` ({fm.get('evidence', '')}) — {fm['description'][:220]}  \n"
                                        f"<span style='color:#888'>caught by: {fm.get('caught_by', '')}</span>",
                                        unsafe_allow_html=True)
        else:
            for pid, p in sorted(idx["patterns"].items()):
                with st.expander(f"{pid} — {p['name']}"):
                    st.caption(p.get("does", ""))
                    st.markdown(f"defends: {', '.join(p['defends']) or '(none — a strategy)'}  ·  "
                                f"cost: {p['cost']}")
                    st.markdown(f"exemplified by: {', '.join(p['exemplified_by'])}")

    # ---- Compare org / house-style approaches ----
    with tabs[6]:
        st.caption("How different labs do the SAME workflow type — the distinctive choices each made.")
        opts = engine.tasks_with_variants(idx)
        if not opts:
            st.info("No task type has ≥2 cards yet to compare.")
        else:
            default = opts.index("preference_ranking") if "preference_ranking" in opts else 0
            t = st.selectbox("Compare approaches to", opts, index=default, key="wd_compare_task")
            res = engine.analyze_compare(idx, t)
            st.markdown("**Shared across all approaches (the invariant core)** — patterns: "
                        + (", ".join(f"`{p}`" for p in res["shared_patterns"]) or "(none)")
                        + " · signatures: " + (", ".join(res["shared_sigs"]) or "(none)"))
            for v in res["variants"]:
                with st.container(border=True):
                    st.markdown(f"**{v['lineage']}**  ·  `{v['id']}`  ·  annotator: `{v['annotator']}`")
                    if v["distinctive"]:
                        st.markdown(f"🔑 {v['distinctive']}")
                    st.markdown("patterns only this lab uses: "
                                + (", ".join(f"`{p}`" for p in v["distinct_patterns"]) or "—"))
                    st.markdown("risks only this lab carries: " + (", ".join(v["distinct_sigs"]) or "—"))

    # ---- Cookbook index: browse every recipe by any angle ----
    with tabs[7]:
        st.caption("The cookbook's indexes — group every recipe by any angle to find inspiration.")
        by = st.selectbox("Group recipes by", engine.COOKBOOK_ANGLES, key="wd_cookbook_by")
        res = engine.analyze_cookbook(idx, by)
        st.markdown(f"**{len(res['groups'])}** groups across **{len(idx['cards'])}** recipes")
        for val, items in res["groups"].items():
            with st.expander(f"{val}  ({len(items)})"):
                for it in items:
                    extra = f" · {it['lineage']}" if it["lineage"] else ""
                    st.markdown(f"- `{it['id']}` — {it['modality']}/{it['task']}{extra}")
