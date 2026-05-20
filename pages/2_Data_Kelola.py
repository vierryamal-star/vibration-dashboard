import streamlit as st
import pandas as pd
import io
from datetime import datetime, date, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, save_to_db, parse_excel,
    delete_by_dates, delete_all,
    THRESHOLD, render_login_sidebar, check_role
)

st.set_page_config(page_title="Data & Kelola — PLTU TBK", page_icon="🗄️", layout="wide")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }

/* Tab styling */
div[data-testid="stTabs"] > div > div[role="tablist"] {
    gap: 4px;
    border-bottom: 2px solid rgba(128,128,128,.15);
    padding-bottom: 0;
}
div[data-testid="stTabs"] button[role="tab"] {
    font-size: 13px; font-weight: 600;
    padding: 8px 18px; border-radius: 8px 8px 0 0;
}

/* Metric card */
.mk-card {
    border-radius: 10px; padding: 16px 18px;
    border: 1px solid rgba(128,128,128,.15);
    background: rgba(128,128,128,.04);
}
.mk-val { font-size: 28px; font-weight: 800; line-height: 1; }
.mk-lbl { font-size: 11px; opacity: .5; margin-top: 5px; font-weight: 500; }

/* Info box */
.info-box {
    border-radius: 10px; padding: 14px 16px;
    border-left: 4px solid #2563eb;
    background: rgba(37,99,235,.07);
    font-size: 13px; line-height: 1.6;
}
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

/* Format tabel */
.ft { width:100%; border-collapse:collapse; font-size:13px; }
.ft thead tr { border-bottom: 2px solid rgba(128,128,128,.15); }
.ft thead th {
    padding: 10px 14px; font-size:10px; font-weight:700;
    text-transform:uppercase; letter-spacing:.08em; opacity:.5; text-align:left;
}
.ft tbody tr { border-bottom: 1px solid rgba(128,128,128,.07); }
.ft tbody tr:hover { filter: brightness(1.06); }
.ft td { padding: 9px 14px; vertical-align: middle; font-size:13px; }

/* Section header */
.sec-head { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
.sec-bar  { width:4px; height:20px; border-radius:2px;
            background:linear-gradient(180deg,#2563eb,#0891b2); flex-shrink:0; }
.sec-title{ font-size:15px; font-weight:700; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                 label="📊 Monitor")
    st.page_link("pages/1_Analisis.py",    label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py", label="🗄️ Data & Kelola")
    render_login_sidebar()

role = check_role()

def sec_header(title):
    st.markdown(f'<div class="sec-head"><div class="sec-bar"></div>'
                f'<span class="sec-title">{title}</span></div>', unsafe_allow_html=True)

st.markdown("## 🗄️ Data & Kelola")

tab_hist, tab_upload, tab_hapus, tab_setting = st.tabs([
    "📋 Histori Data",
    "⬆️ Upload Data",
    "🗑️ Hapus Data",
    "⚙️ Pengaturan",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB HISTORI
# ══════════════════════════════════════════════════════════════════════════════
with tab_hist:
    df_hist = load_history()

    if df_hist.empty:
        st.markdown('<div class="info-box">📂 Belum ada data historis. Upload file Excel di tab <b>Upload Data</b>.</div>',
                    unsafe_allow_html=True)
    else:
        df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
        df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
        df_hist["date_str"] = df_hist["date"].dt.strftime("%Y-%m-%d")

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

        # ── KPI ringkas ───────────────────────────────────────────────────────
        n_total  = len(df_hist)
        n_equip  = df_hist["equipment"].nunique()
        n_unit   = df_hist["unit"].nunique()
        last_tgl = df_hist["date"].max().strftime("%d %b %Y") if pd.notna(df_hist["date"].max()) else "–"

        k1, k2, k3, k4 = st.columns(4)
        for col, val, lbl in [
            (k1, f"{n_total:,}",  "Total Baris"),
            (k2, str(n_equip),    "Equipment"),
            (k3, str(n_unit),     "Unit"),
            (k4, last_tgl,        "Data Terakhir"),
        ]:
            col.markdown(f'<div class="mk-card"><div class="mk-val">{val}</div>'
                         f'<div class="mk-lbl">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)

        # ── Filter ───────────────────────────────────────────────────────────
        sec_header("Filter Data")
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            min_d = df_hist["date"].min().date()
            max_d = df_hist["date"].max().date()
            date_range = st.date_input("Rentang Tanggal", value=(min_d, max_d), key="hist_date")
        with fc2:
            unit_opts = sorted(df_hist["unit"].dropna().unique())
            sel_unit  = st.multiselect("Unit", unit_opts, default=unit_opts, key="hist_unit")
        with fc3:
            eq_opts  = sorted(df_hist["equipment"].dropna().unique())
            sel_eq   = st.multiselect("Equipment", eq_opts, default=eq_opts, key="hist_eq")

        if len(date_range) == 2:
            d_from, d_to = str(date_range[0]), str(date_range[1])
            df_show = df_hist[
                (df_hist["date_str"] >= d_from) &
                (df_hist["date_str"] <= d_to) &
                (df_hist["unit"].isin(sel_unit)) &
                (df_hist["equipment"].isin(sel_eq))
            ]
        else:
            df_show = df_hist[df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_eq)]

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        sec_header(f"Data ({len(df_show):,} baris)")

        df_disp = df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore").copy()
        if "date" in df_disp.columns:
            df_disp["date"] = pd.to_datetime(df_disp["date"]).dt.strftime("%d %b %Y")
        if "value" in df_disp.columns:
            df_disp["value"] = df_disp["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

        # ── Download ──────────────────────────────────────────────────────────
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        dl1, dl2, _ = st.columns([1, 1, 3])
        df_exp = df_show.drop(columns=["id","uploaded_at","date_str"], errors="ignore")
        fname  = f"vibration_{datetime.now().strftime('%Y%m%d')}"
        with dl1:
            st.download_button("⬇️ Download CSV", df_exp.to_csv(index=False).encode("utf-8"),
                               file_name=f"{fname}.csv", mime="text/csv", use_container_width=True)
        with dl2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df_exp.to_excel(w, index=False, sheet_name="Data")
            st.download_button("⬇️ Download Excel", buf.getvalue(),
                               file_name=f"{fname}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Upload hanya tersedia untuk <b>Editor</b>. Silakan login di sidebar.</div>',
                    unsafe_allow_html=True)
    else:
        sec_header("Upload File Excel")
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Pilih satu atau beberapa file Excel (.xlsx)",
            type=["xlsx"], accept_multiple_files=True,
            help="Sheet: Vibration_Data — kolom: Equipment, Unit, Titik Ukur, Direction, Date, Value"
        )

        if uploaded:
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

            # Preview
            preview_rows = []
            for f in uploaded:
                df_pv = parse_excel(f)
                preview_rows.append({
                    "File": f.name,
                    "Baris": len(df_pv),
                    "Equipment": df_pv["equipment"].nunique() if not df_pv.empty else 0,
                    "Rentang Tanggal": (
                        f"{pd.to_datetime(df_pv['date']).min().strftime('%d %b %Y')} – "
                        f"{pd.to_datetime(df_pv['date']).max().strftime('%d %b %Y')}"
                        if not df_pv.empty else "–"
                    ),
                })
            df_pv_tbl = pd.DataFrame(preview_rows)
            st.markdown("**Preview file yang akan diupload:**")
            st.dataframe(df_pv_tbl, use_container_width=True, hide_index=True)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

            if st.button("⬆️ Simpan ke Database", type="primary", use_container_width=False):
                total_saved = total_skip = 0
                for file in uploaded:
                    df_new = parse_excel(file)
                    if not df_new.empty:
                        saved   = save_to_db(df_new)
                        skipped = len(df_new) - saved
                        total_saved += saved; total_skip += skipped
                        st.success(f"✅ **{file.name}** — {saved} baris disimpan · {skipped} duplikat dilewati")
                if total_saved > 0:
                    st.success(f"🎉 Total **{total_saved}** baris baru berhasil disimpan.")
                    st.cache_data.clear()
                if total_skip > 0:
                    st.info(f"ℹ️ {total_skip} baris duplikat dilewati (sudah ada di database).")

        st.divider()

        sec_header("Format File yang Didukung")
        st.markdown("Sheet **`Vibration_Data`** dengan kolom-kolom berikut:")

        fmt_rows = [
            ("Equipment",    "Nama equipment",             "Turbine 01, BFP A, ID Fan"),
            ("Unit",         "Unit PLTU",                  "TBK #1, TBK #2, TBK COM"),
            ("Titik Ukur",   "Posisi pengukuran",          "DE Motor, NDE Pump, Bearing 1"),
            ("Direction",    "Arah: H / V / A",            "H"),
            ("Date",         "Tanggal pengukuran",         "06/05/2026"),
            ("Value (mm/s)", "Nilai vibrasi RMS",          "2.450"),
        ]
        rows_html = ""
        for i, (col, ket, ex) in enumerate(fmt_rows):
            bg = "rgba(128,128,128,.03)" if i%2==1 else "transparent"
            rows_html += (f'<tr style="background:{bg}">'
                          f'<td style="padding:9px 14px;font-weight:700;font-family:monospace;color:#2563eb">{col}</td>'
                          f'<td style="padding:9px 14px">{ket}</td>'
                          f'<td style="padding:9px 14px;opacity:.65;font-style:italic">{ex}</td>'
                          f'</tr>')
        st.markdown(f"""
<div style="border-radius:10px;overflow:hidden;border:1px solid rgba(128,128,128,.15)">
<table class="ft">
<thead><tr>
  <th>Kolom</th><th>Keterangan</th><th>Contoh</th>
</tr></thead>
<tbody>{rows_html}</tbody></table></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB HAPUS
# ══════════════════════════════════════════════════════════════════════════════
with tab_hapus:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Hapus data hanya tersedia untuk <b>Editor</b>. Silakan login di sidebar.</div>',
                    unsafe_allow_html=True)
    else:
        df_hapus = load_history()
        if df_hapus.empty:
            st.info("Tidak ada data untuk dihapus.")
        else:
            df_hapus["date"]     = pd.to_datetime(df_hapus["date"], errors="coerce")
            df_hapus["date_str"] = df_hapus["date"].dt.strftime("%Y-%m-%d")

            h_tab1, h_tab2 = st.tabs(["🗓️ Hapus Per Tanggal", "⚠️ Hapus Semua"])

            # ── Hapus Per Tanggal ─────────────────────────────────────────────
            with h_tab1:
                st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

                # Batasi hanya 5 hari ke belakang dari hari ini
                today     = date.today()
                min_allow = today - timedelta(days=365)
                min_allow_str = min_allow.strftime("%Y-%m-%d")

                # Tanggal yang tersedia dalam rentang 5 hari ke belakang
                avail_dates_all = sorted(df_hapus["date_str"].dropna().unique(), reverse=True)
                avail_dates     = [d for d in avail_dates_all if d >= min_allow_str]

                st.markdown(f"""
<div class="info-box">
🗓️ Hanya data <b>5 hari ke belakang</b> yang dapat dihapus per tanggal
(<b>{min_allow.strftime('%d %b %Y')}</b> – <b>{today.strftime('%d %b %Y')}</b>).<br>
Untuk menghapus data lebih lama, gunakan tab <b>Hapus Semua</b>.
</div>""", unsafe_allow_html=True)
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

                if not avail_dates:
                    st.markdown('<div class="warn-box">⚠️ Tidak ada data dalam 5 hari terakhir yang bisa dihapus.</div>',
                                unsafe_allow_html=True)
                else:
                    # Tampilkan ringkasan tanggal yang tersedia
                    summ_avail = (
                        df_hapus[df_hapus["date_str"].isin(avail_dates)]
                        .groupby("date_str").size().reset_index(name="Jumlah Baris")
                        .sort_values("date_str", ascending=False)
                    )
                    summ_avail["Tanggal"] = summ_avail["date_str"].apply(
                        lambda d: datetime.strptime(d,"%Y-%m-%d").strftime("%d %B %Y"))

                    sec_header("Tanggal Tersedia (5 Hari Terakhir)")
                    # Tabel ringkasan tersedia
                    rows_s = ""
                    for i, (_, r) in enumerate(summ_avail.iterrows()):
                        bg = "rgba(128,128,128,.03)" if i%2==1 else "transparent"
                        rows_s += (f'<tr style="background:{bg}">'
                                   f'<td style="padding:9px 14px">{r["Tanggal"]}</td>'
                                   f'<td style="padding:9px 14px;text-align:right;font-weight:600">'
                                   f'{r["Jumlah Baris"]:,} baris</td></tr>')
                    st.markdown(f"""
<div style="border-radius:10px;overflow:hidden;border:1px solid rgba(128,128,128,.15);margin-bottom:16px">
<table class="ft" style="width:100%">
<thead><tr><th>Tanggal</th><th style="text-align:right">Jumlah Baris</th></tr></thead>
<tbody>{rows_s}</tbody></table></div>""", unsafe_allow_html=True)

                    sel_dates = st.multiselect(
                        "Pilih tanggal yang akan dihapus",
                        options=avail_dates,
                        format_func=lambda d: datetime.strptime(d,"%Y-%m-%d").strftime("%d %B %Y"),
                        key="del_dates",
                    )

                    if sel_dates:
                        df_prev = df_hapus[df_hapus["date_str"].isin(sel_dates)]
                        n_del   = len(df_prev)

                        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="warn-box">⚠️ Akan menghapus <b>{n_del:,} baris</b> dari <b>{len(sel_dates)} tanggal</b> yang dipilih.</div>',
                                    unsafe_allow_html=True)
                        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

                        ba, _ = st.columns([1,4])
                        with ba:
                            if st.button(f"🗑️ Hapus {n_del:,} Baris", key="btn_del_date",
                                         type="secondary", use_container_width=True):
                                with st.spinner("Menghapus..."):
                                    delete_by_dates(sel_dates)
                                st.success("✅ Data berhasil dihapus.")
                                st.cache_data.clear()
                                st.rerun()
                    else:
                        st.caption("Pilih minimal satu tanggal untuk melanjutkan.")

            # ── Hapus Semua ───────────────────────────────────────────────────
            with h_tab2:
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                total_rows = len(df_hapus)

                st.markdown(f'<div class="danger-box">🔴 Aksi ini akan menghapus <b>seluruh {total_rows:,} baris</b> data secara permanen dan tidak dapat dibatalkan.</div>',
                            unsafe_allow_html=True)
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

                konfirmasi = st.text_input("Ketik **HAPUS SEMUA** untuk konfirmasi:", key="konfirm_all",
                                           placeholder="HAPUS SEMUA")
                bb, _ = st.columns([1,4])
                with bb:
                    if st.button("🗑️ Hapus Semua Data", key="btn_del_all",
                                 type="secondary", use_container_width=True):
                        if konfirmasi.strip() == "HAPUS SEMUA":
                            with st.spinner("Menghapus semua data..."):
                                delete_all()
                            st.success("✅ Semua data berhasil dihapus.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("❌ Konfirmasi tidak sesuai. Ketik: HAPUS SEMUA (huruf kapital)")

# ══════════════════════════════════════════════════════════════════════════════
# TAB PENGATURAN
# ══════════════════════════════════════════════════════════════════════════════
with tab_setting:
    if role != "editor":
        st.markdown('<div class="warn-box">🔒 Pengaturan hanya tersedia untuk <b>Editor</b>. Silakan login di sidebar.</div>',
                    unsafe_allow_html=True)
    else:
        sec_header("Threshold ISO 10816 (mm/s RMS)")
        st.caption("Nilai diperbarui untuk sesi ini selama app aktif.")
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🔧 Turbine**")
            ta = st.number_input("Accepted <",      value=float(THRESHOLD["Turbine"]["A"]), step=0.1, key="ta")
            tb = st.number_input("Pre Warning ≤",   value=float(THRESHOLD["Turbine"]["B"]), step=0.1, key="tb")
            tc_val = st.number_input("Warning ≤",   value=float(THRESHOLD["Turbine"]["C"]), step=0.1, key="tc")
            st.caption("Di atas Warning → Danger")
        with c2:
            st.markdown("**🔧 Pump / Fan**")
            pa = st.number_input("Accepted <",      value=float(THRESHOLD["Pump/Fan"]["A"]), step=0.1, key="pa")
            pb = st.number_input("Pre Warning ≤",   value=float(THRESHOLD["Pump/Fan"]["B"]), step=0.1, key="pb")
            pc_val = st.number_input("Warning ≤",   value=float(THRESHOLD["Pump/Fan"]["C"]), step=0.1, key="pc")
            st.caption("Di atas Warning → Danger")

        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        sv, _ = st.columns([1,4])
        with sv:
            if st.button("💾 Simpan Threshold", type="primary", use_container_width=True):
                THRESHOLD["Turbine"]  = {"A":ta, "B":tb, "C":tc_val}
                THRESHOLD["Pump/Fan"] = {"A":pa, "B":pb, "C":pc_val}
                st.success("✅ Threshold diperbarui.")

    st.divider()
    sec_header("Legenda Status Zona")
    lg1, lg2, lg3, lg4 = st.columns(4)
    zone_data = [
        (lg1, "#2563eb", "rgba(37,99,235,.1)",   "🔵 Accepted",    "Vibrasi normal\nTidak ada tindakan"),
        (lg2, "#16a34a", "rgba(22,163,74,.1)",   "🟢 Pre Warning", "Mulai dipantau\nlebih sering"),
        (lg3, "#d97706", "rgba(217,119,6,.1)",   "🟡 Warning",     "Jadwalkan\npemeriksaan"),
        (lg4, "#dc2626", "rgba(220,38,38,.1)",   "🔴 Danger",      "Tindakan segera\ndiperlukan"),
    ]
    for col, tc, bg, title, desc in zone_data:
        col.markdown(f"""
<div style="border-radius:10px;padding:14px;border:1px solid {tc}30;
            background:{bg};text-align:center">
  <div style="font-size:15px;font-weight:700;color:{tc};margin-bottom:5px">{title}</div>
  <div style="font-size:12px;opacity:.7;line-height:1.5">{desc}</div>
</div>""", unsafe_allow_html=True)
