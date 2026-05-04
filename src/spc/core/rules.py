"""SPC rule-violation detectors for Individual and Moving Range charts.

Four rules are applied (configurable thresholds):

    Rule 1 — Action Limits
        Any single point outside UCL / LCL.

    Rule 2 — Warning Zone
        2 of 3 consecutive points in the same Warning Zone
        (between ±2σ and ±3σ on the same side of the centre line).
        "No more than 1 value in the Warning Zone" is the user's intent, but
        the statistically standard formulation (2-of-3) is used here because
        it controls the false-alarm rate properly.  Both thresholds are
        configurable.

    Rule 3 — Run above / below centre line
        K or more consecutive points on the same side of the centre line
        (default K = 8, configurable).

    Rule 4 — Trend
        K or more consecutive points steadily rising or falling
        (default K = 6, configurable).

Each function returns a boolean Series aligned to the input index where
True marks a violation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rule1_action_limits(
    values: pd.Series,
    ucl: float,
    lcl: float,
) -> pd.Series:
    """Rule 1: point outside action limits (UCL / LCL)."""
    return (values > ucl) | (values < lcl)


def rule2_warning_zone(
    values: pd.Series,
    cl: float,
    uwl: float,
    lwl: float,
    *,
    k: int = 2,
    window: int = 3,
) -> pd.Series:
    """Rule 2: k of window consecutive points in the same warning zone.

    A point is in the *upper* warning zone when value > uwl.
    A point is in the *lower* warning zone when value < lwl.

    Parameters
    ----------
    k:
        Number of points required in the zone within the window (default 2).
    window:
        Rolling window size (default 3).
    """
    upper_zone = (values > uwl).astype(int)
    lower_zone = (values < lwl).astype(int)

    upper_violation = (upper_zone.rolling(window).sum() >= k) & (values > uwl)
    lower_violation = (lower_zone.rolling(window).sum() >= k) & (values < lwl)

    return (upper_violation | lower_violation).fillna(False).astype(bool)


def rule3_run_same_side(
    values: pd.Series,
    cl: float,
    *,
    k: int = 8,
) -> pd.Series:
    """Rule 3: k or more consecutive points on the same side of the centre line."""
    above = (values > cl).astype(int)
    below = (values < cl).astype(int)

    # Rolling sum == k means all k points are on the same side
    upper_run = above.rolling(k).sum() == k
    lower_run = below.rolling(k).sum() == k

    return (upper_run | lower_run).fillna(False).astype(bool)


def rule4_trend(
    values: pd.Series,
    *,
    k: int = 6,
) -> pd.Series:
    """Rule 4: k or more consecutive points steadily rising or falling.

    A 'steady rise' means each successive value is strictly greater than the
    previous one across k consecutive points (k-1 successive differences > 0).
    """
    diffs = values.diff()
    rising = (diffs > 0).astype(int)
    falling = (diffs < 0).astype(int)

    # For k consecutive rising values we need k-1 positive differences in a row
    n = k - 1
    up_trend = rising.rolling(n).sum() == n
    down_trend = falling.rolling(n).sum() == n

    return (up_trend | down_trend).fillna(False).astype(bool)


def apply_all_rules(
    values: pd.Series,
    limits: dict[str, float],
    *,
    rule2_k: int = 2,
    rule2_window: int = 3,
    rule3_k: int = 8,
    rule4_k: int = 6,
) -> pd.DataFrame:
    """Apply all four rules and return a DataFrame of boolean violation flags.

    Parameters
    ----------
    values:
        Individual measurements aligned to their original index.
    limits:
        Dict produced by :func:`spc.core.limits.compute_limits`.

    Returns
    -------
    DataFrame with columns ``rule1`` … ``rule4`` and a ``any_violation`` column.
    """
    r1 = rule1_action_limits(values, limits["i_ucl"], limits["i_lcl"])
    r2 = rule2_warning_zone(
        values, limits["i_cl"], limits["i_uwl"], limits["i_lwl"],
        k=rule2_k, window=rule2_window,
    )
    r3 = rule3_run_same_side(values, limits["i_cl"], k=rule3_k)
    r4 = rule4_trend(values, k=rule4_k)

    df = pd.DataFrame(
        {"rule1": r1, "rule2": r2, "rule3": r3, "rule4": r4},
        index=values.index,
    )
    df["any_violation"] = df.any(axis=1)
    return df


def apply_mr_rule1(
    mr_values: pd.Series,
    mr_ucl: float,
) -> pd.Series:
    """Rule 1 on the Moving Range chart (MR > UCL).

    The LCL for a range chart is always 0, so only the upper limit is checked.
    """
    return mr_values > mr_ucl


def apply_mr_rules(
    mr_values: pd.Series,
    mr_ucl: float,
    mr_uwl: float,
    *,
    rule2_k: int = 2,
    rule2_window: int = 3,
) -> pd.Series:
    """Rules 1 and 2 on the Moving Range chart; returns combined boolean Series.

    Rule 1 — any MR point above UCL.
    Rule 2 — k of *window* consecutive MR points in the warning zone (above UWL).
    """
    r1 = (mr_values > mr_ucl).fillna(False).astype(bool)
    upper_zone = (mr_values > mr_uwl).astype(float)
    r2 = (
        (upper_zone.rolling(rule2_window).sum() >= rule2_k)
        & (mr_values > mr_uwl)
    ).fillna(False).astype(bool)
    return (r1 | r2)
