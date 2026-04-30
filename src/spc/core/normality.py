"""Normality test helper used as a pre-check before SPC limit interpretation.

Shewhart charts assume near-normality.  We use the Shapiro-Wilk test for
n ≤ 5000 (its valid range) and Anderson-Darling otherwise.  The result is
advisory — it does not block the analysis but is surfaced in the UI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def normality_check(values: pd.Series) -> dict:
    """Run a normality test and return a result dictionary.

    Returns
    -------
    dict with keys:
        test_name, statistic, p_value, is_normal (at α=0.05), n, warning_message
    """
    clean = values.dropna()
    n = len(clean)

    if n < 3:
        return {
            "test_name": "N/A",
            "statistic": None,
            "p_value": None,
            "is_normal": None,
            "n": n,
            "warning_message": "Too few observations for a normality test (need ≥ 3).",
        }

    if n <= 5000:
        stat, p = stats.shapiro(clean)
        test_name = "Shapiro-Wilk"
    else:
        result = stats.anderson(clean, dist="norm")
        # Use the 5 % critical value (index 2)
        stat = float(result.statistic)
        p = None  # Anderson-Darling does not return a p-value directly
        critical = result.critical_values[2]
        is_normal = stat < critical
        return {
            "test_name": "Anderson-Darling",
            "statistic": stat,
            "p_value": None,
            "is_normal": is_normal,
            "n": n,
            "warning_message": (
                "" if is_normal
                else "Anderson-Darling test suggests non-normality (α=0.05). "
                     "Interpret control limits with caution."
            ),
        }

    is_normal = p > 0.05
    return {
        "test_name": test_name,
        "statistic": float(stat),
        "p_value": float(p),
        "is_normal": is_normal,
        "n": n,
        "warning_message": (
            "" if is_normal
            else f"Shapiro-Wilk p = {p:.4f} < 0.05: non-normality detected. "
                 "Interpret control limits with caution."
        ),
    }
