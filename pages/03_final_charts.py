"""Page 3 — Final Charts.

Displays the definitive I-MR charts using the clean retained dataset and the
final verified control limits from Phase I.  When multiple measurement variables
were analysed, each is shown in its own tab.
"""

import pandas as pd
import streamlit as st

from spc.charts import build_individuals_chart, build_mr_chart
from spc.core.limits import compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1

st.header("📈 Final I-MR Charts")

results: dict = st.session_state.get("phase_i_results", {})
value_cols: list = st.session_state.get("value_cols", [])
completed = [c for c in value_cols if c in results and results[c] is not None]

if not completed:
    st.warning("No Phase I results found. Please run the **Phase I Study** first.")
    st.stop()

if len(completed) < len(value_cols):
    pending = [c for c in value_cols if c not in completed]
    st.info(
        f"Phase I complete for: {', '.join(f'**{c}**' for c in completed)}.  "
        f"Still pending: {', '.join(f'*{c}*' for c in pending)}."
    )


def _render_charts(col: str) -> None:
    result = results[col]
    lim = result.final_limits

    values = result.final_values.copy()
    values.index = result.original_labels
    mr = result.final_mr.copy()
    mr.index = result.original_labels

    violations = apply_all_rules(
        values, lim,
        rule2_k=result.rule_config["rule2_k"],
        rule2_window=result.rule_config["rule2_window"],
        rule3_k=result.rule_config["rule3_k"],
        rule4_k=result.rule_config["rule4_k"],
    )
    mr_violations = apply_mr_rule1(mr, lim["mr_ucl"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("N (final)",   f"{result.n_final}")
    c2.metric("Mean (X̄)",   f"{lim['i_cl']:.4f}")
    c3.metric("UAL",         f"{lim['i_ucl']:.4f}")
    c4.metric("LAL",         f"{lim['i_lcl']:.4f}")
    c5.metric("σ̂ (within)", f"{lim['sigma_within']:.4f}")

    st.divider()

    st.subheader("Individuals (I) Chart — Final")
    i_fig = build_individuals_chart(
        values, lim, violations,
        title=f"Individuals Chart — Final Verified Limits ({col})",
    )
    st.plotly_chart(i_fig, width='stretch')

    st.subheader("Moving Range (MR) Chart — Final")
    mr_fig = build_mr_chart(
        mr, lim, mr_violations,
        title=f"Moving Range Chart — Final Verified Limits ({col})",
    )
    st.plotly_chart(mr_fig, width='stretch')

    st.subheader("Final Control Lines")
    lim_df = pd.DataFrame({
        "Chart": ["I", "I", "I", "I", "I", "MR", "MR"],
        "Line":  ["UAL (Action)", "UWL (Warning)", "CL (Mean)",
                  "LWL (Warning)", "LAL (Action)", "UAL", "CL (MR̄)"],
        "Value": [
            lim["i_ucl"], lim["i_uwl"], lim["i_cl"],
            lim["i_lwl"], lim["i_lcl"],
            lim["mr_ucl"], lim["mr_cl"],
        ],
    })
    st.dataframe(lim_df.style.format({"Value": "{:.6f}"}), width='stretch')

    remaining = int(violations["any_violation"].sum())
    if remaining:
        st.warning(
            f"⚠️ {remaining} violation(s) remain in the final dataset.  "
            "The study did not fully converge — interpret limits with caution."
        )
    else:
        st.success("No violations detected in the final clean dataset.")


if len(completed) == 1:
    _render_charts(completed[0])
else:
    tabs = st.tabs(completed)
    for tab, col in zip(tabs, completed):
        with tab:
            _render_charts(col)
