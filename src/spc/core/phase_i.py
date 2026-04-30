"""Phase I SPC engine — analyst-driven two-pass evaluation.

Oakland's principle (J.S. Oakland, *Statistical Process Control*, Ch. 4–5;
Wheeler, *Understanding SPC*):

    * Only common-cause variation should remain in the Phase I baseline.
    * A point should be removed ONLY when an assignable cause is identified.
    * The analyst — not the algorithm — decides whether a flagged point is a
      genuine special cause or natural common-cause variation.

This module exposes a single pure function :func:`run_phase_i_pass` that
evaluates one pass of an I-MR SPC study and returns all violations for
analyst review.  The two-pass human-in-the-loop workflow lives in the UI
layer (pages/02_Phase_I.py):

    Pass 1  →  analyst reviews flags, documents assignable causes, selects
               which points (if any) to remove.
    Pass 2  →  (only if removals were made) re-evaluates the cleaned data.
               The result of Pass 2 is the certified baseline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from spc.core.limits import compute_limits, compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1


@dataclass
class PassResult:
    """Result of one Phase I evaluation pass.

    All row references use a clean integer RangeIndex (0 … n-1).
    The mapping back to original labels (dates, batch IDs, …) is stored in
    ``original_labels``: ``original_labels[i]`` is the label for
    ``values.iloc[i]``.  ``original_ilocs[i]`` is the corresponding
    positional index in the *input* Series (used for duplicate-safe removal).
    """

    values: pd.Series               # retained measurements, integer-indexed
    mr: pd.Series                   # moving range (first entry is NaN)
    limits: dict[str, float]
    individual_violations: pd.DataFrame  # rule1..rule4 + any_violation, integer-indexed
    mr_violations: pd.Series        # bool, integer-indexed (NaN → False)
    original_labels: pd.Index       # one label per row in values
    original_ilocs: np.ndarray      # iloc positions of each row in the input Series
    n_original: int                 # non-NaN count fed into this pass
    rule_config: dict[str, int]

    @property
    def any_violations(self) -> bool:
        """True if at least one flagged point exists (I or MR chart)."""
        return (
            bool(self.individual_violations["any_violation"].any())
            or bool(self.mr_violations.any())
        )

    @property
    def flagged_integer_indices(self) -> list[int]:
        """Sorted integer positions (into self.values) of all flagged points."""
        ind_np = self.individual_violations["any_violation"].to_numpy(dtype=bool)
        mr_np  = self.mr_violations.to_numpy(dtype=bool)
        combined = ind_np | mr_np
        return [int(i) for i, flag in zip(self.values.index, combined) if flag]


@dataclass
class PhaseIResult:
    """Final Phase I result stored for downstream pages.

    Built by the UI layer after the analyst has confirmed all decisions.
    """

    final_values: pd.Series         # integer-indexed clean retained values
    final_mr: pd.Series
    final_limits: dict[str, float]
    original_labels: pd.Index       # one label per row in final_values
    n_original: int
    n_final: int
    n_total_removed: int
    rule_config: dict[str, int]
    audit_log: pd.DataFrame         # all flagged points with analyst decisions
    n_passes: int                   # 1 or 2
    final_pass_has_violations: bool  # True if final pass still shows violations



def run_phase_i_pass(
    values: pd.Series,
    *,
    rule2_k: int = 2,
    rule2_window: int = 3,
    rule3_k: int = 8,
    rule4_k: int = 6,
) -> PassResult:
    """Evaluate one Phase I pass on the supplied measurements.

    This function is **pure**: it does not modify ``values`` and never
    decides which points to remove.  Removal decisions belong to the
    analyst, who must document an assignable cause for each removal before
    the baseline is finalised (Oakland, Ch. 4–5).

    Parameters
    ----------
    values:
        Time-ordered individual measurements.  NaN values are excluded.
        The original index (dates, IDs, …) is captured in the returned
        :class:`PassResult` for display purposes.

    Returns
    -------
    :class:`PassResult`
        Contains limits, violation flags, and the integer → original-label
        mapping.  Feed the result to the UI layer for analyst review.
    """
    rule_config = {
        "rule2_k": rule2_k,
        "rule2_window": rule2_window,
        "rule3_k": rule3_k,
        "rule4_k": rule4_k,
    }

    # Extract non-NaN values; record original labels and iloc positions for
    # each retained point; then reset to a plain RangeIndex so all downstream
    # operations (rules, limits) are unambiguous and index-type-agnostic.
    clean_mask_np = values.notna().to_numpy()
    original_labels: pd.Index = values.index[clean_mask_np]
    original_ilocs: np.ndarray = np.where(clean_mask_np)[0]
    clean = values.iloc[original_ilocs].reset_index(drop=True)
    n_original = len(clean)

    if n_original < 2:
        raise ValueError("At least 2 non-NaN observations are required.")

    limits = compute_limits(clean)
    mr = compute_moving_range(clean)

    ind_violations = apply_all_rules(
        clean, limits,
        rule2_k=rule2_k, rule2_window=rule2_window,
        rule3_k=rule3_k, rule4_k=rule4_k,
    )
    mr_violations = apply_mr_rule1(mr, limits["mr_ucl"]).fillna(False)

    return PassResult(
        values=clean,
        mr=mr,
        limits=limits,
        individual_violations=ind_violations,
        mr_violations=mr_violations,
        original_labels=original_labels,
        original_ilocs=original_ilocs,
        n_original=n_original,
        rule_config=rule_config,
    )
