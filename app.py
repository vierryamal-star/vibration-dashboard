import streamlit as st
import pandas as pd
from datetime import datetime
from utils import (
    save_to_db, load_history, parse_excel,
    get_zone, get_threshold, THRESHOLD, add_zone_cols,
    render_login_sidebar,
    get_temp_threshold, get_zone_temp,
    get_pump_runtime, compute_running_hours, get_pump_age,
    ZC, ZB, ZONE_LABEL, ZONE_ICON, UI, render_page_header, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Monitor Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

/* Equipment Card Modern */
.eq-card-modern {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid rgba(128,128,128,.15);
    background: color-mix(in srgb, var(--background-color) 95%, transparent);
    box-shadow: 0 2px 10px rgba(0,0,0,.04);
    margin-bottom: 12px;
    transition: transform .15s ease, box-shadow .15s ease;
}
.eq-card-modern:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0,0,0,.08);
}

/* Modern Pill Matrix */
.pill-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    margin-top: 10px;
}
.pill-item {
    border-radius: 8px;
    padding: 6px 4px;
    text-align: center;
    border: 1px solid transparent;
}

/* Table Style */
.vt-wrap {
    border-radius: 12px; overflow: hidden;
    border: 1px solid color-mix(in srgb, currentColor 12%, transparent);
    margin-bottom: 24px;
    box-shadow: 0 2px 14px rgba(0,0,0,.06);
}
.vt {
    width: 100%; border-collapse: collapse; font-size: 13px;
    background: color-mix(in srgb, var(--background-color) 95%, transparent);
    color: inherit;
}
.vt thead tr {
    background: color-mix(in srgb, var(--secondary-background-color) 100%, transparent);
    border-bottom: 2px solid color-mix(in srgb, currentColor 10%, transparent);
}
.vt thead th {
    padding: 11px 14px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .08em;
    color: inherit; opacity: .6; white-space: nowrap;
}
.vt tbody tr {
    border-bottom: 1px solid color-mix(in srgb, currentColor 6%, transparent);
    transition: background .1s;
}
.vt tbody tr:hover { filter: brightness(1.05); }
.vt td { padding: 9px 14px; vertical-align: middle; }
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

def bar_pct(val, thr):
    max_scale = thr.get("C", 4.5) * 1.2
    return min(int((val / max(max_scale, 0.001)) * 100), 100)

# ── Data Loading ──────────────────────────────────────────────────────────────
df_hist = load_history()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try:
        st.image("assets/logo_pln_ip.png", width=200)
    except Exception:
        pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.markdown("""
<style>
[data-testid="stPageLink"]:has(p:contains("📊 Monitor Vibrasi")) {
    background: rgba(59,130,246,.12);
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
}
</style>""", unsafe_allow_html=True)
    st.page_link("app.py",                  label="📊 Monitor Vibrasi")
    st.page_link("pages/1_Analisis.py",     label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py",  label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py", label="🛠️ Kelola Pompa")
    st.divider()
    if st.button("🔄 Refresh Data", key="sb_refresh", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

if df_hist.empty:
    render_page_header("📊 Monitor Vibrasi & Status Operasi")
    st.info("📂 Belum ada data. Silakan upload data Excel pada menu **Data & Kelola**.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
all_units = sorted(df_hist["unit"].dropna().unique())
all_dates = sorted(df_hist["date"].dt.date.dropna().unique(), reverse=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER & CLOCK
# ══════════════════════════════════════════════════════════════════════════════
render_page_header("📊 Monitor Vibrasi & Status Operasi")

@st.fragment(run_every="1s")
def _live_clock():
    _now = datetime.now()
    _hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][_now.weekday()]
    _bulan = ["","Januari","Februari","Maret","April","Mei","Juni","Juli",
              "Agustus","September","Oktober","November","Desember"][_now.month]
    st.markdown(
        f'<div style="font-size:12px;opacity:.65;margin-top:-6px;margin-bottom:12px">'
        f'🕐 {_hari}, {_now.day} {_bulan} {_now.year} &nbsp;·&nbsp; '
        f'<span style="font-variant-numeric:tabular-nums;font-weight:700">{_now.strftime("%H:%M:%S")}</span>'
        f'</div>', unsafe_allow_html=True)

_live_clock()

# ══════════════════════════════════════════════════════════════════════════════
# FILTER BAGIAN UNIT PINTAR (STATUS CHIPS)
# ══════════════════════════════════════════════════════════════════════════════
# Kalkulasi status terkini per Bagian Unit untuk label chip
unit_status_summary = {}
for u in all_units:
    sub_u = df_hist[df_hist["unit"] == u]
    sub_latest = (
        sub_u[sub_u["direction"] != "T"]
        .sort_values("date")
        .groupby(["equipment", "titik", "direction"], as_index=False)
        .last()
    )
    if not sub_latest.empty:
        zones = sub_latest.apply(
            lambda r: get_zone(r["value"], get_threshold(r["equipment"]))[0], axis=1
        )
        n_danger = (zones == "ZONE D").sum()
        n_warn = (zones == "ZONE C").sum()
        if n_danger > 0:
            unit_status_summary[u] = f"🔴 {u} ({n_danger})"
        elif n_warn > 0:
            unit_status_summary[u] = f"🟡 {u} ({n_warn})"
        else:
            unit_status_summary[u] = f"✅ {u}"
    else:
        unit_status_summary[u] = u

unit_display_options = ["🏢 Semua Bagian Unit"] + [unit_status_summary[u] for u in all_units]
unit_map_reverse = {unit_status_summary[u]: u for u in all_units}
unit_map_reverse["🏢 Semua Bagian Unit"] = "All"

st.caption("**🏭 Bagian Unit Pembangkit**")
sel_unit_label = st.segmented_control(
    "Bagian Unit",
    options=unit_display_options,
    default="🏢 Semua Bagian Unit",
    key="mon_unit_segmented",
    label_visibility="collapsed"
)

sel_unit_raw = unit_map_reverse.get(sel_unit_label, "All")
sel_unit = all_units if sel_unit_raw == "All" else [sel_unit_raw]

all_equip = sorted(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())

# Reset session_state equipment saat unit berganti
if st.session_state.get("_last_unit") != sel_unit_raw:
    st.session_state["mon_equip"] = all_equip
    st.session_state["_last_unit"] = sel_unit_raw

# Filter Tambahan: Equipment & Mode Tanggal
c_eq, c_dt = st.columns([3, 2])
with c_eq:
    with st.expander(f"⚙️ Filter Spesifik Equipment ({len(all_equip)} mesin)", expanded=False):
        if st.button("Pilih Semua Mesin", key="eq_selall", width="stretch"):
            st.session_state["mon_equip"] = all_equip
        if "mon_equip" in st.session_state:
            st.session_state["mon_equip"] = [
                e for e in st.session_state["mon_equip"] if e in all_equip
            ]
        sel_equip = st.multiselect("Equipment", all_equip, key="mon_equip", label_visibility="collapsed")

if not sel_equip:
    sel_equip = all_equip

with c_dt:
    date_mode = st.radio(
        "Mode Tampilan",
        ["🕐 Nilai Terbaru", "📅 Tanggal Tertentu"],
        horizontal=True,
        key="mon_date_mode",
        label_visibility="collapsed"
    )

sel_tgl_str = None
if date_mode == "📅 Tanggal Tertentu":
    sel_tgl = st.date_input("Pilih Tanggal", value=max(all_dates), min_value=min(all_dates), max_value=max(all_dates), key="mon_tgl")
    sel_tgl_str = pd.to_datetime(sel_tgl).strftime("%Y-%m-%d")
    df_base = df_hist[
        df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip) &
        (df_hist["date"].dt.date == sel_tgl)
    ].copy()
    st.caption(f"Data arsip tanggal: **{pd.to_datetime(sel_tgl_str).strftime('%d %b %Y')}**")
else:
    df_base = df_hist[
        df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip)
    ].copy()
    _last_date = df_hist["date"].max()
    _last_date_str = pd.to_datetime(_last_date).strftime("%d %b %Y") if pd.notna(_last_date) else "–"
    st.caption(f"Menampilkan kondisi **paling mutakhir** (Data terakhir: **{_last_date_str}**)")

if df_base.empty:
    st.warning("⚠️ Tidak ada data pengukuran yang sesuai dengan filter yang dipilih.")
    st.stop()

df_base = add_zone_cols(df_base)

latest_all = (
    df_base
    .sort_values("date")
    .groupby(["unit", "equipment", "titik", "direction"], as_index=False)
    .last()
)

latest      = latest_all[latest_all["direction"] != "T"].copy()
latest_temp = latest_all[latest_all["direction"] == "T"].copy()

total = len(latest)
n_d = int((latest["zone"] == "ZONE D").sum())
n_c = int((latest["zone"] == "ZONE C").sum())
n_b = int((latest["zone"] == "ZONE B").sum())
n_a = int((latest["zone"] == "ZONE A").sum())

# ══════════════════════════════════════════════════════════════════════════════
# KPI STATISTIK
# ══════════════════════════════════════════════════════════════════════════════
kpi_items = [
    ("📊", "Total Titik", str(total), "#6366f1"),
    ("🔵", "Accepted (A)", str(n_a), "#2563eb"),
    ("🟢", "Pre Warning (B)", str(n_b), "#16a34a"),
    ("🟡", "Warning (C)", str(n_c), "#d97706"),
    ("🔴", "Danger (D)", str(n_d), "#dc2626"),
]
kpi_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:8px 0 14px">'
for ico, lbl, val, col in kpi_items:
    kpi_html += f"""
<div style="background:{col}15;border:1px solid {col}30;border-radius:12px;padding:12px 8px;text-align:center">
  <div style="font-size:24px;font-weight:800;color:{col};line-height:1">{val}</div>
  <div style="font-size:11px;margin-top:4px;opacity:.75;font-weight:600">{ico} {lbl}</div>
</div>"""
kpi_html += "</div>"
st.markdown(kpi_html, unsafe_allow_html=True)

# Filter Status Kartu
_zone_filter_map = {
    "Semua Status": None,
    f"🔴 Danger ({n_d})": "ZONE D",
    f"🟡 Warning ({n_c})": "ZONE C",
    f"🟢 Pre Warning ({n_b})": "ZONE B",
    f"🔵 Accepted ({n_a})": "ZONE A",
}
zone_filter_label = st.radio(
    "Filter Status Mesin", list(_zone_filter_map.keys()),
    horizontal=True, key="zone_filter", label_visibility="collapsed"
)
zone_filter_key = _zone_filter_map[zone_filter_label]

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# STATUS CARD PER EQUIPMENT (GRID VIEW)
# ══════════════════════════════════════════════════════════════════════════════
df_card_lat = latest[
    latest["unit"].isin(sel_unit) &
    latest["equipment"].isin(sel_equip)
].copy()

df_temp_lat = latest_temp[
    latest_temp["unit"].isin(sel_unit) &
    latest_temp["equipment"].isin(sel_equip)
].copy()

def _max_dir(df_eq, d):
    sub = df_eq[df_eq["direction"] == d][["value", "titik"]].dropna(subset=["value"])
    if sub.empty: return None, None
    idx = sub["value"].idxmax()
    return float(sub.loc[idx, "value"]), str(sub.loc[idx, "titik"])

def _max_temp(eq):
    sub = df_temp_lat[df_temp_lat["equipment"] == eq][["value", "titik"]].dropna(subset=["value"])
    if sub.empty: return None, None
    idx = sub["value"].idxmax()
    return float(sub.loc[idx, "value"]), str(sub.loc[idx, "titik"])

def _render_pill(label, val, unit_s, zk, titik):
    if val is None or pd.isna(val):
        return f"""
<div class="pill-item" style="background:rgba(128,128,128,.08);">
  <div style="font-size:10px;font-weight:700;opacity:.4;">{label}</div>
  <div style="font-size:13px;font-weight:600;opacity:.3;">–</div>
</div>"""
    c = ZC.get(zk, "#6b7280")
    bg = ZB.get(zk, "transparent")
    val_str = f"{val:.1f}" if unit_s == "°C" else f"{val:.2f}"
    return f"""
<div class="pill-item" title="{titik or ''}" style="background:{bg};border-color:{c}40;">
  <div style="font-size:10px;font-weight:700;color:{c};">{label}</div>
  <div style="font-size:13px;font-weight:800;color:{c};">{val_str}</div>
</div>"""

eq_rows = []
for eq in sorted(df_card_lat["equipment"].dropna().unique()):
    if eq not in sel_equip: continue
    df_eq = df_card_lat[df_card_lat["equipment"] == eq]
    thr   = get_threshold(eq)
    hv, ht = _max_dir(df_eq, "H")
    vv, vt = _max_dir(df_eq, "V")
    av, at = _max_dir(df_eq, "A")
    all_v  = [x for x in [hv, vv, av] if x is not None and not pd.isna(x)]
    mx     = max(all_v) if all_v else float("nan")
    zk, zi, zl = get_zone(mx, thr)
    tv, tt = _max_temp(eq)
    tgl = pd.to_datetime(df_eq["date"].max()).strftime("%d %b %Y") if pd.notna(df_eq["date"].max()) else "–"
    eq_rows.append(dict(eq=eq, unit=df_eq["unit"].iloc[0],
        H=hv, Ht=ht, V=vv, Vt=vt, A=av, At=at, T=tv, Tt=tt,
        zk=zk, zi=zi, zl=zl, thr=thr, tgl=tgl, mx=mx))

if zone_filter_key:
    eq_rows = [r for r in eq_rows if r["zk"] == zone_filter_key]

@st.fragment(run_every="5s")
def _render_cards():
    df_runtime_now = get_pump_runtime()

    def _runtime_box(eq, unit):
        match = df_runtime_now[
            (df_runtime_now["equipment"] == eq) & (df_runtime_now["unit"] == unit)
        ] if not df_runtime_now.empty else pd.DataFrame()
        
        if match.empty:
            return '<div style="font-size:11px;opacity:.5;margin-bottom:6px;">⏱️ Jam operasi belum diatur</div>'
        
        row_data = match.iloc[0].to_dict()
        hours  = compute_running_hours(row_data)
        status = row_data.get("status", "stopped")
        rc = "#16a34a" if status == "running" else "#6b7280"
        dot = "🟢 Running" if status == "running" else "⚪ Stopped"
        
        return f"""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:11px;">
  <span style="color:{rc};font-weight:700;">{dot}</span>
  <span style="font-weight:700;opacity:.85;">⏱️ {hours:,.1f} jam</span>
</div>"""

    for i in range(0, len(eq_rows), 3):
        cols = st.columns(3)
        for col, r in zip(cols, eq_rows[i:i+3]):
            bc = ZC.get(r["zk"], "#6b7280")
            bar = bar_pct(r["mx"], r["thr"]) if not pd.isna(r["mx"]) else 0
            is_danger = r["zk"] == "ZONE D"
            border_left = f"6px solid {bc}" if is_danger else f"4px solid {bc}"
            
            zk_h = get_zone(r["H"], r["thr"])[0] if r["H"] is not None else "N/A"
            zk_v = get_zone(r["V"], r["thr"])[0] if r["V"] is not None else "N/A"
            zk_a = get_zone(r["A"], r["thr"])[0] if r["A"] is not None else "N/A"
            zk_t = get_zone_temp(r["T"], get_temp_threshold(r["eq"], r["Tt"]))[0] if r["T"] is not None else "N/A"

            pills_html = f"""
<div class="pill-grid">
  {_render_pill("H (mm/s)", r['H'], "mm/s", zk_h, r['Ht'])}
  {_render_pill("V (mm/s)", r['V'], "mm/s", zk_v, r['Vt'])}
  {_render_pill("A (mm/s)", r['A'], "mm/s", zk_a, r['At'])}
  {_render_pill("T (°C)", r['T'], "°C", zk_t, r['Tt'])}
</div>"""

            with col:
                st.markdown(f"""
<div class="eq-card-modern" style="border-left:{border_left};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-size:15px;font-weight:800;line-height:1.2;">{r['eq']}</div>
      <div style="font-size:11px;opacity:.5;margin-bottom:6px;">{r['unit']}</div>
    </div>
    <span style="font-size:11px;font-weight:700;color:{bc};background:{ZB.get(r['zk'],'transparent')};padding:2px 8px;border-radius:99px;border:1px solid {bc}40;">
      {r['zi']} {r['zl']}
    </span>
  </div>
  {_runtime_box(r['eq'], r['unit'])}
  <div style="display:flex;justify-content:space-between;font-size:12px;margin-top:4px;">
    <span style="opacity:.6;">Max Vibrasi:</span>
    <span style="font-weight:700;color:{bc};">{r['mx']:.3f} mm/s</span>
  </div>
  <div style="height:3px;border-radius:2px;background:rgba(128,128,128,.15);overflow:hidden;margin-top:4px;">
    <div style="height:3px;width:{bar}%;background:{bc};"></div>
  </div>
  {pills_html}
</div>""", unsafe_allow_html=True)

_render_cards()

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# DETAIL LENGKAP SEMUA PENGUKURAN (TABLE VIEW)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🔍 Matriks Pengukuran Seluruh Titik")

da, db = st.columns([5, 3])
with da:
    st.caption("**Bagian Unit**")
    det_unit_opts = ["All"] + sorted(latest["unit"].dropna().unique())
    det_unit_sel  = st.radio("det_unit", det_unit_opts, horizontal=True, key="det_unit", label_visibility="collapsed")
with db:
    st.caption("**Arah Vibrasi Terpilih**")
    det_dir_sel = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="det_dir_multi", label_visibility="collapsed")
    if not det_dir_sel: det_dir_sel = ["H","V","A"]

show_temp_col = st.checkbox("🌡️ Tampilkan Kolom Temperatur (°C)", value=True, key="det_show_temp") if not latest_temp.empty else False

df_det = latest.copy()
df_det_temp = latest_temp.copy()
if det_unit_sel != "All":
    df_det = df_det[df_det["unit"] == det_unit_sel]
    df_det_temp = df_det_temp[df_det_temp["unit"] == det_unit_sel]

def _val_td(val, thr, show=True):
    if not show or val is None or pd.isna(val):
        return '<td style="text-align:center;padding:8px 10px;opacity:.25;">–</td>'
    zk = get_zone(val, thr)[0]
    tc = ZC.get(zk, "#6b7280")
    bg = ZB.get(zk, "transparent")
    return f'<td style="text-align:center;padding:8px 10px;background:{bg};"><span style="font-weight:700;color:{tc};">{val:.3f}</span></td>'

def _val_td_temp(val, thr, show=True):
    if not show or val is None or pd.isna(val):
        return '<td style="text-align:center;padding:8px 10px;opacity:.25;">–</td>'
    zk = get_zone_temp(val, thr)[0]
    tc = ZC.get(zk, "#6b7280")
    bg = ZB.get(zk, "transparent")
    return f'<td style="text-align:center;padding:8px 10px;background:{bg};"><span style="font-weight:700;color:{tc};">{val:.1f}°C</span></td>'

def _badge_td(zk, zi, zl):
    tc = ZC.get(zk, "#6b7280")
    bg = ZB.get(zk, "transparent")
    return f'<td style="padding:8px 12px;text-align:center;"><span style="background:{bg};color:{tc};border:1px solid {tc}40;border-radius:99px;padding:3px 10px;font-size:11px;font-weight:700;">{zi} {zl}</span></td>'

def _render_tbl(df_unit, unit_label, df_unit_temp=None):
    equips = sorted(df_unit["equipment"].dropna().unique())
    if not equips: return ""

    dir_th = "".join(f'<th style="text-align:center;min-width:75px">{d}</th>' for d in ["H","V","A"] if d in det_dir_sel)
    temp_th = '<th style="text-align:center;min-width:75px">Suhu</th>' if show_temp_col else ""

    rows = ""
    for eq in equips:
        df_eq = df_unit[df_unit["equipment"] == eq].sort_values("titik")
        thr   = get_threshold(eq)
        titiks = sorted(df_eq["titik"].dropna().unique())

        _all_vals_eq = df_eq["value"].dropna().tolist()
        _worst_zone = "ZONE A"
        _zone_order = {"ZONE D": 4, "ZONE C": 3, "ZONE B": 2, "ZONE A": 1, "N/A": 0}
        for _v in _all_vals_eq:
            _zk = get_zone(_v, thr)[0]
            if _zone_order.get(_zk, 0) > _zone_order.get(_worst_zone, 0):
                _worst_zone = _zk
        eq_border = ZC.get(_worst_zone, "#6b7280")

        for i, titik in enumerate(titiks):
            df_t = df_eq[df_eq["titik"] == titik]

            gv = lambda d, _df=df_t: (
                float(_df[_df["direction"] == d]["value"].dropna().iloc[0])
                if not _df[_df["direction"] == d]["value"].dropna().empty else None
            )

            h, v, a = gv("H"), gv("V"), gv("A")
            all_v = [x for x in [h, v, a] if x is not None]
            max_v = max(all_v) if all_v else float("nan")
            zk, zi, zl = get_zone(max_v, thr)

            temp_td = ""
            if show_temp_col:
                t_val = None
                if df_unit_temp is not None and not df_unit_temp.empty:
                    sub_t = df_unit_temp[(df_unit_temp["equipment"] == eq) & (df_unit_temp["titik"] == titik)]["value"].dropna()
                    if not sub_t.empty: t_val = float(sub_t.iloc[0])
                temp_td = _val_td_temp(t_val, get_temp_threshold(eq, titik))

            tgl = pd.to_datetime(df_t["date"].max()).strftime("%d %b %Y") if pd.notna(df_t["date"].max()) else "–"

            eq_td = f'<td rowspan="{len(titiks)}" style="padding:10px 14px;font-size:13px;font-weight:700;vertical-align:middle;border-left:4px solid {eq_border};background:rgba(128,128,128,.03);">{eq}</td>' if i == 0 else ""

            rows += (
                f'<tr>'
                + eq_td
                + f'<td style="padding:8px 14px;opacity:.85;">{titik}</td>'
                + _val_td(h, thr, "H" in det_dir_sel)
                + _val_td(v, thr, "V" in det_dir_sel)
                + _val_td(a, thr, "A" in det_dir_sel)
                + _val_td(max_v, thr)
                + temp_td
                + _badge_td(zk, zi, zl)
                + f'<td style="padding:8px 14px;font-size:11px;opacity:.5;text-align:right;">{tgl}</td>'
                + '</tr>'
            )

    return (
        f'<div style="margin-bottom:24px;">'
        f'<div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;opacity:.6;margin-bottom:8px;">🏭 {unit_label}</div>'
        f'<div class="vt-wrap"><table class="vt"><thead><tr>'
        f'<th style="text-align:left;min-width:140px;">Equipment</th>'
        f'<th style="text-align:left;min-width:120px;">Titik Ukur</th>'
        f'{dir_th}'
        f'<th style="text-align:center;min-width:80px;">Max</th>'
        f'{temp_th}'
        f'<th style="text-align:center;min-width:100px;">Status ISO</th>'
        f'<th style="text-align:right;min-width:90px;">Tanggal</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div></div>'
    )

if det_unit_sel == "All":
    for u in sorted(df_det["unit"].dropna().unique()):
        blk = _render_tbl(df_det[df_det["unit"] == u], f"Bagian Unit · {u}", df_det_temp[df_det_temp["unit"] == u])
        if blk: st.markdown(blk, unsafe_allow_html=True)
else:
    blk = _render_tbl(df_det, f"Bagian Unit · {det_unit_sel}", df_det_temp)
    if blk: st.markdown(blk, unsafe_allow_html=True)
