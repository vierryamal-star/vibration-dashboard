import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS, load_history

try:
    st.set_page_config(
        page_title="Datasheet Peralatan — PLTU TBK",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# Sembunyikan navigasi bawaan Streamlit agar sidebar menu tidak dobel
st.markdown("""
<style>
[data-testid="stSidebarNav"] {
    display: none !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("📋 Datasheet & Spesifikasi Peralatan")
st.caption("Pusat informasi teknis, nomor bearing, pelumasan, dan spesifikasi mesin PLTU TBK.")

# ── Database Master Datasheet Peralatan ────────────────────────────────────
# Dapat disesuaikan atau diper
