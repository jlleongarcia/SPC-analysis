"""Core SPC limit calculations for Individual (I) and Moving Range (MR) charts.

Individuals charts use the d2 unbiasing constant where d2 = 1.128 for a
moving range of span 2. All control-limit formulas follow the standard
Shewhart approach derived from the average moving range (MR-bar).

Control lines
─────────────
    Individual chart
        CL  = X-bar
        UCL = X-bar + 3 * (MR-bar / d2)
        LCL = X-bar - 3 * (MR-bar / d2)

    Warning lines  (±2σ, i.e. two-thirds of the way to the action limits)
        UWL = X-bar + 2 * (MR-bar / d2)
        LWL = X-bar - 2 * (MR-bar / d2)

    Moving-range chart
        CL  = MR-bar
        UCL = D4 * MR-bar   (D4 = 3.267 for n=2)
        LCL = 0             (LCL is always 0 for n=2)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Unbiasing constants for span-2 moving range ─────────────────────────────
D2: float = 1.128   # E(MR/σ) for n=2
D4: float = 3.267   # UCL factor for MR chart (n=2)


def compute_moving_range(values: pd.Series) -> pd.Series:
    """Return the absolute successive differences (span-2 moving range)."""
    return values.diff().abs()


def compute_limits(
    values: pd.Series,
    *,
    mr_mask: "np.ndarray | None" = None,
) -> dict[str, float]:
    """Compute all control lines for an I-MR chart pair.

    Parameters
    ----------
    values:
        Ordered series of individual measurements.  NaN entries are excluded
        before computation.
    mr_mask:
        Optional boolean array of length ``len(values.dropna())``.  When
        provided, only moving ranges where ``mr_mask[j]`` is *True* are
        included in the MR-bar computation.  Use this to exclude "bridging"
        MRs — i.e. MRs computed between observations that were not originally
        adjacent because one or more points were removed between them.

    Returns
    -------
    dict with keys:
        x_bar, mr_bar, sigma_within,
        i_ucl, i_uwl, i_cl, i_lwl, i_lcl,
        mr_ucl, mr_cl
    """
    clean = values.dropna()
    if len(clean) < 2:
        raise ValueError("At least 2 non-NaN values are required to compute limits.")

    mr = compute_moving_range(clean)

    if mr_mask is not None:
        mask = np.asarray(mr_mask, dtype=bool)
        mr_for_bar = mr[mask & mr.notna()]
        if len(mr_for_bar) == 0:
            mr_for_bar = mr.dropna()   # fallback: use all if mask excludes everything
    else:
        mr_for_bar = mr.dropna()

    x_bar: float = float(clean.mean())
    mr_bar: float = float(mr_for_bar.mean())
    sigma: float = mr_bar / D2  # within-subgroup (short-term) std dev estimate

    return {
        "x_bar": x_bar,
        "mr_bar": mr_bar,
        "sigma_within": sigma,
        # Individual chart lines
        "i_ucl": x_bar + 3 * sigma,
        "i_uwl": x_bar + 2 * sigma,
        "i_cl": x_bar,
        "i_lwl": x_bar - 2 * sigma,
        "i_lcl": x_bar - 3 * sigma,
        # MR chart lines  (UWL = 2/3 of the way from CL to UCL)
        "mr_ucl": D4 * mr_bar,
        "mr_uwl": mr_bar * (1 + (2 / 3) * (D4 - 1)),
        "mr_cl": mr_bar,
    }
