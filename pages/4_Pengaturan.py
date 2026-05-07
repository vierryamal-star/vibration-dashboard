import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import THRESHOLD, render_login_sidebar

st.set_page_config(page_title="Pengaturan — PLTU TBK", page_icon="⚙️", layout="wide")
st.markdown("""<style>[data-testid="stSidebarNav"]{display:none;}</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py",      label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py",      label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py",    label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py", label="⚙️ Pengaturan")
    st.page_link("pages/5_Prediksi.py",   label="🔮 Prediksi Trend")
    render_login_sidebar()

st.markdown("## ⚙️ Pengaturan")

# ── Threshold ────────────────────────────────────────────────────────────────
st.markdown("### Threshold ISO 10816 (mm/s RMS)")
st.caption("Nilai default sesuai ISO 10816. Sesuaikan dengan kondisi equipment PLTU TBK.")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Turbine**")
    ta = st.number_input("Zone A ≤ (sangat baik)",   value=float(THRESHOLD["Turbine"]["A"]), step=0.1, key="ta")
    tb = st.number_input("Zone B ≤ (normal)",         value=float(THRESHOLD["Turbine"]["B"]), step=0.1, key="tb")
    tc = st.number_input("Zone C ≤ (perlu perhatian)",value=float(THRESHOLD["Turbine"]["C"]), step=0.1, key="tc")
    st.caption("Di atas Zone C → Zone D (bahaya)")

with c2:
    st.markdown("**Pump / Fan**")
    pa = st.number_input("Zone A ≤ (sangat baik)",   value=float(THRESHOLD["Pump/Fan"]["A"]), step=0.1, key="pa")
    pb = st.number_input("Zone B ≤ (normal)",         value=float(THRESHOLD["Pump/Fan"]["B"]), step=0.1, key="pb")
    pc = st.number_input("Zone C ≤ (perlu perhatian)",value=float(THRESHOLD["Pump/Fan"]["C"]), step=0.1, key="pc")
    st.caption("Di atas Zone C → Zone D (bahaya)")

if st.button("💾 Simpan Threshold", type="primary"):
    THRESHOLD["Turbine"]  = {"A": ta, "B": tb, "C": tc}
    THRESHOLD["Pump/Fan"] = {"A": pa, "B": pb, "C": pc}
    st.success("✅ Threshold berhasil diperbarui untuk sesi ini.")

st.divider()

# ── Legenda ───────────────────────────────────────────────────────────────────
st.markdown("### 📋 Legenda Zone ISO 10816")
lg1, lg2, lg3, lg4 = st.columns(4)
lg1.success("**🟢 Zone A**\n\nSangat baik\nBaru dipasang / baru overhaul")
lg2.warning("**🟡 Zone B**\n\nNormal operasi\nDapat beroperasi terus")
lg3.error("**🟠 Zone C**\n\nPerlu pemantauan\nOperasi terbatas, jadwalkan perbaikan")
lg4.error("**🔴 Zone D**\n\nBahaya\nHentikan — tindakan segera")

st.divider()

# ── Info sistem ───────────────────────────────────────────────────────────────
st.markdown("### ℹ️ Informasi Sistem")
st.markdown("""
| Item | Keterangan |
|------|-----------|
| Standar | ISO 10816 — Mechanical vibration evaluation |
| Satuan | mm/s RMS (velocity) |
| Sumber data | Upload Excel manual (.xlsx) |
| Penyimpanan | SQLite lokal (vibration_history.db) |
| Threshold Turbine | Zone A: 3.8 / Zone B: 7.5 / Zone C: 11.8 mm/s |
| Threshold Pump/Fan | Zone A: 1.4 / Zone B: 2.8 / Zone C: 4.5 mm/s |
| Direction | H = Horizontal · V = Vertical · A = Axial |
""")

st.divider()
st.markdown("### 📁 Format File Excel yang Didukung")
st.markdown("""
Sheet **Vibration_Data** dengan kolom:

| Kolom | Keterangan | Contoh |
|-------|-----------|--------|
| Equipment | Nama equipment | Turbine, BFP A, CWP A |
| Unit | Unit PLTU | TBK #1, TBK #2 |
| Titik Ukur | Posisi pengukuran | Bearing No.1, NDE Motor |
| Direction | Arah: H / V / A | H |
| Date | Tanggal pengukuran | 06/05/2026 |
| Value (mm/s) | Nilai vibrasi RMS | 2.450 |
""")
