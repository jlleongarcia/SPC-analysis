"""Page 1 — Data Import.

Accepts CSV or Excel files.  The user selects which column contains the
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
    - One column must contain the **individual measurement value**.
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
    numeric_cols = df_raw.select_dtypes(include="number").columns.tolist()
    all_cols = df_raw.columns.tolist()

    if not numeric_cols:
        st.error("No numeric columns found. Please check your file.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        value_col = st.selectbox(
            "Measurement column",
            options=numeric_cols,
            help="The column containing individual process measurements.",
        )
    with col2:
        label_col = st.selectbox(
            "Observation label column (optional)",
            options=["— none —"] + all_cols,
            help="Date, batch ID, or sequence number. Used as the chart x-axis.",
        )

    # ── Preview selected series ───────────────────────────────────────────────
    values: pd.Series = df_raw[value_col].copy()

    if label_col != "— none —":
        values.index = df_raw[label_col].astype(str)
        values.index.name = label_col
    else:
        values.index = range(1, len(values) + 1)
        values.index.name = "Observation"

    n_missing = values.isna().sum()
    st.markdown(
        f"**{values.notna().sum():,}** valid observations  |  "
        f"**{n_missing}** missing (will be excluded from computations)"
    )

    # ── Confirm and store ─────────────────────────────────────────────────────
    if st.button("✅ Confirm and proceed →", type="primary"):
        st.session_state["raw_values"] = values
        st.session_state["value_col"] = value_col
        # Clear any previous Phase I state so downstream pages start fresh
        for _k in list(st.session_state.keys()):
            if _k.startswith(("phase_i_", "chk_", "cause_")):
                del st.session_state[_k]
        st.success("Data stored. Navigate to **Phase I Study** in the sidebar.")

elif "raw_values" in st.session_state:
    st.info(
        f"Currently loaded: **{len(st.session_state['raw_values']):,}** observations "
        f"(column: *{st.session_state.get('value_col', '?')}*).  "
        "Upload a new file to replace."
    )

# ── Sample data generator ─────────────────────────────────────────────────────
with st.expander("📎 No file yet? Generate sample data"):
    import numpy as np

    st.markdown(
        "Generate a synthetic dataset to explore the tool.  "
        "A small number of out-of-control points are injected automatically."
    )
    n_obs = st.slider("Number of observations", 30, 300, 80)
    mean_val = st.number_input("Process mean", value=100.0)
    std_val = st.number_input("Process std dev", value=2.5, min_value=0.01)

    if st.button("Generate sample dataset"):
        rng = np.random.default_rng(42)
        data = rng.normal(mean_val, std_val, n_obs)
        # Inject a few obvious out-of-control points
        ooc_idx = rng.choice(n_obs, size=max(2, n_obs // 20), replace=False)
        data[ooc_idx] += rng.choice([-1, 1], size=len(ooc_idx)) * std_val * 4

        sample_df = pd.DataFrame({"observation": range(1, n_obs + 1), "value": data})
        csv_bytes = sample_df.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download sample CSV",
            data=csv_bytes,
            file_name="spc_sample_data.csv",
            mime="text/csv",
        )
        st.dataframe(sample_df.head(10))
