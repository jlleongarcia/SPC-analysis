"""Phase I iterative SPC engine.

Algorithm
─────────
    1. Start with the full dataset (all non-NaN values).
    2. Compute I-MR control limits from the current retained set.
    3. Apply all four SPC rules to the Individual chart.
    4. Apply Rule 1 to the Moving Range chart.
    5. Identify all flagged indices.
    6. If any violations exist AND max_iterations not reached:
           • Record the iteration snapshot (limits, violations, removed points).
           • Remove flagged points from the retained set.
           • Go to step 2.
    7. If no violations, the process is in statistical control.
       Compute final capability indices and return the full audit trail.

Design decisions for enterprise use
────────────────────────────────────
    • Every removed point is logged with the specific rule(s) it violated.
    • Iterations are capped at ``max_iterations`` to prevent over-pruning.
    • A ``removal_log`` DataFrame provides the audit trail required by
      quality management systems (ISO 9001, IATF 16949, GMP, etc.).
    • The engine never mutates the original data — it returns new objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from spc.core.limits import compute_limits, compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1


@dataclass
class IterationSnapshot:
    """Stores the state of one Phase I iteration."""

    iteration: int
    retained_indices: list
    limits: dict[str, float]
    individual_violations: pd.DataFrame   # rule1…rule4 + any_violation
    mr_violations: pd.Series
    removed_indices: list                 # removed *after* this iteration
    n_retained: int
    n_removed_this_iter: int


@dataclass
class PhaseIResult:
    """Full result of the Phase I iterative study."""

    converged: bool                        # True if no violations at end
    iterations: list[IterationSnapshot]
    final_limits: dict[str, float]
    final_values: pd.Series               # clean retained measurements
    final_mr: pd.Series
    removal_log: pd.DataFrame             # full audit trail
    n_original: int
    n_final: int
    n_total_removed: int
    rule_config: dict[str, int]


def run_phase_i(
    values: pd.Series,
    *,
    max_iterations: int = 10,
    rule2_k: int = 2,
    rule2_window: int = 3,
    rule3_k: int = 8,
    rule4_k: int = 6,
) -> PhaseIResult:
    """Execute the Phase I iterative SPC study on individual measurements.

    Parameters
    ----------
    values:
        Full time-ordered series of individual measurements (NaN allowed;
        they are excluded from computation but their index positions are kept).
    max_iterations:
        Safety cap on the number of removal iterations (default 10).
    rule2_k, rule2_window, rule3_k, rule4_k:
        Rule threshold overrides — see :mod:`spc.core.rules` for details.

    Returns
    -------
    :class:`PhaseIResult`
    """
    rule_config = {
        "rule2_k": rule2_k,
        "rule2_window": rule2_window,
        "rule3_k": rule3_k,
        "rule4_k": rule4_k,
    }

    original_values = values.copy()
    n_original = int(original_values.notna().sum())

    retained = original_values.dropna().copy()
    iterations: list[IterationSnapshot] = []
    removal_rows: list[dict] = []

    for iteration in range(1, max_iterations + 1):
        if len(retained) < 2:
            break

        limits = compute_limits(retained)
        mr = compute_moving_range(retained)

        ind_violations = apply_all_rules(
            retained, limits,
            rule2_k=rule2_k, rule2_window=rule2_window,
            rule3_k=rule3_k, rule4_k=rule4_k,
        )
        mr_violations = apply_mr_rule1(mr, limits["mr_ucl"])

        # Union of all flagged indices (individual OR MR rule 1)
        flagged_individual = ind_violations.index[ind_violations["any_violation"]]
        flagged_mr = mr_violations.index[mr_violations.fillna(False)]
        flagged_all = flagged_individual.union(flagged_mr)

        snap = IterationSnapshot(
            iteration=iteration,
            retained_indices=list(retained.index),
            limits=limits,
            individual_violations=ind_violations,
            mr_violations=mr_violations.fillna(False),
            removed_indices=list(flagged_all),
            n_retained=len(retained),
            n_removed_this_iter=len(flagged_all),
        )
        iterations.append(snap)

        if len(flagged_all) == 0:
            # No violations — process is in control
            final_limits = limits
            final_values = retained.copy()
            final_mr = compute_moving_range(final_values)
            return PhaseIResult(
                converged=True,
                iterations=iterations,
                final_limits=final_limits,
                final_values=final_values,
                final_mr=final_mr,
                removal_log=_build_removal_log(removal_rows),
                n_original=n_original,
                n_final=len(final_values),
                n_total_removed=n_original - len(final_values),
                rule_config=rule_config,
            )

        # Build audit-trail rows before removing
        for idx in flagged_all:
            rules_fired = []
            if idx in flagged_individual:
                row = ind_violations.loc[idx]
                for r in ["rule1", "rule2", "rule3", "rule4"]:
                    if row[r]:
                        rules_fired.append(r)
            if idx in flagged_mr:
                rules_fired.append("mr_rule1")
            removal_rows.append(
                {
                    "iteration": iteration,
                    "index": idx,
                    "value": float(retained.loc[idx]),
                    "rules_violated": ", ".join(rules_fired),
                    "x_bar_at_removal": limits["i_cl"],
                    "ucl_at_removal": limits["i_ucl"],
                    "lcl_at_removal": limits["i_lcl"],
                }
            )

        retained = retained.drop(index=flagged_all)

    # Loop ended without convergence (hit max_iterations or insufficient data)
    limits = compute_limits(retained) if len(retained) >= 2 else {}
    final_values = retained.copy()
    final_mr = compute_moving_range(final_values) if len(final_values) >= 2 else pd.Series(dtype=float)

    return PhaseIResult(
        converged=False,
        iterations=iterations,
        final_limits=limits,
        final_values=final_values,
        final_mr=final_mr,
        removal_log=_build_removal_log(removal_rows),
        n_original=n_original,
        n_final=len(final_values),
        n_total_removed=n_original - len(final_values),
        rule_config=rule_config,
    )


def _build_removal_log(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["iteration", "index", "value", "rules_violated",
                     "x_bar_at_removal", "ucl_at_removal", "lcl_at_removal"]
        )
    return pd.DataFrame(rows).set_index("index")
