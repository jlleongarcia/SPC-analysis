"""Page 2 — Phase I Iterative SPC Study."""

import pandas as pd
import streamlit as st

from spc.core import normality_check, run_phase_i
from spc.core.limits import compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1
from spc.charts import build_imr_panel

st.header("🔄 Phase I Study")

if "raw_values" not in st.session_state:
    st.warning("No data loaded. Please go to **Data Import** first.")
    st.stop()

values: pd.Series = st.session_state["raw_values"]

# ── Normality pre-check ───────────────────────────────────────────────────────
st.subheader("Normality Pre-Check")
norm_result = normality_check(values)
col_n1, col_n2, col_n3 = st.columns(3)
col_n1.metric("Test", norm_result["test_name"])
col_n2.metric("Statistic", f"{norm_result['statistic']:.4f}" if norm_result["statistic"] else "N/A")
p_label = f"{norm_result['p_value']:.4f}" if norm_result["p_value"] is not None else "—"
col_n3.metric("p-value", p_label)

if norm_result["warning_message"]:
    st.warning(norm_result["warning_message"])
else:
    st.success("Data appears normally distributed (α = 0.05). Shewhart limits are valid.")

st.divider()

# ── Rule & iteration configuration ───────────────────────────────────────────
st.subheader("Configuration")

with st.expander("⚙️ Rule thresholds & iteration settings", expanded=False):
    c1, c2, c3, c4, c5 = st.columns(5)
    rule2_k      = c1.number_input("Rule 2 — k points", min_value=1, max_value=5, value=2,
                                    help="k of window consecutive points in the warning zone.")
    rule2_window = c2.number_input("Rule 2 — window", min_value=2, max_value=10, value=3)
    rule3_k      = c3.number_input("Rule 3 — run length", min_value=4, max_value=15, value=8,
                                    help="Consecutive points same side of centre line.")
    rule4_k      = c4.number_input("Rule 4 — trend length", min_value=4, max_value=12, value=6,
                                    help="Consecutive rising or falling points.")
    max_iter     = c5.number_input("Max iterations", min_value=1, max_value=20, value=10)

st.divider()

# ── Run Phase I ───────────────────────────────────────────────────────────────
if st.button("▶ Run Phase I Analysis", type="primary"):
    with st.spinner("Running iterative SPC analysis…"):
        result = run_phase_i(
            values,
            max_iterations=int(max_iter),
            rule2_k=int(rule2_k),
            rule2_window=int(rule2_window),
            rule3_k=int(rule3_k),
            rule4_k=int(rule4_k),
        )
    st.session_state["phase_i_result"] = result
    st.rerun()

# ── Display results if available ──────────────────────────────────────────────
result = st.session_state.get("phase_i_result")
if result is None:
    st.stop()

# Summary banner
if result.converged:
    st.success(
        f"✅ Process reached statistical control after **{len(result.iterations)}** iteration(s).  "
        f"**{result.n_total_removed}** of {result.n_original} points removed."
    )
else:
    st.error(
        f"⚠️ Process did **not** converge within {max_iter} iterations.  "
        f"{result.n_total_removed} of {result.n_original} points removed.  "
        "Review the audit trail and consider whether an assignable cause exists."
    )

# ── Per-iteration expanders ───────────────────────────────────────────────────
st.subheader("Iteration Detail")

removed_so_far = pd.Series(dtype=float)

for snap in result.iterations:
    retained_vals = values.loc[snap.retained_indices].dropna()
    mr = compute_moving_range(retained_vals)

    label = (
        f"Iteration {snap.iteration}  —  "
        f"{snap.n_retained} observations, "
        f"{snap.n_removed_this_iter} violation(s) found"
    )
    with st.expander(label, expanded=(snap.iteration == 1)):
        # Limits table
        lim = snap.limits
        lim_df = pd.DataFrame(
            {
                "Chart": ["I"] * 5 + ["MR"] * 2,
                "Line": ["UCL", "UWL", "CL", "LWL", "LCL", "UCL", "CL"],
                "Value": [
                    lim["i_ucl"], lim["i_uwl"], lim["i_cl"],
                    lim["i_lwl"], lim["i_lcl"],
                    lim["mr_ucl"], lim["mr_cl"],
                ],
            }
        )
        st.dataframe(lim_df.style.format({"Value": "{:.4f}"}), use_container_width=True)

        # I-MR chart for this iteration
        fig = build_imr_panel(
            retained_vals,
            mr,
            lim,
            violations=snap.individual_violations,
            mr_violations=snap.mr_violations,
            removed_values=removed_so_far if not removed_so_far.empty else None,
            title=f"I-MR — Iteration {snap.iteration}",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Violation table
        if snap.n_removed_this_iter > 0:
            st.markdown("**Points flagged for removal:**")
            viol_display = snap.individual_violations[
                snap.individual_violations["any_violation"]
            ][["rule1", "rule2", "rule3", "rule4"]].copy()
            viol_display.insert(0, "value", retained_vals.reindex(viol_display.index))
            st.dataframe(viol_display, use_container_width=True)

    # Accumulate removed ghost points for next iteration
    if snap.removed_indices:
        removed_so_far = pd.concat([
            removed_so_far,
            values.loc[snap.removed_indices].dropna(),
        ])

st.success("Navigate to **Final Charts** or **Capability** to continue.")
