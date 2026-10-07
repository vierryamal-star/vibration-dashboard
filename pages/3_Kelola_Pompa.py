import streamlit as st
import streamlit.components.v1 as components
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS

try:
    st.set_page_config(
        page_title="Jam Operasi & Monitoring — PLTU TBK",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

/* Info Card Login Vercel */
.login-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: color-mix(in srgb, var(--secondary-background-color) 65%, var(--background-color));
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    border-left: 4px solid #2563eb;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 16px;
}
.login-creds {
    display: flex;
    gap: 16px;
    font-size: 13px;
    margin-top: 4px;
}
.cred-badge {
    background: rgba(37,99,235,0.1);
    color: #2563eb;
    font-family: monospace;
    font-size: 13px;
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
}
.iframe-container {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("⏱️ Monitoring Jam Operasi & Status Bearing")
st.caption("Aplikasi live running hours & rotasi peralatan PLTU Tanjung Balai Karimun.")

# ── Banner Informasi Akun & Tombol Buka Tab Baru ───────────────────────────
st.markdown("""
<div class="login-banner">
  <div>
    <div style="font-weight: 800; font-size: 14px; color: #2563eb;">🔑 Kredensial Masuk Sistem Bearing:</div>
    <div class="login-creds">
      <div>Username: <span class="cred-badge">viewer</span></div>
      <div>Password: <span class="cred-badge">viewer123</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

col_info, col_link = st.columns([3, 1])
with col_info:
    st.info("💡 Sistem di bawah terhubung langsung ke server portal monitoring. Anda dapat login dan mengelola running hours secara interaktif.")
with col_link:
    st.link_button("↗️ Buka di Tab Penuh", "https://bearing-monitoring.vercel.app/", use_container_width=True)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# ── Embed Web Vercel ────────────────────────────────────────────────────────
with st.container():
    components.iframe(
        src="https://bearing-monitoring.vercel.app/",
        height=880,
        scrolling=True
    )
