"""Home page."""

import streamlit as st

st.title("SPC Analysis — Statistical Process Control")
st.markdown(
    """
    **Phase I retrospective baseline establishment for Individual (I) and Moving Range (MR) charts.**

    Use the sidebar to navigate between steps.  A typical workflow is:

    1. **Data Import** — Upload your measurement data (CSV or Excel).
    2. **Phase I Study** — Run the iterative SPC loop to establish stable control limits.
    3. **Final Charts** — Inspect the final I-MR charts with clean data and verified limits.
    4. **Capability** — Evaluate Cp, Cpk, Pp, Ppk against your process tolerances.
    5. **Audit Trail** — Review every removed point with its rule justification.
    """
)

st.info("👈 Select a page from the sidebar to begin.")
