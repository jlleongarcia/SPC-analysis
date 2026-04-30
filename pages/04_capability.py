"""Page 4 — Process Capability.

Computes Cp, Cpk, Pp, Ppk, and the Relative Precision Index (RPI) once the
user provides the Upper and Lower Specification Limits (USL / LSL).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from spc.core.capability import compute_capability

st.header("⚙️ Process Capability")

results: dict = st.session_state.get("phase_i_results", {})
value_cols: list = st.session_state.get("value_cols", [])
completed = [c for c in value_cols if c in results and results[c] is not None]

if not completed:
    st.warning("No Phase I results found. Please run the **Phase I Study** first.")
    st.stop()

if len(completed) > 1:
    selected_col = st.selectbox(
        "Variable to analyse",
        options=completed,
        help="Select which measurement variable to compute capability indices for.",
    )
else:
    selected_col = completed[0]

result = results[selected_col]
values = result.final_values
lim = result.final_limits

st.markdown(
    """
    Enter the **specification limits** defined by your engineering requirements or
    customer contract.  These are *not* the control limits — they are the tolerance
    boundaries your process must meet.
    """
)

# ── Specification limit inputs ────────────────────────────────────────────────
col1, col2 = st.columns(2)
usl = col1.number_input(
    "Upper Specification Limit (USL)",
    value=float(lim["i_cl"] + 3 * lim["sigma_within"] * 1.5),
    format="%.4f",
    help="The maximum acceptable value for this process characteristic.",
)
lsl = col2.number_input(
    "Lower Specification Limit (LSL)",
    value=float(lim["i_cl"] - 3 * lim["sigma_within"] * 1.5),
    format="%.4f",
    help="The minimum acceptable value for this process characteristic.",
)

if usl <= lsl:
    st.error("USL must be greater than LSL.")
    st.stop()

# ── Compute indices ───────────────────────────────────────────────────────────
cap = compute_capability(values, usl, lsl, mr_bar=lim["mr_bar"])

st.divider()
st.subheader("Capability Indices")

# ── Metric cards ──────────────────────────────────────────────────────────────
row1 = st.columns(4)
row1[0].metric("Cp  (potential)", f"{cap['cp']:.3f}",
               delta="≥ 1.00 ✓" if cap["capable_cp"] else "< 1.00 ✗",
               delta_color="normal" if cap["capable_cp"] else "inverse")
row1[1].metric("Cpk  (potential, centred)", f"{cap['cpk']:.3f}",
               delta="≥ 1.33 ✓" if cap["capable_cpk"] else "< 1.33 ✗",
               delta_color="normal" if cap["capable_cpk"] else "inverse")
row1[2].metric("Pp  (performance)", f"{cap['pp']:.3f}")
row1[3].metric("Ppk  (performance, centred)", f"{cap['ppk']:.3f}")

row2 = st.columns(4)
row2[0].metric("RPI  (= Cp)", f"{cap['rpi']:.3f}")
row2[1].metric("X̄ (mean)", f"{cap['x_bar']:.4f}")
row2[2].metric("σ̂ within", f"{cap['sigma_within']:.4f}")
row2[3].metric("σ overall", f"{cap['sigma_overall']:.4f}")

# ── Verdict ───────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Verdict")

verdict_lines = []
if cap["capable_cp"]:
    verdict_lines.append("✅ **Cp ≥ 1.00** — Process spread fits within the tolerance band.")
else:
    verdict_lines.append("❌ **Cp < 1.00** — Process variation exceeds the tolerance band.  "
                         "The process is **not capable**.")

if cap["capable_cpk"]:
    verdict_lines.append("✅ **Cpk ≥ 1.33** — Process is well-centred and meets the enterprise "
                         "minimum capability threshold.")
else:
    verdict_lines.append("⚠️ **Cpk < 1.33** — Process may be off-centre or insufficient margin "
                         "exists.  Consider re-centring or reducing variation.")

if cap["cp"] > 0 and (cap["cpk"] / cap["cp"]) < 0.85:
    verdict_lines.append("⚠️ **Cp vs Cpk gap** — Significant off-centring detected "
                         f"(Cpk/Cp = {cap['cpk']/cap['cp']:.2f}).  "
                         "Investigate systematic bias.")

for line in verdict_lines:
    st.markdown(line)

# ── Gauge chart ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("Distribution vs. Specification Limits")

import numpy as np
from scipy.stats import norm

x_lo = min(lsl, cap["x_bar"] - 4 * cap["sigma_overall"])
x_hi = max(usl, cap["x_bar"] + 4 * cap["sigma_overall"])
x_vals = np.linspace(x_lo, x_hi, 400)
y_vals = norm.pdf(x_vals, cap["x_bar"], cap["sigma_within"])

fig = go.Figure()
fig.add_trace(go.Scatter(x=x_vals, y=y_vals, mode="lines", name="Distribution (σ within)",
                         fill="tozeroy", line={"color": "#1f77b4"}))
fig.add_vline(x=usl, line_dash="dash", line_color="#d62728", annotation_text="USL",
              annotation_position="top right")
fig.add_vline(x=lsl, line_dash="dash", line_color="#d62728", annotation_text="LSL",
              annotation_position="top left")
fig.add_vline(x=cap["x_bar"], line_dash="solid", line_color="#2ca02c",
              annotation_text="X̄", annotation_position="top right")
fig.update_layout(
    template="plotly_white",
    xaxis_title="Value",
    yaxis_title="Density",
    title="Process Distribution vs. Specification Limits",
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

# ── Cp / Cpk interpretation guide ────────────────────────────────────────────
with st.expander("📖 Index interpretation guide"):
    st.markdown(
        """
        | Index | Formula | What it measures |
        |-------|---------|-----------------|
        | **Cp** | (USL−LSL) / (6σ_within) | Potential capability — spread only |
        | **Cpk** | min[(USL−X̄)/3σ, (X̄−LSL)/3σ] | Potential capability — spread AND centring |
        | **Pp** | (USL−LSL) / (6σ_overall) | Actual performance — spread only |
        | **Ppk** | min[(USL−X̄)/3σ_overall, (X̄−LSL)/3σ_overall] | Actual performance — spread AND centring |
        | **RPI** | = Cp | Relative Precision Index (numerically identical to Cp) |

        **Enterprise thresholds (common defaults):**
        - Cp ≥ 1.00 → process spread fits within tolerance
        - Cpk ≥ 1.33 → minimum enterprise requirement (IATF / automotive)
        - Cpk ≥ 1.67 → critical characteristics in some standards

        **σ_within** is estimated from the average moving range (MR̄ / d₂), capturing short-term
        variation only.  **σ_overall** is the sample standard deviation of all retained values,
        capturing long-term drift as well.  A large gap between Cp and Pp signals process drift.
        """
    )
