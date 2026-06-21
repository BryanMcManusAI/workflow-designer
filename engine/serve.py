#!/usr/bin/env python3
"""Local interactive web UI for the Workflow Designer — the "test and view in a browser" tool.

A tiny stdlib HTTP server: the SAME deterministic Python engine, exposed as a JSON API, with a
vanilla-JS page where you pick the axes + patterns and watch the assembled workflow, interrogation,
backwards-from-good, and coverage update live — adopt a pattern and the open risks shrink as the
coverage bar rises. No Streamlit, no build step, no dependencies; the engine logic stays in Python
(the browser only renders what the API returns).

Run:   python3 engine/serve.py [--port 8011]
Open:  http://localhost:8011
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine
import build_site  # reuse the shared CSS so the local app and the static site look the same

IDX = engine.load_index()
LIST_KEYS = ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures")


def _norm(stub):
    out = {"goal": stub.get("goal", ""), "modality": stub.get("modality"),
           "task_structure": stub.get("task_structure"),
           "annotator_structure": stub.get("annotator_structure")}
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
    }


def meta():
    v = engine.vocab(IDX)
    patterns = [{"id": pid, "name": p["name"]} for pid, p in sorted(IDX["patterns"].items())]
    return {"vocab": v, "patterns": patterns,
            "n_cards": len(IDX["cards"]), "n_patterns": len(IDX["patterns"])}


PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workflow Designer — interactive</title>
<style>__CSS__
.layout{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;}
.controls{flex:0 0 280px;position:sticky;top:16px;}
.main{flex:1;min-width:320px;}
label.fld{display:block;font-weight:600;margin:12px 0 3px;font-size:.9rem;}
select,input[type=text]{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:8px;
background:var(--bg);color:var(--fg);font:inherit;}
.qa{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:4px;}
.qa label{font-weight:400;font-size:.85rem;display:flex;gap:5px;align-items:center;}
.design-chips{margin:6px 0;min-height:24px;}
.pill{display:inline-flex;align-items:center;gap:6px;background:var(--chip);color:var(--chip-fg);
border-radius:20px;padding:2px 6px 2px 10px;font-size:.78rem;margin:2px;}
.pill button{background:none;border:none;color:var(--chip-fg);cursor:pointer;font-size:1rem;line-height:1;padding:0;}
button.btn{background:var(--accent);color:#fff;border:none;border-radius:7px;padding:6px 12px;
font:inherit;cursor:pointer;font-size:.85rem;} button.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line);}
button.adopt{background:var(--ok);color:var(--ok-fg);border:none;border-radius:6px;padding:2px 9px;
font-size:.75rem;font-weight:700;cursor:pointer;}
.covbar{height:14px;border-radius:7px;background:var(--code);overflow:hidden;margin:6px 0;}
.covbar>i{display:block;height:100%;background:var(--accent);}
.risk-card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0;}
.row{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;}
</style></head>
<body><div class="wrap">
  <h1>🧬 Workflow Designer <span style="font-size:.5em;font-weight:500;color:var(--muted)">interactive</span></h1>
  <p class="muted" id="corpus"></p>
  <div class="layout">
    <aside class="controls">
      <label class="fld">Goal</label>
      <input type="text" id="goal" placeholder="what data are you building?">
      <label class="fld">Modality</label><select id="modality"></select>
      <label class="fld">Task structure</label><select id="task_structure"></select>
      <label class="fld">Annotator structure</label><select id="annotator_structure"></select>
      <label class="fld">QA mechanisms in place</label><div class="qa" id="qa"></div>
      <label class="fld">Your design (adopted patterns)</label>
      <div class="design-chips" id="design"></div>
      <button class="btn ghost" id="reset">↺ Reset design</button>
    </aside>
    <main class="main">
      <div class="row"><strong>Coverage</strong><span class="muted" id="covtext"></span></div>
      <div class="covbar"><i id="covfill"></i></div>
      <div class="tabs" id="tabs"></div>
      <div id="panel"></div>
    </main>
  </div>
</div>
<script>__JS__</script>
</body></html>
"""

JS = r"""
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chip = (t,k='') => `<span class="chip ${k}">${esc(t)}</span>`;
let META=null, DATA=null, TAB='workflow';
const stub = {goal:"Evaluate AI-generated marketing copy at scale with an LLM judge",
  modality:"text", task_structure:"rubric_rating", annotator_structure:"model_as_annotator",
  qa_mechanism:[], uses_patterns:[], addressed_signatures:[], failure_signatures:[]};
const TABS = [["workflow","Assembled workflow"],["interrogate","Interrogate"],
  ["backwards","Backwards-from-good"],["retrieve","Analogues"]];

function opt(sel, vals, cur){ sel.innerHTML = vals.map(v=>`<option ${v===cur?'selected':''}>${esc(v)}</option>`).join(''); }

async function init(){
  META = await (await fetch('/api/meta')).json();
  $('#corpus').textContent = `${META.n_cards} recipes · ${META.n_patterns} patterns · deterministic, no LLM`;
  opt($('#modality'), META.vocab.modality, stub.modality);
  opt($('#task_structure'), META.vocab.task_structure, stub.task_structure);
  opt($('#annotator_structure'), META.vocab.annotator_structure, stub.annotator_structure);
  $('#qa').innerHTML = META.vocab.qa_mechanism.map(q=>
    `<label><input type="checkbox" value="${esc(q)}">${esc(q)}</label>`).join('');
  $('#goal').value = stub.goal;
  $('#tabs').innerHTML = TABS.map(([id,l])=>`<button data-tab="${id}" class="${id===TAB?'active':''}">${l}</button>`).join('');
  $('#goal').oninput = e => { stub.goal = e.target.value; };
  ['modality','task_structure','annotator_structure'].forEach(k=>
    $('#'+k).onchange = e => { stub[k]=e.target.value; analyze(); });
  $('#qa').onchange = () => { stub.qa_mechanism = [...$('#qa').querySelectorAll('input:checked')].map(i=>i.value); analyze(); };
  $('#reset').onclick = () => { stub.uses_patterns=[]; analyze(); };
  $('#tabs').onclick = e => { const t=e.target.dataset.tab; if(!t) return; TAB=t;
    document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('active', b.dataset.tab===t)); render(); };
  analyze();
}

async function analyze(){
  DATA = await (await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({stub})})).json();
  renderDesign(); renderCoverage(); render();
}

function renderDesign(){
  $('#design').innerHTML = stub.uses_patterns.length
    ? stub.uses_patterns.map(p=>`<span class="pill">${esc(p)}<button data-drop="${esc(p)}">×</button></span>`).join('')
    : '<span class="muted" style="font-size:.85rem">none yet — adopt from Interrogate</span>';
  $('#design').querySelectorAll('[data-drop]').forEach(b=>b.onclick=()=>{
    stub.uses_patterns = stub.uses_patterns.filter(x=>x!==b.dataset.drop); analyze(); });
}

function renderCoverage(){
  const c = DATA.coverage, pct = Math.round(c.pct*100);
  $('#covfill').style.width = pct+'%';
  $('#covtext').textContent = `${c.n_covered}/${c.n_applicable} applicable risks defended (${pct}%)`;
}

function badge(have){ return have?'<span class="badge have">have</span>':'<span class="badge add">add</span>'; }

function render(){
  if(TAB==='workflow') return renderWorkflow();
  if(TAB==='interrogate') return renderInterrogate();
  if(TAB==='backwards') return renderBackwards();
  if(TAB==='retrieve') return renderRetrieve();
}

function play(p){
  let g = '';
  if(p.as_done){ g = `<br><span class="muted seen">as <code>${esc(p.as_done.card)}</code> does — ${esc(p.as_done.gate)}: ${esc(p.as_done.checks)}</span>`; }
  else if(p.seen_in && p.seen_in.length){ g = `<br><span class="muted seen">seen in ${p.seen_in.map(c=>`<code>${esc(c)}</code>`).join(', ')}</span>`; }
  return `<li>${badge(p.have)} <code>${esc(p.id)}</code> — ${esc(p.instruction)}${g}</li>`;
}

function renderWorkflow(){
  const wf = DATA.workflow;
  const steps = wf.steps.map(s=>`<li><strong>${esc(s.phase)}</strong> — ${esc(s.do)}`
    + (s.patterns.length?`<ul class="plays">${s.patterns.map(play).join('')}</ul>`:'') + `</li>`).join('');
  const conv = wf.conventions.length?wf.conventions.map(play).join(''):'<li class="muted">a frozen, example-driven guideline is the baseline</li>';
  const audit = wf.audit.map(play).join('');
  const spec = wf.spec_threats.length?`<p class="colhead">…stress-test that “good” isn’t a proxy</p><ul class="spec">`
    + wf.spec_threats.map(s=>`<li><code>${esc(s.signature)}</code> — ${esc(s.probe)}</li>`).join('')+`</ul>`:'';
  $('#panel').innerHTML = `<h3>The assembled sample workflow</h3>
    <p class="muted">${badge(true)} = in your design · ${badge(false)} = from the backwards build list`
    + (wf.precedent?` · closest precedent <code>${esc(wf.precedent)}</code>`:'')+`</p>
    <div class="cols"><div><p class="colhead">Labeling steps</p><ol class="steps">${steps}</ol></div>
    <div><p class="colhead">Fields per item</p><ul class="fields">${wf.fields.map(f=>`<li><code>${esc(f)}</code></li>`).join('')}</ul>
    <p class="colhead">Suggested conventions</p><ul class="plays">${conv}</ul>
    <p class="colhead">Audit strategy</p><ul class="plays">${audit}</ul>${spec}</div></div>`;
}

function renderInterrogate(){
  const r = DATA.interrogate;
  let h = '<h3>Interrogation — open risks &amp; the patterns that catch them</h3>';
  if(r.defended.length) h += `<p class="ok">Defended by your design: ${r.defended.map(s=>`<code>${esc(s)}</code>`).join(', ')}</p>`;
  if(!r.open.length) h += '<p class="ok">No open risks left — your design covers them. 🎯</p>';
  h += r.open.map(o=>`<div class="risk-card"><div class="row"><p><code class="risk">${esc(o.signature)}</code> ${esc(o.question)}</p></div>`
    + (o.unguarded?'<p class="warn">UNGUARDED — a corpus gap.</p>':'')
    + o.patterns.map(p=>`<div class="row"><span>borrow <code>${esc(p.id)}</code> — ${esc(p.name)} <span class="muted">· cost: ${esc(p.cost)}</span></span>`
      + `<button class="adopt" data-adopt="${esc(p.id)}">+ adopt</button></div>`).join('')
    + (o.example.card?`<p class="seen muted">seen in <code>${esc(o.example.card)}</code></p>`:'')+`</div>`).join('');
  if(r.conflicts && r.conflicts.length) h += `<p class="warn">⟂ conflicts: `+r.conflicts.map(c=>`<code>${esc(c[0])}</code>⟂<code>${esc(c[1])}</code>`).join(', ')+`</p>`;
  if(r.complements && r.complements.length) h += `<p class="muted">complements: `+r.complements.slice(0,6).map(c=>`<code>${esc(c.id)}</code>`).join(', ')+`</p>`;
  $('#panel').innerHTML = h;
  $('#panel').querySelectorAll('[data-adopt]').forEach(b=>b.onclick=()=>{
    if(!stub.uses_patterns.includes(b.dataset.adopt)){ stub.uses_patterns.push(b.dataset.adopt); analyze(); }});
}

function renderBackwards(){
  const bw = DATA.backwards;
  let h = '<h3>Backwards from good</h3><p><strong>“Good” here means free of:</strong> '
    + bw.good_means.map(s=>chip(s,'risk')).join(' ')+'</p>';
  if(bw.needed_patterns.length){ h += '<p><strong>The workflow that guarantees it</strong> — one defense per open risk:</p><ul>'
    + bw.needed_patterns.map(p=>`<li><code>${esc(p.id)}</code> — ${esc(p.name)} <span class="muted">· closes <code>${esc(p.for)}</code></span></li>`).join('')+'</ul>'; }
  else h += '<p class="ok">Your design already covers every applicable failure mode. 🎯</p>';
  if(bw.spec_threats.length){ h += '<div class="callout"><strong>But first — is your <em>good</em> actually good?</strong><ul>'
    + bw.spec_threats.map(s=>`<li><code>${esc(s.signature)}</code> — ${esc(s.question)} <span class="muted">probe: ${esc(s.probe)}</span></li>`).join('')+'</ul></div>'; }
  $('#panel').innerHTML = h;
}

function renderRetrieve(){
  const {near,far} = DATA.retrieve;
  $('#panel').innerHTML = `<h3>Analogous prior workflows</h3><div class="cols">
    <div><p class="colhead">Near — your modality / task / annotator</p><ul>`
    + near.slice(0,5).map(r=>`<li><code>${esc(r.id)}</code> <span class="muted">(${esc(r.modality)}/${esc(r.task)}) — shares ${esc(r.why.join(', '))}</span></li>`).join('')
    + `</ul></div><div><p class="colhead">Far — distant domain, same (rare) risk</p><ul>`
    + far.slice(0,5).map(r=>`<li><code>${esc(r.id)}</code> <span class="muted">(${esc(r.modality)}/${esc(r.task)})</span> ${r.shared.slice(0,3).map(s=>chip(s,'risk')).join(' ')}</li>`).join('')
    + `</ul></div></div>`;
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
        if self.path != "/api/analyze":
            return self._send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        try:
            stub = json.loads(self.rfile.read(length) or b"{}").get("stub", {})
            self._send(200, json.dumps(payload(stub)), "application/json")
        except Exception as exc:  # never crash the server on a bad request
            self._send(400, json.dumps({"error": str(exc)}), "application/json")


def main():
    ap = argparse.ArgumentParser(description="Workflow Designer — local interactive web UI (stdlib).")
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Workflow Designer running → http://localhost:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
