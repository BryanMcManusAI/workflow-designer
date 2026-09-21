#!/usr/bin/env python3
"""Local interactive web UI for the Workflow Designer — the "test and view in a browser" tool.

A tiny stdlib HTTP server: the SAME deterministic Python engine, exposed as a JSON API, with a
vanilla-JS page that walks you through designing a workflow in four steps — Describe → Find & close
risks → Your recipe → Why it works — with your design + coverage pinned so adopting a pattern
visibly climbs the bar. No Streamlit, no build step, no dependencies; the engine logic stays in
Python (the browser only renders what the API returns).

Run:   python3 engine/serve.py [--port 8011]
Open:  http://localhost:8011
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine
import build_site  # reuse the shared CSS + the curated examples (presets)
import semantic    # goal-driven topical retrieval (Tier-1 deterministic in the hot path; keyless)
import inform      # the advisory front door (Good Data Brief) — the strategic entry mode
import llm         # only to report whether the optional Tier-2 rerank is available

IDX = engine.load_index()
LIST_KEYS = ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures",
             "high_cost_signatures", "tolerable_signatures")


def _norm(stub):
    out = {"goal": stub.get("goal", ""), "modality": stub.get("modality"),
           "task_structure": stub.get("task_structure"),
           "annotator_structure": stub.get("annotator_structure"),
           "process_mode": stub.get("process_mode"),
           # the good-data-questionnaire scalar answers (edge-case philosophy, workflow context)
           "edge_case_mode": stub.get("edge_case_mode"),
           "downstream": stub.get("downstream"),
           # the retrospective bridge: the customer's own documented incidents (list of dicts —
           # kept as-is, not coerced through LIST_KEYS) and where they came from
           "observed_failures": [f for f in (stub.get("observed_failures") or [])
                                 if isinstance(f, dict)],
           "source_diagnosis": stub.get("source_diagnosis")}
    for k in LIST_KEYS:
        v = stub.get(k, [])
        out[k] = [v] if isinstance(v, str) else list(v or [])
    return out


def payload(stub):
    """Everything the UI needs for one design state — all from the same analyze_* functions the
    CLI / REPL / tests use. Pure + JSON-serializable, so it's unit-testable without the server."""
    stub = _norm(stub)
    near, far = engine.analyze_retrieve(IDX, stub)
    return {
        "stub": stub,
        "workflow": engine.analyze_workflow(IDX, stub),
        "interrogate": engine.analyze_interrogate(IDX, stub),
        "backwards": engine.analyze_backwards(IDX, stub),
        "coverage": engine.analyze_coverage(IDX, stub),
        "retrieve": {"near": near, "far": far},
        # Tier-1 (deterministic, instant, keyless) topical ranking so the GOAL text — not just the
        # axis dropdowns — drives which prior workflows surface. LLM rerank stays an explicit CLI step.
        "semantic": semantic.analyze_semantic(IDX, stub, use_llm=False, top=5),
        # The advisory front door: the Good Data Brief for this goal (the Advise-me mode's payload),
        # plus the reaction probes for the Calibrate step (elicitation for the tacit-knower).
        "inform": inform.analyze_inform(IDX, stub),
        "probes": inform.analyze_probes(IDX, stub),
    }


# A stub preloaded at launch (--stub path) — the one-URL demo: `serve.py --stub
# output/<id>_designer_stub.json` opens straight onto the Good Data Brief for a bridged
# retrospective diagnosis, the customer's own failures already in place.
PRELOAD = None


def meta():
    v = engine.vocab(IDX)
    patterns = [{"id": pid, "name": p["name"]} for pid, p in sorted(IDX["patterns"].items())]
    return {"vocab": v, "patterns": patterns,
            "examples": build_site.EXAMPLES, "llm_available": llm.available(),
            "signature_help": engine.QUESTIONS,
            "preloaded_stub": PRELOAD,
            "n_cards": len(IDX["cards"]), "n_patterns": len(IDX["patterns"])}


PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workflow Designer</title>
<style>__CSS__
.stepper{display:flex;align-items:center;gap:4px;margin:10px 0 22px;flex-wrap:wrap;}
.st{display:flex;align-items:center;gap:7px;cursor:pointer;}
.st .dot{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;
font-size:13px;border:1px solid var(--line);color:var(--muted);}
.st.done .dot{background:var(--ok);color:var(--ok-fg);border-color:transparent;}
.st.cur .dot{background:var(--accent);color:#fff;border-color:transparent;font-weight:600;}
.st .lbl{font-size:13px;color:var(--muted);} .st.cur .lbl{color:var(--fg);font-weight:600;}
.st .bar{display:none;} .sbar{flex:1;height:1px;background:var(--line);min-width:14px;}
.twocol{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;}
.summary{flex:0 0 230px;position:sticky;top:12px;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:12px 14px;}
.stepmain{flex:1;min-width:300px;}
/* Below the two-column width the summary would wrap yet stay position:sticky — pinning to the top
   while the content scrolls behind it. Stack it and drop the sticky so it just sits above the step. */
@media (max-width:640px){
  .twocol{flex-direction:column;}
  .summary{position:static;flex:0 0 auto;width:100%;}
  .stepmain{min-width:0;}
}
.nav{display:flex;justify-content:space-between;align-items:center;margin-top:18px;}
.eyebrow{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:0 0 2px;}
label.fld{display:block;font-weight:500;margin:14px 0 1px;font-size:14px;}
.help{font-size:12px;color:var(--muted);margin:0 0 5px;}
select,input[type=text]{width:100%;padding:8px 9px;border:1px solid var(--line);border-radius:8px;
background:var(--bg);color:var(--fg);font:inherit;}
.qa{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:4px;}
.qa label{font-weight:400;font-size:13px;display:flex;gap:5px;align-items:center;}
.pill{display:inline-flex;align-items:center;gap:6px;background:var(--chip);color:var(--chip-fg);
border-radius:20px;padding:2px 6px 2px 10px;font-size:.78rem;margin:2px;}
.pill button{background:none;border:none;color:var(--chip-fg);cursor:pointer;font-size:1rem;line-height:1;padding:0;}
button.btn{background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:8px;
padding:7px 14px;font:inherit;cursor:pointer;font-size:.9rem;} button.btn:hover{background:var(--card);}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent);}
button.ghost{border:none;color:var(--muted);}
button.preset{margin:3px;font-size:.85rem;padding:6px 11px;}
button.adopt{background:var(--ok);color:var(--ok-fg);border:none;border-radius:6px;padding:3px 10px;
font-size:.78rem;font-weight:700;cursor:pointer;white-space:nowrap;}
.covbar{height:8px;border-radius:999px;background:var(--code);overflow:hidden;margin:6px 0;}
.covbar>i{display:block;height:100%;background:#1D9E75;}
.risk-card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0;}
.risk-card.covered{border-color:var(--ok-fg);}
.row{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;}
.srctoggle{font-size:.82rem;color:var(--muted);white-space:nowrap;display:flex;align-items:center;gap:5px;cursor:pointer;}
.block{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 12px;}
.block.todo{border-color:var(--accent);}
.block.donelist{opacity:.7;}
.plist{list-style:none;padding-left:0;margin:4px 0;} .plist li{margin:7px 0;line-height:1.5;}
.tag{font-size:.68rem;background:var(--code);color:var(--muted);border-radius:5px;padding:1px 6px;vertical-align:1px;}
.src{font-size:.8rem;color:var(--muted);margin:2px 0 0 16px;}
ol.skel li{margin:7px 0;}
.wrap{max-width:900px;}
#content{line-height:1.65;}
.intro{color:var(--muted);font-size:.95rem;line-height:1.6;margin:8px 0 0;max-width:680px;}
details.how{margin:14px 0 4px;border:1px solid var(--line);border-radius:10px;background:var(--card);}
details.how summary{cursor:pointer;padding:11px 14px;font-size:.9rem;list-style:none;}
details.how summary::-webkit-details-marker{display:none;}
details.how summary::before{content:"\203A";display:inline-block;margin-right:9px;color:var(--muted);transition:transform .15s;}
details.how[open] summary::before{transform:rotate(90deg);}
details.how .body{padding:2px 16px 14px;font-size:.88rem;color:var(--muted);line-height:1.7;}
details.how ol{margin:4px 0 10px;padding-left:20px;} details.how li{margin:6px 0;}
.stepper{margin:18px 0 28px;}
.steptitle{font-size:1.2rem;font-weight:500;margin:2px 0 6px;}
.eyebrow{margin-bottom:5px;}
.help{line-height:1.6;margin:0 0 16px;}
.risk-card{padding:14px 16px;margin:14px 0;line-height:1.55;}
.risk-card .row{line-height:1.55;}
.summary{padding:14px 16px;line-height:1.5;}
label.fld{margin:18px 0 2px;}
select,input[type=text]{padding:9px 11px;}
.stepmain ol li,.stepmain ul li{line-height:1.6;margin:7px 0;}
.stepmain .colhead{margin:18px 0 6px;}
.nav{margin-top:24px;}
button.btn{padding:8px 16px;}
.risk-card{padding:18px 20px;margin:18px 0;}
.riskq{font-size:.95rem;line-height:1.55;margin:0 0 12px;}
.optlabel{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:0 0 7px;}
.opts{display:flex;flex-direction:column;gap:9px;}
.opt{display:flex;justify-content:space-between;align-items:center;gap:14px;background:var(--bg);
border:1px solid var(--line);border-radius:9px;padding:10px 8px 10px 14px;}
.opt:hover{border-color:var(--accent);}
.optname{font-size:.86rem;line-height:1.4;}
button.adopt{padding:8px 16px;font-size:.85rem;border-radius:7px;}
.block{margin:0 0 18px;padding:16px 18px;}
.plist li{margin:12px 0;}
ol.skel li{margin:12px 0;}
.colhead{margin:26px 0 10px;}
button.preset{padding:9px 15px;margin:4px 6px 4px 0;}
.stepper{margin:20px 0 32px;}
.nav{margin-top:30px;}
.summary{padding:16px 18px;}
.summary .pill{margin:3px 3px;}
label.fld{margin:22px 0 3px;}
.prow{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;}
.pmain{flex:1;min-width:0;}
.prow .adopt{flex:none;}
.modeseg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;margin:6px 0 10px;}
.seg{background:transparent;border:none;padding:9px 16px;font:inherit;font-size:.88rem;color:var(--muted);cursor:pointer;}
.seg.on{background:var(--accent);color:#fff;}
.sev{font-size:.66rem;font-weight:700;text-transform:uppercase;border-radius:5px;padding:1px 6px;vertical-align:1px;}
.sev.high{background:var(--risk);color:var(--risk-fg);}
.sev.med{background:var(--warn);color:var(--warn-fg);}
.sev.low{background:var(--code);color:var(--muted);}
.costchip{background:var(--chip);color:var(--chip-fg);border:1px solid transparent;border-radius:20px;
padding:4px 12px;font:inherit;font-size:.82rem;cursor:pointer;margin:3px 3px 3px 0;}
.costchip:hover{border-color:var(--accent);}
.costchip.on{background:var(--risk);color:var(--risk-fg);font-weight:500;}
</style></head>
<body><div class="wrap">
  <div class="row" style="align-items:baseline">
    <h1 style="margin:0">Workflow designer</h1>
    <span class="muted" id="corpus" style="font-size:.85rem"></span>
  </div>
  <p class="intro">Describe what you want to build and get advice on what good data means for that
  goal — or go further and assemble the full buildable recipe. Every suggestion traceable to a real
  prior workflow; deterministic core, nothing it can't source.</p>
  <details class="how">
    <summary>How this works &amp; which door to take</summary>
    <div class="body">
      <p style="margin:0 0 8px">Three ways in, one evidence base — pick by how much you want back:</p>
      <ol>
        <li><strong>Advise me</strong> (start here) — describe what you're building, optionally
        calibrate by reacting to real prior failures, and get a <em>Good Data Brief</em>: what good
        data means for your goal, the five-minute check per risk, and one defense each. Advisory —
        your pipeline stays yours.</li>
        <li><strong>Design forward</strong> — the full treatment: surface the failure modes similar
        workflows actually hit, adopt defenses and watch coverage climb, and get the assembled
        recipe (labeling steps, per-item fields, conventions, audit strategy).</li>
        <li><strong>Reverse-engineer from good</strong> — start from what "good" means, work
        backward to the workflow that guarantees it.</li>
      </ol>
      Every suggestion, in every mode, cites the real prior workflow it borrows from. Jump between
      steps anytime by clicking them above; your progress stays pinned on the left.
    </div>
  </details>
  <div class="stepper" id="stepper"></div>
  <div id="content"></div>
</div>
<script>__JS__</script>
</body></html>
"""

JS = r"""
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Risk chips carry their plain-language definition as a hover title, so vocabulary never blocks
// a first-time reader (the gloss comes from the engine's interrogation questions).
const chip = (t,k='') => {
  const help = (META && META.signature_help && META.signature_help[t]) || '';
  return `<span class="chip ${k}" ${help?`title="${esc(help)}"`:''}>${esc(String(t).replace(/_/g,' '))}</span>`;
};
const badge = h => h?'<span class="badge have">have</span>':'<span class="badge add">add</span>';
let META=null, DATA=null, STEP=0, SHOW_SOURCES=false, MODE='advise';
const stub = {goal:"Evaluate AI-generated marketing copy with an LLM judge",
  modality:"text", task_structure:"rubric_rating", annotator_structure:"model_as_annotator",
  qa_mechanism:[], uses_patterns:[], addressed_signatures:[], failure_signatures:[],
  high_cost_signatures:[], tolerable_signatures:[], process_mode:""};
const agentNote = () => { const a=DATA.workflow.agent; return a?`<div class="callout" style="margin:0 0 14px"><strong>Process: ${esc(a.label)}.</strong> ${esc(a.note)}</div>`:''; };
const FLOWS = {
  advise:  [["Describe",renderDescribe],["Calibrate",renderCalibrate],["Your Good Data Brief",renderBrief]],
  forward: [["Describe",renderDescribe],["Find & close risks",renderRisks],["Your recipe",renderRecipe],["The rationale",renderWhy]],
  reverse: [["Describe",renderDescribe],["Define ‘good’",renderGoodMeans],["Reverse-engineer",renderBuildList],["Your recipe",renderRecipe]],
};
const steps = () => FLOWS[MODE];
const eb = () => `<p class="eyebrow">Step ${STEP+1} of ${steps().length}</p>`;
const HELP = {modality:"what the data is — text, image, audio, code…",
  task_structure:"the shape of the judgment — classify, rank, rate, extract…",
  annotator_structure:"who labels — a crowd, an expert, or a model"};

async function init(){
  META = await (await fetch('/api/meta')).json();
  $('#corpus').textContent = `${META.n_cards} recipes · ${META.n_patterns} patterns · deterministic core`;
  if(META.preloaded_stub){
    // bridged from a retrospective diagnosis: land directly on the populated brief
    Object.assign(stub, META.preloaded_stub);
    MODE='advise'; STEP=steps().length-1;
  }
  await analyze(); render();
}
async function analyze(){
  DATA = await (await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({stub})})).json();
}
function go(s){ STEP=Math.max(0,Math.min(steps().length-1,s)); render(); }

function renderStepper(){
  const S=steps();
  $('#stepper').innerHTML = S.map(([l],i)=>{
    const cls = i<STEP?'done':(i===STEP?'cur':'');
    const dot = i<STEP?'<i class="ti ti-check"></i>':(i+1);
    return `<span class="st ${cls}" data-s="${i}"><span class="dot">${dot}</span><span class="lbl">${esc(l)}</span></span>`
      + (i<S.length-1?'<span class="sbar"></span>':'');
  }).join('');
  document.querySelectorAll('.st').forEach(e=>e.onclick=()=>go(+e.dataset.s));
}
function opt(vals,cur){ return vals.map(v=>`<option value="${esc(v)}" ${v===cur?'selected':''}>${esc(v.replace(/_/g,' '))}</option>`).join(''); }

function summary(){
  // Advise mode: the sidebar mirrors what the CUSTOMER is doing — their answers so far — not the
  // designer's adoption/coverage mechanics ("Adopted 0 · Coverage 0%" reads as a failing grade to
  // someone who is only here for advice).
  if(MODE==='advise'){
    const yn=(v,unset)=>v?esc(String(v).replace(/_/g,' ')):`<span class="muted">${unset}</span>`;
    const rows=[["Process",yn(stub.process_mode,'either')],["Edge cases",yn(stub.edge_case_mode,'react on Calibrate')],
      ["Data feeds",yn(stub.downstream,'unspecified')],
      ["Costly failures",stub.high_cost_signatures.length?stub.high_cost_signatures.map(s=>chip(s,'risk')).join(' '):`<span class="muted">none marked</span>`]];
    return `<div class="summary">
      <div class="row"><span class="muted" style="font-size:.82rem">Your brief so far</span>
        <button class="ghost" style="font-size:.8rem;padding:0" data-s="0">edit</button></div>
      <p style="margin:6px 0 8px;font-size:.9rem;line-height:1.45">${esc(stub.goal||'(untitled)')}</p>
      <div style="margin-bottom:10px">${[stub.modality,stub.task_structure,stub.annotator_structure].map(x=>chip(x)).join(' ')}</div>
      ${rows.map(([k,v])=>`<div style="border-top:1px solid var(--line);padding:6px 0 2px"><span class="muted" style="font-size:.78rem">${k}</span><div style="font-size:.85rem">${v}</div></div>`).join('')}
    </div>`;
  }
  const c=DATA.coverage, pct=Math.round(c.pct*100);
  const chips = stub.uses_patterns.length
    ? stub.uses_patterns.map(p=>`<span class="pill">${esc(p)}<button data-drop="${esc(p)}" title="remove">×</button></span>`).join('')
    : '<span class="muted" style="font-size:.82rem">none yet</span>';
  return `<div class="summary">
    <div class="row"><span class="muted" style="font-size:.82rem">Your design</span>
      <button class="ghost" style="font-size:.8rem;padding:0" data-s="0">edit</button></div>
    <p style="margin:6px 0 8px;font-size:.9rem;line-height:1.45">${esc(stub.goal||'(untitled)')}</p>
    <div style="margin-bottom:10px">${[stub.modality,stub.task_structure,stub.annotator_structure].map(x=>chip(x)).join(' ')}</div>
    <div style="border-top:1px solid var(--line);padding-top:8px">
      <p style="margin:0 0 4px;font-size:.82rem;color:var(--muted)">Adopted (${stub.uses_patterns.length})</p>${chips}</div>
    <div style="border-top:1px solid var(--line);padding-top:8px;margin-top:8px">
      <div class="row" style="font-size:.85rem"><span class="muted">Coverage</span><span>${c.n_covered} / ${c.n_applicable} · ${pct}%</span></div>
      <div class="covbar"><i style="width:${pct}%"></i></div></div>
  </div>`;
}
function wire(){
  document.querySelectorAll('[data-drop]').forEach(b=>b.onclick=async()=>{
    stub.uses_patterns=stub.uses_patterns.filter(x=>x!==b.dataset.drop); await analyze(); render();});
  document.querySelectorAll('[data-s]').forEach(b=>{ if(b.tagName==='BUTTON') b.onclick=()=>go(+b.dataset.s);});
  document.querySelectorAll('[data-adopt]').forEach(b=>b.onclick=async()=>{
    if(!stub.uses_patterns.includes(b.dataset.adopt)){stub.uses_patterns.push(b.dataset.adopt); await analyze(); render();}});
}
function twocol(main){ return `<div class="twocol">${summary()}<div class="stepmain">${main}</div></div>`; }
function navbar(prev,next){
  return `<div class="nav">
    ${prev!=null?`<button class="btn ghost" data-s="${prev}"><i class="ti ti-arrow-left"></i> back</button>`:'<span></span>'}
    ${next!=null?`<button class="btn primary" data-s="${next}">${next>STEP?steps()[next][0]:'continue'} <i class="ti ti-arrow-right"></i></button>`:'<span></span>'}
  </div>`;
}
function nav(){ return navbar(STEP>0?STEP-1:null, STEP<steps().length-1?STEP+1:null); }

function render(){ renderStepper(); steps()[STEP][1](); }

function renderDescribe(){
  const v=META.vocab;
  const presets = Object.keys(META.examples).map(n=>`<button class="btn preset" data-ex="${esc(n)}">${esc(n)}</button>`).join('');
  const sel = (k)=>`<label class="fld">${k.replace(/_/g,' ')}</label><p class="help">${HELP[k]}</p>
    <select id="${k}">${opt(v[k], stub[k])}</select>`;
  const qa = v.qa_mechanism.map(q=>`<label><input type="checkbox" value="${esc(q)}" ${stub.qa_mechanism.includes(q)?'checked':''}>${esc(q)}</label>`).join('');
  const modeline = MODE==='advise'
    ? 'Tell it what you are building; it briefs you on what good data means for that goal — what quietly wrecks it, the five-minute check for each risk, and one way to defend it. Advisory: your pipeline stays yours.'
    : MODE==='forward'
    ? 'Describe a workflow; the tool finds its risks and assembles a recipe.'
    : 'Start from your goal; the tool works backward from what “good” data means to the workflow that guarantees it.';
  $('#content').innerHTML = eb()+`<p class="steptitle">${MODE==='advise'?'Describe what you want to build':'Describe the workflow you want to build'}</p>
    <div class="modeseg"><button class="seg ${MODE==='advise'?'on':''}" data-mode="advise">Advise me</button><button class="seg ${MODE==='forward'?'on':''}" data-mode="forward">Design forward</button><button class="seg ${MODE==='reverse'?'on':''}" data-mode="reverse">Reverse-engineer from good</button></div>
    <p class="help" style="margin-bottom:12px">${modeline}</p>
    <div style="margin-bottom:8px">${presets}</div>
    <label class="fld">Goal</label><input type="text" id="goal" value="${esc(stub.goal)}">
    ${sel('modality')}${sel('task_structure')}${sel('annotator_structure')}
    <label class="fld">QA mechanisms already in place</label><p class="help">optional — checks you already run</p>
    <div class="qa" id="qa">${qa}</div>
    ${MODE==='advise' ? '' : qControls()}
    ${nav()}`;
  document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{MODE=b.dataset.mode; render();});
  wireQ();
  $('#goal').oninput=e=>{stub.goal=e.target.value;};
  ['modality','task_structure','annotator_structure'].forEach(k=>$('#'+k).onchange=async e=>{stub[k]=e.target.value; await analyze(); render();});
  $('#qa').onchange=async()=>{stub.qa_mechanism=[...$('#qa').querySelectorAll('input:checked')].map(i=>i.value); await analyze(); render();};
  document.querySelectorAll('[data-ex]').forEach(b=>b.onclick=async()=>{
    const ex=META.examples[b.dataset.ex]; Object.assign(stub,{qa_mechanism:[],uses_patterns:[],addressed_signatures:[],failure_signatures:[],high_cost_signatures:[],tolerable_signatures:[],process_mode:"",edge_case_mode:"",downstream:""},ex);
    await analyze(); render();});
  wire();
}

function renderRisks(){
  const r=DATA.interrogate;
  let h=eb()+`<p class="steptitle">Close each open risk</p>
    <p class="help">${r.open.length} risk${r.open.length===1?'':'s'} similar workflows hit. Adopt a defense for each — coverage climbs as you go.</p>`;
  if(r.defended.length) h+=`<p class="ok" style="font-size:.88rem">Already covered: ${r.defended.map(s=>`<code>${esc(s)}</code>`).join(', ')}</p>`;
  if(!r.open.length) h+='<p class="ok">No open risks left — your design covers them all. 🎯</p>';
  h+=r.open.map(o=>`<div class="risk-card">
      <p class="riskq"><span class="sev ${o.severity}">${o.severity}-cost</span> <span class="chip risk">${esc(o.signature)}</span> ${esc(o.question)}</p>`
    + (o.unguarded?'<p class="warn" style="font-size:.82rem;margin:6px 0 0">UNGUARDED — a corpus gap.</p>':'')
    + (o.patterns.length?`<p class="optlabel">${o.patterns.length>1?'Adopt one defense:':'Adopt the defense:'}</p>`:'')
    + `<div class="opts">`
    + o.patterns.slice(0,2).map(p=>`<div class="opt">
        <span class="optname" title="cost: ${esc(p.cost)}"><code>${esc(p.id)}</code> <span class="muted">${esc(p.name)}</span></span>
        <button class="adopt" data-adopt="${esc(p.id)}"><i class="ti ti-plus"></i> adopt</button></div>`).join('')
    + `</div></div>`).join('');
  $('#content').innerHTML = twocol(h)+nav();
  wire();
}

function patLine(p, tag, adoptable){
  let src='';
  if(SHOW_SOURCES && p.as_done) src=`<div class="src">as <code>${esc(p.as_done.card)}</code> — ${esc(p.as_done.gate)}: ${esc(p.as_done.checks)}</div>`;
  else if(SHOW_SOURCES && p.seen_in&&p.seen_in.length) src=`<div class="src">seen in ${p.seen_in.map(c=>`<code>${esc(c)}</code>`).join(', ')}</div>`;
  const act = (adoptable && !p.have) ? `<button class="adopt" data-adopt="${esc(p.id)}"><i class="ti ti-plus"></i> adopt</button>` : '';
  return `<li class="prow"><span class="pmain"><code>${esc(p.id)}</code> <span class="tag">${esc(tag[p.id]||'')}</span> — ${esc(p.instruction)}${src}</span>${act}</li>`;
}
function recipeParts(){
  const wf=DATA.workflow; const tag={};
  wf.steps.forEach(s=>s.patterns.forEach(p=>tag[p.id]=s.phase.split(' ')[0].toLowerCase()));
  wf.conventions.forEach(p=>tag[p.id]='convention'); wf.audit.forEach(p=>tag[p.id]='audit');
  const all={}; [...wf.steps.flatMap(s=>s.patterns),...wf.conventions,...wf.audit].forEach(p=>all[p.id]=p);
  const items=Object.values(all);
  return {wf,tag,add:items.filter(p=>!p.have),have:items.filter(p=>p.have)};
}
function renderGoodMeans(){
  const bw=DATA.backwards;
  const chips=bw.good_means.map(s=>{const on=stub.high_cost_signatures.includes(s);
    return `<button class="costchip ${on?'on':''}" data-cost="${esc(s)}">${esc(s)}${on?' ✓':''}</button>`;}).join(' ');
  let h=eb()+`<p class="steptitle">What “good” data means here</p>
    <p class="help">Good data is data free of the ways it goes bad. Working backward, first pin what “good” means — then guarantee it.</p>
    <p style="margin:12px 0 5px"><strong>“Good” ${esc(stub.task_structure||'')} data is free of:</strong></p>
    <div style="margin-bottom:5px">${chips}</div>
    <p class="help" style="margin:0 0 14px">Click the risks that are most costly for you — the workflow defends those hardest, and the build list reprioritizes.</p>`;
  if(bw.spec_threats.length){ h+=`<div class="callout"><strong>But first — is your <em>good</em> actually good?</strong>
    <p class="muted" style="font-size:.85rem;margin:4px 0">The gold is the thing most likely to be wrong. Each check asks whether “good” is secretly a proxy.</p><ul>`
    +bw.spec_threats.map(s=>`<li><code>${esc(s.signature)}</code> — ${esc(s.question)} <span class="muted">probe: ${esc(s.probe)}</span></li>`).join('')+`</ul></div>`; }
  $('#content').innerHTML = twocol(h)+nav();
  document.querySelectorAll('[data-cost]').forEach(b=>b.onclick=async()=>{
    const s=b.dataset.cost, a=stub.high_cost_signatures, i=a.indexOf(s);
    i>=0?a.splice(i,1):a.push(s); await analyze(); render();});
  wire();
}
function renderBuildList(){
  const need=DATA.backwards.needed_patterns;  // one defense per open risk, costliest first
  const {have}=recipeParts();
  const row=p=>`<li class="prow"><span class="pmain"><span class="sev ${p.severity}">${p.severity}</span> <code>${esc(p.id)}</code> <span class="muted">closes <code>${esc(p.for)}</code></span></span><button class="adopt" data-adopt="${esc(p.id)}"><i class="ti ti-plus"></i> adopt</button></li>`;
  let h=eb()+`<p class="steptitle">Reverse-engineer the workflow</p>
    <p class="help">One defense per open risk guarantees the “good” you defined — costliest first. Adopt them to build the workflow backward; coverage climbs toward 100%.</p>
    ${agentNote()}
    <div class="block todo"><p class="colhead"><i class="ti ti-circle-plus"></i> Defenses to add — ${need.length}</p>
      ${need.length?`<ul class="plist">${need.map(row).join('')}</ul>`:'<p class="ok" style="font-size:.9rem">Every defense is in place — the workflow guarantees your “good.” 🎯</p>'}</div>
    <div class="block donelist"><p class="colhead"><i class="ti ti-circle-check"></i> Already in place — ${have.length}</p>
      ${have.length?`<ul class="plist">${have.map(p=>`<li><code>${esc(p.id)}</code></li>`).join('')}</ul>`:'<p class="muted" style="font-size:.88rem">none yet</p>'}</div>`;
  $('#content').innerHTML = twocol(h)+nav();
  wire();
}
function renderRecipe(){
  const {wf,tag,add,have}=recipeParts();
  const skeleton=wf.steps.map(s=>`<li><strong>${esc(s.phase)}</strong> — ${esc(s.do)}</li>`).join('');
  const main=eb()+`<p class="steptitle">Your assembled workflow</p>
    <div class="row" style="margin-bottom:12px"><p class="help" style="margin:0">A buildable recipe for your design.`
    +(wf.precedent?` Closest precedent <code>${esc(wf.precedent)}</code>.`:'')+`</p>
      <label class="srctoggle"><input type="checkbox" id="srcToggle" ${SHOW_SOURCES?'checked':''}> show sources</label></div>
    ${agentNote()}
    <div class="block todo"><p class="colhead"><i class="ti ti-circle-plus"></i> To add — ${add.length} recommended</p>
      ${add.length?`<ul class="plist">${add.map(p=>patLine(p,tag,true)).join('')}</ul>`:'<p class="muted" style="font-size:.88rem">Nothing — your design already covers every applicable risk.</p>'}</div>
    <div class="block donelist"><p class="colhead"><i class="ti ti-circle-check"></i> Already in your design — ${have.length}</p>
      ${have.length?`<ul class="plist">${have.map(p=>patLine(p,tag,false)).join('')}</ul>`:'<p class="muted" style="font-size:.88rem">none yet — adopt patterns above</p>'}</div>
    <p class="colhead">The workflow</p><ol class="skel">${skeleton}</ol>
    <p class="colhead">Fields per item</p><div>${wf.fields.map(f=>`<span class="chip">${esc(f)}</span>`).join(' ')}</div>`;
  $('#content').innerHTML = twocol(main)+nav();
  const t=$('#srcToggle'); if(t) t.onchange=()=>{SHOW_SOURCES=t.checked; render();};
  wire();
}

function renderWhy(){
  const bw=DATA.backwards, {near,far}=DATA.retrieve;
  let h=eb()+`<p class="steptitle">The rationale</p>
    <p class="help" style="margin-bottom:10px">Why these defenses — the backwards-from-good reasoning the recipe was built on.</p>`;
  if(bw.principles && bw.principles.length){ h+=`<p><strong>“Good” ${esc((DATA.stub&&DATA.stub.task_structure)||'')} data <em>has</em>:</strong> the constructs the literature says define it —</p><ul>`
    +bw.principles.map(p=>{const ev=(p.evidence&&p.evidence[0])||{};
      const src=ev.source?` <span class="muted">— ${esc(ev.source)}${ev.seen_in?`; seen in <code>${esc(ev.seen_in)}</code>`:''}</span>`:'';
      return `<li><strong>${esc(p.name)}</strong>${p.defended?' ✓':''} <span class="muted">(= absence of ${p.protects.map(s=>esc(s)).join(', ')})</span><br>${esc(p.tenet)}${src}</li>`;}).join('')+`</ul>`; }
  h+=`<p><strong>So “good” here means free of:</strong> ${bw.good_means.map(s=>chip(s,'risk')).join(' ')}</p>`;
  if(bw.spec_threats.length){ h+=`<div class="callout"><strong>But first — is your <em>good</em> actually good?</strong><ul>`
    +bw.spec_threats.map(s=>`<li><code>${esc(s.signature)}</code> — ${esc(s.question)} <span class="muted">probe: ${esc(s.probe)}${s.cite?` · per ${esc(s.cite.principle)}, ${esc(s.cite.source)}`:''}</span></li>`).join('')+`</ul></div>`; }
  h+=`<div id="sempanel">${semPanel(DATA.semantic)}</div>`;
  h+=`<div class="cols" style="display:flex;gap:20px;flex-wrap:wrap;margin-top:10px">
    <div style="flex:1;min-width:240px"><p class="colhead" style="font-weight:500">Near analogues <span class="muted">(structural)</span></p><ul>`
    +near.slice(0,4).map(r=>`<li><code>${esc(r.id)}</code> <span class="muted">(${esc(r.modality)}/${esc(r.task)})</span></li>`).join('')
    +`</ul></div><div style="flex:1;min-width:240px"><p class="colhead" style="font-weight:500">Far — same rare risk</p><ul>`
    +far.slice(0,4).map(r=>`<li><code>${esc(r.id)}</code> ${r.shared.slice(0,2).map(s=>chip(s,'risk')).join(' ')}</li>`).join('')
    +`</ul></div></div>`;
  $('#content').innerHTML = twocol(h)+nav();
  wire();
  const rb=$('#rerankbtn'); if(rb) rb.addEventListener('click', rerank);
}

// The three questionnaire controls (process / edge cases / data feeds). On Describe for the design
// modes; in advise mode they live on Calibrate instead, so the first screen stays light.
function wireQ(){
  document.querySelectorAll('[data-pm]').forEach(b=>b.onclick=async()=>{stub.process_mode=b.dataset.pm; await analyze(); render();});
  document.querySelectorAll('[data-ec]').forEach(b=>b.onclick=async()=>{stub.edge_case_mode=b.dataset.ec; await analyze(); render();});
  document.querySelectorAll('[data-ds]').forEach(b=>b.onclick=async()=>{stub.downstream=b.dataset.ds; await analyze(); render();});
}

function qControls(edgeToo=true){
  return `<label class="fld">Process style</label><p class="help">strict = freeze the guideline up front (reproducible, auditable); adaptive = iterate as you go (responsive)</p>
    <div class="modeseg">
      <button class="seg ${!stub.process_mode?'on':''}" data-pm="">either</button>
      <button class="seg ${stub.process_mode==='strict'?'on':''}" data-pm="strict">strict steps</button>
      <button class="seg ${stub.process_mode==='adaptive'?'on':''}" data-pm="adaptive">adapt dynamically</button>
    </div>`
  +(edgeToo?`<label class="fld">Edge cases</label><p class="help">how should ambiguous cases be handled? — picks which defense closes them, and becomes a decision guideline</p>
    <div class="modeseg">
      <button class="seg ${!stub.edge_case_mode?'on':''}" data-ec="">unsure</button>
      <button class="seg ${stub.edge_case_mode==='escalate'?'on':''}" data-ec="escalate">escalate to a human</button>
      <button class="seg ${stub.edge_case_mode==='rule'?'on':''}" data-ec="rule">resolve by rule</button>
      <button class="seg ${stub.edge_case_mode==='signal'?'on':''}" data-ec="signal">keep as signal</button>
    </div>`:'')
  +`<label class="fld">This data feeds</label><p class="help">where it sits in the larger system — evaluation data dies on contamination, training data on coverage; this reweights what to defend hardest</p>
    <div class="modeseg">
      <button class="seg ${!stub.downstream?'on':''}" data-ds="">unspecified</button>
      <button class="seg ${stub.downstream==='training'?'on':''}" data-ds="training">model training</button>
      <button class="seg ${stub.downstream==='evaluation'?'on':''}" data-ds="evaluation">evaluation / a claim</button>
    </div>`;
}

// CALIBRATE — reaction-based elicitation for the customer who knows good data when they see it but
// hasn't pre-articulated it. React to real prior failures (sorts each into costly/tolerable), pick
// an ambiguity instinct, and correct the precedent mirror (the correction feeds the goal text →
// retrieval). Entirely optional: a customer who answered everything on Describe just clicks through.
let PROBE_SKIPPED = new Set();
function renderCalibrate(){
  const pr=DATA.probes;
  let h=eb()+`<p class="steptitle">Calibrate <span class="muted" style="font-weight:400;font-size:.8em">(optional — skip ahead anytime; every answer or reaction sharpens the brief)</span></p>
    <p class="help" style="margin-bottom:10px"><strong>Answer what you can…</strong></p>
    ${qControls(false)}
    <p class="help" style="margin:16px 0 10px"><strong>…and react to the rest.</strong> Definitions are hard to state up front; reactions aren’t. Everything below is a real case from a prior workflow.</p>`;
  if(pr.mirror && pr.mirror.frame){
    h+=`<div class="callout" style="margin-bottom:14px"><strong>Is this the right frame?</strong> <em>${esc(pr.mirror.frame)}</em>
      <span class="muted" style="font-size:11.5px"> — the closest precedent, <code>${esc(pr.mirror.card)}</code></span>
      <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <button class="btn" id="mirror-yes">Yes, that’s the frame</button>
        <input type="text" id="mirror-diff" placeholder="No — what’s different about yours?" style="flex:1;min-width:220px">
        <button class="btn" id="mirror-apply">Apply</button>
      </div><p class="muted" id="mirror-note" style="font-size:11.5px;margin:6px 0 0"></p></div>`;}
  const live=pr.failure_probes.filter(p=>!PROBE_SKIPPED.has(p.signature));
  if(live.length){
    h+=`<p style="margin:0 0 6px"><strong>Would these be expensive for you?</strong> <span class="muted">(each really happened to an analogous workflow)</span></p>`;
    live.forEach(p=>{
      const stakeHead = p.stake ? `<strong style="color:var(--des,#C7A56B)">${esc(p.stake)}.</strong> ` : '';
      h+=`<div style="border:1px solid var(--line,#333);border-radius:8px;padding:12px 16px;margin-bottom:10px">
        <p style="margin:0 0 8px;font-size:13.5px">${stakeHead}${esc(p.story)} <span class="muted">(${chip(p.signature,'risk')} · <code>${esc(p.card)}</code>)</span></p>
        <div style="display:flex;gap:8px"><button class="btn" data-probe="${esc(p.signature)}" data-verdict="costly">Costly for us</button>
        <button class="btn" data-probe="${esc(p.signature)}" data-verdict="tolerable">Tolerable</button>
        <button class="btn" data-probe="${esc(p.signature)}" data-verdict="skip">Not sure</button></div></div>`;});
  } else if(pr.failure_probes.length===0){
    h+=`<p class="help">Your declared sensitivities already cover the costly failures — nothing to probe.</p>`;}
  if(pr.edge_options){
    h+=`<p style="margin:14px 0 6px"><strong>When an ambiguous item shows up, which instinct is yours?</strong></p>`
      +pr.edge_options.map(o=>`<div style="border:1px solid var(--line,#333);border-radius:8px;padding:10px 14px;margin-bottom:8px;cursor:pointer" data-edge="${esc(o.mode)}">
        <span style="font-size:13.5px">${esc(o.instinct)}</span></div>`).join('');}
  else h+=`<p class="help" style="margin-top:10px">Ambiguous-case policy set: <strong>${esc(stub.edge_case_mode)}</strong> ✓ <button class="ghost" id="edge-clear" style="font-size:.8rem">change</button></p>`;
  $('#content').innerHTML = twocol(h)+nav();
  const ec=$('#edge-clear'); if(ec) ec.onclick=async()=>{stub.edge_case_mode=''; await analyze(); render();};
  wireQ();
  const my=$('#mirror-yes'); if(my) my.onclick=()=>{$('#mirror-note').textContent='Good — the brief will use this frame.';};
  const ma=$('#mirror-apply'); if(ma) ma.onclick=async()=>{const v=$('#mirror-diff').value.trim();
    if(v){ stub.goal = stub.goal + ' Unlike ' + DATA.probes.mirror.card + ', ' + v; await analyze(); render(); }};
  document.querySelectorAll('[data-probe]').forEach(b=>b.onclick=async()=>{
    const sig=b.dataset.probe, v=b.dataset.verdict;
    if(v==='skip'){ PROBE_SKIPPED.add(sig); render(); return; }
    const key = v==='costly' ? 'high_cost_signatures' : 'tolerable_signatures';
    if(!stub[key].includes(sig)) stub[key].push(sig);
    await analyze(); render();});
  document.querySelectorAll('[data-edge]').forEach(d=>d.onclick=async()=>{stub.edge_case_mode=d.dataset.edge; await analyze(); render();});
  wire();
}

// ADVISE MODE — the Good Data Brief: the advisory front door. Organized around the customer's goal,
// every line load-bearing (a check to run, a defense to adopt, a war story that happened). Ends with
// the funnel: one click jumps into the designer's full recipe for the same stub.
function renderBrief(){
  const b=DATA.inform;
  const sevword={high:'costly to get wrong',med:'moderate',low:'cheap to fix later'};
  const names=b.principles.slice(0,3).map(p=>p.name.split(' (')[0]);
  let h=eb()+`<p class="steptitle">Your Good Data Brief</p>
    <p class="help" style="margin-bottom:12px">${esc(b.goal)}</p>`;
  if(b.support && b.support.level!=='strong'){
    const weak=b.support.level==='weak';
    h+=`<div class="callout" style="margin-bottom:12px;border-left:3px solid ${weak?'#C7A56B':'var(--muted,#888)'}">
      <strong>${weak?'⚠️ ':'◐ '}How far to trust this brief:</strong> ${esc(b.support.note)}</div>`;}
  h+=`<div class="callout" style="margin-bottom:16px"><strong>In one line:</strong> for this data to be good, it has to have ${names.slice(0,-1).map(esc).join(', ')} and ${esc(names[names.length-1])} — each defined below, with the check that tells you whether you have it and one way to get it.</div>`;
  b.principles.forEach((p,i)=>{
    const d=p.defense;
    h+=`<div style="border:1px solid var(--line,#333);border-radius:8px;padding:14px 18px;margin-bottom:12px">
      <p style="margin:0 0 6px"><strong>${i+1} · ${esc(p.name)}</strong>${p.secured?' <span class="chip">✓ your plan covers this</span>':''}</p>
      <p class="help" style="margin:0 0 8px">${esc(p.tenet)}</p>`;
    if(p.war_story){
      if(p.war_story.stake) h+=`<p style="margin:0 0 4px;font-size:13px"><strong style="color:var(--des,#C7A56B)">What it cost, documented:</strong> ${esc(p.war_story.stake)}.</p>`;
      h+=`<p style="margin:0 0 8px;font-size:13px"><strong>If you skip it:</strong> ${esc(p.war_story.desc)} <span class="muted">(a real case: <code>${esc(p.war_story.card)}</code>)</span></p>`;}
    if(p.check) h+=`<p style="margin:0 0 8px;font-size:13px"><strong>The five-minute check:</strong> ${esc(p.check)}</p>`;
    if(d && !p.secured){
      const done=d.as_done?` — as <code>${esc(d.as_done.card)}</code> does: ${esc(d.as_done.checks)}`:(d.seen_in.length?` — see <code>${esc(d.seen_in[0])}</code>`:'');
      h+=`<p style="margin:0 0 8px;font-size:13px"><strong>One way to get it:</strong> ${esc(d.name)} <span class="muted">(cost: ${esc(d.cost)})</span>${done}</p>`;}
    h+=`<p class="muted" style="margin:0;font-size:11.5px">guards ${p.risks.map(r=>chip(r,'risk')).join(' ')}${p.lead_risk?` · ${esc(sevword[p.severity]||'')}`:''} · ${esc(p.source)}</p></div>`;
  });
  if(b.spec_threats.length){
    h+=`<div class="callout"><strong>Before any of that — is your “good” actually good?</strong>
      <p class="help" style="margin:6px 0">The most expensive failure isn't missing a check; it's certifying data against a definition that was quietly measuring something else.</p><ul>`
      +b.spec_threats.map(t=>`<li style="margin:6px 0">${esc(t.question)}<br><span class="muted">Run: ${esc(t.probe)}</span></li>`).join('')+`</ul></div>`;}
  if(b.mental_model && b.mental_model.frame)
    h+=`<div class="callout" style="margin-top:14px"><strong>How to think about this task:</strong> <em>${esc(b.mental_model.frame)}</em><br><span class="muted" style="font-size:11.5px">the closest real precedent: <code>${esc(b.mental_model.card)}</code> — worth reading before you write a guideline</span></div>`;
  if(b.guidelines && b.guidelines.length)
    h+=`<p style="margin-top:14px"><strong>Decision guidelines</strong></p><ul>`+b.guidelines.map(g=>`<li style="margin:6px 0;font-size:13.5px">${esc(g)}</li>`).join('')+`</ul>`;
  if(b.conventions && b.conventions.length)
    h+=`<p style="margin-top:14px"><strong>Starter conventions — the condensed set</strong> <span class="muted">(six core rules beat forty edge cases)</span></p><ul>`
      +b.conventions.map(c=>`<li style="margin:6px 0;font-size:13.5px">${esc(c.rule)} <span class="muted">(<code>${esc(c.id)}</code> · closes ${chip(c.closes,'risk')})</span></li>`).join('')+`</ul>`;
  if(b.priorities.length)
    h+=`<p style="margin-top:14px"><strong>What to defend hardest, in order:</strong> ${b.priorities.slice(0,6).map(p=>chip(p.signature,'risk')+` <span class="muted">(${esc(p.severity)})</span>`).join(' · ')}</p>`;
  h+=`<div class="callout" style="margin-top:16px"><strong>How you build toward this is yours.</strong>
    <span class="help">If you want the full buildable workflow — labeling steps, per-item fields, conventions, audit plan — the designer assembles it from the same evidence base.</span>
    <div style="margin-top:8px"><button class="btn" id="tofull">See the full buildable workflow →</button></div></div>`;
  $('#content').innerHTML = twocol(h)+nav();
  const tf=$('#tofull'); if(tf) tf.onclick=()=>{MODE='forward'; STEP=2; render();};
  wire();
}

// The goal-driven retrieval panel — re-rendered in place after an opt-in Tier-2 rerank.
function semPanel(sem){
  if(!(sem && sem.ranked && sem.ranked.length)) return '';
  const isLLM = sem.tier && sem.tier.indexOf('llm')===0;
  const rows = sem.ranked.filter(r=> isLLM || r.topical>0).slice(0,6).map(r=>{
    const sc = ('llm_score' in r) ? `<span class="muted">[${r.llm_score}]</span> ` : '';
    const why = r.why ? `<span class="muted"> — ${esc(r.why)}</span>`
              : ' '+(r.shared_terms||[]).slice(0,4).map(t=>`<span class="chip">${esc(t)}</span>`).join(' ');
    return `<li>${sc}<code>${esc(r.id)}</code> <span class="muted">(${esc(r.modality)}/${esc(r.task)})</span>${why}</li>`;
  }).join('');
  const btn = (META.llm_available && !isLLM)
    ? ` <button class="btn" id="rerankbtn" style="margin-left:6px">↑ rerank with Claude</button>` : '';
  return `<p style="margin-top:12px"><strong>Closest to what you described</strong> `
       + `<span class="muted">— your goal text ranks these (${esc(sem.tier)})</span>${btn}</p><ul>${rows}</ul>`;
}

// Opt-in Tier-2: one explicit LLM rerank of the goal-driven retrieval. Off until clicked; keyless setups
// never see the button (META.llm_available=false). Catches cross-domain matches the deterministic tiers miss.
async function rerank(){
  const b=$('#rerankbtn'); if(b){ b.textContent='reranking…'; b.disabled=true; }
  try{
    const r=await fetch('/api/rerank',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({stub})});
    const sem=await r.json();
    DATA.semantic=sem;                       // cache so it survives a re-render
    const p=$('#sempanel'); if(p) p.innerHTML=semPanel(sem);
  }catch(e){ const x=$('#rerankbtn'); if(x){ x.textContent='rerank failed'; x.disabled=false; } }
}
init();
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _send(self, code, body, ctype):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = PAGE.replace("__CSS__", build_site.CSS).replace("__JS__", JS)
            self._send(200, page, "text/html; charset=utf-8")
        elif self.path == "/api/meta":
            self._send(200, json.dumps(meta()), "application/json")
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path not in ("/api/analyze", "/api/rerank"):
            return self._send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        try:
            stub = json.loads(self.rfile.read(length) or b"{}").get("stub", {})
            if self.path == "/api/rerank":
                # Opt-in Tier-2: an explicit LLM rerank of the goal-driven retrieval (one call,
                # only when the user clicks). Falls back to Tier-1 inside analyze_semantic if no key.
                out = semantic.analyze_semantic(IDX, _norm(stub), use_llm=True, top=6)
                self._send(200, json.dumps(out), "application/json")
            else:
                self._send(200, json.dumps(payload(stub)), "application/json")
        except Exception as exc:  # never crash the server on a bad request
            self._send(400, json.dumps({"error": str(exc)}), "application/json")


def main():
    ap = argparse.ArgumentParser(description="Workflow Designer — local interactive web UI (stdlib).")
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--stub", help="open pre-loaded on this stub's Good Data Brief "
                                   "(e.g. a bridged retrospective diagnosis)")
    args = ap.parse_args()
    if args.stub:
        global PRELOAD
        PRELOAD = _norm(engine.load_stub(args.stub))
        print(f"preloaded stub: {args.stub} -> opening on the Good Data Brief")
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Workflow Designer running → http://localhost:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
