# User Guide

## What is this tool?

This tool performs **Phase I Statistical Process Control (SPC)** on retrospective
(historical) process data. Its purpose is to establish verified, stable control
limits that prove a process was "in control" during the baseline period.

Once those limits are established, they can be used for **Phase II** — ongoing
real-time monitoring of the same process.

---

## When should I use it?

Use this tool when you need to:

- Establish **Action Limits** and **Warning Lines** for a process for the first time
- Validate a historical dataset before publishing official control limits
- Produce a **capability study** (Cp, Cpk) backed by clean, verified data
- Generate an **audit trail** of removed observations for a PPAP, control plan, or GMP record

---

## Step-by-step pipeline

### Step 1 — Data Import

Prepare your data as a **CSV** or **Excel** file with:

- One row per observation (one measurement per time period — shift, day, batch, etc.)
- One numeric column containing the individual measurement values
- An optional column for the observation label (date, batch ID, sequence number)

Upload the file, select your measurement column, and click **Confirm and proceed**.

> If you don't have a file yet, use the **Generate sample dataset** expander at the
> bottom of the page to download a synthetic example.

---

### Step 2 — Phase I Study

This is the core of the tool. It follows the **Oakland two-pass analyst-driven
workflow** (J.S. Oakland, *Statistical Process Control*, Ch. 4–5).

**Before running**, a **normality pre-check** (Shapiro-Wilk test) is performed.
Shewhart charts assume near-normality; a warning is shown if the data deviates
significantly.

**Configuration options** (expandable panel):

| Setting | Default | What it controls |
|---------|---------|------------------|
| Rule 2 — k points | 2 | Number of points required in the warning zone within the window |
| Rule 2 — window | 3 | Rolling window size for Rule 2 |
| Rule 3 — run length | 8 | Consecutive points same side of centre line |
| Rule 4 — trend length | 6 | Consecutive rising or falling points |

Click **▶ Run Pass 1**. The tool:

1. Computes X̄, MR̄, and all control lines from the full dataset
2. Applies the four SPC rules to the Individuals chart and Rule 1 to the MR chart
3. Presents every flagged point in a **decision table**

**Decision table (Pass 1 results):**

For each flagged observation you must decide:
- **Remove?** — tick the checkbox to exclude the point from the baseline
- **Assignable cause** — if removing, you *must* document the known process-level
  reason (equipment failure, operator error, raw material lot, etc.)

If no assignable cause is known, leave the checkbox unticked — Oakland's principle
is that a statistically flagged point with no confirmed cause should remain.

Click **Confirm decisions**. The tool then:

- If **no points removed**: finalises the baseline immediately (single pass).
- If **points removed**: runs **Pass 2** on the reduced dataset to re-evaluate the
  revised limits. Pass 2 results are shown with the updated I-MR chart.

The study stops after at most **two passes**, preventing the "utopia limits" problem
caused by iteratively trimming until no violations remain.

> **Oakland's principle (§5.4):** Removing observations without a confirmed
> assignable cause is *tampering* — it artificially tightens limits and increases
> real-world false-alarm rates. Statistical flagging identifies *candidates*;
> the analyst decides.

---

### Step 3 — Final Charts

Displays the definitive **Individuals (I)** and **Moving Range (MR)** charts
using only the clean retained data and the final verified control limits.

A summary table lists all six control lines (UAL, UWL, CL, LWL, LAL for the I
chart; UAL and CL for the MR chart) at full precision.

If the study did not converge (hit the iteration cap), a warning is shown and
remaining violations are highlighted in red.

---

### Step 4 — Capability

Enter the **Upper Specification Limit (USL)** and **Lower Specification Limit
(LSL)** — these are your engineering or customer tolerances, not the control limits.

The tool computes:

| Index | What it tells you |
|-------|------------------|
| **Cp** | Does the process spread fit inside the tolerance band? |
| **Cpk** | Does the process spread fit AND is it well-centred? |
| **Pp** | Same as Cp but using long-term variation (σ_overall) |
| **Ppk** | Same as Cpk but using long-term variation |
| **RPI** | Relative Precision Index — numerically identical to Cp |

**Minimum thresholds for enterprise use:**

- Cp ≥ 1.00 → process is minimally capable
- Cpk ≥ 1.33 → standard enterprise requirement
- Cpk ≥ 1.67 → critical or safety characteristics

A **distribution vs. specification** chart is shown so you can visually assess
how much margin exists between the process spread and the specification limits.

---

### Step 5 — Audit Trail

Displays the full **analyst decision log** — every point flagged during Phase I, with:

| Column | Description |
|--------|-------------|
| Pass | 1 or 2 — which pass detected the violation |
| Observation | Label (date, batch ID, etc.) |
| Value | Measured value |
| Rules violated | Which of the four SPC rules fired |
| Decision | "Removed" or "Retained (analyst decision)" |
| Assignable cause | The documented process-level cause (required for removals) |
| X̄ / UAL / LAL | Control lines in force during that pass |

Use the **Export audit trail as CSV** button to download this log for attachment
to your QMS documentation (PPAP, control plan, GMP batch record, etc.).

A warning is raised if more than **20%** of observations were removed — this
may indicate the baseline period was itself unstable, or that the dataset is
too small.

---

## Tips and common pitfalls

### Minimum dataset size
I-MR charts are theoretically valid from n ≥ 2, but in practice **n ≥ 30** is
recommended for reliable limit estimation. Fewer than 20 points after removal
should trigger a review of the baseline period selection.

### Non-normality
If the Shapiro-Wilk test flags non-normality, consider:
- A **data transformation** (log, Box-Cox) before importing
- Investigating whether the data is a **mixture of two populations** (e.g. two
  machines, two shifts, two raw material lots) — splitting them is usually better
  than transforming

### Cp vs. Cpk gap
If Cp ≥ 1.33 but Cpk < 1.00, the process spread is adequate but the process is
**off-centre**. Corrective action should focus on re-centring (adjusting the set
point), not on reducing variation.

### Pp vs. Cp gap
If Pp is significantly lower than Cp (ratio < 0.85), long-term drift or
between-batch variation is present. A stable Cpk alone is insufficient — the
source of long-term variation must be identified and controlled.
