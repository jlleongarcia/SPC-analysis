"""Page 5 — Audit Trail.

Displays the analyst's decisions from Phase I for all measurement variables:
every flagged point, which rules fired, the analyst's decision
(removed / retained), and the documented assignable cause.

When multiple variables were analysed, a cross-variable summary highlights
observations removed from more than one variable simultaneously.
"""

import pandas as pd
import streamlit as st

st.header("📋 Audit Trail")

results: dict = st.session_state.get("phase_i_results", {})
value_cols: list = st.session_state.get("value_cols", [])
completed = [c for c in value_cols if c in results and results[c] is not None]

if not completed:
    st.warning("No Phase I results found. Please run the **Phase I Study** first.")
    st.stop()


def _render_variable_audit(col: str) -> None:
    result = results[col]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Original observations", result.n_original)
    col2.metric("Retained (final)",       result.n_final)
    col3.metric("Removed",                result.n_total_removed)
    col4.metric("Passes completed",       result.n_passes)

    removal_pct = 100 * result.n_total_removed / result.n_original if result.n_original else 0

    if result.n_total_removed == 0 and result.audit_log.empty:
        st.success("No violations detected — the process was in control from Pass 1.")
    elif result.n_total_removed == 0:
        st.info(
            f"{len(result.audit_log)} flagged point(s) reviewed and **retained** by analyst "
            "decision.  Limits reflect the full dataset."
        )
    elif removal_pct > 20:
        st.warning(
            f"⚠️ {removal_pct:.1f}% of observations were removed.  "
            "A high removal rate may indicate systemic process problems or an unsuitable "
            "baseline period."
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
    st.subheader("Analyst Decision Log")

    log = result.audit_log
    if log.empty:
        st.info("No points were flagged — nothing to log.")
        return

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

    def _highlight(row):
        if row["Decision"] == "Removed":
            return ["background-color: #fde8e8"] * len(row)
        return [""] * len(row)

    st.dataframe(
        display_log.style
            .apply(_highlight, axis=1)
            .format({"Value": "{:.4f}", "X̄ (at review)": "{:.4f}",
                     "UAL (at review)": "{:.4f}", "LAL (at review)": "{:.4f}"}),
        width='stretch',
    )

    st.divider()
    csv = display_log.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"⬇️ Download audit log — {col} (CSV)",
        data=csv,
        file_name=f"phase_i_audit_{col}.csv",
        mime="text/csv",
    )

    st.subheader("Rule Configuration Used")
    st.json(result.rule_config)

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
            """
        )


# ── Per-variable tabs ─────────────────────────────────────────────────────────
if len(completed) == 1:
    _render_variable_audit(completed[0])
else:
    tabs = st.tabs(completed)
    for tab, col in zip(tabs, completed):
        with tab:
            _render_variable_audit(col)

# ── Cross-variable summary ────────────────────────────────────────────────────
if len(completed) >= 2:
    st.divider()
    st.subheader("🔗 Cross-Variable Summary")

    # Build combined log with "Variable" column
    all_rows = []
    for col in completed:
        log = results[col].audit_log
        if not log.empty:
            sub = log.reset_index().copy()
            sub.insert(0, "Variable", col)
            all_rows.append(sub)

    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)

        # Shared removals (same observation removed in ≥2 variables)
        removed = combined[combined["decision"] == "Removed"]
        obs_counts = removed.groupby("observation")["Variable"].apply(list)
        shared = obs_counts[obs_counts.apply(len) >= 2]

        sc1, sc2, sc3 = st.columns(3)
        total_removed = int(combined["decision"].eq("Removed").sum())
        sc1.metric("Total removals (all variables)", total_removed)
        sc2.metric("Obs. removed from ≥2 variables", len(shared))
        sc3.metric("Variables with removals",
                   sum(1 for c in completed if results[c].n_total_removed > 0))

        if not shared.empty:
            st.markdown("**Observations removed from multiple variables (common-cause candidates):**")
            shared_df = pd.DataFrame([
                {"Observation": obs, "Removed from": ", ".join(cols)}
                for obs, cols in shared.items()
            ])
            st.dataframe(shared_df, width='stretch')

        st.markdown("**All decisions across all variables:**")

        def _highlight_multi(row):
            if row["decision"] == "Removed":
                return ["background-color: #fde8e8"] * len(row)
            return [""] * len(row)

        st.dataframe(
            combined.style.apply(_highlight_multi, axis=1),
            width='stretch',
        )

        full_csv = combined.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download combined audit log (all variables, CSV)",
            data=full_csv,
            file_name="phase_i_audit_combined.csv",
            mime="text/csv",
        )
    else:
        st.info("No points were flagged in any variable — nothing to log.")
