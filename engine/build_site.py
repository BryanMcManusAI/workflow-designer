#!/usr/bin/env python3
"""Pre-render the Workflow Designer into a self-contained static site (docs/index.html).

Runs the deterministic engine over a few curated examples at BUILD time and bakes the results into
one HTML file — no Streamlit, no server, no engine in the browser, no network. The page is the
public face of the tool: a visitor flips between examples and sees the backwards-from-good pass,
the analogues, the interrogation, and a creative move, every suggestion still tagged with the
pattern + signature + cost it's grounded in.

Build:  python3 engine/build_index.py   # if the corpus changed
        python3 engine/build_site.py     # -> docs/index.html
Host:   GitHub Pages, "Deploy from branch: main -> /docs" (zero config).
"""
import html
import os

import engine

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "docs")
OUT = os.path.join(OUT_DIR, "index.html")
REPO_URL = "https://github.com/BryanMcManusAI/workflow-designer"

# Curated examples for the public demo (one per modality family).
EXAMPLES = {
    "Image reward-model preferences": {
        "goal": "Collect pairwise preference data to train a reward model for an image generator",
        "modality": "image", "task_structure": "preference_ranking", "annotator_structure": "crowd",
        "qa_mechanism": ["gold_honeypots", "agreement"],
        "uses_patterns": ["multi-annotator-aggregate", "gold-honeypots"],
    },
    "LLM-judge for marketing copy": {
        "goal": "Evaluate AI-generated marketing copy at scale with an LLM judge",
        "modality": "text", "task_structure": "rubric_rating", "annotator_structure": "model_as_annotator",
        "qa_mechanism": [], "uses_patterns": ["human-gold-anchor"],
    },
    "Code-generation eval set": {
        "goal": "Build an eval set that measures whether generated code is functionally correct",
        "modality": "code", "task_structure": "freeform_generation", "annotator_structure": "expert",
        "qa_mechanism": ["execution_check"], "uses_patterns": ["execution-verification"],
    },
}
SHIFT_TARGET = {"image": "video", "text": "image", "code": "text", "audio": "text"}


def e(s):
    return html.escape(str(s))


def chip(text, kind=""):
    cls = f"chip {kind}".strip()
    return f'<span class="{cls}">{e(text)}</span>'


def normalize(stub):
    stub = dict(stub)
    for k in ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures"):
        stub.setdefault(k, [])
    return stub


# ---- per-section HTML (reads the same analyze_* data the CLI/REPL/tests use) ----

def section_backwards(idx, stub):
    bw = engine.analyze_backwards(idx, stub)
    parts = ['<h3>Backwards from good <span class="lead-tag">the core move</span></h3>']
    parts.append('<p class="muted">Good data is data <em>free of the ways it goes bad</em>. The '
                 'engine runs in reverse: from what “good” means here, to the failure modes that '
                 'threaten it, to one defense per risk — then stress-tests whether your definition '
                 'of “good” is itself a proxy.</p>')
    parts.append('<p><strong>“Good” data here means free of:</strong> '
                 + " ".join(chip(s, "risk") for s in bw["good_means"][:10]) + "</p>")
    if bw["needed_patterns"]:
        parts.append('<p><strong>The workflow that guarantees it</strong> — one defense per open risk:</p><ul>')
        for p in bw["needed_patterns"][:7]:
            parts.append(f'<li><code>{e(p["id"])}</code> — {e(p["name"])} '
                         f'<span class="muted">· closes <code>{e(p["for"])}</code></span></li>')
        parts.append("</ul>")
    elif bw["already_have"]:
        parts.append('<p class="ok">The starting patterns already cover every applicable failure mode.</p>')
    if bw["spec_threats"]:
        parts.append('<div class="callout"><strong>But first — is your <em>good</em> actually good?</strong>'
                     '<p class="muted">The hardest lesson from the detector work: the gold is the thing most '
                     'likely to be wrong. Each check asks whether “good” is secretly a proxy.</p><ul>')
        for s in bw["spec_threats"][:4]:
            parts.append(f'<li><code>{e(s["signature"])}</code> — {e(s["question"])} '
                         f'<span class="muted">probe: {e(s["probe"])}</span></li>')
        parts.append("</ul></div>")
    return "\n".join(parts)


def section_retrieve(idx, stub):
    near, far = engine.analyze_retrieve(idx, stub)
    near_html = "".join(
        f'<li><code>{e(r["id"])}</code> <span class="muted">({e(r["modality"])}/{e(r["task"])}) '
        f'— shares {e(", ".join(r["why"]))}</span></li>' for r in near[:4])
    far_html = "".join(
        f'<li><code>{e(r["id"])}</code> <span class="muted">({e(r["modality"])}/{e(r["task"])})</span> '
        f'— {" ".join(chip(s, "risk") for s in r["shared"][:3])}</li>' for r in far[:4])
    return (f'<h3>1 · It finds analogous prior workflows</h3>'
            f'<div class="cols"><div><p class="colhead">Near — your modality / task / annotator</p>'
            f'<ul>{near_html}</ul></div>'
            f'<div><p class="colhead">Far — distant domain, <em>same risk</em> (the creative pulls, '
            f'ranked by how rare the shared risk is)</p><ul>{far_html}</ul></div></div>')


def section_interrogate(idx, stub):
    res = engine.analyze_interrogate(idx, stub)
    parts = ['<h3>2 · It interrogates your design against their failure modes</h3>',
             '<p class="muted">Each suggestion names the pattern that defends the risk, the cost it '
             'adds, and a real workflow that hit it. That traceability is the point.</p>']
    if res["defended"]:
        parts.append('<p class="ok">Already defended by the starting patterns: '
                     + ", ".join(f"<code>{e(s)}</code>" for s in res["defended"]) + "</p>")
    for r in res["open"][:6]:
        pats = "".join(
            f'<li>borrow <code>{e(p["id"])}</code> — {e(p["name"])} '
            f'<span class="muted">· cost: {e(p["cost"])}</span></li>' for p in r["patterns"][:3])
        seen = (f'<p class="seen muted">a real workflow that hit this: <code>{e(r["example"]["card"])}</code></p>'
                if r["example"]["card"] else "")
        unguarded = '<p class="warn">UNGUARDED — a corpus gap; no pattern defends this yet.</p>' if r["unguarded"] else ""
        parts.append(f'<div class="risk-card"><p><code class="risk">{e(r["signature"])}</code> '
                     f'{e(r["question"])}</p>{unguarded}<ul>{pats}</ul>{seen}</div>')
    if len(res["open"]) > 6:
        parts.append(f'<p class="muted">…and {len(res["open"]) - 6} more open risks.</p>')
    return "\n".join(parts)


def section_shift(idx, stub):
    to = SHIFT_TARGET.get(stub["modality"], "text")
    ms = engine.analyze_modality_shift(idx, stub, to)
    parts = [f'<h3>3 · It makes creative moves — e.g. “what would this become for {e(to)}?”</h3>']
    if ms["kept"]:
        kept = "".join(f'<li><code>{e(k["id"])}</code> <span class="muted">→ {e(k["notes"][:160])}</span></li>'
                       for k in ms["kept"])
        parts.append(f'<p><strong>Keeps the skeleton, re-derives what changes:</strong></p><ul>{kept}</ul>')
    if ms["new_risks"]:
        parts.append('<p><strong>New risks ' + chip(to) + ' introduces:</strong> '
                     + " ".join(chip(nr["signature"], "risk") for nr in ms["new_risks"]) + "</p>")
    return "\n".join(parts)


def section_compare(idx, stub):
    if stub["task_structure"] not in engine.tasks_with_variants(idx):
        return ""
    comp = engine.analyze_compare(idx, stub["task_structure"])
    rows = "".join(f'<li><strong>{e(v["lineage"])}</strong> — {e(v["distinctive"][:220])}</li>'
                   for v in comp["variants"] if v["distinctive"])
    if not rows:
        return ""
    return (f'<h3>4 · It shows how leading labs solved the same problem differently</h3><ul>{rows}</ul>')


def _badge(have):
    return ('<span class="badge have">have</span>' if have
            else '<span class="badge add">add</span>')


def _play_li(p):
    ground = ""
    if p.get("as_done"):
        a = p["as_done"]
        ground = (f'<br><span class="muted seen">as <code>{e(a["card"])}</code> does — '
                  f'{e(a["gate"])}: {e(a["checks"])}</span>')
    elif p.get("seen_in"):
        ground = (f'<br><span class="muted seen">seen in '
                  + ", ".join(f"<code>{e(c)}</code>" for c in p["seen_in"]) + "</span>")
    return (f'<li>{_badge(p["have"])} <code>{e(p["id"])}</code> — {e(p["instruction"])}{ground}</li>')


def section_workflow(idx, stub):
    """The headline deliverable: a concrete, buildable sample workflow for these selections."""
    wf = engine.analyze_workflow(idx, stub)
    steps = []
    for s in wf["steps"]:
        plays = "".join(_play_li(p) for p in s["patterns"])
        plays = f'<ul class="plays">{plays}</ul>' if plays else ""
        steps.append(f'<li><strong>{e(s["phase"])}</strong> — {e(s["do"])}{plays}</li>')
    fields = "".join(f"<li><code>{e(f)}</code></li>" for f in wf["fields"])
    conventions = ("".join(_play_li(p) for p in wf["conventions"])
                   or '<li class="muted">a frozen, example-driven guideline is the baseline convention</li>')
    audit = "".join(_play_li(p) for p in wf["audit"])
    spec = "".join(f'<li><code>{e(s["signature"])}</code> — {e(s["probe"])}</li>'
                   for s in wf["spec_threats"])
    spec_block = (f'<p class="colhead">…and stress-test that “good” isn’t a proxy</p>'
                  f'<ul class="spec">{spec}</ul>') if spec else ""
    precedent = (f'<span class="muted"> · closest real precedent: '
                 f'<code>{e(wf["precedent"])}</code></span>' if wf["precedent"] else "")
    return f"""<div class="workflow">
  <h3>The assembled sample workflow <span class="lead-tag">the output</span></h3>
  <p class="muted">For these selections, the engine assembles a concrete, buildable recipe —
  <span class="badge have">have</span> = already in the starting design,
  <span class="badge add">add</span> = from the backwards-from-good build list.{precedent}</p>
  <div class="wf-grid">
    <div class="wf-col wf-steps"><p class="colhead">Labeling steps</p><ol class="steps">{''.join(steps)}</ol></div>
    <div class="wf-col"><p class="colhead">Fields per item</p><ul class="fields">{fields}</ul>
      <p class="colhead">Suggested conventions</p><ul class="plays">{conventions}</ul>
      <p class="colhead">Audit strategy</p><ul class="plays">{audit}</ul>{spec_block}
    </div>
  </div>
</div>"""


def build_example(idx, name, stub):
    stub = normalize(stub)
    head = (f'<p class="stub-line"><strong>{e(stub["goal"])}</strong><br>'
            f'{chip(stub["modality"])} {chip(stub["task_structure"])} {chip(stub["annotator_structure"])}'
            f' · starting patterns: '
            + (" ".join(f"<code>{e(p)}</code>" for p in stub["uses_patterns"]) or "none") + "</p>")
    body = "\n".join([
        head,
        section_workflow(idx, stub),
        '<hr class="soft">',
        section_backwards(idx, stub),
        '<p class="muted small">How it got there ↓</p>',
        section_retrieve(idx, stub),
        section_interrogate(idx, stub),
        section_shift(idx, stub),
        section_compare(idx, stub),
    ])
    return body


CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e4e4e7;--accent:#3b5bdb;--chip:#eef1fb;
--chip-fg:#33409a;--risk:#fbe9e7;--risk-fg:#9a3b2e;--ok:#e7f5ec;--ok-fg:#1f7a44;--warn:#fff4e5;
--warn-fg:#9a6a1f;--card:#fafafa;--code:#f1f1f4;}
@media (prefers-color-scheme:dark){:root{--bg:#15161a;--fg:#e8e8ea;--muted:#9a9aa2;--line:#2c2d33;
--accent:#7c93f5;--chip:#222640;--chip-fg:#b9c4f7;--risk:#3a2420;--risk-fg:#f0a89b;--ok:#1d3326;
--ok-fg:#86e0a6;--warn:#3a3020;--warn-fg:#f0cf94;--card:#1b1c21;--code:#24252b;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:880px;margin:0 auto;padding:40px 24px 80px;}
h1{font-size:2rem;margin:0 0 4px;}
h2.sub{font-weight:500;color:var(--muted);margin:0 0 20px;font-size:1.1rem;}
h3{font-size:1.15rem;margin:28px 0 8px;}
a{color:var(--accent);}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.86em;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
.muted{color:var(--muted);} .ok{color:var(--ok-fg);} .warn{color:var(--warn-fg);font-weight:600;}
.metrics{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 6px;}
.metric{flex:1;min-width:120px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:12px 14px;}
.metric .n{font-size:1.5rem;font-weight:700;} .metric .l{color:var(--muted);font-size:.85rem;}
.chip{display:inline-block;background:var(--chip);color:var(--chip-fg);border-radius:20px;
padding:1px 10px;font-size:.8rem;margin:1px 2px;white-space:nowrap;}
.chip.risk{background:var(--risk);color:var(--risk-fg);}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0 8px;border-bottom:1px solid var(--line);}
.tabs button{background:none;border:none;border-bottom:2px solid transparent;color:var(--muted);
font:inherit;padding:8px 4px;cursor:pointer;}
.tabs button.active{color:var(--fg);border-bottom-color:var(--accent);font-weight:600;}
.example{display:none;} .example.active{display:block;}
.stub-line{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;}
.lead-tag{font-size:.7rem;background:var(--accent);color:#fff;border-radius:20px;padding:2px 9px;
vertical-align:middle;margin-left:6px;font-weight:600;}
.cols{display:flex;gap:20px;flex-wrap:wrap;} .cols>div{flex:1;min-width:260px;}
.colhead{font-weight:600;margin:6px 0;}
ul{margin:6px 0;padding-left:20px;} li{margin:3px 0;}
.risk-card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:10px 14px;margin:8px 0;}
.risk-card code.risk{background:var(--risk);color:var(--risk-fg);}
.callout{background:var(--warn);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0;}
.callout .muted{color:var(--warn-fg);opacity:.85;}
hr.soft{border:none;border-top:1px solid var(--line);margin:20px 0;}
.seen{font-size:.85rem;margin:4px 0 0;}
.small{font-size:.85rem;}
.workflow{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0;}
.wf-grid{display:flex;gap:24px;flex-wrap:wrap;}
.wf-col{flex:1;min-width:280px;} .wf-steps{flex:1.25;}
ol.steps{padding-left:22px;} ol.steps>li{margin:8px 0;}
ul.plays{list-style:none;padding-left:0;margin:4px 0;} ul.plays>li{margin:4px 0;font-size:.92rem;}
ul.fields{margin:4px 0 12px;} ul.spec{margin:4px 0;font-size:.88rem;}
.badge{display:inline-block;border-radius:5px;padding:0 6px;font-size:.68rem;font-weight:700;
text-transform:uppercase;letter-spacing:.04em;vertical-align:middle;}
.badge.have{background:var(--ok);color:var(--ok-fg);}
.badge.add{background:var(--warn);color:var(--warn-fg);}
footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:.9rem;}
"""

JS = """
const tabs=[...document.querySelectorAll('.tabs button')];
const secs=[...document.querySelectorAll('.example')];
tabs.forEach(b=>b.addEventListener('click',()=>{
  tabs.forEach(x=>x.classList.remove('active'));
  secs.forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  document.querySelector('.example[data-ex="'+b.dataset.ex+'"]').classList.add('active');
}));
"""


def main():
    idx = engine.load_index()
    n_domains = len({c["domain"] for c in idx["cards"].values()})

    tabs, sections = [], []
    for i, (name, stub) in enumerate(EXAMPLES.items()):
        active = " active" if i == 0 else ""
        tabs.append(f'<button class="{active.strip()}" data-ex="{i}">{e(name)}</button>')
        sections.append(f'<section class="example{active}" data-ex="{i}">{build_example(idx, name, stub)}</section>')

    metrics = "".join(f'<div class="metric"><div class="n">{n}</div><div class="l">{l}</div></div>'
                      for n, l in [(len(idx["cards"]), "recipes"),
                                   (len(idx["patterns"]), "reusable patterns"),
                                   (n_domains, "domains"),
                                   ("published", "methods, grounded")])

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workflow Designer — a creative partner for ML data workflows</title>
<meta name="description" content="A deterministic creative partner for designing ML data workflows: finds analogous prior workflows, interrogates a design against their failure modes, and works backwards from what 'good' means — every suggestion grounded in a real prior workflow with a real cost.">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>🧬 Workflow Designer</h1>
  <h2 class="sub">A deterministic creative partner for designing ML data workflows</h2>
  <p>Describe a data workflow you want to build. The partner finds <strong>analogous prior
  workflows</strong>, <strong>interrogates</strong> your design against the failure modes they hit,
  and works <strong>backwards from what “good” means</strong> — and every suggestion is grounded in a
  real prior workflow with a real cost. It's deterministic: no LLM in the loop, nothing it can't
  trace back to a source. It can't bluff.</p>
  <div class="metrics">{metrics}</div>
  <p class="muted">Pick a workflow to design — the analysis below is computed by the engine, baked in
  at build time:</p>
  <div class="tabs">{''.join(tabs)}</div>
  {''.join(sections)}
  <footer>
    <p><strong>Why deterministic.</strong> Every suggestion cites the pattern it borrows, the failure
    signature it inherits, and the cost it adds — legible back to a real prior workflow, never a
    confident fabrication. Generative <em>because</em> it's legible, not despite it.</p>
    <p>Source &amp; the interactive REPL/CLI: <a href="{REPO_URL}">{REPO_URL}</a>. MIT licensed;
    corpus is synthetic/public only.</p>
  </footer>
</div>
<script>{JS}</script>
</body>
</html>
"""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w") as f:
        f.write(page)
    print(f"wrote {OUT}: {len(EXAMPLES)} examples, {len(idx['cards'])} cards, {len(idx['patterns'])} patterns")


if __name__ == "__main__":
    main()
