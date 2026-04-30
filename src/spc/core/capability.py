"""Process capability indices: Cp, Cpk, Pp, Ppk and the Relative Precision Index.

Definitions
───────────
    σ_within  — short-term std dev estimated from the average moving range
                (σ = MR-bar / d2).  Used for *potential* capability (Cp, Cpk).

    σ_overall — long-term std dev estimated as the sample standard deviation of
                all retained measurements.  Used for *performance* (Pp, Ppk).

    Cp   = (USL - LSL) / (6 * σ_within)
    Cpk  = min( (USL - X-bar) / (3 * σ_within),
                (X-bar - LSL) / (3 * σ_within) )

    Pp   = (USL - LSL) / (6 * σ_overall)
    Ppk  = min( (USL - X-bar) / (3 * σ_overall),
                (X-bar - LSL) / (3 * σ_overall) )

    RPI  = 2T / (6 * σ_within)   where T = (USL - LSL) / 2
         = Cp                     (they are numerically identical)

    The process is *capable* when Cp ≥ 1.0  (6σ < tolerance band).
    For enterprise use, a target of Cpk ≥ 1.33 is the common minimum.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from spc.core.limits import D2


def compute_capability(
    values: pd.Series,
    usl: float,
    lsl: float,
    *,
    mr_bar: float | None = None,
) -> dict[str, float]:
    """Compute Cp, Cpk, Pp, Ppk, and RPI for a set of individual measurements.

    Parameters
    ----------
    values:
        Retained (clean) individual measurements.
    usl:
        Upper Specification Limit.
    lsl:
        Lower Specification Limit.
    mr_bar:
        Pre-computed average moving range.  If None it is computed from
        *values* internally.

    Returns
    -------
    dict with keys: usl, lsl, tolerance, x_bar,
                    sigma_within, sigma_overall,
                    cp, cpk, pp, ppk, rpi, capable_cp, capable_cpk
    """
    clean = values.dropna()
    if len(clean) < 2:
        raise ValueError("At least 2 observations are required.")
    if usl <= lsl:
        raise ValueError("USL must be strictly greater than LSL.")

    x_bar = float(clean.mean())
    sigma_overall = float(clean.std(ddof=1))

    if mr_bar is None:
        mr = clean.diff().abs().dropna()
        mr_bar = float(mr.mean())
    sigma_within = mr_bar / D2

    tolerance = (usl - lsl) / 2  # half-tolerance T

    cp = (usl - lsl) / (6 * sigma_within) if sigma_within > 0 else float("inf")
    cpu = (usl - x_bar) / (3 * sigma_within) if sigma_within > 0 else float("inf")
    cpl = (x_bar - lsl) / (3 * sigma_within) if sigma_within > 0 else float("inf")
    cpk = min(cpu, cpl)

    pp = (usl - lsl) / (6 * sigma_overall) if sigma_overall > 0 else float("inf")
    ppu = (usl - x_bar) / (3 * sigma_overall) if sigma_overall > 0 else float("inf")
    ppl = (x_bar - lsl) / (3 * sigma_overall) if sigma_overall > 0 else float("inf")
    ppk = min(ppu, ppl)

    rpi = cp  # numerically equivalent: (2T) / (6σ) = (USL-LSL) / (6σ) = Cp

    return {
        "usl": usl,
        "lsl": lsl,
        "tolerance": tolerance,
        "x_bar": x_bar,
        "sigma_within": sigma_within,
        "sigma_overall": sigma_overall,
        "cp": cp,
        "cpk": cpk,
        "pp": pp,
        "ppk": ppk,
        "rpi": rpi,
        # Capability verdicts
        "capable_cp": cp >= 1.0,
        "capable_cpk": cpk >= 1.33,
    }
