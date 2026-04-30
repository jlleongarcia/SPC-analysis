"""Page 5 — Audit Trail.

Displays the analyst's decisions from Phase I: every flagged point, which
rules fired, the analyst's decision (removed / retained), and the documented
assignable cause.

This page provides the documentation required by quality management systems
(ISO 9001, IATF 16949, GMP) for any baseline adjustment — per Oakland's
principle that removal requires a real-world assignable cause.
"""

import pandas as pd
import streamlit as st

st.header("📋 Audit Trail")

if "phase_i_result" not in st.session_state or st.session_state["phase_i_result"] is None:
    st.warning("No Phase I result found. Please run the **Phase I Study** first.")
    st.stop()

result = st.session_state["phase_i_result"]

# ── Summary ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Original observations", result.n_original)
col2.metric("Retained (final)",       result.n_final)
col3.metric("Removed",                result.n_total_removed)
col4.metric("Passes completed",       result.n_passes)

removal_pct = 100 * result.n_total_removed / result.n_original if result.n_original else 0
if result.n_total_removed == 0 and result.audit_log.empty:
    st.success("No violations were detected — the process was in control from Pass 1.")
elif result.n_total_removed == 0:
    st.info(
        f"{len(result.audit_log)} flagged point(s) reviewed and **retained** by analyst decision.  "
        "Limits reflect the full dataset."
    )
elif removal_pct > 20:
    st.warning(
        f"⚠️ {removal_pct:.1f}% of observations were removed.  "
        "A high removal rate may indicate systemic process problems or an unsuitable "
        "baseline period.  Review the underlying process before applying these limits "
        "operationally."
    )
else:
    st.info(
        f"{result.n_total_removed} of {result.n_original} observations removed "
        f"({removal_pct:.1f}%) across {result.n_passes} pass(es)."
    )

if result.final_pass_has_violations:
    st.warning(
        "⚠️ The final pass still shows statistical violations.  These are acknowledged "
        "as common-cause variation per analyst review."
    )

st.divider()

# ── Audit log table ───────────────────────────────────────────────────────────
st.subheader("Analyst Decision Log")
st.markdown(
    """
    Each row represents a statistically flagged observation.  
    The **Decision** column records whether the analyst chose to remove it  
    or retain it as common-cause variation.  
    **Assignable Cause** must be non-empty for any removed point.
    """
)

log = result.audit_log
if log.empty:
    st.info("No points were flagged — nothing to log.")
else:
    display_log = log.reset_index().rename(columns={
        "observation":      "Observation",
        "pass":             "Pass",
        "value":            "Value",
        "rules_violated":   "Rules Violated",
        "decision":         "Decision",
        "assignable_cause": "Assignable Cause",
        "x_bar":            "X̄ (at review)",
        "ual":              "UAL (at review)",
        "lal":              "LAL (at review)",
    })

    # Highlight removed rows
    def _highlight(row):
        if row["Decision"] == "Removed":
            return ["background-color: #fde8e8"] * len(row)
        return [""] * len(row)

    st.dataframe(
        display_log.style
            .apply(_highlight, axis=1)
            .format({"Value": "{:.4f}", "X̄ (at review)": "{:.4f}",
                     "UAL (at review)": "{:.4f}", "LAL (at review)": "{:.4f}"}),
        use_container_width=True,
    )

    # ── Export ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Export")
    csv = display_log.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download audit log (CSV)",
        data=csv,
        file_name="phase_i_audit_log.csv",
        mime="text/csv",
    )

st.divider()

# ── Rule configuration used ───────────────────────────────────────────────────
st.subheader("Rule Configuration Used")
st.json(result.rule_config)

# ── Rule reference ────────────────────────────────────────────────────────────
with st.expander("📖 Rule definitions"):
    st.markdown(
        """
        | Rule | Name | Condition |
        |------|------|-----------|
        | **Rule 1** | Action Limits | Any point outside UCL or LCL (±3σ) |
        | **Rule 2** | Warning Zone | k of *window* consecutive points beyond ±2σ on the same side |
        | **Rule 3** | Run | k or more consecutive points on the same side of the centre line |
        | **Rule 4** | Trend | k or more consecutive points strictly rising or falling |
        | **MR Rule 1** | MR Action Limit | Moving range exceeds MR UCL (= D₄ × MR̄) |

        Default thresholds: Rule 2 → k=2 of 3; Rule 3 → k=8; Rule 4 → k=6.
        All thresholds are configurable in the Phase I Study page.
        """
    )
