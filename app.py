import streamlit as st
import pandas as pd
from datetime import datetime
from utils import (
    load_history, get_zone, get_threshold, add_zone_cols,
    get_temp_threshold, get_zone_temp,
    get_pump_runtime, compute_running_hours, now_wib,
    ZC, ZB, render_page_header, render_app_sidebar, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Monitor Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }
.eq-card-modern {
    border-radius: 12px; padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 70%, var(--background-color));
    box-shadow: 0 2px 10px rgba(0,0,0,.04); margin-bottom: 12px; color: var(--text-color);
}
.eq-subtext {
    font-size: 11px; color: color-mix(in srgb, var(--text-color) 70%, transparent);
    margin-bottom: 6px; font-weight: 500;
}
.pill-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 8px; }
.pill-item { border-radius: 8px; padding: 6px 3px; text-align: center; border: 1px solid transparent; }
details.eq-details {
    margin-top: 8px; border-top: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent); padding-top: 8px;
}
details.eq-details summary {
    cursor: pointer; font-size: 11px; font-weight: 600;
    color: color-mix(in srgb, var(--text-color) 75%, transparent); list-style: none;
}
.badge-stale {
    background: rgba(239, 68, 68, 0.12); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4);
    font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700;
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()

df_hist = load_history()
if df_hist.empty:
    render_page_header("📊 Monitor Vibrasi & Status Operasi")
    st.info("📂 Belum ada data. Silakan upload data Excel pada menu **Data & Kelola**.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
all_units = sorted(df_hist["unit"].dropna().unique())
all_dates = sorted(df_hist["date"].dt.date.dropna().unique(), reverse=True)

# Live clock berbasis JavaScript murni (efisien, tanpa rerun server)
head_col, clock_col = st.columns([3, 2])
with head_col:
    render_page_header("📊 Monitor Vibrasi & Status Operasi")
with clock_col:
    st.components.v1.html("""
    <div id="js_clock" style="text-align:right; font-family:sans-serif;">
        <div id="time_part" style="font-size:26px; font-weight:800; font-variant-numeric:tabular-nums; color:#2563eb; line-height:1.1;">--:--:-- WIB</div>
        <div id="date_part" style="font-size:11px; font-weight:600; opacity:0.7; margin-top:2px;">Memuat waktu...</div>
    </div>
    <script>
    function updateClock() {
        const now = new Date();
        const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        const wib = new Date(utc + (3600000 * 7));
        const days = ["Minggu","Senin","Selasa","Rabu","Kamis","Jumat","Sabtu"];
        const months = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
        const pad = (n) => n.toString().padStart(2, '0');
        document.getElementById("time_part").innerHTML = `${pad(wib.getHours())}:${pad(wib.getMinutes())}:${pad(wib.getSeconds())} <span style="font-size:13px;font-weight:600;opacity:.75;">WIB</span>`;
        document.getElementById("date_part").innerText = `${days[wib.getDay()]}, ${wib.getDate()} ${months[wib.getMonth()]} ${wib.getFullYear()} (GMT+7)`;
    }
    setInterval(updateClock, 1000);
    updateClock();
    </script>
    """, height=65)

# Filter Unit
st.caption("**🏭 Bagian Unit Pembangkit**")
sel_unit_label = st.segmented_control(
    "Bagian Unit", options=["🏢 Semua Bagian Unit"] + all_units,
    default="🏢 Semua Bagian Unit", key="mon_unit_segmented", label_visibility="collapsed"
)
sel_unit = all_units if (sel_unit_label == "🏢 Semua Bagian Unit" or not sel_unit_label) else [sel_unit_label]

all_equip = sorted(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())
c_eq, c_dt = st.columns([3, 2])
with c_eq:
    with st.expander(f"⚙️ Filter Spesifik Equipment ({len(all_equip)} mesin)", expanded=False):
        sel_equip = st.multiselect("Equipment", all_equip, default=all_equip, key="mon_equip", label_visibility="collapsed")
if not sel_equip:
    sel_equip = all_equip

with c_dt:
    date_mode = st.radio("Mode Tampilan", ["🕐 Nilai Terbaru", "📅 Tanggal Tertentu"], horizontal=True, key="mon_date_mode", label_visibility="collapsed")

if date_mode == "📅 Tanggal Tertentu":
    sel_tgl = st.date_input("Pilih Tanggal", value=max(all_dates), min_value=min(all_dates), max_value=max(all_dates), key="mon_tgl")
    df_base = df_hist[df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip) & (df_hist["date"].dt.date == sel_tgl)].copy()
else:
    df_base = df_hist[df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip)].copy()

if df_base.empty:
    st.warning("⚠️ Tidak ada data pengukuran yang sesuai dengan filter.")
    st.stop()

df_base = add_zone_cols(df_base)
latest_all = (
    df_base.sort_values("date")
    .groupby(["unit", "equipment", "titik", "direction"], as_index=False)
    .last()
)
latest = latest_all[latest_all["direction"] != "T"].copy()
latest_temp = latest_all[latest_all["direction"] == "T"].copy()

# KPI Header
n_d = int((latest["zone"] == "ZONE D").sum())
n_c = int((latest["zone"] == "ZONE C").sum())
n_b = int((latest["zone"] == "ZONE B").sum())
n_a = int((latest["zone"] == "ZONE A").sum())

kpi_items = [
    ("📊", "Total Titik", str(len(latest)), "#4f46e5"),
    ("🔵", "Accepted (A)", str(n_a), "#2563eb"),
    ("🟢", "Pre Warning (B)", str(n_b), "#16a34a"),
    ("🟡", "Warning (C)", str(n_c), "#d97706"),
    ("🔴", "Danger (D)", str(n_d), "#dc2626"),
]
kpi_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:8px 0 14px">'
for ico, lbl, val, col in kpi_items:
    kpi_html += f"""
<div style="background:{col}14;border:1px solid {col}30;border-radius:12px;padding:12px 8px;text-align:center">
  <div style="font-size:24px;font-weight:800;color:{col};line-height:1">{val}</div>
  <div style="font-size:11px;margin-top:4px;color:{col};font-weight:700">{ico} {lbl}</div>
</div>"""
kpi_html += "</div>"
st.markdown(kpi_html, unsafe_allow_html=True)

# Card Grid
now_dt = now_wib()
eq_rows = []
for eq in sorted(latest["equipment"].dropna().unique()):
    df_eq = latest[latest["equipment"] == eq]
    thr = get_threshold(eq)
    last_measure = df_eq["date"].max()
    days_old = (now_dt - last_measure).days if pd.notna(last_measure) else 999
    is_stale = days_old > 30

    vals = df_eq["value"].dropna().to_numpy()
    if len(vals) > 0:
        max_idx = df_eq["value"].idxmax()
        mx_val = float(df_eq.loc[max_idx, "value"])
        mx_titik = str(df_eq.loc[max_idx, "titik"])
        mx_dir = str(df_eq.loc[max_idx, "direction"])
        zk, zi, zl = get_zone(mx_val, thr)
    else:
        mx_val, mx_titik, mx_dir = None, "–", ""
        zk, zi, zl = "N/A", "⬜", "Belum ada data"

    eq_rows.append({
        "eq": eq, "unit": df_eq["unit"].iloc[0], "mx": mx_val,
        "mx_titik": mx_titik, "mx_dir": mx_dir, "zk": zk, "zi": zi, "zl": zl,
        "thr": thr, "tgl": last_measure.strftime("%d %b %Y") if pd.notna(last_measure) else "–",
        "is_stale": is_stale, "days_old": days_old
    })

# Fragment disesuaikan dengan TTL cache 15 detik
@st.fragment(run_every="15s")
def _render_cards():
    df_runtime_now = get_pump_runtime()
    for i in range(0, len(eq_rows), 3):
        cols = st.columns(3)
        for col, r in zip(cols, eq_rows[i:i+3]):
            bc = ZC.get(r["zk"], "#6b7280")
            val_txt = f"{r['mx']:.3f} mm/s" if r['mx'] is not None else "Tidak ada getaran"
            stale_badge = f'<span class="badge-stale">⚠️ {r["days_old"]} hari lalu</span>' if r["is_stale"] else ""

            match_rt = df_runtime_now[
                (df_runtime_now["equipment"] == r["eq"]) & (df_runtime_now["unit"] == r["unit"])
            ] if not df_runtime_now.empty else pd.DataFrame()
            if not match_rt.empty:
                r_dict = match_rt.iloc[0].to_dict()
                h_run = compute_running_hours(r_dict)
                st_run = "🟢 Running" if r_dict.get("status") == "running" else "⚪ Stopped"
                rt_html = f'<div style="font-size:11px;font-weight:700;margin-bottom:6px;">{st_run} · ⏱️ {h_run:,.1f} jam</div>'
            else:
                rt_html = '<div style="font-size:11px;opacity:.6;margin-bottom:6px;">⏱️ Jam operasi belum diatur</div>'

            with col:
                st.markdown(f"""
<div class="eq-card-modern" style="border-left: 5px solid {bc};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-size:15px;font-weight:800;">{r['eq']} {stale_badge}</div>
      <div class="eq-subtext">{r['unit']} · 📅 {r['tgl']}</div>
    </div>
    <span style="font-size:11px;font-weight:700;color:{bc};background:{ZB.get(r['zk'],'transparent')};padding:2px 8px;border-radius:99px;border:1px solid {bc}50;">
      {r['zi']} {r['zl']}
    </span>
  </div>
  {rt_html}
  <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-top:4px;">
    <span style="opacity:0.75;font-weight:600;">Max ({r['mx_titik']} · {r['mx_dir']}):</span>
    <span style="font-weight:800;color:{bc};font-size:13px;">{val_txt}</span>
  </div>
</div>""", unsafe_allow_html=True)

_render_cards()

st.divider()
st.markdown("### 🔍 Matriks Pengukuran Cepat (Pivot Table)")

# Optimasi Pivot Table
if not latest.empty:
    pivot_df = latest.pivot_table(
        index=["unit", "equipment", "titik"],
        columns="direction",
        values="value",
        aggfunc="first"
    ).reset_index()
    for col_dir in ["H", "V", "A"]:
        if col_dir not in pivot_df.columns:
            pivot_df[col_dir] = None
    pivot_df["Max RMS"] = pivot_df[["H", "V", "A"]].max(axis=1)
    
    st.dataframe(
        pivot_df, width="stretch", hide_index=True,
        column_config={
            "unit": "Bagian Unit", "equipment": "Equipment", "titik": "Titik Ukur",
            "H": st.column_config.NumberColumn("H (mm/s)", format="%.3f"),
            "V": st.column_config.NumberColumn("V (mm/s)", format="%.3f"),
            "A": st.column_config.NumberColumn("A (mm/s)", format="%.3f"),
            "Max RMS": st.column_config.NumberColumn("Max (mm/s)", format="%.3f"),
        }
    )
