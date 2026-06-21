"""The REPL drives the same engine; these check the adopt-loop behaves — adopting a pattern
shrinks the open-risk set and raises coverage — and that the session round-trips through save.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

import engine  # noqa: E402
import repl  # noqa: E402

from conftest import REPRESENTATIVE_STUBS  # noqa: E402


def _coverage_line(transcript):
    # the render shows "[####....] X/Y applicable risks defended (Z%)"
    for ln in transcript.splitlines():
        if "applicable risks defended" in ln:
            return ln
    return ""


def test_help_and_quit():
    out = repl.run(["help", "quit", "interrogate"])  # quit stops before interrogate
    assert "commands" in out
    assert "MODE 3" not in out  # everything after quit is skipped


def test_adopt_shrinks_open_and_raises_coverage(idx):
    stub = repl.default_stub()  # text / rubric_rating / model_as_annotator, no patterns
    # First interrogate to see the open risks, grab the top risk's defending pattern.
    res = engine.analyze_interrogate(idx, stub)
    top_sig = res["open"][0]["signature"]
    defender = res["open"][0]["patterns"][0]["id"]
    before_n = engine.analyze_coverage(idx, stub)["n_covered"]

    out = repl.run(["interrogate", f"adopt {defender}", "coverage"], stub=dict(stub), idx=idx)
    assert f"adopted `{defender}`" in out
    # after adopting, coverage must have risen and the closed signature must be covered
    after = engine.analyze_coverage(idx, {**stub, "uses_patterns": [defender]})
    assert after["n_covered"] > before_n
    assert top_sig in after["covered"]


def test_adopt_by_number(idx):
    stub = repl.default_stub()
    out = repl.run(["interrogate", "adopt 1", "status"], stub=dict(stub), idx=idx)
    assert "adopted" in out
    assert "applicable risks defended" in out


def test_unknown_pattern_is_rejected(idx):
    out = repl.run(["adopt not-a-real-pattern"], idx=idx)
    assert "unknown pattern" in out


def test_set_validates_against_vocab(idx):
    out = repl.run(["set modality klingon", "set modality image", "status"], idx=idx)
    assert "not a known modality" in out
    assert "set modality = image" in out


def test_save_roundtrips_through_load_stub(idx, tmp_path):
    stub = repl.default_stub()
    path = tmp_path / "session.yaml"
    repl.run(["adopt human-gold-anchor", f"save {path}"], stub=dict(stub), idx=idx)
    assert path.exists()
    reloaded = engine.load_stub(str(path))
    assert reloaded["modality"] == stub["modality"]
    assert "human-gold-anchor" in reloaded["uses_patterns"]


def test_workflow_command_outputs_all_sections(idx):
    out = repl.run(["workflow"], stub=dict(REPRESENTATIVE_STUBS["image_preference"]), idx=idx)
    for section in ("ASSEMBLED SAMPLE WORKFLOW", "LABELING STEPS",
                    "FIELDS the annotator fills per item", "SUGGESTED CONVENTIONS", "AUDIT STRATEGY"):
        assert section in out, section
    assert "[have]" in out or "[ADD]" in out


def test_creative_moves_run_clean(idx):
    # shift / flip / transplant / compare / cookbook / show all execute without error
    cmds = ["shift video", "flip annotator_structure crowd", "substitute crowd",
            "transplant", "compare preference_ranking", "cookbook domain",
            "browse patterns", "show judge-eval-study", "vocab"]
    out = repl.run(cmds, stub=dict(REPRESENTATIVE_STUBS["marketing_copy"]), idx=idx)
    assert "MODALITY-SHIFT to: video" in out
    assert "FLIP: annotator_structure -> crowd" in out
    assert "ACTOR-SUBSTITUTE" in out
    assert "COMPARE" in out
    assert "unknown command" not in out
