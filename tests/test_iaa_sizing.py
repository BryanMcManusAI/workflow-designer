"""iaa_sizing: the two populations the planning rule rests on, pinned."""
import math

import pytest

import iaa_sizing as s


def test_zero_skill_at_98_percent_pass_rate():
    """Two coins at a 2% fail rate: raw agreement 0.9608 and AC1 0.959 look near perfect; kappa and
    fail agreement say there is no skill. This is why raw agreement is not the headline."""
    r = s.agreement_from_counts(*s.population_cells(0.02, 0.02, 0.02))
    assert abs(r["raw_agreement"] - 0.9608) < 1e-4
    assert abs(r["ac1"] - 0.959) < 1e-3
    assert abs(r["kappa"]) < 1e-9
    assert abs(r["fail_agreement_p_pos"] - 0.02) < 1e-9


def test_realistic_population():
    """2% fails, auditors catch 75% of them and fail 0.5% of good items: fail agreement about 0.567,
    kappa about 0.558, while raw agreement still reads 0.983."""
    r = s.agreement_from_counts(*s.population_cells(0.02, 0.75, 0.005))
    assert abs(r["fail_agreement_p_pos"] - 0.567) < 2e-3
    assert abs(r["kappa"] - 0.558) < 2e-3
    assert r["raw_agreement"] > 0.98


def test_counts_table_identities():
    r = s.agreement_from_counts(11, 4, 5, 980)
    assert r["n"] == 1000
    assert abs(r["fail_agreement_p_pos"] - 22 / 31) < 1e-9
    assert abs(r["bias_index"] - (-1 / 1000)) < 1e-12
    assert r["pass_agreement_p_neg"] > r["fail_agreement_p_pos"]


def test_p_pos_undefined_with_no_fails():
    r = s.agreement_from_counts(0, 0, 0, 100)
    assert math.isnan(r["fail_agreement_p_pos"])
    assert r["raw_agreement"] == 1.0


def test_overlap_sizing_counts_fails_not_items():
    o = s.overlap_for_fails(50, 0.02)
    assert o["random_items_needed"] == 2500
    o = s.overlap_for_fails(50, 0.02, catch=0.75, false_fail=0.005)
    # fails per item = 0.02*0.75 + 0.98*0.005 = 0.0199
    assert o["random_items_needed"] == math.ceil(50 / 0.0199)
    o = s.overlap_for_fails(50, 0.02, catch=0.75, false_fail=0.005, enriched_share=0.17, enriched_fail_share=0.60)
    assert o["enriched_items_needed"] < o["random_items_needed"]
    assert abs(o["enriched_fail_rate"] - 0.02 * 0.60 / 0.17) < 1e-9


def test_expected_fails():
    assert abs(s.expected_fails(2000, 0.02) - 40) < 1e-9


def test_bootstrap_brackets_the_point():
    ci = s.bootstrap_ci(11, 4, 5, 980, reps=300, seed=1)
    r = s.agreement_from_counts(11, 4, 5, 980)
    lo, hi = ci["p_pos_ci"]
    assert lo <= r["fail_agreement_p_pos"] <= hi
    assert ci["p_pos_undefined_share"] == 0


def test_bootstrap_flags_tables_too_small_to_read():
    ci = s.bootstrap_ci(1, 1, 0, 98, reps=200, seed=2)
    assert ci["p_pos_undefined_share"] > 0


def test_cli_runs(capsys):
    assert s.main(["size", "--pass-rate", "0.98", "--target-fails", "50", "--catch", "0.75"]) == 0
    out = capsys.readouterr().out
    assert "raw agreement 0.9608" in out and "random stratum" in out
    assert s.main(["counts", "--a", "11", "--b", "4", "--c", "5", "--d", "980", "--reps", "100"]) == 0
    assert "fail agreement p_pos" in capsys.readouterr().out


@pytest.mark.parametrize("cells", [(0, 0, 0, 0)])
def test_empty_table_rejected(cells):
    with pytest.raises(ValueError):
        s.agreement_from_counts(*cells)
