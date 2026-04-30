"""Page 2 — Phase I SPC Study (Oakland two-pass analyst-driven workflow).

Workflow
────────
Pass 1:  Compute limits and flag statistical candidates for review.
         The analyst reviews each flagged point and decides whether to remove it.
         Per Oakland (Ch. 4–5): removal requires a documented assignable cause.

Pass 2:  If any removals were made, re-evaluate the cleaned data.
         The result of Pass 2 (or Pass 1 if no removals) is the certified
         baseline used in Final Charts, Capability, and Audit Trail.
"""

import numpy as np
import pandas as pd
import streamlit as st

from spc.core import normality_check, run_phase_i_pass, PhaseIResult
from spc.core.limits import compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1
from spc.charts import build_imr_panel

st.header("🔄 Phase I Study")

if "raw_values" not in st.session_state:
    st.warning("No data loaded. Please go to **Data Import** first.")
    st.stop()

raw_values: pd.Series = st.session_state["raw_values"]

# ── Normality pre-check (collapsible, always available) ───────────────────────
with st.expander("🔬 Normality Pre-Check", expanded=False):
    norm_result = normality_check(raw_values)
    col_n1, col_n2, col_n3 = st.columns(3)
    col_n1.metric("Test", norm_result["test_name"])
    col_n2.metric(
        "Statistic",
        f"{norm_result['statistic']:.4f}" if norm_result["statistic"] else "N/A",
    )
    p_label = f"{norm_result['p_value']:.4f}" if norm_result["p_value"] is not None else "—"
    col_n3.metric("p-value", p_label)
    if norm_result["warning_message"]:
        st.warning(norm_result["warning_message"])
    else:
        st.success("Data appears normally distributed (α = 0.05). Shewhart limits are valid.")

st.divider()


# ── Reset helper ──────────────────────────────────────────────────────────────
def _reset_phase_i() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith(("phase_i_", "chk_", "cause_")):
            del st.session_state[k]


# ── Stage dispatcher ──────────────────────────────────────────────────────────
stage = st.session_state.get("phase_i_stage", "idle")

# ══════════════════════════════════════════════════════════════════════════════
# STAGE idle — configuration and Pass 1 launch
# ══════════════════════════════════════════════════════════════════════════════
if stage == "idle":
    st.subheader("Configuration")
    with st.expander("⚙️ Rule thresholds", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        rule2_k      = c1.number_input("Rule 2 — k points",      min_value=1, max_value=5,  value=2)
        rule2_window = c2.number_input("Rule 2 — window",         min_value=2, max_value=10, value=3)
        rule3_k      = c3.number_input("Rule 3 — run length",     min_value=4, max_value=15, value=8)
        rule4_k      = c4.number_input("Rule 4 — trend length",   min_value=4, max_value=12, value=6)

    st.info(
        "**Oakland principle (Ch. 4–5)** — This tool flags statistical candidates "
        "for removal. It never removes data automatically. You will review each "
        "flagged point and provide a documented assignable cause before any "
        "removal is accepted into the baseline."
    )

    if st.button("▶ Run Pass 1", type="primary"):
        with st.spinner("Evaluating Pass 1…"):
            pass1 = run_phase_i_pass(
                raw_values,
                rule2_k=int(rule2_k),
                rule2_window=int(rule2_window),
                rule3_k=int(rule3_k),
                rule4_k=int(rule4_k),
            )
        # Clear any stale widget keys from a previous run
        for k in list(st.session_state.keys()):
            if k.startswith(("chk_", "cause_")):
                del st.session_state[k]
        st.session_state["phase_i_pass1"] = pass1
        st.session_state["phase_i_stage"] = "pass1_done"
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STAGE pass1_done — show chart + analyst decision table
# ══════════════════════════════════════════════════════════════════════════════
elif stage == "pass1_done":
    pass1 = st.session_state["phase_i_pass1"]
    lim   = pass1.limits

    # Relabel values/mr with original dates for chart display
    vals = pass1.values.copy()
    vals.index = pass1.original_labels
    mr = pass1.mr.copy()
    mr.index = pass1.original_labels

    # ── Pass 1 chart ──────────────────────────────────────────────────────────
    st.subheader("Pass 1 — I-MR Chart")
    fig = build_imr_panel(
        vals, mr, lim,
        violations=pass1.individual_violations,
        mr_violations=pass1.mr_violations,
        title="Pass 1 — All Data",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Control lines (Pass 1)", expanded=False):
        lim_df = pd.DataFrame({
            "Chart": ["I"] * 5 + ["MR"] * 2,
            "Line":  ["UAL", "UWL", "CL", "LWL", "LAL", "UAL", "CL"],
            "Value": [
                lim["i_ucl"], lim["i_uwl"], lim["i_cl"],
                lim["i_lwl"], lim["i_lcl"],
                lim["mr_ucl"], lim["mr_cl"],
            ],
        })
        st.dataframe(lim_df.style.format({"Value": "{:.4f}"}), use_container_width=True)

    st.divider()

    flagged_ints = pass1.flagged_integer_indices

    # ── No violations ─────────────────────────────────────────────────────────
    if not flagged_ints:
        st.success(
            f"✅ **No violations detected.** The process is in statistical control.  "
            f"All **{pass1.n_original}** observations are retained as the baseline."
        )
        col_a, col_b = st.columns([2, 6])
        if col_a.button("✅ Accept baseline", type="primary"):
            result = PhaseIResult(
                final_values=pass1.values,
                final_mr=compute_moving_range(pass1.values),
                final_limits=pass1.limits,
                original_labels=pass1.original_labels,
                n_original=pass1.n_original,
                n_final=pass1.n_original,
                n_total_removed=0,
                rule_config=pass1.rule_config,
                audit_log=pd.DataFrame(),
                n_passes=1,
                final_pass_has_violations=False,
            )
            st.session_state["phase_i_result"] = result
            st.session_state["phase_i_pass2"]  = None
            st.session_state["phase_i_stage"]  = "final"
            st.rerun()
        col_b.button("🔄 Start over", on_click=_reset_phase_i)

    # ── Violations present: decision table ────────────────────────────────────
    else:
        st.subheader(f"Flagged Points — {len(flagged_ints)} candidate(s) for review")
        st.warning(
            "**Oakland principle:** Statistical rules flag *candidates* — not confirmed "
            "special causes.  For each point, decide whether you can document a "
            "real-world assignable cause.  **If you cannot, retain the point** — "
            "it represents common-cause variation inherent to the process."
        )

        # Header row
        h = st.columns([2.5, 1.5, 2.5, 0.8, 3.7])
        h[0].markdown("**Observation**")
        h[1].markdown("**Value**")
        h[2].markdown("**Rules Fired**")
        h[3].markdown("**Remove?**")
        h[4].markdown("**Assignable Cause** *(required to remove)*")
        st.markdown("---")

        decisions: dict[int, dict] = {}
        for int_idx in flagged_ints:
            label    = pass1.original_labels[int_idx]
            value    = float(pass1.values.iloc[int_idx])
            row_viol = pass1.individual_violations.iloc[int_idx]
            rules    = [r for r in ["rule1", "rule2", "rule3", "rule4"]
                        if bool(row_viol[r])]
            if bool(pass1.mr_violations.iloc[int_idx]):
                rules.append("mr_rule1")

            cols = st.columns([2.5, 1.5, 2.5, 0.8, 3.7])
            cols[0].write(str(label))
            cols[1].write(f"{value:.4f}")
            cols[2].write(", ".join(rules))
            remove = cols[3].checkbox(
                "remove", key=f"chk_{int_idx}", value=False,
                label_visibility="collapsed",
            )
            cause = cols[4].text_input(
                "cause", key=f"cause_{int_idx}",
                placeholder="e.g. Sensor fault on this date",
                label_visibility="collapsed",
            )
            decisions[int_idx] = {"remove": remove, "cause": cause}

        st.divider()
        col_confirm, col_reset = st.columns([2, 6])

        if col_confirm.button("✅ Confirm decisions", type="primary"):
            # Validate: removal requires a documented cause
            errors = [
                f"**{pass1.original_labels[i]}** — assignable cause is required before removal."
                for i, d in decisions.items()
                if d["remove"] and not d["cause"].strip()
            ]
            if errors:
                for e in errors:
                    st.error(e)
            else:
                to_remove_ints = [i for i, d in decisions.items() if d["remove"]]

                # Build audit log for all flagged points
                audit_rows = []
                for int_idx, dec in decisions.items():
                    lbl = pass1.original_labels[int_idx]
                    val = float(pass1.values.iloc[int_idx])
                    rv  = pass1.individual_violations.iloc[int_idx]
                    r   = [r for r in ["rule1", "rule2", "rule3", "rule4"] if bool(rv[r])]
                    if bool(pass1.mr_violations.iloc[int_idx]):
                        r.append("mr_rule1")
                    audit_rows.append({
                        "pass":             1,
                        "observation":      str(lbl),
                        "value":            val,
                        "rules_violated":   ", ".join(r),
                        "decision":         "Removed" if dec["remove"] else "Retained (analyst decision)",
                        "assignable_cause": dec["cause"].strip(),
                        "x_bar":            pass1.limits["i_cl"],
                        "ual":              pass1.limits["i_ucl"],
                        "lal":              pass1.limits["i_lcl"],
                    })
                audit_df = pd.DataFrame(audit_rows).set_index("observation")

                # ── No removals: Pass 1 is the certified baseline ─────────────
                if not to_remove_ints:
                    result = PhaseIResult(
                        final_values=pass1.values,
                        final_mr=compute_moving_range(pass1.values),
                        final_limits=pass1.limits,
                        original_labels=pass1.original_labels,
                        n_original=pass1.n_original,
                        n_final=pass1.n_original,
                        n_total_removed=0,
                        rule_config=pass1.rule_config,
                        audit_log=audit_df,
                        n_passes=1,
                        final_pass_has_violations=True,
                    )
                    st.session_state["phase_i_result"] = result
                    st.session_state["phase_i_pass2"]  = None
                    st.session_state["phase_i_stage"]  = "final"
                    st.rerun()

                # ── Run Pass 2 on cleaned data ────────────────────────────────
                else:
                    # Use original iloc positions for duplicate-safe removal
                    ilocs_to_remove = {int(pass1.original_ilocs[i]) for i in to_remove_ints}
                    keep_mask = np.array([
                        i not in ilocs_to_remove for i in range(len(raw_values))
                    ])
                    clean_raw = raw_values.iloc[keep_mask]

                    with st.spinner("Running Pass 2…"):
                        pass2 = run_phase_i_pass(clean_raw, **pass1.rule_config)

                    result = PhaseIResult(
                        final_values=pass2.values,
                        final_mr=compute_moving_range(pass2.values),
                        final_limits=pass2.limits,
                        original_labels=pass2.original_labels,
                        n_original=pass1.n_original,
                        n_final=pass2.n_original,
                        n_total_removed=len(to_remove_ints),
                        rule_config=pass1.rule_config,
                        audit_log=audit_df,
                        n_passes=2,
                        final_pass_has_violations=pass2.any_violations,
                    )
                    st.session_state["phase_i_result"] = result
                    st.session_state["phase_i_pass2"]  = pass2
                    st.session_state["phase_i_stage"]  = "final"
                    st.rerun()

        col_reset.button("🔄 Start over", on_click=_reset_phase_i)

# ══════════════════════════════════════════════════════════════════════════════
# STAGE final — certified baseline summary
# ══════════════════════════════════════════════════════════════════════════════
elif stage == "final":
    result = st.session_state["phase_i_result"]
    pass1  = st.session_state["phase_i_pass1"]
    pass2  = st.session_state.get("phase_i_pass2")
    lim    = result.final_limits
    removal_pct = 100 * result.n_total_removed / result.n_original if result.n_original else 0

    # ── Summary banner ────────────────────────────────────────────────────────
    if result.n_total_removed == 0 and not result.final_pass_has_violations:
        st.success(
            f"✅ **Process in statistical control — no violations.**  "
            f"All **{result.n_original}** observations retained as the baseline."
        )
    elif result.n_total_removed == 0 and result.final_pass_has_violations:
        st.warning(
            f"⚠️ **Baseline certified — analyst retained all flagged points.**  "
            f"Limits reflect the full dataset including acknowledged variation.  "
            f"Reviewed: **{len(pass1.flagged_integer_indices)}** candidate(s)."
        )
    elif not result.final_pass_has_violations:
        st.success(
            f"✅ **Pass 2 complete — process in statistical control.**  "
            f"**{result.n_total_removed}** of {result.n_original} point(s) removed "
            f"({removal_pct:.1f}%). Baseline certified."
        )
    else:
        st.warning(
            f"⚠️ **Pass 2 complete — {result.n_total_removed} point(s) removed "
            f"({removal_pct:.1f}%).  Pass 2 still shows violations.**  "
            "Remaining violations may be common-cause variation. "
            "Do not attempt further removal without fresh process evidence."
        )

    # ── Metrics ───────────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("N (final)",    result.n_final)
    m2.metric("Mean (X̄)",    f"{lim['i_cl']:.4f}")
    m3.metric("UAL",          f"{lim['i_ucl']:.4f}")
    m4.metric("LAL",          f"{lim['i_lcl']:.4f}")
    m5.metric("σ̂ (within)",  f"{lim['sigma_within']:.4f}")

    st.divider()

    # ── Final I-MR chart ──────────────────────────────────────────────────────
    final_vals = result.final_values.copy()
    final_vals.index = result.original_labels
    final_mr = result.final_mr.copy()
    final_mr.index = result.original_labels

    final_viol = apply_all_rules(
        final_vals, lim,
        rule2_k=result.rule_config["rule2_k"],
        rule2_window=result.rule_config["rule2_window"],
        rule3_k=result.rule_config["rule3_k"],
        rule4_k=result.rule_config["rule4_k"],
    )
    final_mr_viol = apply_mr_rule1(final_vals, lim["mr_ucl"])

    st.subheader(f"Final I-MR Chart (Pass {result.n_passes})")
    fig = build_imr_panel(
        final_vals, final_mr, lim,
        violations=final_viol,
        mr_violations=final_mr_viol,
        title=f"Certified Baseline — Pass {result.n_passes}",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.success("Navigate to **Final Charts**, **Capability**, or **Audit Trail** to continue.")
    st.button("🔄 Start over / new run", on_click=_reset_phase_i)

    st.success("Data appears normally distributed (α = 0.05). Shewhart limits are valid.")

st.divider()

