"""Page 2 — Phase I SPC Study (multi-variable Oakland two-pass workflow).

Each selected measurement variable gets its own independent Phase I study,
displayed in a separate tab.  When a variable completes Phase I, observations
it removed are cross-flagged as "suspect" in all other variables' decision
tables — the analyst is free to retain them, but the evidence is surfaced.

Workflow (per variable)
───────────────────────
Pass 1:  Compute limits and flag statistical candidates for review.
         The analyst reviews each flagged point and decides whether to remove it.
         Per Oakland (Ch. 4–5): removal requires a documented assignable cause.

Pass 2:  If any removals were made, re-evaluate the cleaned data.
         The result of Pass 2 (or Pass 1 if no removals) is the certified
         baseline stored in phase_i_results[col].
"""

import numpy as np
import pandas as pd
import streamlit as st

from spc.core import normality_check, run_phase_i_pass, PhaseIResult
from spc.core.limits import compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1
from spc.charts import build_imr_panel

st.header("🔄 Phase I Study")

if "raw_df" not in st.session_state:
    st.warning("No data loaded. Please go to **Data Import** first.")
    st.stop()

raw_df: pd.DataFrame = st.session_state["raw_df"]
value_cols: list[str] = st.session_state["value_cols"]

# ── Normality pre-check ───────────────────────────────────────────────────────
with st.expander("🔬 Normality Pre-Check", expanded=False):
    for i, col in enumerate(value_cols):
        if i:
            st.divider()
        st.markdown(f"**{col}**")
        norm = normality_check(raw_df[col])
        nc1, nc2, nc3 = st.columns(3)
        nc1.metric("Test", norm["test_name"])
        nc2.metric("Statistic", f"{norm['statistic']:.4f}" if norm["statistic"] else "N/A")
        p_lbl = f"{norm['p_value']:.4f}" if norm["p_value"] is not None else "—"
        nc3.metric("p-value", p_lbl)
        if norm["warning_message"]:
            st.warning(norm["warning_message"])
        else:
            st.success("Normally distributed (α = 0.05). Shewhart limits are valid.")

st.divider()


# ── Reset helper ──────────────────────────────────────────────────────────────
def _reset_phase_i() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith(("phase_i_", "chk_", "cause_")):
            del st.session_state[k]


# ── Global rule config ────────────────────────────────────────────────────────
with st.expander("⚙️ Rule thresholds (applied to all variables)", expanded=False):
    gc1, gc2, gc3, gc4 = st.columns(4)
    rule2_k      = gc1.number_input("Rule 2 — k points",    min_value=1, max_value=5,  value=2)
    rule2_window = gc2.number_input("Rule 2 — window",       min_value=2, max_value=10, value=3)
    rule3_k      = gc3.number_input("Rule 3 — run length",   min_value=4, max_value=15, value=8)
    rule4_k      = gc4.number_input("Rule 4 — trend length", min_value=4, max_value=12, value=6)

_rule_cfg = {
    "rule2_k":      int(rule2_k),
    "rule2_window": int(rule2_window),
    "rule3_k":      int(rule3_k),
    "rule4_k":      int(rule4_k),
}

st.info(
    "**Oakland principle (Ch. 4–5)** — This tool flags statistical candidates "
    "for removal. It never removes data automatically. You will review each "
    "flagged point and provide a documented assignable cause before any "
    "removal is accepted into the baseline."
)


# ── Cross-flag helper ─────────────────────────────────────────────────────────
def _cross_flagged_info(col: str) -> dict[str, list[str]]:
    """Return {obs_label: [other_col, ...]} for labels removed from other variables."""
    results: dict = st.session_state.get("phase_i_results", {})
    info: dict[str, list[str]] = {}
    for other_col, res in results.items():
        if other_col == col or res is None:
            continue
        if not res.audit_log.empty:
            removed = (
                res.audit_log[res.audit_log["decision"] == "Removed"]
                .index.tolist()
            )
            for lbl in removed:
                info.setdefault(str(lbl), []).append(other_col)
    return info


# ── Finalise helper ───────────────────────────────────────────────────────────
def _finalise(
    col: str,
    pass1,
    audit_df: pd.DataFrame,
    to_remove_ints: list[int],
    raw_series: pd.Series,
) -> None:
    """Build PhaseIResult (1 or 2 passes) and persist to session_state."""
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
            final_pass_has_violations=not audit_df.empty,
        )
        st.session_state[f"phase_i_pass2__{col}"] = None
    else:
        ilocs_to_remove = {int(pass1.original_ilocs[i]) for i in to_remove_ints}
        keep_mask = np.array([
            i not in ilocs_to_remove for i in range(len(raw_series))
        ])
        clean_raw = raw_series.iloc[keep_mask]
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
        st.session_state[f"phase_i_pass2__{col}"] = pass2

    st.session_state.setdefault("phase_i_results", {})[col] = result
    st.session_state[f"phase_i_stage__{col}"] = "final"
    st.rerun()


# ── Per-variable Phase I renderer ─────────────────────────────────────────────
def _render_variable(col: str, raw_series: pd.Series) -> None:
    stage = st.session_state.get(f"phase_i_stage__{col}", "idle")

    # ══ IDLE ══════════════════════════════════════════════════════════════════
    if stage == "idle":
        if st.button("▶ Run Pass 1", type="primary", key=f"run_p1__{col}"):
            with st.spinner("Evaluating Pass 1…"):
                pass1 = run_phase_i_pass(raw_series, **_rule_cfg)
            # Clear stale widget keys for this variable
            for k in list(st.session_state.keys()):
                if k.startswith((f"chk__{col}__", f"cause__{col}__")):
                    del st.session_state[k]
            # Pre-suggest removal for cross-flagged observations
            cross_info = _cross_flagged_info(col)
            for int_idx in pass1.flagged_integer_indices:
                lbl_str = str(pass1.original_labels[int_idx])
                if lbl_str in cross_info:
                    st.session_state.setdefault(f"chk__{col}__{int_idx}", True)
            st.session_state[f"phase_i_pass1__{col}"] = pass1
            st.session_state[f"phase_i_stage__{col}"] = "pass1_done"
            st.rerun()

    # ══ PASS 1 DONE ═══════════════════════════════════════════════════════════
    elif stage == "pass1_done":
        pass1 = st.session_state[f"phase_i_pass1__{col}"]
        lim   = pass1.limits

        vals = pass1.values.copy()
        vals.index = pass1.original_labels
        mr = pass1.mr.copy()
        mr.index = pass1.original_labels

        st.subheader("Pass 1 — I-MR Chart")
        fig = build_imr_panel(
            vals, mr, lim,
            violations=pass1.individual_violations,
            mr_violations=pass1.mr_violations,
            title=f"Pass 1 — {col}",
        )
        st.plotly_chart(fig, width='stretch')

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
            st.dataframe(lim_df.style.format({"Value": "{:.4f}"}), width='stretch')

        st.divider()
        flagged_ints = pass1.flagged_integer_indices
        cross_info   = _cross_flagged_info(col)

        # ── No violations ──────────────────────────────────────────────────────
        if not flagged_ints:
            st.success(
                f"✅ **No violations detected.** All **{pass1.n_original}** observations "
                "retained as the baseline."
            )
            cl1, cl2 = st.columns([2, 6])
            if cl1.button("✅ Accept baseline", type="primary", key=f"accept__{col}"):
                _finalise(col, pass1, pd.DataFrame(), [], raw_series)
            cl2.button("🔄 Start over", on_click=_reset_phase_i, key=f"reset_p1__{col}")

        # ── Violations: decision table ─────────────────────────────────────────
        else:
            n_cross = sum(
                1 for i in flagged_ints if str(pass1.original_labels[i]) in cross_info
            )
            if n_cross:
                st.warning(
                    f"⚠️ **{n_cross} of these point(s)** were also removed from another variable.  "
                    "Their removal is pre-suggested below — you still need to provide an "
                    "assignable cause to confirm."
                )
            else:
                st.warning(
                    "**Oakland principle:** Statistical rules flag *candidates* — not confirmed "
                    "special causes. For each point, decide whether you can document a "
                    "real-world assignable cause.  **If you cannot, retain the point.**"
                )

            expander_label = (
                f"🔍 Review {len(flagged_ints)} flagged point(s)"
                + (f"  — {n_cross} cross-flagged ⚠️" if n_cross else "")
            )
            decisions: dict[int, dict] = {}
            with st.expander(expander_label, expanded=False):
                h = st.columns([2.5, 1.5, 2.5, 0.8, 3.7])
                h[0].markdown("**Observation**")
                h[1].markdown("**Value**")
                h[2].markdown("**Rules Fired**")
                h[3].markdown("**Remove?**")
                h[4].markdown("**Assignable Cause** *(required to remove)*")
                st.markdown("---")
                for int_idx in flagged_ints:
                    label     = pass1.original_labels[int_idx]
                    value     = float(pass1.values.iloc[int_idx])
                    row_viol  = pass1.individual_violations.iloc[int_idx]
                    rules     = [r for r in ["rule1", "rule2", "rule3", "rule4"]
                                 if bool(row_viol[r])]
                    if bool(pass1.mr_violations.iloc[int_idx]):
                        rules.append("mr_rule1")

                    lbl_str   = str(label)
                    is_cross  = lbl_str in cross_info

                    # Pre-suggest removal if cross-flagged (only on first render)
                    if is_cross and f"chk__{col}__{int_idx}" not in st.session_state:
                        st.session_state[f"chk__{col}__{int_idx}"] = True

                    rules_md = ", ".join(rules)
                    if is_cross:
                        sources = ", ".join(cross_info[lbl_str])
                        rules_md += f"  ⚠️ *suspect: removed from {sources}*"

                    row_cols = st.columns([2.5, 1.5, 2.5, 0.8, 3.7])
                    row_cols[0].write(lbl_str)
                    row_cols[1].write(f"{value:.4f}")
                    row_cols[2].markdown(rules_md)
                    remove = row_cols[3].checkbox(
                        "remove", key=f"chk__{col}__{int_idx}",
                        label_visibility="collapsed",
                    )
                    cause = row_cols[4].text_input(
                        "cause", key=f"cause__{col}__{int_idx}",
                        placeholder="e.g. Sensor fault on this date",
                        label_visibility="collapsed",
                    )
                    decisions[int_idx] = {"remove": remove, "cause": cause}

            st.divider()
            col_confirm, col_reset = st.columns([2, 6])

            if col_confirm.button("✅ Confirm decisions", type="primary", key=f"confirm__{col}"):
                errors = [
                    f"**{pass1.original_labels[i]}** — assignable cause required before removal."
                    for i, d in decisions.items()
                    if d["remove"] and not d["cause"].strip()
                ]
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    to_remove_ints = [i for i, d in decisions.items() if d["remove"]]
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
                    _finalise(col, pass1, audit_df, to_remove_ints, raw_series)

            col_reset.button("🔄 Start over", on_click=_reset_phase_i, key=f"reset_p1d__{col}")

    # ══ FINAL ═════════════════════════════════════════════════════════════════
    elif stage == "final":
        result = st.session_state["phase_i_results"][col]
        pass1  = st.session_state[f"phase_i_pass1__{col}"]
        lim    = result.final_limits
        removal_pct = 100 * result.n_total_removed / result.n_original if result.n_original else 0

        if result.n_total_removed == 0 and not result.final_pass_has_violations:
            st.success(
                f"✅ **Process in statistical control — no violations.**  "
                f"All **{result.n_original}** observations retained."
            )
        elif result.n_total_removed == 0:
            st.warning(
                f"⚠️ **Baseline certified — analyst retained all flagged points.**  "
                f"Reviewed: **{len(pass1.flagged_integer_indices)}** candidate(s)."
            )
        elif not result.final_pass_has_violations:
            st.success(
                f"✅ **Pass 2 complete — in statistical control.**  "
                f"**{result.n_total_removed}** of {result.n_original} point(s) removed "
                f"({removal_pct:.1f}%). Baseline certified."
            )
        else:
            st.warning(
                f"⚠️ **Pass 2 — {result.n_total_removed} point(s) removed "
                f"({removal_pct:.1f}%).  Remaining violations may be common-cause.  "
                "Do not attempt further removal without fresh process evidence."
            )

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("N (final)",   result.n_final)
        m2.metric("Mean (X̄)",   f"{lim['i_cl']:.4f}")
        m3.metric("UAL",         f"{lim['i_ucl']:.4f}")
        m4.metric("LAL",         f"{lim['i_lcl']:.4f}")
        m5.metric("σ̂ (within)", f"{lim['sigma_within']:.4f}")

        st.divider()

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
        final_mr_viol = apply_mr_rule1(final_mr, lim["mr_ucl"])

        st.subheader(f"Final I-MR Chart (Pass {result.n_passes})")
        fig = build_imr_panel(
            final_vals, final_mr, lim,
            violations=final_viol,
            mr_violations=final_mr_viol,
            title=f"Certified Baseline — {col} (Pass {result.n_passes})",
        )
        st.plotly_chart(fig, width='stretch')

        st.divider()
        st.success("Navigate to **Final Charts**, **Capability**, or **Audit Trail** to continue.")
        st.button("🔄 Start over / new run", on_click=_reset_phase_i, key=f"reset_final__{col}")


# ── Variable tabs ─────────────────────────────────────────────────────────────
if len(value_cols) == 1:
    _render_variable(value_cols[0], raw_df[value_cols[0]])
else:
    tabs = st.tabs(value_cols)
    for tab, col in zip(tabs, value_cols):
        with tab:
            _render_variable(col, raw_df[col])


# ── Cross-variable summary (shown when ≥2 variables have completed Phase I) ───
if len(value_cols) >= 2:
    results: dict = st.session_state.get("phase_i_results", {})
    completed = [c for c in value_cols if c in results and results[c] is not None]

    if len(completed) >= 2:
        st.divider()
        st.subheader("🔗 Cross-Variable Analysis")
        st.markdown(
            "Observations removed from **multiple variables** on the same machine "
            "likely share a common assignable cause (equipment event, environmental "
            "disturbance, etc.).  These are the highest-priority items to investigate."
        )

        # Build {label: [cols it was removed from]}
        all_removed: dict[str, list[str]] = {}
        for col in completed:
            res = results[col]
            if not res.audit_log.empty:
                for lbl in res.audit_log[res.audit_log["decision"] == "Removed"].index:
                    all_removed.setdefault(str(lbl), []).append(col)

        shared   = {lbl: cols for lbl, cols in all_removed.items() if len(cols) >= 2}
        only_one = {lbl: cols for lbl, cols in all_removed.items() if len(cols) == 1}

        ca, cb = st.columns(2)
        ca.metric("Removed from ≥2 variables",      len(shared))
        cb.metric("Removed from exactly 1 variable", len(only_one))

        if shared:
            st.markdown("**Observations removed from multiple variables:**")
            cross_df = pd.DataFrame([
                {"Observation": lbl, "Removed from": ", ".join(cols)}
                for lbl, cols in sorted(shared.items())
            ])
            st.dataframe(cross_df, width='stretch')
        else:
            st.info("No observations were removed from more than one variable simultaneously.")


