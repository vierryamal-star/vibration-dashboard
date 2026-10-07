import streamlit as st
import pandas as pd
import io
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, save_to_db_detailed, parse_excel,
    delete_by_dates_detailed, delete_all_detailed,
    load_db_thresholds, save_db_thresholds, DEFAULT_THRESHOLD,
    check_role, render_page_header, render_app_sidebar, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Data & Kelola — PLTU TBK",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }
.warn-box {
    border-radius: 10px; padding: 14px 16px;
    border-left: 4px solid #d97706; background: rgba(217,119,6,.08);
    font-size: 13px; line-height: 1.6;
}
.danger-box {
    border-radius: 10px; padding: 14px 16px;
    border-left: 4px solid #dc2626; background: rgba(220,38,38,.08);
    font-size: 13px; line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()

def flash(kind: str, msg: str) -> None:
    st.session_state.setdefault("_dk_flash", []).append((kind, msg))

for kind, msg in st.session_state.pop("_dk_flash", []):
    getattr(st, kind)(msg)

role = check_role()
render_page_header("🗄️ Manajemen Data & Konfigurasi")

tab_hist, tab_upload, tab_hapus, tab_setting = st.tabs([
    "📋 Eksplorasi Data",
    "⬆️ Upload Excel",
    "🗑️ Hapus Data",
    "⚙️ Konfigurasi Threshold",
])

# ── TAB 1: EKSPLORASI DATA ───────────────────────────────────────────────────
with tab_hist:
    df_hist = load_history()
    if df_hist.empty:
        st.info("📂 Database masih kosong. Buka tab **Upload Excel** untuk menambahkan data.")
    else:
        df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
        df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
        df_hist["date_str"] = df_hist["date"].dt.strftime("%Y-%m-%d")

        n_total  = len(df_hist)
        n_equip  = df_hist["equipment"].nunique()
        n_unit   = df_hist["unit"].nunique()
        last_tgl = df_hist["date"].max().strftime("%d %b %Y") if pd.notna(df_hist["date"].max()) else "–"

        kpi_items = [
            ("📄", "Total Baris", f"{n_total:,}", "#4f46e5"),
            ("⚙️", "Equipment", str(n_equip), "#2563eb"),
            ("🏭", "Bagian Unit", str(n_unit), "#16a34a"),
            ("🕒", "Data Terakhir", last_tgl, "#d97706"),
        ]
        kpi_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:10px 0 18px">'
        for ico, lbl, val, col in kpi_items:
            kpi_html += f"""
<div style="background:{col}14;border:1px solid {col}30;border-radius:12px;padding:14px;text-align:center">
  <div style="font-size:22px;font-weight:800;color:{col};line-height:1.1">{val}</div>
  <div style="font-size:11px;margin-top:6px;color:{col};font-weight:700">{ico} {lbl}</div>
</div>"""
        kpi_html += "</div>"
        st.markdown(kpi_html, unsafe_allow_html=True)

        with st.expander("🔍 **Filter & Pencarian Data**", expanded=True):
            fc1, fc2, fc3 = st.columns([2, 2, 2])
            min_d = df_hist["date"].min().date()
            max_d = df_hist["date"].max().date()
            with fc1:
                date_range = st.date_input("Rentang Tanggal", value=(min_d, max_d), key="dk_filter_date")
            with fc2:
                unit_opts = sorted(df_hist["unit"].dropna().unique())
                sel_unit = st.multiselect("Pilih Bagian Unit", unit_opts, default=unit_opts, key="dk_filter_unit")
            with fc3:
                eq_avail = sorted(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())
                sel_eq = st.multiselect("Pilih Equipment", eq_avail, default=eq_avail, key="dk_filter_eq")

        if isinstance(date_range, tuple) and len(date_range) == 2:
            d_from, d_to = str(date_range[0]), str(date_range[1])
            df_show = df_hist[
                (df_hist["date_str"] >= d_from) &
                (df_hist["date_str"] <= d_to) &
                (df_hist["unit"].isin(sel_unit)) &
                (df_hist["equipment"].isin(sel_eq))
            ].copy()
        else:
            df_show = df_hist[df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_eq)].copy()

        st.markdown(f"**Menampilkan `{len(df_show):,}` baris data:**")
        df_disp = df_show.drop(columns=["id", "uploaded_at", "date_str"], errors="ignore").copy()
        
        st.dataframe(
            df_disp, width="stretch", hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"),
                "value": st.column_config.NumberColumn("Nilai Ukur", format="%.3f"),
                "equipment": "Equipment", "unit": "Bagian Unit",
                "titik": "Titik Ukur", "direction": "Arah/Tipe"
            }
        )

        col_dl1, col_dl2, _ = st.columns([1, 1, 3])
        df_exp = df_show.drop(columns=["id", "uploaded_at", "date_str"], errors="ignore")
        fname = f"vibration_data_{datetime.now().strftime('%Y%m%d_%H%M')}"
        with col_dl1:
            st.download_button(
                "⬇️ Download CSV", df_exp.to_csv(index=False).encode("utf-8"),
                file_name=f"{fname}.csv", mime="text/csv", width="stretch"
            )
        with col_dl2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df_exp.to_excel(w, index=False, sheet_name="Data")
            st.download_button(
                "⬇️ Download Excel (.xlsx)", buf.getvalue(),
                file_name=f"{fname}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )

# ── TAB 2: UPLOAD DATA ───────────────────────────────────────────────────────
with tab_upload:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Fitur Upload Data hanya dapat diakses oleh <b>Editor</b>. Silakan login di sidebar.</div>', unsafe_allow_html=True)
    else:
        st.markdown("#### ⬆️ Import Data Vibrasi / Suhu")
        st.caption("Upload file Excel (.xlsx). Jika sheet **`Vibration_Data`** tidak ditemukan, sheet pertama akan dibaca secara otomatis.")

        uploaded = st.file_uploader(
            "Drop file Excel di sini", type=["xlsx"], accept_multiple_files=True,
            help="Kolom wajib: equipment, unit, titik, direction, date, value"
        )

        if uploaded:
            st.markdown("---")
            preview_rows = []
            parsed_dfs = []
            for f in uploaded:
                df_pv = parse_excel(f)
                is_valid = not df_pv.empty
                if is_valid:
                    parsed_dfs.append((f.name, df_pv))
                preview_rows.append({
                    "Nama File": f.name,
                    "Status": "✅ Sesuai Format" if is_valid else "❌ Gagal / Kolom Kurang",
                    "Jumlah Baris": f"{len(df_pv):,}" if is_valid else "0",
                    "Bagian Unit": ", ".join(df_pv["unit"].unique()) if is_valid else "–",
                    "Equipment": df_pv["equipment"].nunique() if is_valid else 0,
                })
            st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)

            if parsed_dfs and st.button("🚀 Simpan Semua Data ke Database", type="primary", width="stretch"):
                total_saved = 0
                total_duplicates = 0
                errors = []
                prog = st.progress(0.0)

                for idx, (fname, df_data) in enumerate(parsed_dfs):
                    saved, err = save_to_db_detailed(df_data)
                    if err:
                        errors.append(f"{fname}: {err}")
                    else:
                        total_saved += saved
                        total_duplicates += (len(df_data) - saved)
                    prog.progress((idx + 1) / len(parsed_dfs))

                if errors:
                    flash("error", f"Terjadi kesalahan database: {'; '.join(errors)}")
                else:
                    msg = f"🎉 Sukses! {total_saved:,} baris baru berhasil disimpan."
                    if total_duplicates > 0:
                        msg += f" ({total_duplicates:,} baris duplikat dilewati)."
                    flash("success", msg)

                st.cache_data.clear()
                st.rerun()

# ── TAB 3: HAPUS DATA ────────────────────────────────────────────────────────
with tab_hapus:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Fitur Penghapusan Data hanya dapat diakses oleh <b>Editor</b>.</div>', unsafe_allow_html=True)
    else:
        df_hapus = load_history()
        if df_hapus.empty:
            st.info("Database kosong, tidak ada data yang dapat dihapus.")
        else:
            df_hapus["date"] = pd.to_datetime(df_hapus["date"], errors="coerce")
            df_hapus["date_str"] = df_hapus["date"].dt.strftime("%Y-%m-%d")
            del_tab1, del_tab2 = st.tabs(["🗓️ Hapus Berdasarkan Tanggal", "⚠️ Hapus Seluruh Database"])

            with del_tab1:
                avail_dates = sorted(df_hapus["date_str"].dropna().unique(), reverse=True)
                col_sel, col_prev = st.columns([1, 1])
                with col_sel:
                    st.markdown("##### Pilih Tanggal Pengukuran")
                    sel_dates = st.multiselect(
                        "Pilih tanggal yang ingin dihapus:",
                        options=avail_dates,
                        format_func=lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%d %B %Y"),
                        key="del_sel_dates"
                    )

                with col_prev:
                    if sel_dates:
                        df_del_preview = df_hapus[df_hapus["date_str"].isin(sel_dates)]
                        n_del = len(df_del_preview)
                        st.markdown(f'<div class="warn-box">⚠️ Sebanyak <b>{n_del:,} baris</b> dari <b>{len(sel_dates)} tanggal</b> akan dihapus permanen.</div>', unsafe_allow_html=True)
                        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                        st.download_button(
                            "💾 Unduh Backup Data yang Akan Dihapus (CSV)",
                            df_del_preview.to_csv(index=False).encode("utf-8"),
                            file_name=f"backup_sebelum_hapus_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv", width="stretch"
                        )
                        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                        if st.button(f"🗑️ Konfirmasi Hapus Permanen ({n_del:,} Baris)", type="secondary", width="stretch"):
                            deleted, err = delete_by_dates_detailed(sel_dates)
                            if err:
                                flash("error", f"Gagal menghapus data: {err}")
                            else:
                                flash("success", f"Berhasil menghapus {deleted:,} baris dari database.")
                            st.cache_data.clear()
                            st.rerun()

            with del_tab2:
                total_db_rows = len(df_hapus)
                st.markdown(f'<div class="danger-box">🔴 <b>PERINGATAN:</b> Aksi ini akan menghapus <b>seluruh {total_db_rows:,} baris</b> data historis dan tidak bisa dibatalkan.</div>', unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.download_button(
                    "💾 Unduh Backup Seluruh Database Sebelum Hapus (CSV)",
                    df_hapus.to_csv(index=False).encode("utf-8"),
                    file_name=f"full_database_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", width="stretch"
                )
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                col_confirm, col_btn = st.columns([2, 1])
                with col_confirm:
                    confirm_text = st.text_input("Ketik **HAPUS SEMUA** untuk konfirmasi:", placeholder="HAPUS SEMUA")
                with col_btn:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🚨 Eksekusi Hapus Semua", type="primary", width="stretch", disabled=(confirm_text.strip() != "HAPUS SEMUA")):
                        count, err = delete_all_detailed()
                        if err:
                            flash("error", f"Gagal menghapus database: {err}")
                        else:
                            flash("success", f"Seluruh database dibersihkan ({count:,} baris dihapus).")
                        st.cache_data.clear()
                        st.rerun()

# ── TAB 4: PENGATURAN THRESHOLD ──────────────────────────────────────────────
with tab_setting:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Pengaturan threshold hanya dapat disesuaikan oleh <b>Editor</b>.</div>', unsafe_allow_html=True)
    else:
        st.markdown("#### ⚙️ Konfigurasi Batas Standar Vibrasi (ISO 10816)")
        st.caption("Nilai disimpan permanen ke database Supabase dan berlaku untuk seluruh user.")

        cur_cfg = load_db_thresholds()
        cur_turb = cur_cfg.get("Turbine", DEFAULT_THRESHOLD["Turbine"])
        cur_pf = cur_cfg.get("Pump/Fan", DEFAULT_THRESHOLD["Pump/Fan"])

        col_t, col_p = st.columns(2)
        with col_t:
            st.markdown("**🔧 Klasifikasi Turbin**")
            ta = st.number_input("Zone A (Accepted) <", value=float(cur_turb["A"]), step=0.1, key="ta_cfg")
            tb = st.number_input("Zone B (Pre Warning) ≤", value=float(cur_turb["B"]), step=0.1, key="tb_cfg")
            tc = st.number_input("Zone C (Warning) ≤", value=float(cur_turb["C"]), step=0.1, key="tc_cfg")

        with col_p:
            st.markdown("**🔧 Klasifikasi Pompa / Fan**")
            pa = st.number_input("Zone A (Accepted) <", value=float(cur_pf["A"]), step=0.1, key="pa_cfg")
            pb = st.number_input("Zone B (Pre Warning) ≤", value=float(cur_pf["B"]), step=0.1, key="pb_cfg")
            pc = st.number_input("Zone C (Warning) ≤", value=float(cur_pf["C"]), step=0.1, key="pc_cfg")

        c_save, c_reset = st.columns([2, 1])
        with c_save:
            if st.button("💾 Simpan Permanen ke Database", type="primary", width="stretch"):
                if not (ta < tb < tc and pa < pb < pc):
                    st.error("Batas nilai tidak logis! Pastikan urutan: Zone A < Zone B < Zone C.")
                else:
                    new_cfg = {
                        "Turbine": {"A": ta, "B": tb, "C": tc},
                        "Pump/Fan": {"A": pa, "B": pb, "C": pc},
                    }
                    ok, msg = save_db_thresholds(new_cfg)
                    flash("success" if ok else "error", msg)
                    st.rerun()

        with c_reset:
            if st.button("🔄 Kembalikan Default ISO", width="stretch"):
                ok, msg = save_db_thresholds(DEFAULT_THRESHOLD)
                flash("success" if ok else "error", "Threshold dikembalikan ke nilai standar ISO.")
                st.rerun()
