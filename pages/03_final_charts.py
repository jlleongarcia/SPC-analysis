"""Page 3 — Final Charts.

Displays the definitive I-MR charts using the clean retained dataset and the
final verified control limits from Phase I.
"""

import pandas as pd
import streamlit as st

from spc.charts import build_individuals_chart, build_mr_chart
from spc.core.limits import compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1

st.header("📈 Final I-MR Charts")

if "phase_i_result" not in st.session_state or st.session_state["phase_i_result"] is None:
    st.warning("No Phase I result found. Please run the **Phase I Study** first.")
    st.stop()

result = st.session_state["phase_i_result"]
lim = result.final_limits

# Restore original labels (dates, IDs) for chart display
values = result.final_values.copy()
values.index = result.original_labels[result.final_values.index]
mr = result.final_mr.copy()
mr.index = result.original_labels[result.final_mr.index]

# Re-apply rules on the final clean set for annotation (should show no violations
# if the study converged, but we display them anyway for transparency)
violations = apply_all_rules(
    values, lim,
    rule2_k=result.rule_config["rule2_k"],
    rule2_window=result.rule_config["rule2_window"],
    rule3_k=result.rule_config["rule3_k"],
    rule4_k=result.rule_config["rule4_k"],
)
mr_violations = apply_mr_rule1(mr, lim["mr_ucl"])

# ── Summary metrics ───────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("N (final)", f"{result.n_final}")
c2.metric("Mean (X̄)", f"{lim['i_cl']:.4f}")
c3.metric("UAL", f"{lim['i_ucl']:.4f}")
c4.metric("LAL", f"{lim['i_lcl']:.4f}")
c5.metric("σ̂ (within)", f"{lim['sigma_within']:.4f}")

st.divider()

# ── Individuals chart ─────────────────────────────────────────────────────────
st.subheader("Individuals (I) Chart — Final")
i_fig = build_individuals_chart(
    values, lim, violations,
    title="Individuals Chart — Final Verified Limits",
)
st.plotly_chart(i_fig, use_container_width=True)

# ── MR chart ──────────────────────────────────────────────────────────────────
st.subheader("Moving Range (MR) Chart — Final")
mr_fig = build_mr_chart(
    mr, lim, mr_violations,
    title="Moving Range Chart — Final Verified Limits",
)
st.plotly_chart(mr_fig, use_container_width=True)

# ── Limits table ──────────────────────────────────────────────────────────────
st.subheader("Final Control Lines")

lim_df = pd.DataFrame(
    {
        "Chart": ["I", "I", "I", "I", "I", "MR", "MR"],
        "Line": ["UAL (Action)", "UWL (Warning)", "CL (Mean)", "LWL (Warning)", "LAL (Action)",
                 "UAL", "CL (MR̄)"],
        "Value": [
            lim["i_ucl"], lim["i_uwl"], lim["i_cl"],
            lim["i_lwl"], lim["i_lcl"],
            lim["mr_ucl"], lim["mr_cl"],
        ],
    }
)
st.dataframe(lim_df.style.format({"Value": "{:.6f}"}), use_container_width=True)

# Warn if violations remain (non-converged study)
remaining = int(violations["any_violation"].sum())
if remaining:
    st.warning(
        f"⚠️ {remaining} violation(s) remain in the final dataset.  "
        "The study did not fully converge — interpret limits with caution."
    )
else:
    st.success("No violations detected in the final clean dataset.")
