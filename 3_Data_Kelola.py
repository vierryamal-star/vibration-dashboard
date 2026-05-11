import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import (
    load_history, save_to_db, parse_excel, delete_by_dates, 
    delete_all, render_login_sidebar, check_role
)

st.set_page_config(
    page_title="Data & Kelola — PLTU TBK",
    page_icon="🗄️",
    layout="wide"
)

# ====================== SIDEBAR ======================
with st.sidebar:
    try:
        st.image("assets/logo_pln_ip.png", width=200)
    except:
        st.markdown("### ⚡ PLTU TBK")
    
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    
    st.markdown("### Navigasi")
    st.page_link("app.py", label="📊 Monitor", icon="1️⃣")
    st.page_link("pages/2_Analisis.py", label="📈 Analisis", icon="2️⃣")
    st.page_link("pages/3_Data_Kelola.py", label="🗄️ Data & Kelola", icon="3️⃣")
    
    render_login_sidebar()

st.markdown("# 🗄️ Data & Kelola")

# ====================== LOAD DATA ======================
df_hist = load_history()

tab1, tab2, tab3 = st.tabs(["📤 Upload Data", "📋 Histori Data", "⚙️ Pengaturan"])

# ====================== TAB 1: UPLOAD DATA ======================
with tab1:
    st.markdown("### Upload Data Baru")
    
    if check_role() != "editor":
        st.warning("🔒 Fitur upload hanya tersedia untuk **Editor**. Silakan login di sidebar.")
    else:
        uploaded_files = st.file_uploader(
            "Pilih file Excel (.xlsx)", 
            type=["xlsx"],
            accept_multiple_files=True,
            help="Sheet harus bernama 'Vibration_Data'"
        )

        if uploaded_files:
            total_saved = 0
            for file in uploaded_files:
                with st.spinner(f"Memproses {file.name}..."):
                    df_new = parse_excel(file)
                    if not df_new.empty:
                        saved = save_to_db(df_new)
                        total_saved += saved
                        skipped = len(df_new) - saved
                        st.success(f"✅ {file.name}: {saved} baris disimpan, {skipped} duplikat dilewati")
            
            if total_saved > 0:
                st.balloons()
                st.success(f"🎉 Total {total_saved} baris data baru berhasil disimpan!")
                st.cache_data.clear()
                st.rerun()

# ====================== TAB 2: HISTORI DATA ======================
with tab2:
    st.markdown("### Histori Data Tersimpan")
    
    if df_hist.empty:
        st.info("Belum ada data tersimpan.")
    else:
        df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
        df_hist["date_str"] = df_hist["date"].dt.strftime("%Y-%m-%d")
        
        col1, col2 = st.columns([3, 2])
        with col1:
            min_d = df_hist["date"].min().date() if not df_hist.empty else datetime.today().date()
            max_d = df_hist["date"].max().date() if not df_hist.empty else datetime.today().date()
            date_range = st.date_input("Filter Tanggal", value=(min_d, max_d))
        
        with col2:
            unit_opts = sorted(df_hist["unit"].dropna().unique())
            sel_unit = st.multiselect("Filter Unit", unit_opts, default=unit_opts)

        # Apply filter
        if len(date_range) == 2:
            df_show = df_hist[
                (df_hist["date_str"] >= str(date_range[0])) &
                (df_hist["date_str"] <= str(date_range[1])) &
                (df_hist["unit"].isin(sel_unit))
            ]
        else:
            df_show = df_hist[df_hist["unit"].isin(sel_unit)]

        st.write(f"Menampilkan **{len(df_show):,}** baris data")
        
        st.dataframe(
            df_show.drop(columns=["id", "uploaded_at"], errors="ignore"),
            use_container_width=True,
            hide_index=True
        )

        # Download buttons
        csv = df_show.to_csv(index=False).encode('utf-8')
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("⬇️ Download CSV", csv, f"vibration_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        with col_dl2:
            st.download_button("⬇️ Download Excel", 
                             df_show.to_excel(index=False).encode('utf-8'), 
                             f"vibration_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ====================== TAB 3: PENGATURAN & HAPUS DATA ======================
with tab3:
    st.markdown("### Pengaturan & Hapus Data")
    
    if check_role() != "editor":
        st.warning("🔒 Fitur ini hanya untuk Editor.")
    else:
        subtab1, subtab2 = st.tabs(["🗑️ Hapus Data", "⚙️ Pengaturan Threshold"])

        # Hapus Data
        with subtab1:
            st.warning("⚠️ Bagian ini bersifat permanen!")
            
            all_dates = sorted(df_hist["date_str"].unique(), reverse=True) if not df_hist.empty else []
            
            sel_dates = st.multiselect(
                "Pilih tanggal yang akan dihapus", 
                all_dates,
                format_func=lambda x: pd.to_datetime(x).strftime("%d %B %Y")
            )
            
            if sel_dates and st.button("🗑️ Hapus Data Terpilih", type="secondary"):
                with st.spinner("Menghapus data..."):
                    deleted = delete_by_dates(sel_dates)
                st.success(f"✅ {deleted} baris data berhasil dihapus.")
                st.cache_data.clear()
                st.rerun()

            st.divider()
            if st.button("🗑️ Hapus SEMUA Data", type="secondary"):
                konfirm = st.text_input("Ketik 'HAPUS SEMUA' untuk konfirmasi", key="delall")
                if konfirm == "HAPUS SEMUA":
                    delete_all()
                    st.success("Semua data telah dihapus.")
                    st.cache_data.clear()
                    st.rerun()

        # Pengaturan Threshold
        with subtab2:
            st.markdown("### Threshold ISO 10816 (mm/s)")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Turbine**")
                ta = st.number_input("Zone A", value=1.4, step=0.1, key="ta")
                tb = st.number_input("Zone B", value=2.8, step=0.1, key="tb")
                tc = st.number_input("Zone C", value=4.5, step=0.1, key="tc")
            
            with c2:
                st.markdown("**Pump / Fan**")
                pa = st.number_input("Zone A", value=1.4, step=0.1, key="pa")
                pb = st.number_input("Zone B", value=2.8, step=0.1, key="pb")
                pc = st.number_input("Zone C", value=4.5, step=0.1, key="pc")
            
            if st.button("💾 Simpan Threshold", type="primary"):
                st.success("✅ Threshold berhasil diperbarui (untuk sesi ini)")

st.caption("PLTU TBK Vibration Monitoring System")
