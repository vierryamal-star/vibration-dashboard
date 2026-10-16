import streamlit as st
import pandas as pd
import io
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, save_to_db_detailed, parse_excel,
    delete_by_dates_detailed, delete_all_detailed,
    flash, show_flash, clear_vibration_caches, now_wib,
    current_thresholds, save_thresholds, reset_thresholds, threshold_status, SETTINGS_SQL,
    check_role,
    render_page_header, render_app_sidebar, GLOBAL_UI_CSS,
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
    border-left: 4px solid #d97706;
    background: rgba(217,119,6,.08);
    font-size: 13px; line-height: 1.6;
}
.danger-box {
    border-radius: 10px; padding: 14px 16px;
    border-left: 4px solid #dc2626;
    background: rgba(220,38,38,.08);
    font-size: 13px; line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

# Render Sidebar Terpusat
render_app_sidebar()

role = check_role()

render_page_header("🗄️ Manajemen Data & Konfigurasi")

VALID_DIRS = {"H", "V", "A", "T"}
KEY_COLS = ["equipment", "unit", "titik", "direction", "date"]
# Batas kewajaran untuk menandai kemungkinan salah ketik (tidak memblokir penyimpanan)
SUS_VIB_MAX = 25.0     # mm/s
SUS_TEMP_MAX = 250.0   # °C


@st.cache_data(show_spinner=False, max_entries=20)
def parse_cached(name: str, data: bytes) -> pd.DataFrame:
    """Parse Excel sekali per isi file (bukan di setiap interaksi widget)."""
    bio = io.BytesIO(data)
    bio.name = name
    return parse_excel(bio)


def prepare_upload(df: pd.DataFrame):
    """
    Bersihkan data upload. Return (df_siap, info).
    Arah selain H/V/A/T dan tanggal tidak valid dibuang (tidak akan terbaca dashboard);
    baris ganda dalam file hanya dilaporkan (penyimpanan menyimpan nilai pertama);
    nilai yang tidak wajar hanya ditandai.
    """
    d = df.copy()
    bad_dir = ~d["direction"].isin(VALID_DIRS)
    info = {"bad_dir_n": int(bad_dir.sum()),
            "bad_dir_vals": sorted(d.loc[bad_dir, "direction"].astype(str).unique())[:5]}
    d = d[~bad_dir].copy()

    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    info["bad_date_n"] = int(d["date"].isna().sum())
    d = d.dropna(subset=["date"]).copy()
    d["date"] = d["date"].dt.strftime("%Y-%m-%d")

    info["dup_n"] = int(d.duplicated(KEY_COLS, keep="first").sum())

    is_t = d["direction"].eq("T")
    sus = (d["value"] < 0) | (~is_t & (d["value"] > SUS_VIB_MAX)) | (is_t & (d["value"] > SUS_TEMP_MAX))
    info["sus_n"] = int(sus.sum())
    info["sus_rows"] = d[sus].head(5)
    return d, info


def xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Data")
    return buf.getvalue()


tab_hist, tab_upload, tab_hapus, tab_setting = st.tabs([
    "📋 Eksplorasi Data",
    "⬆️ Upload Excel",
    "🗑️ Hapus Data",
    "⚙️ Konfigurasi Threshold",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: EKSPLORASI DATA
# ══════════════════════════════════════════════════════════════════════════════
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
                eq_opts = sorted(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())
                sel_eq = st.multiselect("Pilih Equipment", eq_opts, default=eq_opts, key="dk_filter_eq")

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

        st.markdown(f"**Menampilkan `{len(df_show):,}` baris data sesuai filter:**")

        # Kolom tetap bertipe asli (tanggal & angka) supaya klik header = urut yang benar;
        # tampilan saja yang diformat lewat column_config.
        df_disp = df_show.drop(columns=["id", "uploaded_at", "date_str"], errors="ignore").copy()
        st.dataframe(
            df_disp, width="stretch", hide_index=True,
            column_config={
                "equipment": st.column_config.TextColumn("Equipment"),
                "unit": st.column_config.TextColumn("Bagian Unit"),
                "titik": st.column_config.TextColumn("Titik Ukur"),
                "direction": st.column_config.TextColumn("Arah"),
                "date": st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"),
                "value": st.column_config.NumberColumn("Nilai", format="%.3f"),
            },
        )

        col_dl1, col_dl2, _ = st.columns([1, 1, 3])
        df_exp = df_show.drop(columns=["id", "uploaded_at", "date_str"], errors="ignore")
        fname = f"vibration_data_{now_wib().strftime('%Y%m%d_%H%M')}"
        
        with col_dl1:
            st.download_button(
                "⬇️ Download CSV",
                lambda: df_exp.to_csv(index=False).encode("utf-8"),   # dibuat saat diklik
                file_name=f"{fname}.csv",
                mime="text/csv",
                width="stretch"
            )
        with col_dl2:
            st.download_button(
                "⬇️ Download Excel (.xlsx)",
                lambda: xlsx_bytes(df_exp),                              # dibuat saat diklik
                file_name=f"{fname}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: UPLOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    show_flash("upload")
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Fitur Upload Data hanya dapat diakses oleh <b>Editor</b>. Silakan login pada menu di sidebar.</div>', unsafe_allow_html=True)
    else:
        st.markdown("#### ⬆️ Import Data Vibrasi / Suhu")
        st.caption("Upload satu atau beberapa file Excel (.xlsx) dengan lembar kerja bernama **`Vibration_Data`**.")

        nonce = st.session_state.get("_dk_up_nonce", 0)
        uploaded = st.file_uploader(
            "Drop file Excel di sini atau klik untuk memilih",
            type=["xlsx"],
            accept_multiple_files=True,
            key=f"dk_uploader_{nonce}",
            help="Kolom wajib: equipment, unit, titik, direction, date, value"
        )

        if uploaded:
            st.markdown("---")
            preview_rows, parsed = [], []

            for f in uploaded:
                df_raw = parse_cached(f.name, f.getvalue())
                if df_raw.empty:
                    preview_rows.append({"Nama File": f.name, "Status Validasi": "❌ Gagal / Kolom Kurang",
                                         "Jumlah Baris": "0", "Bagian Unit": "–", "Equipment": 0,
                                         "Rentang Tanggal": "–", "Catatan": "–"})
                    continue
                df_ok, info = prepare_upload(df_raw)
                parsed.append((f.name, df_ok, info))

                notes = []
                if info["bad_dir_n"]:
                    notes.append(f"{info['bad_dir_n']} baris arah tak dikenal dilewati ({', '.join(info['bad_dir_vals'])})")
                if info["bad_date_n"]:
                    notes.append(f"{info['bad_date_n']} baris tanggal tidak valid dilewati")
                if info["dup_n"]:
                    notes.append(f"{info['dup_n']} baris ganda dalam file (hanya nilai pertama disimpan)")
                if info["sus_n"]:
                    notes.append(f"⚠️ {info['sus_n']} nilai tidak wajar")
                dts = pd.to_datetime(df_ok["date"]) if not df_ok.empty else None
                preview_rows.append({
                    "Nama File": f.name,
                    "Status Validasi": "✅ Sesuai Format" if not df_ok.empty else "❌ Tidak ada baris valid",
                    "Jumlah Baris": f"{len(df_ok):,}",
                    "Bagian Unit": ", ".join(sorted(df_ok["unit"].unique())) if not df_ok.empty else "–",
                    "Equipment": int(df_ok["equipment"].nunique()) if not df_ok.empty else 0,
                    "Rentang Tanggal": (f"{dts.min().strftime('%d %b %Y')} s.d. {dts.max().strftime('%d %b %Y')}"
                                        if dts is not None else "–"),
                    "Catatan": "; ".join(notes) if notes else "–",
                })

            st.markdown("**Hasil Pengecekan File:**")
            st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)

            for name, _, info in parsed:
                if info["sus_n"]:
                    with st.expander(f"⚠️ {name}: {info['sus_n']} nilai tampak tidak wajar — cek kemungkinan salah ketik"):
                        st.caption(f"Vibrasi > {SUS_VIB_MAX:g} mm/s, suhu > {SUS_TEMP_MAX:g} °C, atau nilai negatif. "
                                   "Data tetap bisa disimpan; ini hanya penanda. Contoh baris:")
                        st.dataframe(info["sus_rows"], hide_index=True, width="stretch")

            parsed = [p for p in parsed if not p[1].empty]
            if parsed:
                if st.button("🚀 Simpan Semua Data ke Database", type="primary", width="stretch"):
                    total_saved = total_exist = total_dup = total_bad = 0
                    errors = []
                    progress_bar = st.progress(0.0)

                    for idx, (fname, df_data, info) in enumerate(parsed):
                        unique_n = len(df_data) - info["dup_n"]
                        saved, err = save_to_db_detailed(df_data)
                        total_saved += saved
                        total_dup += info["dup_n"]
                        total_bad += info["bad_dir_n"] + info["bad_date_n"]
                        if err:
                            extra = f" ({saved:,} baris sempat tersimpan)" if saved else ""
                            errors.append(f"**{fname}**: {err}{extra}")
                        else:
                            total_exist += unique_n - saved
                        progress_bar.progress((idx + 1) / len(parsed))

                    # Pesan disimpan dulu (flash) karena st.rerun() akan menghapus tampilan saat ini.
                    if total_saved:
                        flash("upload", "success", f"🎉 Selesai! **{total_saved:,}** baris baru tersimpan ke database.")
                    elif not errors:
                        flash("upload", "info", "Tidak ada baris baru — seluruh data pada file sudah ada di database.")
                    if total_exist:
                        flash("upload", "info", f"**{total_exist:,}** baris sudah ada di database (dilewati).")
                    if total_dup:
                        flash("upload", "info", f"**{total_dup:,}** baris ganda dalam file (hanya nilai pertama yang disimpan).")
                    if total_bad:
                        flash("upload", "warning", f"**{total_bad:,}** baris dilewati karena arah tak dikenal / tanggal tidak valid.")
                    for e in errors:
                        flash("upload", "error", f"Gagal menyimpan {e}")
                    clear_vibration_caches()
                    st.session_state["_dk_up_nonce"] = nonce + 1      # kosongkan pemilih file
                    st.rerun()

        with st.expander("ℹ️ Panduan Format Kolom Excel"):
            st.markdown("""
Pastikan file Excel memiliki sheet **`Vibration_Data`** dengan susunan header berikut:
* **`equipment`**: Nama mesin (contoh: *BFP A, ID Fan, Turbine 01*)
* **`unit`**: Bagian unit (contoh: *TBK #1, TBK #2, TBK CAH, TBK COM, TBK FF*)
* **`titik`**: Titik ukur (contoh: *DE Motor, NDE Pump, Bearing 1*)
* **`direction`**: Arah getaran / tipe (*H, V, A* untuk vibrasi atau *T* untuk temperatur)
* **`date`**: Tanggal pengukuran (*YYYY-MM-DD* atau format tanggal Excel)
* **`value`**: Angka nilai pengukuran RMS (mm/s) atau Suhu (°C)
            """)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: HAPUS DATA
# ══════════════════════════════════════════════════════════════════════════════
with tab_hapus:
    show_flash("hapus")
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Fitur Penghapusan Data hanya dapat diakses oleh <b>Editor</b>.</div>', unsafe_allow_html=True)
    else:
        df_hapus = load_history()
        if df_hapus.empty:
            st.info("Database kosong, tidak ada data yang dapat dihapus.")
        else:
            df_hapus["date"] = pd.to_datetime(df_hapus["date"], errors="coerce")
            df_hapus["date_str"] = df_hapus["date"].dt.strftime("%Y-%m-%d")

            dn = st.session_state.get("_dk_del_nonce", 0)    # dinaikkan setelah hapus agar pilihan tanggal dikosongkan
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
                        key=f"del_sel_dates_{dn}"
                    )

                with col_prev:
                    if sel_dates:
                        df_del_preview = df_hapus[df_hapus["date_str"].isin(sel_dates)]
                        n_del = len(df_del_preview)
                        st.markdown(f'<div class="warn-box">⚠️ Sebanyak <b>{n_del:,} baris</b> dari <b>{len(sel_dates)} tanggal</b> akan dihapus permanen.</div>', unsafe_allow_html=True)
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                        
                        bk = df_del_preview.drop(columns=["id", "uploaded_at", "date_str"], errors="ignore").copy()
                        bk["date"] = bk["date"].dt.strftime("%Y-%m-%d")
                        st.download_button(
                            "⬇️ Unduh cadangan baris yang akan dihapus (CSV)",
                            lambda: bk.to_csv(index=False).encode("utf-8"),
                            file_name=f"backup_hapus_{now_wib().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv", width="stretch", key=f"del_bk_{dn}",
                        )
                        sure = st.checkbox(f"Saya yakin menghapus {n_del:,} baris ini", key=f"del_chk_{dn}")
                        if st.button(f"🗑️ Konfirmasi Hapus ({n_del:,} Baris)", type="secondary", width="stretch",
                                     disabled=not sure, key=f"del_btn_{dn}"):
                            with st.spinner("Menghapus data..."):
                                n_done, err = delete_by_dates_detailed(sel_dates)
                            if err:
                                flash("hapus", "error", f"Gagal menghapus data: {err}"
                                      + (f" ({n_done:,} baris sempat terhapus)" if n_done else ""))
                            elif n_done:
                                flash("hapus", "success", f"{n_done:,} baris pada {len(sel_dates)} tanggal berhasil dihapus.")
                            else:
                                flash("hapus", "info", "Tidak ada baris yang terhapus.")
                            clear_vibration_caches()
                            st.session_state["_dk_del_nonce"] = dn + 1
                            st.rerun()
                    else:
                        st.caption("Pilih minimal satu tanggal pada dropdown di samping.")

            with del_tab2:
                total_db_rows = len(df_hapus)
                st.markdown(f'<div class="danger-box">🔴 <b>PERINGATAN:</b> Aksi ini akan menghapus <b>seluruh {total_db_rows:,} baris</b> data historis di Supabase dan tidak bisa dibatalkan.</div>', unsafe_allow_html=True)
                st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

                full_bk = df_hapus.drop(columns=["id", "uploaded_at", "date_str"], errors="ignore").copy()
                full_bk["date"] = full_bk["date"].dt.strftime("%Y-%m-%d")
                st.download_button(
                    "⬇️ Unduh cadangan SELURUH data (CSV) sebelum menghapus",
                    lambda: full_bk.to_csv(index=False).encode("utf-8"),
                    file_name=f"backup_seluruh_data_{now_wib().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", key=f"del_all_bk_{dn}",
                )
                col_confirm, col_btn = st.columns([2, 1])
                with col_confirm:
                    confirm_text = st.text_input("Ketik **HAPUS SEMUA** untuk konfirmasi penghapusan:",
                                                 placeholder="HAPUS SEMUA", key=f"del_all_txt_{dn}")
                with col_btn:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🚨 Hapus Semua Data", type="primary", width="stretch", disabled=(confirm_text.strip() != "HAPUS SEMUA"),
                                 key=f"del_all_btn_{dn}"):
                        with st.spinner("Membersihkan seluruh database..."):
                            n_done, err = delete_all_detailed()
                        if err:
                            flash("hapus", "error", f"Gagal menghapus seluruh data: {err}")
                        else:
                            flash("hapus", "success", f"Seluruh data berhasil dihapus ({n_done:,} baris).")
                        clear_vibration_caches()
                        st.session_state["_dk_del_nonce"] = dn + 1
                        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: PENGATURAN THRESHOLD
# ══════════════════════════════════════════════════════════════════════════════
with tab_setting:
    show_flash("threshold")
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Pengaturan threshold hanya dapat disesuaikan oleh <b>Editor</b>.</div>', unsafe_allow_html=True)
    else:
        st.markdown("#### ⚙️ Konfigurasi Batas Standar Vibrasi (ISO 10816)")
        stt = threshold_status()
        if stt["source"] == "database":
            who = f" oleh **{stt['updated_by']}**" if stt.get("updated_by") else ""
            when = ""
            if stt.get("updated_at"):
                ts = pd.to_datetime(stt["updated_at"], errors="coerce", utc=True)
                when = f" pada {ts.tz_convert('Asia/Jakarta').strftime('%d %b %Y %H:%M')} WIB" if pd.notna(ts) else ""
            st.caption(f"✅ Memakai batas **tersimpan di database**{who}{when} — berlaku untuk semua pengguna.")
        elif stt["source"] == "sesi":
            st.warning("Batas ini hanya berlaku untuk sesi browser Anda dan hilang saat refresh. "
                       "Buat tabel `app_settings` (lihat di bawah) agar tersimpan permanen untuk semua pengguna.",
                       icon="⚠️")
        else:
            st.caption("Memakai **nilai default bawaan**. Perubahan yang disimpan berlaku untuk semua pengguna.")
        if stt.get("error"):
            with st.expander("Aktifkan penyimpanan permanen (jalankan sekali di Supabase → SQL Editor)"):
                st.code(SETTINGS_SQL, language="sql")
                st.caption(f"Detail teknis: {stt['error'][:200]}")

        cur = current_thresholds()
        tn = st.session_state.get("_dk_thr_nonce", 0)

        col_t, col_p = st.columns(2)
        with col_t:
            st.markdown("**🔧 Klasifikasi Turbin**")
            ta = st.number_input("Zone A (Accepted) <", value=float(cur["Turbine"]["A"]), step=0.1, key=f"ta_cfg_{tn}")
            tb = st.number_input("Zone B (Pre Warning) ≤", value=float(cur["Turbine"]["B"]), step=0.1, key=f"tb_cfg_{tn}")
            tc = st.number_input("Zone C (Warning) ≤", value=float(cur["Turbine"]["C"]), step=0.1, key=f"tc_cfg_{tn}")

        with col_p:
            st.markdown("**🔧 Klasifikasi Pompa / Fan**")
            pa = st.number_input("Zone A (Accepted) <", value=float(cur["Pump/Fan"]["A"]), step=0.1, key=f"pa_cfg_{tn}")
            pb = st.number_input("Zone B (Pre Warning) ≤", value=float(cur["Pump/Fan"]["B"]), step=0.1, key=f"pb_cfg_{tn}")
            pc = st.number_input("Zone C (Warning) ≤", value=float(cur["Pump/Fan"]["C"]), step=0.1, key=f"pc_cfg_{tn}")

        problems = []
        if not (0 < ta < tb < tc):
            problems.append("Turbin: batas harus berurutan, 0 < A < B < C.")
        if not (0 < pa < pb < pc):
            problems.append("Pompa/Fan: batas harus berurutan, 0 < A < B < C.")
        for p in problems:
            st.error(p)

        actor = st.text_input("Nama Petugas (opsional, tercatat bersama perubahan)", key="dk_actor").strip()

        b1, b2 = st.columns([3, 1])
        with b1:
            if st.button("💾 Simpan Konfigurasi Batas", type="primary", width="stretch", disabled=bool(problems)):
                ok, msg, persisted = save_thresholds(
                    {"Turbine": {"A": ta, "B": tb, "C": tc}, "Pump/Fan": {"A": pa, "B": pb, "C": pc}}, actor)
                clear_vibration_caches()
                flash("threshold", ("success" if persisted else "warning") if ok else "error", msg)
                st.session_state["_dk_thr_nonce"] = tn + 1
                st.rerun()
        with b2:
            reset_ok = st.checkbox("Konfirmasi reset", key=f"dk_thr_reset_chk_{tn}")
            if st.button("↩️ Default", width="stretch", disabled=not reset_ok, key=f"dk_thr_reset_btn_{tn}"):
                ok, msg = reset_thresholds()
                clear_vibration_caches()
                flash("threshold", "success" if ok else "error", msg)
                st.session_state["_dk_thr_nonce"] = tn + 1
                st.rerun()

        st.divider()
        st.markdown("**Keterangan Zona ISO:**")
        lg1, lg2, lg3, lg4 = st.columns(4)
        leg_items = [
            (lg1, "#2563eb", "🔵 Accepted", "Kondisi sangat baik, operasi normal."),
            (lg2, "#16a34a", "🟢 Pre Warning", "Kondisi wajar, mulai lakukan pemantauan tren."),
            (lg3, "#d97706", "🟡 Warning", "Kondisi menurun, jadwalkan investigasi/pemeliharaan."),
            (lg4, "#dc2626", "🔴 Danger", "Kondisi kritis, potensi kerusakan tinggi — tindak segera."),
        ]
        for col, tc, title, desc in leg_items:
            col.markdown(f"""
<div style="border-radius:10px;padding:12px;border:1px solid {tc}30;background:{tc}12;text-align:center">
  <div style="font-size:14px;font-weight:700;color:{tc};margin-bottom:4px">{title}</div>
  <div style="font-size:11px;opacity:.85;line-height:1.4">{desc}</div>
</div>""", unsafe_allow_html=True)
