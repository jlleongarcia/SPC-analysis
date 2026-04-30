"""SPC Analysis — main Streamlit entry point.

Run with:
    uv run streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="SPC Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation (st.navigation gives full control over sidebar labels) ─────────
home = st.Page(
    "pages/00_Home.py",
    title="Home",
    icon="📊",
    default=True,
)
data_import   = st.Page("pages/01_Data_Import.py",   title="Data Import",   icon="📂")
phase_i       = st.Page("pages/02_Phase_I.py",        title="Phase I Study", icon="🔄")
final_charts  = st.Page("pages/03_Final_Charts.py",   title="Final Charts",  icon="📈")
capability    = st.Page("pages/04_Capability.py",     title="Capability",    icon="⚙️")
audit_trail   = st.Page("pages/05_Audit_Trail.py",    title="Audit Trail",   icon="📋")

pg = st.navigation([home, data_import, phase_i, final_charts, capability, audit_trail])
pg.run()
