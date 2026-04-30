"""Unit tests for SPC core modules."""

import numpy as np
import pandas as pd
import pytest

from spc.core.limits import compute_limits, compute_moving_range, D2
from spc.core.rules import (
    rule1_action_limits,
    rule2_warning_zone,
    rule3_run_same_side,
    rule4_trend,
    apply_all_rules,
)
from spc.core.capability import compute_capability
from spc.core.phase_i import run_phase_i_pass


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def stable_series():
    """50-point in-control series (mean=100, σ≈2)."""
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(100, 2, 50), name="value")


@pytest.fixture
def series_with_outlier(stable_series):
    s = stable_series.copy()
    s.iloc[25] = 120  # clear Rule 1 violation
    return s


# ─── Limits ──────────────────────────────────────────────────────────────────

class TestLimits:
    def test_basic_structure(self, stable_series):
        lim = compute_limits(stable_series)
        assert set(lim.keys()) == {
            "x_bar", "mr_bar", "sigma_within",
            "i_ucl", "i_uwl", "i_cl", "i_lwl", "i_lcl",
            "mr_ucl", "mr_cl",
        }

    def test_symmetry(self, stable_series):
        lim = compute_limits(stable_series)
        assert pytest.approx(lim["i_ucl"] - lim["i_cl"], rel=1e-9) == lim["i_cl"] - lim["i_lcl"]
        assert pytest.approx(lim["i_uwl"] - lim["i_cl"], rel=1e-9) == lim["i_cl"] - lim["i_lwl"]

    def test_sigma_formula(self, stable_series):
        mr = compute_moving_range(stable_series).dropna()
        expected_sigma = mr.mean() / D2
        lim = compute_limits(stable_series)
        assert pytest.approx(lim["sigma_within"], rel=1e-9) == expected_sigma

    def test_ucl_is_3sigma_above_mean(self, stable_series):
        lim = compute_limits(stable_series)
        assert pytest.approx(lim["i_ucl"], rel=1e-9) == lim["i_cl"] + 3 * lim["sigma_within"]

    def test_too_few_values_raises(self):
        with pytest.raises(ValueError, match="At least 2"):
            compute_limits(pd.Series([1.0]))

    def test_nan_ignored(self):
        s = pd.Series([1.0, np.nan, 2.0, 3.0, 4.0])
        lim = compute_limits(s)
        assert np.isfinite(lim["x_bar"])


# ─── Rules ───────────────────────────────────────────────────────────────────

class TestRule1:
    def test_detects_high_outlier(self):
        s = pd.Series([10.0] * 20)
        # UCL = 10 + 3σ; inject a point far above
        s.iloc[10] = 50.0
        lim = compute_limits(s)
        flags = rule1_action_limits(s, lim["i_ucl"], lim["i_lcl"])
        assert flags.iloc[10]

    def test_no_false_positives_stable(self, stable_series):
        lim = compute_limits(stable_series)
        flags = rule1_action_limits(stable_series, lim["i_ucl"], lim["i_lcl"])
        # Stable series should have very few (ideally zero) violations
        assert flags.sum() <= 2


class TestRule2:
    def test_detects_two_of_three_in_zone(self):
        lim = {"i_cl": 0.0, "i_uwl": 2.0, "i_lwl": -2.0}
        # 2 out of 3 consecutive above uwl
        s = pd.Series([0, 0, 3.0, 3.0, 0, 0, 0, 0, 0, 0])
        flags = rule2_warning_zone(s, lim["i_cl"], lim["i_uwl"], lim["i_lwl"])
        assert flags.iloc[3]  # window ending at index 3 has 2 of 3 above uwl


class TestRule3:
    def test_detects_8_above(self):
        s = pd.Series([1.0] * 8 + [0.0] * 5)  # 8 above mean 0
        flags = rule3_run_same_side(s, cl=0.0, k=8)
        assert flags.iloc[7]

    def test_no_flag_for_7(self):
        s = pd.Series([1.0] * 7 + [0.0] * 5)
        flags = rule3_run_same_side(s, cl=0.0, k=8)
        assert not flags.any()


class TestRule4:
    def test_detects_6_rising(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0] + [5.0] * 5)
        flags = rule4_trend(s, k=6)
        assert flags.iloc[5]  # 6 consecutive rising values detected

    def test_no_flag_for_5(self):
        # 5 rising points → 4 successive diffs > 0; k=6 requires 5 diffs → no flag
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0] + [4.0] * 5)
        flags = rule4_trend(s, k=6)
        assert not flags.any()


# ─── Capability ───────────────────────────────────────────────────────────────

class TestCapability:
    def test_cp_formula(self, stable_series):
        lim = compute_limits(stable_series)
        usl, lsl = 106.0, 94.0
        cap = compute_capability(stable_series, usl, lsl, mr_bar=lim["mr_bar"])
        expected_cp = (usl - lsl) / (6 * lim["sigma_within"])
        assert pytest.approx(cap["cp"], rel=1e-6) == expected_cp

    def test_rpi_equals_cp(self, stable_series):
        cap = compute_capability(stable_series, 106.0, 94.0)
        assert pytest.approx(cap["rpi"], rel=1e-9) == cap["cp"]

    def test_cpk_le_cp(self, stable_series):
        cap = compute_capability(stable_series, 106.0, 94.0)
        assert cap["cpk"] <= cap["cp"] + 1e-9

    def test_usl_le_lsl_raises(self, stable_series):
        with pytest.raises(ValueError, match="USL must be strictly greater"):
            compute_capability(stable_series, usl=90.0, lsl=100.0)


# ─── Phase I engine ───────────────────────────────────────────────────────────

class TestPhaseI:
    def test_no_violations_on_perfectly_stable_data(self):
        # Perfectly alternating values at ±0.3σ: no runs, no trends,
        # never near warning zone. Rule violations require cause (Oakland Ch. 4-5).
        mean, s = 100.0, 2.0
        vals = [mean + (0.3 * s if i % 2 == 0 else -0.3 * s) for i in range(30)]
        result = run_phase_i_pass(pd.Series(vals, name="value"))
        assert not result.any_violations

    def test_flags_obvious_outlier(self, series_with_outlier):
        result = run_phase_i_pass(series_with_outlier)
        assert result.any_violations
        assert 25 in result.flagged_integer_indices

    def test_original_labels_length_matches_values(self, stable_series):
        result = run_phase_i_pass(stable_series)
        assert len(result.original_labels) == len(result.values)

    def test_original_ilocs_length_matches_values(self, stable_series):
        result = run_phase_i_pass(stable_series)
        assert len(result.original_ilocs) == len(result.values)

    def test_nan_excluded_from_pass(self):
        s = pd.Series([1.0, np.nan, 2.0, 3.0, 4.0, 5.0])
        result = run_phase_i_pass(s)
        assert result.n_original == 5

    def test_too_few_raises(self):
        with pytest.raises(ValueError, match="At least 2"):
            run_phase_i_pass(pd.Series([1.0]))

    def test_rule_config_stored(self, stable_series):
        result = run_phase_i_pass(stable_series, rule3_k=10)
        assert result.rule_config["rule3_k"] == 10

    def test_flagged_indices_valid_positions(self, series_with_outlier):
        result = run_phase_i_pass(series_with_outlier)
        for idx in result.flagged_integer_indices:
            assert 0 <= idx < result.n_original

    def test_date_string_index_preserved(self):
        import pandas as pd
        dates = pd.date_range("2024-01-01", periods=30, freq="D").strftime("%Y-%m-%d")
        rng = np.random.default_rng(42)
        s = pd.Series(rng.normal(100, 2, 30), index=dates, name="value")
        result = run_phase_i_pass(s)
        assert len(result.original_labels) == len(result.values)
        # All original labels should be date strings
        assert all(isinstance(lbl, str) for lbl in result.original_labels)

