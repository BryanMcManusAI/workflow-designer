"""Shared fixtures for the Workflow Designer test suite.

The engine reads its committed engine/index.json regardless of cwd (paths are resolved relative
to engine.py), so tests just need engine/ on sys.path. No network, no API key.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT, "engine")
sys.path.insert(0, ENGINE_DIR)

import engine  # noqa: E402  (after sys.path mutation)


# Canonical failure-signature vocabulary (SCHEMA.md). `instrumentation-bug` is the one allowed
# literal that is deliberately NOT a signature (a code defect; never drives far-analogy).
SIGNATURE_VOCAB = {
    "confounded", "unanchored", "self_affinity", "inflation", "underpowered", "priming",
    "sampling_frame", "drift", "bottleneck", "over_specification", "under_specification",
    "label_leakage", "class_imbalance", "gaming", "assumption_laundering",
}

# Controlled qa_mechanism vocabulary (SCHEMA.md) — underscored, no hyphens.
QA_VOCAB = {
    "gold_honeypots", "agreement", "qualification_calibration", "adjudication", "audit_sampling",
    "consensus_threshold", "guideline_freeze", "input_pooling", "order_randomization",
    "execution_check",
}


def make_stub(**kw):
    """Build a stub dict normalized the way engine.load_stub() guarantees (the 4 list keys)."""
    stub = {
        "goal": kw.get("goal", ""),
        "modality": kw.get("modality"),
        "task_structure": kw.get("task_structure"),
        "annotator_structure": kw.get("annotator_structure"),
        "process_mode": kw.get("process_mode"),
    }
    for k in ("qa_mechanism", "uses_patterns", "addressed_signatures", "failure_signatures",
              "high_cost_signatures", "tolerable_signatures"):
        v = kw.get(k, [])
        stub[k] = [v] if isinstance(v, str) else list(v or [])
    return stub


# Representative stubs reused across tests + goldens (mirror the portfolio examples + the default).
REPRESENTATIVE_STUBS = {
    "marketing_copy": make_stub(
        goal="Evaluate AI-generated marketing copy at scale with an LLM judge",
        modality="text", task_structure="rubric_rating", annotator_structure="model_as_annotator",
        uses_patterns=["human-gold-anchor"]),
    "image_preference": make_stub(
        goal="Collect pairwise preference data for an image-generation reward model",
        modality="image", task_structure="preference_ranking", annotator_structure="crowd",
        qa_mechanism=["gold_honeypots", "agreement"],
        uses_patterns=["multi-annotator-aggregate", "gold-honeypots"]),
    "code_eval": make_stub(
        goal="Build an eval set that measures whether generated code is functionally correct",
        modality="code", task_structure="freeform_generation", annotator_structure="expert",
        qa_mechanism=["execution_check"], uses_patterns=["execution-verification"]),
}


@pytest.fixture(scope="session")
def idx():
    return engine.load_index()


@pytest.fixture(scope="session")
def eng():
    return engine


@pytest.fixture
def stubs():
    # fresh copies so a test mutating a stub can't leak into another
    return {k: dict(v) for k, v in REPRESENTATIVE_STUBS.items()}
