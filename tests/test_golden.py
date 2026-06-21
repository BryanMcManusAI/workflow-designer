"""Golden snapshots of the engine's analysis for representative stubs.

Snapshots the analyze_* DATA (not rendered text), so the Phase-3 render refactor leaves them
untouched and only a deliberate Phase-2 scoring change moves them. Regenerate intentionally with:

    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""
import json
import os

import pytest

from conftest import REPRESENTATIVE_STUBS

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")


def snapshot(eng, idx, stub):
    inter = eng.analyze_interrogate(idx, stub)
    bw = eng.analyze_backwards(idx, stub)
    near, far = eng.analyze_retrieve(idx, stub)
    wf = eng.analyze_workflow(idx, stub)
    return {
        "near": [[r["id"], r["score"]] for r in near],
        "far": [[r["id"], r["shared"]] for r in far],
        "interrogate_defended": inter["defended"],
        "interrogate_open": [[r["signature"], r["count"], [p["id"] for p in r["patterns"]]]
                             for r in inter["open"]],
        "backwards_good_means": bw["good_means"],
        "backwards_needed": [[p["id"], p["for"]] for p in bw["needed_patterns"]],
        "backwards_spec_threats": [s["signature"] for s in bw["spec_threats"]],
        "workflow_chosen": wf["chosen"],
        "workflow_steps": [[s["phase"], [p["id"] for p in s["patterns"]]] for s in wf["steps"]],
        "workflow_fields": wf["fields"],
        "workflow_conventions": [p["id"] for p in wf["conventions"]],
        "workflow_audit": [p["id"] for p in wf["audit"]],
    }


@pytest.mark.parametrize("name", sorted(REPRESENTATIVE_STUBS))
def test_golden(eng, idx, name):
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    path = os.path.join(GOLDEN_DIR, f"{name}.json")
    got = snapshot(eng, idx, dict(REPRESENTATIVE_STUBS[name]))

    if os.environ.get("UPDATE_GOLDEN") or not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(got, f, indent=2, ensure_ascii=False)
            f.write("\n")
        if os.environ.get("UPDATE_GOLDEN"):
            return  # explicit regen run: don't also assert
    with open(path) as f:
        want = json.load(f)
    assert got == want, f"{name} drifted from golden; review and rerun with UPDATE_GOLDEN=1 if intended"
