# Methodology

## 1. Overview

This tool implements **Phase I Statistical Process Control (SPC)** for Individual
measurements using the **I-MR (Individuals and Moving Range) chart pair**.

Phase I is a retrospective study: given a historical dataset, we want to establish
verified, stable control limits that can then be used for Phase II (ongoing process
monitoring). The key challenge is that the historical data may contain
out-of-control periods — we cannot use those periods to define "normal" limits.

---

## 2. Chart type: Individuals (I-MR)

### When to use I-MR charts

- One measurement per time period (one sample per shift, per day, per batch…)
- Rational subgroups of size n = 1
- Common in chemical, pharmaceutical, environmental, and discrete-part manufacturing

### Moving Range

The moving range of span 2 is the absolute successive difference:

$$MR_i = |x_i - x_{i-1}|$$

It is used to estimate short-term (within-subgroup) process variation.

---

## 3. Control limit formulas

### Unbiasing constant

For span-2 moving ranges, the expected value of MR/σ is:

$$d_2 = 1.128$$

### Within-subgroup standard deviation

$$\hat{\sigma}_{within} = \frac{\overline{MR}}{d_2}$$

where $\overline{MR}$ is the average of all moving ranges.

### Individuals chart

| Line | Formula |
|------|---------|
| UAL (Action) | $\bar{x} + 3\hat{\sigma}$ |
| UWL (Warning) | $\bar{x} + 2\hat{\sigma}$ |
| CL | $\bar{x}$ |
| LWL (Warning) | $\bar{x} - 2\hat{\sigma}$ |
| LAL (Action) | $\bar{x} - 3\hat{\sigma}$ |

### Moving Range chart

| Line | Formula |
|------|---------|
| UAL | $D_4 \cdot \overline{MR}$ |
| CL | $\overline{MR}$ |
| LAL | 0 (always for n=2) |

where $D_4 = 3.267$ for n = 2.

---

## 4. The four SPC rules

Rules are applied to the **Individual** chart. Rule 1 is also applied to the
**Moving Range** chart independently.

### Rule 1 — Action Limits

$$x_i > UAL \quad \text{or} \quad x_i < LAL$$

Any single point beyond ±3σ from the centre line. The probability of a false
alarm on a single point (under normality) is approximately 0.27%.

### Rule 2 — Warning Zone (2-of-3)

2 or more of any 3 consecutive points fall in the same warning zone
(between ±2σ and ±3σ on the same side).

This is the **Western Electric Rule 2** formulation. It is statistically more
precise than the simpler "no point in the warning zone" check because it controls
the false-alarm rate while maintaining sensitivity to process shifts.

### Rule 3 — Run

8 or more consecutive points on the same side of the centre line (default k=8).

A sustained shift in the process mean that is too small to trigger Rule 1 will
manifest as a run. The probability of 8 random coin flips all landing the same
side is 0.78% — well below the 1% threshold.

> Nelson (1984) uses k=9. Western Electric uses k=8. The default here is k=8 but
> it is configurable.

### Rule 4 — Trend

6 or more consecutive points strictly rising or falling (default k=6).

A monotonic trend of 6 points has a probability of (1/2)^5 ≈ 3% of occurring by
chance (only the direction of each successive step matters, not the magnitude).

---

## 5. Phase I iterative algorithm

```
INPUT: full historical dataset D, max_iterations M
OUTPUT: stable limits, clean dataset, removal audit trail

retained ← D (all non-NaN values)

FOR iteration = 1 TO M:
    1. Compute X̄, MR̄, σ̂, and all control lines from retained
    2. Apply Rules 1–4 to Individual chart
    3. Apply Rule 1 to MR chart
    4. flagged ← union of all violation indices
    5. IF flagged is empty:
           RETURN (converged, current limits, retained, audit trail)
    6. Log each flagged point with: iteration, value, rules violated,
       X̄, UAL, LAL at time of removal
    7. retained ← retained \ flagged

RETURN (not converged, current limits, retained, audit trail)
```

### Why iterative?

Removing a point changes the mean and standard deviation, which changes the
limits, which may expose (or eliminate) violations in other points. A single pass
is insufficient for retrospective data with multiple disturbances.

### Stopping criteria

1. **Convergence** — no violations detected (primary criterion)
2. **Iteration cap** — safety limit to prevent over-pruning (default: 10)

### Over-pruning risk

If too many points are removed (>20% is a warning threshold in this tool), the
resulting limits may be unrealistically tight. This can happen when:
- The baseline period itself was unstable
- The tolerance for what counts as "in control" is too strict
- The dataset is too small (n < 30 is borderline for I-MR)

In regulated environments, **every removed point must have a documented process-
level assignable cause** (e.g., equipment failure, operator error, raw material
issue). Statistical flagging is necessary but not sufficient justification.

---

## 6. Normality pre-check

Shewhart charts assume the individual measurements are approximately normally
distributed. Severe non-normality inflates the false-alarm rate significantly.

| n | Test used |
|---|-----------|
| 3 – 5000 | Shapiro-Wilk (high power for small–medium n) |
| > 5000 | Anderson-Darling (Shapiro-Wilk is not valid for n > 5000) |

The test result is advisory — it does not block the analysis but is surfaced
prominently in the UI. If non-normality is confirmed, consider:

- A data transformation (Box-Cox, log)
- A non-parametric SPC method (e.g., CUSUM on ranks)
- Investigating whether the non-normality is caused by mixing sub-populations

---

## 7. Process capability indices

### σ_within vs. σ_overall

**σ_within** (short-term): estimated from the average moving range. Captures only
the inherent point-to-point variation of a stable process. Used for Cp and Cpk.

**σ_overall** (long-term): the sample standard deviation of all retained values.
Captures both inherent variation and any slow drift or shifts. Used for Pp and Ppk.

The ratio Pp/Cp (or Ppk/Cpk) quantifies how much additional variation exists
beyond the inherent short-term noise. A ratio < 0.85 suggests significant drift.

### Formulas

$$C_p = \frac{USL - LSL}{6\hat{\sigma}_{within}}$$

$$C_{pk} = \min\left(\frac{USL - \bar{x}}{3\hat{\sigma}_{within}},\ \frac{\bar{x} - LSL}{3\hat{\sigma}_{within}}\right)$$

$$P_p = \frac{USL - LSL}{6\hat{\sigma}_{overall}}$$

$$P_{pk} = \min\left(\frac{USL - \bar{x}}{3\hat{\sigma}_{overall}},\ \frac{\bar{x} - LSL}{3\hat{\sigma}_{overall}}\right)$$

$$RPI = C_p = \frac{2T}{6\hat{\sigma}_{within}} \quad \text{where } T = \frac{USL - LSL}{2}$$

### Interpretation thresholds

| Index | Minimum | Target (enterprise) | Critical characteristics |
|-------|---------|---------------------|--------------------------|
| Cp | 1.00 | 1.33 | 1.67 |
| Cpk | 1.00 | 1.33 | 1.67 |

A process with Cp ≥ 1.33 but Cpk < 1.00 is capable in spread but dangerously
off-centre — the Cp/Cpk gap must be investigated and corrected.

---

## 8. References

- Montgomery, D.C. (2020). *Introduction to Statistical Quality Control*, 8th ed. Wiley.
- Nelson, L.S. (1984). The Shewhart control chart — tests for special causes. *Journal of Quality Technology*, 16(4), 237–239.
- Western Electric Co. (1956). *Statistical Quality Control Handbook*. AT&T Technologies.
- AIAG (2010). *Statistical Process Control Reference Manual*, 2nd ed. Automotive Industry Action Group.
