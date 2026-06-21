#!/usr/bin/env python3
"""Workflow Designer — interactive REPL (the working tool).

Build a workflow stub, then iterate: interrogate it, *adopt* patterns and watch the open risks
shrink / coverage rise, run creative moves (shift / flip / transplant), compare labs, and save the
session as a reusable stub. Stdlib only, deterministic — it drives the very same engine functions
the CLI and the test suite use, so what you explore here is exactly what ships.

Run:   python3 engine/repl.py [--stub path/to/stub.yaml]
"""
import argparse
import io
import os
import shlex
from contextlib import redirect_stdout

import engine

AXES = ("goal", "modality", "task_structure", "annotator_structure")
LIST_KEYS = ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures")

HELP = """commands
  status                 design summary: axes, adopted patterns, coverage bar
  workflow | w           assemble the sample workflow: labeling steps · fields · conventions · audit
  backwards | b          backwards-from-good: what 'good' means + the build list + spec stress-test
  interrogate | i        open risks + the patterns that catch them (numbered)
  adopt <id|N>           add a pattern — by id, or N = the top pattern for open risk #N
  drop <id>              remove an adopted pattern
  reset                  clear adopted patterns
  coverage | cov         how much of the applicable failure space your design defends
  retrieve | r           near + far analogues
  shift <modality>       modality-shift the skeleton into another modality
  transplant | t         distant patterns that defend your open risks
  flip <axis> <value>    change a constraint; see what survives / breaks
  substitute <value>     actor-substitute: swap the annotator_structure
  compare <task>         how different labs did the same task type
  cookbook <angle>       browse every recipe grouped by an angle
  browse [cards|patterns]   list the corpus
  show <id>              full detail for a card or pattern
  set <axis> <value>     change goal / modality / task_structure / annotator_structure
  vocab                  valid values for each axis
  save <path>            write the current stub to a YAML file
  help | ?               this list
  quit | q               exit
"""

BANNER = "Workflow Designer — interactive partner. Type `help` for commands, `quit` to exit."


def default_stub():
    """The default example stub (mirrors examples/new_workflow.yaml's intent), already normalized."""
    stub = {"goal": "Evaluate AI-generated marketing copy at scale with an LLM judge",
            "modality": "text", "task_structure": "rubric_rating",
            "annotator_structure": "model_as_annotator"}
    for k in LIST_KEYS:
        stub[k] = []
    return stub


def normalize(stub):
    for k in LIST_KEYS:
        v = stub.get(k, [])
        stub[k] = [v] if isinstance(v, str) else list(v or [])
    return stub


def stub_to_yaml(stub):
    lines = []
    for k in AXES:
        lines.append(f"{k}: {stub.get(k, '')}")
    for k in LIST_KEYS:
        lines.append(f"{k}: [{', '.join(stub.get(k, []))}]")
    return "\n".join(lines) + "\n"


class Repl:
    def __init__(self, idx, stub):
        self.idx = idx
        self.stub = normalize(stub)
        self.last_open = []  # the open-risk rows from the most recent interrogate (for `adopt N`)

    # ---- small helpers ----
    def _vocab(self):
        return engine.vocab(self.idx)

    def _is_valid(self, axis, value):
        if axis == "goal":
            return True
        return value in self._vocab().get(axis, [])

    def _bad_value(self, axis, value):
        opts = self._vocab().get(axis, [])
        print(f"  '{value}' is not a known {axis}. Valid: {', '.join(opts) or '(none)'}")

    # ---- views ----
    def status(self):
        engine.stub_banner(self.stub)
        adopted = self.stub["uses_patterns"]
        print("  adopted patterns: " + (", ".join(adopted) if adopted else "(none yet)"))
        engine.render_coverage(engine.analyze_coverage(self.idx, self.stub))

    def interrogate(self):
        res = engine.analyze_interrogate(self.idx, self.stub)
        self.last_open = res["open"]
        engine.render_interrogate(res)

    # ---- pattern moves ----
    def adopt(self, token):
        pid = None
        if token.isdigit():
            n = int(token)
            if not self.last_open:
                # populate suggestions if the user adopts before interrogating
                self.last_open = engine.analyze_interrogate(self.idx, self.stub)["open"]
            if 1 <= n <= len(self.last_open) and self.last_open[n - 1]["patterns"]:
                pid = self.last_open[n - 1]["patterns"][0]["id"]
            else:
                print(f"  no defending pattern for open risk #{token}")
                return
        else:
            pid = token
        if pid not in self.idx["patterns"]:
            print(f"  unknown pattern `{pid}`")
            return
        if pid in self.stub["uses_patterns"]:
            print(f"  `{pid}` already in your design")
            return
        self.stub["uses_patterns"].append(pid)
        print(f"  + adopted `{pid}` — {self.idx['patterns'][pid]['name']}")
        engine.render_coverage(engine.analyze_coverage(self.idx, self.stub))

    def drop(self, pid):
        if pid in self.stub["uses_patterns"]:
            self.stub["uses_patterns"].remove(pid)
            print(f"  - dropped `{pid}`")
            engine.render_coverage(engine.analyze_coverage(self.idx, self.stub))
        else:
            print(f"  `{pid}` is not in your design")

    def reset(self):
        self.stub["uses_patterns"] = []
        print("  design reset (no patterns adopted)")

    # ---- setters ----
    def set_axis(self, axis, value):
        if axis not in AXES:
            print(f"  axis must be one of: {', '.join(AXES)}")
            return
        if not self._is_valid(axis, value):
            self._bad_value(axis, value)
            return
        self.stub[axis] = value
        print(f"  set {axis} = {value}")

    def save(self, path):
        path = os.path.expanduser(path)
        with open(path, "w") as f:
            f.write(stub_to_yaml(self.stub))
        print(f"  wrote stub to {path}")

    def show(self, id_):
        if id_ in self.idx["cards"]:
            c = self.idx["cards"][id_]
            print(f"\n{id_} — {c['modality']}/{c['task_structure']}/{c['annotator_structure']}")
            for label, key in (("lineage", "lineage"), ("domain", "domain"), ("scale", "scale")):
                if c.get(key):
                    print(f"  {label}: {c[key]}")
            if c.get("decision"):
                print(engine.wrap("decision: " + c["decision"], "  "))
            if c.get("distinctive"):
                print(engine.wrap("distinctive: " + c["distinctive"], "  "))
            print("  patterns: " + (", ".join(c["uses_patterns"]) or "—"))
            if c.get("failure_modes"):
                print("  failure modes:")
                for fm in c["failure_modes"]:
                    print(engine.wrap(f"[{fm['signature']}] ({fm.get('evidence','')}) "
                                      f"{fm['description'][:160]}", "    "))
        elif id_ in self.idx["patterns"]:
            p = self.idx["patterns"][id_]
            print(f"\n{id_} — {p['name']}")
            print(engine.wrap(p.get("does", ""), "  "))
            print("  defends: " + (", ".join(p["defends"]) or "(a strategy, no signature)"))
            print("  pairs_with: " + (", ".join(p.get("pairs_with", [])) or "—"))
            print("  conflicts_with: " + (", ".join(p.get("conflicts_with", [])) or "—"))
            print(f"  cost: {p['cost']}")
            print("  exemplified_by: " + ", ".join(p["exemplified_by"]))
        else:
            print(f"  no card or pattern named `{id_}`")

    def browse(self, what):
        what = what or "cards"
        if what.startswith("pattern"):
            for pid, p in sorted(self.idx["patterns"].items()):
                print(f"  {pid} — {p['name']}")
        else:
            for cid, c in sorted(self.idx["cards"].items()):
                print(f"  {cid}  ({c['modality']}/{c['task_structure']})")

    def vocab(self):
        for axis, vals in self._vocab().items():
            print(f"  {axis}: {', '.join(vals)}")

    # ---- dispatch ----
    def dispatch(self, line):
        """Run one command line. Returns False to quit, True otherwise."""
        line = line.strip()
        if not line or line.startswith("#"):
            return True
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]

        if cmd in ("quit", "q", "exit"):
            return False
        elif cmd in ("help", "?"):
            print(HELP)
        elif cmd == "status":
            self.status()
        elif cmd in ("workflow", "w"):
            engine.stub_banner(self.stub)
            engine.render_workflow(engine.analyze_workflow(self.idx, self.stub))
        elif cmd in ("backwards", "b"):
            engine.stub_banner(self.stub)
            engine.render_backwards(self.stub, engine.analyze_backwards(self.idx, self.stub))
        elif cmd in ("interrogate", "i"):
            self.interrogate()
        elif cmd == "adopt":
            self.adopt(args[0]) if args else print("  usage: adopt <pattern-id | N>")
        elif cmd == "drop":
            self.drop(args[0]) if args else print("  usage: drop <pattern-id>")
        elif cmd == "reset":
            self.reset()
        elif cmd in ("coverage", "cov"):
            engine.render_coverage(engine.analyze_coverage(self.idx, self.stub))
        elif cmd in ("retrieve", "r"):
            near, far = engine.analyze_retrieve(self.idx, self.stub)
            engine.render_retrieve(near, far)
        elif cmd in ("transplant", "t"):
            engine.render_transplant(engine.analyze_transplant(self.idx, self.stub))
        elif cmd == "shift":
            if not args:
                print("  usage: shift <modality>")
            elif not self._is_valid("modality", args[0]):
                self._bad_value("modality", args[0])
            else:
                engine.render_modality_shift(
                    engine.analyze_modality_shift(self.idx, self.stub, args[0]), args[0])
        elif cmd == "flip":
            if len(args) < 2:
                print("  usage: flip <axis> <value>")
            else:
                engine.render_flip(engine.analyze_flip(self.idx, self.stub, args[0], args[1]),
                                   args[0], args[1])
        elif cmd == "substitute":
            if not args:
                print("  usage: substitute <annotator_structure>")
            else:
                engine.render_flip(
                    engine.analyze_flip(self.idx, self.stub, "annotator_structure", args[0]),
                    "annotator_structure", args[0], actor=True)
        elif cmd == "compare":
            if not args:
                print(f"  usage: compare <task>; with variants: "
                      f"{', '.join(engine.tasks_with_variants(self.idx))}")
            else:
                engine.render_compare(self.idx, engine.analyze_compare(self.idx, args[0]))
        elif cmd == "cookbook":
            by = args[0] if args else "domain"
            if by not in engine.COOKBOOK_ANGLES:
                print(f"  angle must be one of: {', '.join(engine.COOKBOOK_ANGLES)}")
            else:
                engine.render_cookbook(engine.analyze_cookbook(self.idx, by))
        elif cmd == "browse":
            self.browse(args[0] if args else None)
        elif cmd == "show":
            self.show(args[0]) if args else print("  usage: show <card-or-pattern-id>")
        elif cmd == "set":
            self.set_axis(args[0], " ".join(args[1:])) if len(args) >= 2 else \
                print("  usage: set <axis> <value>")
        elif cmd == "vocab":
            self.vocab()
        elif cmd == "save":
            self.save(args[0]) if args else print("  usage: save <path>")
        else:
            print(f"  unknown command `{cmd}` — type `help`")
        return True


def run(commands, stub=None, idx=None):
    """Drive the REPL non-interactively over a list of command strings; return the transcript.
    Used by the test suite (and handy for scripting a session)."""
    repl = Repl(idx or engine.load_index(), stub or default_stub())
    buf = io.StringIO()
    with redirect_stdout(buf):
        for line in commands:
            if not repl.dispatch(line):
                break
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(description="Workflow Designer interactive REPL (stdlib).")
    ap.add_argument("--stub", help="path to a stub YAML to start from")
    args = ap.parse_args()

    idx = engine.load_index()
    stub = engine.load_stub(args.stub) if args.stub else default_stub()
    repl = Repl(idx, stub)

    print(BANNER)
    print(f"corpus: {len(idx['cards'])} cards · {len(idx['patterns'])} patterns\n")
    repl.status()
    print()
    while True:
        try:
            line = input("wd> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not repl.dispatch(line):
            break


if __name__ == "__main__":
    main()
