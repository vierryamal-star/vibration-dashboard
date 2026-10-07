import streamlit as st
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

/* Banner Info Akun & Akses Cepat */
.portal-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: color-mix(in srgb, var(--secondary-background-color) 65%, var(--background-color));
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    border-left: 4px solid #2563eb;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 14px;
}
.portal-creds {
    display: flex;
    gap: 16px;
    font-size: 13px;
    margin-top: 4px;
}
.cred-chip {
    background: rgba(37,99,235,0.12);
    color: #2563eb;
    font-family: monospace;
    font-size: 13px;
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 700;
}
.native-iframe-box {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    background: #ffffff;
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("⏱️ Monitoring Jam Operasi & Status Bearing")
st.caption("Integrasi langsung sistem pemantauan rotasi dan jam operasi mesin PLTU TBK.")

# ── Banner Kredensial & Navigasi Cepat ───────────────────────────────────────
st.markdown("""
<div class="portal-card">
  <div>
    <div style="font-weight: 800; font-size: 14px; color: #2563eb;">🔑 Kredensial Masuk Sistem:</div>
    <div class="portal-creds">
      <div>Username: <span class="cred-chip">viewer</span></div>
      <div>Password: <span class="cred-chip">viewer123</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

col_info, col_btn = st.columns([3, 1])
with col_info:
    st.info("💡 Portal termuat langsung di bawah. Anda juga dapat membukanya di jendela terpisah untuk tampilan layar penuh.")
with col_btn:
    st.link_button("↗️ Buka di Tab Penuh", "https://bearing-monitoring.vercel.app/", type="primary", use_container_width=True)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# ── Native HTML iframe (Lebih Ringan & Cepat) ─────────────────────────────────
st.markdown("""
<div class="native-iframe-box">
  <iframe 
      src="https://bearing-monitoring.vercel.app/" 
      width="100%" 
      height="880px" 
      frameborder="0"
      loading="eager"
      allow="clipboard-read; clipboard-write"
      style="display: block; width: 100%; border: none;">
  </iframe>
</div>
""", unsafe_allow_html=True)
