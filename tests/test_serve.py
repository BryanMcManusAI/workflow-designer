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


def test_preloaded_stub_reaches_the_page(monkeypatch):
    """serve --stub: the bridged retrospective stub must survive _norm (observed_failures
    intact) and ride the meta payload so the page can open pre-populated on the brief."""
    import serve as srv
    bridged = {
        "goal": "Rebuild the catalog workflow so last quarter's defects do not recur",
        "modality": "text", "task_structure": "extraction", "annotator_structure": "crowd",
        "high_cost_signatures": ["drift", "sampling_frame"],
        "observed_failures": [{"signature": "drift", "description": "week-6 definition change",
                               "source": "retrospective:catalog (Q3 2025)"}],
        "source_diagnosis": "catalog",
    }
    monkeypatch.setattr(srv, "PRELOAD", srv._norm(bridged))
    m = srv.meta()
    pre = m["preloaded_stub"]
    assert pre["observed_failures"][0]["signature"] == "drift", \
        "_norm must carry observed failures through, not coerce or drop them"
    assert pre["source_diagnosis"] == "catalog"
    assert pre["high_cost_signatures"] == ["drift", "sampling_frame"]
    # and the default meta (no preload) stays None
    monkeypatch.setattr(srv, "PRELOAD", None)
    assert srv.meta()["preloaded_stub"] is None
