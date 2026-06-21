"""Integrity of the compiled engine/index.json — the graph the engine actually reads.

These guard the corpus the way build_index can't: that every cross-reference resolves and every
signature is in the controlled vocabulary, so a typo in a card never silently breaks far-analogy.
"""
from conftest import SIGNATURE_VOCAB, QA_VOCAB

# A code defect may be logged on a card's failure_modes with this literal; it is NOT a signature.
ALLOWED_FM_LITERALS = SIGNATURE_VOCAB | {"instrumentation-bug"}


def test_card_patterns_resolve(idx):
    pids = set(idx["patterns"])
    for cid, c in idx["cards"].items():
        for pid in c["uses_patterns"]:
            assert pid in pids, f"{cid} uses unknown pattern {pid!r}"


def test_pattern_exemplars_resolve(idx):
    cids = set(idx["cards"])
    for pid, p in idx["patterns"].items():
        for cid in p["exemplified_by"]:
            assert cid in cids, f"{pid} exemplified_by unknown card {cid!r}"


def test_pattern_links_resolve(idx):
    pids = set(idx["patterns"])
    for pid, p in idx["patterns"].items():
        for other in p.get("pairs_with", []) + p.get("conflicts_with", []):
            assert other in pids, f"{pid} links unknown pattern {other!r}"


def test_card_signatures_in_vocab(idx):
    for cid, c in idx["cards"].items():
        for sig in c["failure_signatures"]:
            assert sig in SIGNATURE_VOCAB, f"{cid} has unknown signature {sig!r}"


def test_card_qa_mechanisms_in_vocab(idx):
    # Guards the hyphen/underscore class of typo (order-randomization vs order_randomization).
    for cid, c in idx["cards"].items():
        for qa in c["qa_mechanism"]:
            assert qa in QA_VOCAB, f"{cid} has unknown qa_mechanism {qa!r}"


def test_pattern_defends_in_vocab(idx):
    for pid, p in idx["patterns"].items():
        for sig in p["defends"]:
            assert sig in SIGNATURE_VOCAB, f"{pid} defends unknown signature {sig!r}"


def test_failure_mode_signatures(idx):
    # The per-mode signature string is matched by startswith() in the engine; its leading token
    # must be a known signature (or the allowed instrumentation-bug literal).
    for cid, c in idx["cards"].items():
        for fm in c["failure_modes"]:
            base = fm["signature"].split()[0] if fm["signature"] else ""
            assert base in ALLOWED_FM_LITERALS, f"{cid} failure_mode signature {fm['signature']!r}"


def test_every_pattern_has_an_exemplar(idx):
    # The provenance ethos: a promoted pattern is grounded in >=1 real card.
    for pid, p in idx["patterns"].items():
        assert p["exemplified_by"], f"{pid} has no exemplifying card"


def test_every_pattern_declares_phase_and_play(idx):
    # Conventions/audit text is grounded in the corpus, not a hardcoded table: every pattern carries
    # its own phase + play in library.yaml so analyze_workflow never has to invent the instruction.
    valid = {"source", "qualify", "label", "resolve", "convention", "audit"}
    for pid, p in idx["patterns"].items():
        assert p.get("phase") in valid, f"{pid} has bad/absent phase {p.get('phase')!r}"
        assert p.get("play"), f"{pid} has no play instruction"
