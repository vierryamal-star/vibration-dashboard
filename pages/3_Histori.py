import streamlit as st
import pandas as pd
import io
from datetime import datetime, date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import load_history, delete_by_dates, delete_all, render_login_sidebar, check_role

st.set_page_config(page_title="Histori Data — PLTU TBK", page_icon="🗄️", layout="wide")
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

st.markdown("## 🗄️ Histori Data")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data historis.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
df_hist["date_str"] = df_hist["date"].dt.strftime("%Y-%m-%d")

# ── Filter tampilan ───────────────────────────────────────────────────────────
fc1, fc2 = st.columns(2)
with fc1:
    min_d = df_hist["date"].min().date() if pd.notna(df_hist["date"].min()) else date.today()
    max_d = df_hist["date"].max().date() if pd.notna(df_hist["date"].max()) else date.today()
    date_range = st.date_input("Filter Tanggal", value=(min_d, max_d), key="hist_date")
with fc2:
    unit_opts = sorted(df_hist["unit"].dropna().unique())
    sel_unit  = st.multiselect("Filter Unit", unit_opts, default=unit_opts, key="hist_unit")

if len(date_range) == 2:
    d_from = str(date_range[0])
    d_to   = str(date_range[1])
    df_show = df_hist[
        (df_hist["date_str"] >= d_from) &
        (df_hist["date_str"] <= d_to) &
        (df_hist["unit"].isin(sel_unit))
    ]
else:
    df_show = df_hist[df_hist["unit"].isin(sel_unit)]

st.write(f"Menampilkan **{len(df_show):,}** baris data")
st.dataframe(
    df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore"),
    use_container_width=True, hide_index=True
)

# ── Download ──────────────────────────────────────────────────────────────────
dl1, dl2 = st.columns(2)
with dl1:
    csv_bytes = df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv_bytes,
        file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
with dl2:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore").to_excel(
            writer, index=False, sheet_name="Vibration_History")
    st.download_button("⬇️ Download Excel", buf.getvalue(),
        file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.divider()

# ── Hapus data (Editor only) ──────────────────────────────────────────────────
st.markdown("### 🗑️ Hapus Data")

if check_role() != "editor":
    st.warning("🔒 Fitur hapus data hanya tersedia untuk **Editor**. Silakan login di sidebar kiri.")
    st.stop()

del_tab1, del_tab2 = st.tabs(["Hapus Per Tanggal", "Hapus Semua"])

# ── Tab 1: Hapus per tanggal ──────────────────────────────────────────────────
with del_tab1:
    st.markdown("Pilih tanggal pengukuran. Semua data pada tanggal tersebut akan dihapus.")

    all_dates_str = sorted(df_hist["date_str"].dropna().unique(), reverse=True)

    sel_dates = st.multiselect(
        "Pilih tanggal",
        options=all_dates_str,
        format_func=lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%d %b %Y"),
        key="del_dates_multi",
    )

    if sel_dates:
        mask = df_hist["date_str"].isin(sel_dates)
        df_preview = df_hist[mask]
        n_del = len(df_preview)

        st.warning(f"⚠️ Akan menghapus **{n_del} baris** dari {len(sel_dates)} tanggal.")

        summary = df_preview.groupby("date_str").size().reset_index(name="Jumlah Baris")
        summary["Tanggal"] = summary["date_str"].apply(
            lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%d %b %Y"))
        st.dataframe(summary[["Tanggal","Jumlah Baris"]], use_container_width=True, hide_index=True)

        if st.button(f"🗑️ Hapus {n_del} baris", key="btn_del_dates", type="secondary"):
            with st.spinner("Menghapus data..."):
                deleted = delete_by_dates(sel_dates)
            st.success(f"✅ Data berhasil dihapus.")
            st.cache_data.clear()
            st.rerun()
    else:
        st.info("Pilih minimal satu tanggal.")

# ── Tab 2: Hapus semua ────────────────────────────────────────────────────────
with del_tab2:
    total_rows = len(df_hist)
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
