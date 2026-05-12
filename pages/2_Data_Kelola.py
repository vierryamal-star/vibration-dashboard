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
st.markdown("""<style>[data-testid="stSidebarNav"]{display:none;}</style>""", unsafe_allow_html=True)

with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                  label="📊 Monitor")
    st.page_link("pages/1_Analisis.py",      label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py",   label="🗄️ Data & Kelola")
    render_login_sidebar()

role = check_role()
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
        st.info("📂 Belum ada data historis.")
    else:
        df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
        df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
        df_hist["date_str"] = df_hist["date"].dt.strftime("%Y-%m-%d")

        st.metric("Total baris tersimpan", f"{len(df_hist):,}")

        fc1, fc2 = st.columns(2)
        with fc1:
            min_d = df_hist["date"].min().date() if pd.notna(df_hist["date"].min()) else date.today()
            max_d = df_hist["date"].max().date() if pd.notna(df_hist["date"].max()) else date.today()
            date_range = st.date_input("Filter Tanggal", value=(min_d, max_d), key="hist_date")
        with fc2:
            unit_opts = sorted(df_hist["unit"].dropna().unique())
            sel_unit  = st.multiselect("Filter Unit", unit_opts, default=unit_opts, key="hist_unit")

        if len(date_range) == 2:
            d_from, d_to = str(date_range[0]), str(date_range[1])
            df_show = df_hist[
                (df_hist["date_str"] >= d_from) &
                (df_hist["date_str"] <= d_to) &
                (df_hist["unit"].isin(sel_unit))
            ]
        else:
            df_show = df_hist[df_hist["unit"].isin(sel_unit)]

        st.write(f"Menampilkan **{len(df_show):,}** baris")
        st.dataframe(
            df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore"),
            use_container_width=True, hide_index=True
        )

        dl1, dl2 = st.columns(2)
        with dl1:
            csv = df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore").to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv,
                file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with dl2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore").to_excel(w, index=False, sheet_name="Data")
            st.download_button("⬇️ Download Excel", buf.getvalue(),
                file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── TAB UPLOAD ────────────────────────────────────────────────────────────────
with tab_upload:
    if role != "editor":
        st.warning("🔒 Upload hanya tersedia untuk **Editor**. Silakan login di sidebar.")
    else:
        st.markdown("Upload satu atau beberapa file Excel sekaligus.")
        uploaded = st.file_uploader(
            "Pilih file Excel (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
            help="Sheet: Vibration_Data — kolom: Equipment, Unit, Titik Ukur, Direction, Date, Value"
        )
        if uploaded:
            if st.button("⬆️ Simpan ke database", type="primary"):
                total_saved = 0
                total_skipped = 0
                for file in uploaded:
                    df_new = parse_excel(file)
                    if not df_new.empty:
                        saved   = save_to_db(df_new)
                        skipped = len(df_new) - saved
                        total_saved   += saved
                        total_skipped += skipped
                        st.success(f"✅ {file.name}: {saved} baris disimpan · {skipped} duplikat")
                if total_saved > 0:
                    st.success(f"🎉 Total {total_saved} baris baru berhasil disimpan.")
                    st.cache_data.clear()
                if total_skipped > 0:
                    st.info(f"ℹ️ {total_skipped} baris duplikat dilewati.")

        st.divider()
        st.markdown("#### Format file yang didukung")
        st.markdown("""
Sheet **Vibration_Data** dengan kolom:

| Kolom | Keterangan | Contoh |
|-------|-----------|--------|
| Equipment | Nama equipment | Turbine 01, BFP A |
| Unit | Unit PLTU | TBK #1, TBK #2, TBK COM |
| Titik Ukur | Posisi pengukuran | Bearing No.1, NDE Motor |
| Direction | Arah: H / V / A | H |
| Date | Tanggal pengukuran | 06/05/2026 |
| Value (mm/s) | Nilai vibrasi RMS | 2.450 |
""")

# ── TAB HAPUS ─────────────────────────────────────────────────────────────────
with tab_hapus:
    if role != "editor":
        st.warning("🔒 Hapus data hanya tersedia untuk **Editor**. Silakan login di sidebar.")
    else:
        df_hapus = load_history()
        if df_hapus.empty:
            st.info("Tidak ada data untuk dihapus.")
        else:
            df_hapus["date"]     = pd.to_datetime(df_hapus["date"], errors="coerce")
            df_hapus["date_str"] = df_hapus["date"].dt.strftime("%Y-%m-%d")

            h_tab1, h_tab2 = st.tabs(["Hapus Per Tanggal", "Hapus Semua"])

            with h_tab1:
                st.markdown("Pilih tanggal — **semua data pada tanggal tersebut akan dihapus**.")
               # =========================================
# FILTER TAHUN
# =========================================

avail_years = sorted(
    df_hapus["date"].dt.year.dropna().unique(),
    reverse=True
)

sel_year = st.selectbox(
    "📅 Tahun",
    avail_years,
    key="del_year"
)

# =========================================
# FILTER BULAN
# =========================================

df_year = df_hapus[
    df_hapus["date"].dt.year == sel_year
]

avail_months = sorted(
    df_year["date"].dt.month.unique()
)

month_map = {
    1:"Januari",
    2:"Februari",
    3:"Maret",
    4:"April",
    5:"Mei",
    6:"Juni",
    7:"Juli",
    8:"Agustus",
    9:"September",
    10:"Oktober",
    11:"November",
    12:"Desember"
}

sel_month = st.selectbox(
    "📅 Bulan",
    avail_months,
    format_func=lambda x: month_map[x],
    key="del_month"
)

# =========================================
# FILTER TANGGAL
# =========================================

df_month = df_year[
    df_year["date"].dt.month == sel_month
]

avail_dates = sorted(
    df_month["date_str"].dropna().unique(),
    reverse=True
)

sel_dates = st.multiselect(
    "📅 Pilih tanggal",
    options=avail_dates,
    format_func=lambda d: datetime.strptime(
        d,"%Y-%m-%d"
    ).strftime("%d %B %Y"),
    key="del_dates",
)
                if sel_dates:
                    df_prev = df_hapus[df_hapus["date_str"].isin(sel_dates)]
                    n_del   = len(df_prev)
                    st.warning(f"⚠️ Akan menghapus **{n_del} baris** dari {len(sel_dates)} tanggal.")
                    summ = df_prev.groupby("date_str").size().reset_index(name="Jumlah Baris")
                    summ["Tanggal"] = summ["date_str"].apply(lambda d: datetime.strptime(d,"%Y-%m-%d").strftime("%d %b %Y"))
                    st.dataframe(summ[["Tanggal","Jumlah Baris"]], use_container_width=True, hide_index=True)
                    if st.button(f"🗑️ Hapus {n_del} baris", key="btn_del_date", type="secondary"):
                        with st.spinner("Menghapus..."):
                            deleted = delete_by_dates(sel_dates)
                        st.success(f"✅ Data berhasil dihapus.")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.info("Pilih minimal satu tanggal.")

            with h_tab2:
                total_rows = len(df_hapus)
                st.error(f"⚠️ Akan menghapus **{total_rows:,} baris** secara permanen.")
                konfirmasi = st.text_input("Ketik HAPUS SEMUA untuk konfirmasi:", key="konfirm_all")
                if st.button("🗑️ Hapus Semua Data", key="btn_del_all", type="secondary"):
                    if konfirmasi.strip() == "HAPUS SEMUA":
                        with st.spinner("Menghapus semua data..."):
                            delete_all()
                        st.success("✅ Semua data berhasil dihapus.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Ketik: HAPUS SEMUA (huruf kapital)")

# ── TAB PENGATURAN ────────────────────────────────────────────────────────────
with tab_setting:
    if role != "editor":
        st.warning("🔒 Pengaturan hanya tersedia untuk **Editor**.")
    else:
        st.markdown("### Threshold ISO 10816 (mm/s RMS)")
        st.caption("Berlaku untuk sesi ini. Nilai disimpan selama app aktif.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Turbine**")
            ta = st.number_input("Accepted < ", value=float(THRESHOLD["Turbine"]["A"]), step=0.1, key="ta")
            tb = st.number_input("Pre Warning ≤", value=float(THRESHOLD["Turbine"]["B"]), step=0.1, key="tb")
            tc = st.number_input("Warning ≤",     value=float(THRESHOLD["Turbine"]["C"]), step=0.1, key="tc")
            st.caption("Di atas Warning → Danger")
        with c2:
            st.markdown("**Pump / Fan**")
            pa = st.number_input("Accepted < ", value=float(THRESHOLD["Pump/Fan"]["A"]), step=0.1, key="pa")
            pb = st.number_input("Pre Warning ≤", value=float(THRESHOLD["Pump/Fan"]["B"]), step=0.1, key="pb")
            pc = st.number_input("Warning ≤",     value=float(THRESHOLD["Pump/Fan"]["C"]), step=0.1, key="pc")
            st.caption("Di atas Warning → Danger")

        if st.button("💾 Simpan Threshold", type="primary"):
            THRESHOLD["Turbine"]  = {"A":ta,"B":tb,"C":tc}
            THRESHOLD["Pump/Fan"] = {"A":pa,"B":pb,"C":pc}
            st.success("✅ Threshold diperbarui.")

    st.divider()
    st.markdown("### Legenda Status")
    lg1,lg2,lg3,lg4 = st.columns(4)
    lg1.info("**🔵 Accepted**\nVibrasi normal, tidak ada tindakan")
    lg2.success("**🟢 Pre Warning**\nMulai dipantau lebih sering")
    lg3.warning("**🟡 Warning**\nJadwalkan pemeriksaan")
    lg4.error("**🔴 Danger**\nTindakan segera diperlukan")
