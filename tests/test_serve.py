"""The local web app exposes the engine as JSON; check the payload is complete, normalized, and
JSON-serializable (the browser only renders this — no engine logic client-side)."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

import serve  # noqa: E402

from conftest import REPRESENTATIVE_STUBS  # noqa: E402


def test_meta_shape():
    m = serve.meta()
    assert m["n_cards"] > 0 and m["n_patterns"] > 0
    assert set(m["vocab"]) >= {"modality", "task_structure", "annotator_structure", "qa_mechanism"}
    assert all("id" in p and "name" in p for p in m["patterns"])
    json.dumps(m)  # must serialize


def test_payload_complete_and_serializable():
    p = serve.payload(dict(REPRESENTATIVE_STUBS["image_preference"]))
    assert set(p) >= {"stub", "workflow", "interrogate", "backwards", "coverage", "retrieve"}
    # the 4 list keys are normalized onto the returned stub
    for k in ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures"):
        assert isinstance(p["stub"][k], list)
    assert p["retrieve"]["near"] and "id" in p["retrieve"]["near"][0]
    json.dumps(p)  # the whole payload must be JSON-serializable (incl. conflict tuples -> arrays)


def test_payload_matches_engine(eng, idx):
    stub = dict(REPRESENTATIVE_STUBS["marketing_copy"])
    p = serve.payload(stub)
    assert p["coverage"]["n_applicable"] == eng.analyze_coverage(idx, serve._norm(stub))["n_applicable"]
    assert [s["phase"] for s in p["workflow"]["steps"]] == \
        [s["phase"] for s in eng.analyze_workflow(idx, serve._norm(stub))["steps"]]


def test_norm_accepts_partial_stub():
    n = serve._norm({"modality": "text"})
    assert n["uses_patterns"] == [] and n["modality"] == "text"
