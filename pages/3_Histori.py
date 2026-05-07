import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime, date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import load_history, DB_PATH

st.set_page_config(page_title="Histori Data — PLTU TBK", page_icon="🗄️", layout="wide")
st.markdown("""<style>[data-testid="stSidebarNav"]{display:none;}</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### 🗂️ Navigasi")
    st.page_link("app.py",               label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py",     label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py",     label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py",   label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py",label="⚙️ Pengaturan")

st.markdown("## 🗄️ Histori Data")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data historis.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")

# ── Filter & tampilkan ────────────────────────────────────────────────────────
fc1, fc2 = st.columns(2)
with fc1:
    min_d = df_hist["date"].min().date() if pd.notna(df_hist["date"].min()) else date.today()
    max_d = df_hist["date"].max().date() if pd.notna(df_hist["date"].max()) else date.today()
    date_range = st.date_input("Filter Tanggal", value=(min_d, max_d), key="hist_date")
with fc2:
    unit_opts = sorted(df_hist["unit"].dropna().unique())
    sel_unit  = st.multiselect("Filter Unit", unit_opts, default=unit_opts, key="hist_unit")

if len(date_range) == 2:
    df_show = df_hist[
        (df_hist["date"].dt.date >= date_range[0]) &
        (df_hist["date"].dt.date <= date_range[1]) &
        (df_hist["unit"].isin(sel_unit))
    ]
else:
    df_show = df_hist[df_hist["unit"].isin(sel_unit)]

st.write(f"Menampilkan **{len(df_show):,}** baris data")
st.dataframe(
    df_show.drop(columns=["id","uploaded_at"], errors="ignore"),
    use_container_width=True, hide_index=True
)

# Download
dl1, dl2 = st.columns(2)
with dl1:
    csv_bytes = df_show.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv_bytes,
        file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
with dl2:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_show.drop(columns=["id","uploaded_at"], errors="ignore").to_excel(
            writer, index=False, sheet_name="Vibration_History")
    st.download_button("⬇️ Download Excel", buf.getvalue(),
        file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.divider()

# ── Hapus data ────────────────────────────────────────────────────────────────
st.markdown("### 🗑️ Hapus Data")
del_tab1, del_tab2, del_tab3 = st.tabs(["Per Tanggal","Per Equipment / Unit","Hapus Semua"])

with del_tab1:
    st.markdown("Hapus data dalam rentang tanggal tertentu.")
    d1, d2 = st.columns(2)
    with d1:
        del_from = st.date_input("Dari tanggal", value=min_d, key="del_from")
    with d2:
        del_to   = st.date_input("Sampai tanggal", value=max_d, key="del_to")
    mask_date = (df_hist["date"].dt.date >= del_from) & (df_hist["date"].dt.date <= del_to)
    n_del = mask_date.sum()
    if n_del > 0:
        st.warning(f"⚠️ Akan menghapus **{n_del} baris** data ({del_from} s/d {del_to})")
        if st.button(f"🗑️ Hapus {n_del} baris data ini", key="btn_del_date", type="secondary"):
            con = sqlite3.connect(DB_PATH)
            con.execute("DELETE FROM vibration WHERE date >= ? AND date <= ?",
                        (str(del_from), str(del_to)))
            con.commit(); con.close()
            st.success("✅ Data berhasil dihapus."); st.rerun()
    else:
        st.info("Tidak ada data pada rentang tanggal tersebut.")

with del_tab2:
    st.markdown("Hapus data untuk equipment atau unit tertentu.")
    de1, de2 = st.columns(2)
    with de1:
        del_unit  = st.multiselect("Unit",      sorted(df_hist["unit"].dropna().unique()),      key="del_unit")
    with de2:
        del_equip = st.multiselect("Equipment", sorted(df_hist["equipment"].dropna().unique()), key="del_equip")

    if del_unit or del_equip:
        mask_eq = pd.Series([True]*len(df_hist), index=df_hist.index)
        if del_unit:  mask_eq = mask_eq & df_hist["unit"].isin(del_unit)
        if del_equip: mask_eq = mask_eq & df_hist["equipment"].isin(del_equip)
        n_del_eq = mask_eq.sum()
        if n_del_eq > 0:
            st.warning(f"⚠️ Akan menghapus **{n_del_eq} baris** data")
            preview = df_hist[mask_eq].groupby(["unit","equipment"]).size().reset_index(name="Jumlah Baris")
            st.dataframe(preview, use_container_width=True, hide_index=True)
            if st.button(f"🗑️ Hapus {n_del_eq} baris data ini", key="btn_del_eq", type="secondary"):
                con = sqlite3.connect(DB_PATH)
                conditions, params = [], []
                if del_unit:
                    conditions.append(f"unit IN ({','.join(['?']*len(del_unit))})")
                    params.extend(del_unit)
                if del_equip:
                    conditions.append(f"equipment IN ({','.join(['?']*len(del_equip))})")
                    params.extend(del_equip)
                query = "DELETE FROM vibration WHERE " + " AND ".join(conditions)
                con.execute(query, params)
                con.commit(); con.close()
                st.success("✅ Data berhasil dihapus."); st.rerun()
    else:
        st.info("Pilih minimal satu unit atau equipment.")

with del_tab3:
    st.markdown("Hapus **semua** data historis secara permanen.")
    total_rows = len(df_hist)
    st.error(f"⚠️ Tindakan ini akan menghapus **{total_rows:,} baris** data dan tidak dapat dibatalkan.")
    konfirmasi = st.text_input("Ketik **HAPUS SEMUA** untuk konfirmasi:", key="konfirm_all")
    if st.button("🗑️ Hapus Semua Data", key="btn_del_all", type="secondary"):
        if konfirmasi == "HAPUS SEMUA":
            con = sqlite3.connect(DB_PATH)
            con.execute("DELETE FROM vibration")
            con.commit(); con.close()
            st.success("✅ Semua data historis berhasil dihapus."); st.rerun()
        else:
            st.error("❌ Konfirmasi salah. Ketik: HAPUS SEMUA (huruf kapital)")
