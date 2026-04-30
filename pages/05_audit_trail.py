"""Page 5 — Audit Trail.

Displays the full removal log from Phase I: every removed point, which
iteration it was removed in, which rules it violated, and the control
limits in force at the time of removal.

This page provides the documentation required by quality management
systems (ISO 9001, IATF 16949, GMP) when removing data points from a
baseline calculation.
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
col2.metric("Retained (final)", result.n_final)
col3.metric("Total removed", result.n_total_removed)
col4.metric("Iterations", len(result.iterations))

removal_pct = 100 * result.n_total_removed / result.n_original if result.n_original else 0
if removal_pct > 20:
    st.warning(
        f"⚠️ {removal_pct:.1f}% of observations were removed.  "
        "A high removal rate may indicate systemic process problems or an "
        "unsuitable baseline period.  Review the underlying process before "
        "applying these limits operationally."
    )
elif result.n_total_removed > 0:
    st.info(f"{removal_pct:.1f}% of observations removed across {len(result.iterations)} iteration(s).")
else:
    st.success("No observations were removed — the process was in control from the first iteration.")

st.divider()

# ── Removal log table ─────────────────────────────────────────────────────────
st.subheader("Removal Log")
st.markdown(
    """
    Each row represents one observation that was removed during Phase I.
    The **rules_violated** column documents the assignable statistical reason.
    You should supplement this with a process-level assignable cause before
    finalising the baseline in a regulated environment.
    """
)

log = result.removal_log
if log.empty:
    st.info("No observations were removed.")
else:
    # Friendly column labels
    display_log = log.reset_index().rename(
        columns={
            "index": "Observation",
            "iteration": "Iteration",
            "value": "Value",
            "rules_violated": "Rules Violated",
            "x_bar_at_removal": "X̄ (at removal)",
            "ucl_at_removal": "UCL (at removal)",
            "lcl_at_removal": "LCL (at removal)",
        }
    )
    st.dataframe(
        display_log.style.format(
            {
                "Value": "{:.4f}",
                "X̄ (at removal)": "{:.4f}",
                "UCL (at removal)": "{:.4f}",
                "LCL (at removal)": "{:.4f}",
            }
        ),
        use_container_width=True,
        height=400,
    )

    # Download button
    csv_bytes = display_log.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Export audit trail as CSV",
        data=csv_bytes,
        file_name="spc_audit_trail.csv",
        mime="text/csv",
    )

st.divider()

# ── Per-iteration rule configuration used ─────────────────────────────────────
st.subheader("Rule Configuration Used")
cfg = result.rule_config
st.json(cfg)

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
