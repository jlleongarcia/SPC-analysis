"""Page 6 — Documentation.

Renders the user guide and methodology documents directly inside the app,
so users never need to leave to consult external files.
"""

from pathlib import Path

import streamlit as st

DOCS_DIR = Path(__file__).parent.parent / "docs"

st.header("📚 Documentation")

tab_guide, tab_method = st.tabs(["User Guide", "Methodology"])

with tab_guide:
    guide_path = DOCS_DIR / "user_guide.md"
    st.markdown(guide_path.read_text(encoding="utf-8"))

with tab_method:
    method_path = DOCS_DIR / "methodology.md"
    st.markdown(method_path.read_text(encoding="utf-8"))
