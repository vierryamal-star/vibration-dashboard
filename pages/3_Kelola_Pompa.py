import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS

try:
    st.set_page_config(
        page_title="Kelola Pompa & Jam Operasi — PLTU TBK",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# Sembunyikan menu navigasi bawaan Streamlit agar tidak dobel
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
render_page_header("⏱️ Kelola Pompa & Running Hours")

st.write("")

with st.container(border=True):
    st.subheader("🚀 Portal Monitoring Bearing & Jam Operasi")
    st.write(
        "Sistem monitoring running hours, rotasi peralatan, dan umur bearing "
        "dikelola secara terpusat pada aplikasi web eksternal."
    )
    
    st.info("🔑 **Kredensial Login:**\n\n- **Username:** `viewer`\n- **Password:** `viewer123`")
    
    st.write("")
    st.link_button(
        "🌐 Buka Aplikasi Bearing Monitoring (Vercel)",
        "https://bearing-monitoring.vercel.app/",
        type="primary",
        use_container_width=True,
    )

st.write("")

with st.expander("📌 Cakupan Peralatan yang Dipantau"):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Unit Turbin #1 & #2**")
        st.caption("Booster Pump (BP A-D), Condensate Pump (CP A-D), CWP, Water Jet Pump, Cooling Tower.")
    with col2:
        st.markdown("**Area Boiler #1 & #2**")
        st.caption("ID Fan, FD Fan, Secondary Air Fan, Motor Screw Feeder, Motor Spreader, Multicyclone, Ash Cooler.")
    with col3:
        st.markdown("**Common & Coal Handling**")
        st.caption("Make Up Pump, Sea Water Intake (SWI A-C), RO Pump, Belt Conveyor (BC 01-04), Tripper.")
