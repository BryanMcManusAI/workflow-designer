"""The swappable-index mechanism that makes the two-track deployment a zero-fork config change:
the same engine reads a different corpus via a path arg or the WD_INDEX env var. The internal corpus
itself is never in this repo — these tests just prove the engine will read an alternate one.
"""
import json

import engine


def test_load_index_accepts_a_path(tmp_path, idx):
    alt = tmp_path / "alt.json"
    trimmed = {"cards": dict(list(idx["cards"].items())[:3]),
               "patterns": idx["patterns"], "principles": idx.get("principles", {})}
    alt.write_text(json.dumps(trimmed))
    loaded = engine.load_index(str(alt))
    assert len(loaded["cards"]) == 3
    # the default committed index is untouched
    assert len(engine.load_index()["cards"]) == len(idx["cards"])


def test_load_index_honors_wd_index_env(tmp_path, monkeypatch):
    alt = tmp_path / "internal.json"
    alt.write_text(json.dumps({"cards": {}, "patterns": {}, "principles": {}}))
    monkeypatch.setenv("WD_INDEX", str(alt))
    assert engine.load_index()["cards"] == {}
    monkeypatch.delenv("WD_INDEX")
    assert engine.load_index()["cards"], "default restored once WD_INDEX is unset"


def test_build_corpus_refuses_in_repo_paths():
    """The clean-room guard: internal output may not be written inside the public repo."""
    import build_corpus
    assert build_corpus._in_repo(build_corpus.ROOT + "/drafts/x.yaml")
    assert not build_corpus._in_repo("/tmp/wd-internal/index.json")
