"""Page 1 — Data Import.

Accepts CSV or Excel files.  The user selects one or more columns containing
measurements and optionally which column to use as the observation label/date.
The parsed data is stored in st.session_state for downstream pages.
"""

import io

import pandas as pd
import streamlit as st

st.header("📂 Data Import")

st.markdown(
    """
    Upload a **CSV** or **Excel** file containing your process measurements.

    - Each row should represent **one observation** (one day, one batch, one sample…).
    - Select **one or more** numeric columns as measurement variables.
    - An optional column can serve as the **observation label** (date, batch ID, etc.).
    """
)

# ── File upload ───────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload data file", type=["csv", "xlsx", "xls"])

if uploaded is not None:
    try:
        if uploaded.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded)
        else:
            df_raw = pd.read_excel(uploaded)
    except Exception as exc:
        st.error(f"Could not read file: {exc}")
        st.stop()

    st.success(f"Loaded {len(df_raw):,} rows × {len(df_raw.columns)} columns.")
    st.dataframe(df_raw.head(20), use_container_width=True)

    # ── Column selection ──────────────────────────────────────────────────────
    # Primary: natively numeric dtypes
    numeric_cols = df_raw.select_dtypes(include="number").columns.tolist()
    # Fallback: object columns where ≥80 % of values coerce to a number
    # (handles CSVs with mixed text sentinels or European decimal formats)
    # Datetime columns are explicitly skipped — they must never be treated as measurements.
    _already = set(numeric_cols)
    for _c in df_raw.columns:
        if _c in _already:
            continue
        if pd.api.types.is_datetime64_any_dtype(df_raw[_c]):
            continue
        _converted = pd.to_numeric(df_raw[_c], errors="coerce")
        if _converted.notna().mean() >= 0.8:
            numeric_cols.append(_c)
    all_cols = df_raw.columns.tolist()

    if not numeric_cols:
        st.error("No numeric columns found. Please check your file.")
        st.stop()

    col1, col2 = st.columns(2)
    with col2:
        label_col = st.selectbox(
            "Observation label column (optional)",
            options=["— none —"] + all_cols,
            help="Date, batch ID, or sequence number. Used as the chart x-axis.",
        )
    # Exclude the chosen label column from measurement options — dates/IDs must
    # not be analysed by SPC or normality tests.
    meas_options = [c for c in numeric_cols if c != label_col]
    if not meas_options:
        st.error("No numeric measurement columns remain after excluding the label column.")
        st.stop()
    with col1:
        value_cols = st.multiselect(
            "Measurement column(s)",
            options=meas_options,
            default=meas_options,           # pre-select all eligible numeric columns
            help="Select one or more columns containing individual process measurements.",
        )

    if not value_cols:
        st.warning("Select at least one measurement column.")
        st.stop()

    # ── Build labeled DataFrame ───────────────────────────────────────────────
    # Coerce selected columns to numeric (handles object dtype from the fallback detection)
    df_labeled = df_raw[value_cols].apply(pd.to_numeric, errors="coerce").copy()
    if label_col != "— none —":
        df_labeled.index = df_raw[label_col].astype(str)
        df_labeled.index.name = label_col
    else:
        df_labeled.index = range(1, len(df_labeled) + 1)
        df_labeled.index.name = "Observation"

    # ── Preview selected columns ──────────────────────────────────────────────
    preview_cols = st.columns(len(value_cols))
    for i, col in enumerate(value_cols):
        n_valid   = df_labeled[col].notna().sum()
        n_missing = df_labeled[col].isna().sum()
        preview_cols[i].metric(col, f"{n_valid:,} valid", delta=f"{n_missing} missing" if n_missing else None)

    # ── Confirm and store ─────────────────────────────────────────────────────
    if st.button("✅ Confirm and proceed →", type="primary"):
        st.session_state["raw_df"]    = df_labeled
        st.session_state["value_cols"] = value_cols
        # Clear any previous Phase I state so downstream pages start fresh
        for _k in list(st.session_state.keys()):
            if _k.startswith(("phase_i_", "chk_", "cause_")):
                del st.session_state[_k]
        vcols_str = ", ".join(f"**{c}**" for c in value_cols)
        st.success(f"Data stored ({vcols_str}). Navigate to **Phase I Study** in the sidebar.")

elif "raw_df" in st.session_state:
    raw_df  = st.session_state["raw_df"]
    vc      = st.session_state.get("value_cols", [])
    vcols_str = ", ".join(f"*{c}*" for c in vc)
    st.info(
        f"Currently loaded: **{len(raw_df):,}** observations  |  "
        f"**{len(vc)}** variable(s): {vcols_str}.  "
        "Upload a new file to replace."
    )

# ── Sample data generator ─────────────────────────────────────────────────────
with st.expander("📎 No file yet? Generate sample data"):
    import numpy as np

    st.markdown(
        "Generate a synthetic dataset with **two correlated measurement variables** "
        "on the same machine.  A small number of out-of-control points are injected "
        "at the same observations for both variables — demonstrating cross-variable flagging."
    )
    n_obs = st.slider("Number of observations", 30, 300, 80)
    mean_val = st.number_input("Process mean (variable A)", value=100.0)
    std_val  = st.number_input("Process std dev",            value=2.5,  min_value=0.01)

    if st.button("Generate sample dataset"):
        rng     = np.random.default_rng(42)
        data_a  = rng.normal(mean_val, std_val, n_obs)
        # Variable B is correlated with A (same machine, different characteristic)
        data_b  = data_a * 0.6 + rng.normal(mean_val * 0.4, std_val * 0.8, n_obs)
        # Inject the same out-of-control events in both
        ooc_idx = rng.choice(n_obs, size=max(2, n_obs // 20), replace=False)
        signs   = rng.choice([-1, 1], size=len(ooc_idx))
        data_a[ooc_idx] += signs * std_val * 4
        data_b[ooc_idx] += signs * std_val * 3

        sample_df = pd.DataFrame({
            "observation":   range(1, n_obs + 1),
            "measurement_A": data_a,
            "measurement_B": data_b,
        })
        csv_bytes = sample_df.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download sample CSV",
            data=csv_bytes,
            file_name="spc_sample_data.csv",

            mime="text/csv",
        )
        st.dataframe(sample_df.head(10))
