import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, save_to_db, parse_excel,
    delete_by_dates, delete_all,
    THRESHOLD, render_login_sidebar, check_role
)

st.set_page_config(page_title="Data & Kelola — PLTU TBK", page_icon="🗄️", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1.2rem; }

/* Font Navigasi Sidebar */
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
    font-size: 16px !important;
    font-weight: 700 !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
    margin-bottom: 6px !important;
}

[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span {
    font-size: 16px !important;
    font-weight: 700 !important;
}

.mk-card {
    border-radius: 10px; padding: 16px 18px;
    border: 1px solid rgba(128,128,128,.18); background: var(--secondary-background-color);
}
.mk-val { font-size: 28px; font-weight: 800; line-height: 1; }
.mk-lbl { font-size: 12px; opacity: .7; margin-top: 6px; font-weight: 600; }
.info-box {
    border-radius: 10px; padding: 14px 16px; border-left: 4px solid #2563eb;
    background: rgba(37,99,235,.09); font-size: 13px; line-height: 1.6;
}
.warn-box {
    border-radius: 10px; padding: 14px 16px; border-left: 4px solid #d97706;
    background: rgba(217,119,6,.1); font-size: 13px; line-height: 1.6;
}
.danger-box {
    border-radius: 10px; padding: 14px 16px; border-left: 4px solid #dc2626;
    background: rgba(220,38,38,.1); font-size: 13px; line-height: 1.6;
}
.sec-head { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
.sec-bar  { width:4px; height:20px; border-radius:2px;
            background:linear-gradient(180deg,#2563eb,#0891b2); flex-shrink:0; }
.sec-title{ font-size:16px; font-weight:800; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    
    st.markdown("""
<style>
[data-testid="stPageLink"]:has(p:contains("🗄️ Data & Kelola")) {
    background: rgba(59,130,246,.2) !important;
    border-radius: 10px !important;
    border-left: 4px solid #3b82f6 !important;
}
</style>""", unsafe_allow_html=True)
    st.page_link("app.py",                 label="📊 Monitor")
    st.page_link("pages/1_Analisis.py",    label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py", label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py",label="🛠️ Kelola Pompa")
    render_login_sidebar()

role = check_role()

def sec_header(title):
    st.markdown(f'<div class="sec-head"><div class="sec-bar"></div><span class="sec-title">{title}</span></div>', unsafe_allow_html=True)

st.markdown("## 🗄️ Data & Kelola")

tab_hist, tab_upload, tab_hapus, tab_setting = st.tabs([
    "📋 Histori Data",
    "⬆️ Upload Data",
    "🗑️ Hapus Data",
    "⚙️ Pengaturan",
])

# ── TAB HISTORI ───────────────────────────────────────────────────────────────
with tab_hist:
    df_hist = load_history()
    if df_hist.empty:
        st.markdown('<div class="info-box">📂 Belum ada data historis.</div>', unsafe_allow_html=True)
    else:
        df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
        df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
        
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f'<div class="mk-card"><div class="mk-val">{len(df_hist):,}</div><div class="mk-lbl">Total Baris</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="mk-card"><div class="mk-val">{df_hist["equipment"].nunique()}</div><div class="mk-lbl">Equipment</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="mk-card"><div class="mk-val">{df_hist["unit"].nunique()}</div><div class="mk-lbl">Unit</div></div>', unsafe_allow_html=True)
        last_tgl = df_hist["date"].max().strftime("%d %b %Y") if pd.notna(df_hist["date"].max()) else "–"
        k4.markdown(f'<div class="mk-card"><div class="mk-val">{last_tgl}</div><div class="mk-lbl">Data Terakhir</div></div>', unsafe_allow_html=True)
        
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        st.dataframe(df_hist.drop(columns=["id","uploaded_at"], errors="ignore"), use_container_width=True, hide_index=True)

# ── TAB UPLOAD ────────────────────────────────────────────────────────────────
with tab_upload:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Upload hanya tersedia untuk <b>Editor</b>. Silakan login di sidebar.</div>', unsafe_allow_html=True)
    else:
        sec_header("Upload File Excel")
        uploaded = st.file_uploader("Pilih file Excel (.xlsx)", type=["xlsx"], accept_multiple_files=True)
        if uploaded:
            preview_rows = []
            for f in uploaded:
                df_pv = parse_excel(f)
                preview_rows.append({
                    "File": f.name, "Baris Valid": len(df_pv),
                    "Equipment": df_pv["equipment"].nunique() if not df_pv.empty else 0
                })
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
            if st.button("⬆️ Simpan ke Database", type="primary"):
                total_saved = 0
                for file in uploaded:
                    df_new = parse_excel(file)
                    if not df_new.empty:
                        total_saved += save_to_db(df_new)
                st.success(f"🎉 Berhasil menyimpan {total_saved} baris baru.")
                st.cache_data.clear()

# ── TAB HAPUS ─────────────────────────────────────────────────────────────────
with tab_hapus:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Hapus data hanya tersedia untuk <b>Editor</b>.</div>', unsafe_allow_html=True)
    else:
        df_hapus = load_history()
        if not df_hapus.empty:
            avail_dates = sorted(pd.to_datetime(df_hapus["date"]).dt.strftime("%Y-%m-%d").unique(), reverse=True)
            sel_del_date = st.multiselect("Pilih tanggal:", avail_dates)
            if sel_del_date and st.button(f"🗑️ Hapus ({len(sel_del_date)} Tanggal)"):
                delete_by_dates(sel_del_date)
                st.success("✅ Data berhasil dihapus.")
                st.cache_data.clear()
                st.rerun()

# ── TAB PENGATURAN ────────────────────────────────────────────────────────────
with tab_setting:
    sec_header("Threshold ISO 10816 (mm/s RMS)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🔧 Turbine**")
        ta = st.number_input("Accepted <", value=float(THRESHOLD["Turbine"]["A"]), step=0.1, key="set_ta")
        tb = st.number_input("Pre Warning ≤", value=float(THRESHOLD["Turbine"]["B"]), step=0.1, key="set_tb")
        tc = st.number_input("Warning ≤", value=float(THRESHOLD["Turbine"]["C"]), step=0.1, key="set_tc")
    with c2:
        st.markdown("**🔧 Pump / Fan**")
        pa = st.number_input("Accepted <", value=float(THRESHOLD["Pump/Fan"]["A"]), step=0.1, key="set_pa")
        pb = st.number_input("Pre Warning ≤", value=float(THRESHOLD["Pump/Fan"]["B"]), step=0.1, key="set_pb")
        pc = st.number_input("Warning ≤", value=float(THRESHOLD["Pump/Fan"]["C"]), step=0.1, key="set_pc")
    if role == "editor" and st.button("💾 Simpan Threshold Sesi Ini", type="primary"):
        THRESHOLD["Turbine"] = {"A": ta, "B": tb, "C": tc}
        THRESHOLD["Pump/Fan"] = {"A": pa, "B": pb, "C": pc}
        st.success("✅ Threshold diperbarui.")
