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

.eq-card{ cursor:pointer; }
.eq-card:hover{ border-left-width:5px !important; }

.vt-wrap{
    border-radius:12px; overflow:hidden;
    border:1px solid color-mix(in srgb, currentColor 12%, transparent);
    margin-bottom:24px;
    box-shadow:0 2px 16px rgba(0,0,0,.15);
}
.vt{
    width:100%; border-collapse:collapse; font-size:13px;
    background: color-mix(in srgb, var(--background-color) 95%, transparent);
    color: inherit;
}
.vt thead tr{
    background: color-mix(in srgb, var(--secondary-background-color) 100%, transparent);
    border-bottom:2px solid color-mix(in srgb, currentColor 10%, transparent);
}
.vt thead th{
    padding:12px 14px; font-size:11px; font-weight:700;
    text-transform:uppercase; letter-spacing:.09em;
    color:inherit; opacity:.55; white-space:nowrap;
}
.vt tbody tr{
    border-bottom:1px solid color-mix(in srgb, currentColor 6%, transparent);
    transition:background .1s;
}
.vt tbody tr:hover{ filter:brightness(1.06); }
.vt td{ padding:9px 14px; vertical-align:middle; }
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

def bar_pct(val, thr):
    """Hitung persentase bar berdasarkan threshold ZONE D (batas kritis) equipment."""
    max_scale = thr.get("C", 4.5) * 1.2
    return min(int((val / max(max_scale, 0.001)) * 100), 100)

# ── Data ──────────────────────────────────────────────────────────────────────
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
    st.page_link("app.py",                 label="📊 Monitor Vibrasi")
    st.page_link("pages/1_Analisis.py",    label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py", label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py",label="🛠️ Kelola Pompa")
    st.divider()
    if st.button("🔄 Refresh Data", key="sb_refresh", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()
    st.divider()
    if not df_hist.empty:
        df_chk = df_hist.copy()
        df_chk["value"] = pd.to_numeric(df_chk["value"], errors="coerce")
        lc = df_chk.sort_values("date").groupby(
            ["unit","equipment","titik","direction"], as_index=False).last()
        def _lc_zone(r):
            if r["direction"] == "T":
                return get_zone_temp(r["value"], get_temp_threshold(r["equipment"], r["titik"]))[0]
            return get_zone(r["value"], get_threshold(r["equipment"]))[0]
        zones_lc = lc.apply(_lc_zone, axis=1)
        nd = int((zones_lc=="ZONE D").sum())
        nc = int((zones_lc=="ZONE C").sum())
        if nd > 0:
            st.error(f"🔴 {nd} titik Danger")
        elif nc > 0:
            st.warning(f"🟡 {nc} titik Warning")
        else:
            st.success("✅ Semua titik normal")

if df_hist.empty:
    st.info("📂 Belum ada data. Upload file Excel di halaman **Data & Kelola**.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
all_units = sorted(df_hist["unit"].dropna().unique())
all_dates = sorted(df_hist["date"].dt.date.dropna().unique(), reverse=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER + FILTER
# ══════════════════════════════════════════════════════════════════════════════
render_page_header("📊 Monitor Vibrasi")

@st.fragment(run_every="1s")
def _live_clock():
    _now = datetime.now()
    _hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][_now.weekday()]
    _bulan = ["","Januari","Februari","Maret","April","Mei","Juni","Juli",
              "Agustus","September","Oktober","November","Desember"][_now.month]
    st.markdown(
        f'<div style="font-size:13px;opacity:.6;margin-top:-8px;margin-bottom:10px">'
        f'🕐 {_hari}, {_now.day} {_bulan} {_now.year} — '
        f'<span style="font-variant-numeric:tabular-nums;font-weight:600">{_now.strftime("%H:%M:%S")}</span>'
        f'</div>', unsafe_allow_html=True)

_live_clock()

fa, fb, fc = st.columns([2, 3, 3])
with fa:
    st.caption("**🏭 Unit**")
    sel_unit_btn = st.radio("Unit", ["All"]+all_units, horizontal=True,
                            key="mon_unit", label_visibility="collapsed")
    sel_unit = all_units if sel_unit_btn=="All" else [sel_unit_btn]

all_equip = sorted(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())

if st.session_state.get("_last_unit") != sel_unit_btn:
    st.session_state["mon_equip"] = all_equip
    st.session_state["_last_unit"] = sel_unit_btn

with fb:
    st.caption("**⚙️ Equipment**")
    with st.expander(f"Filter ({len(all_equip)} equipment)", expanded=False):
        col_selall, _ = st.columns([1,3])
        if col_selall.button("Pilih Semua", key="eq_selall", width="stretch"):
            st.session_state["mon_equip"] = all_equip
        if "mon_equip" in st.session_state:
            st.session_state["mon_equip"] = [
                e for e in st.session_state["mon_equip"] if e in all_equip
            ]
        sel_equip = st.multiselect("Equipment", all_equip,
                                   key="mon_equip", label_visibility="collapsed")

if not sel_equip:
    sel_equip = all_equip

_valid_equip_now = set(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())
if not any(e in _valid_equip_now for e in sel_equip):
    sel_equip = sorted(_valid_equip_now)

with fc:
    st.caption("**📅 Tampilkan**")
    date_mode = st.radio("Mode", ["🕐 Terbaru","📅 Pilih tanggal"],
                         horizontal=True, key="mon_date_mode", label_visibility="collapsed")

sel_tgl_str = None
if date_mode == "📅 Pilih tanggal":
    sel_tgl = st.date_input("Tanggal", value=max(all_dates),
                            min_value=min(all_dates), max_value=max(all_dates),
                            key="mon_tgl")
    sel_tgl_str = pd.to_datetime(sel_tgl).strftime("%Y-%m-%d")
    df_base = df_hist[
        df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip) &
        (df_hist["date"].dt.date == sel_tgl)
    ].copy()
    st.caption(f"Data **{pd.to_datetime(sel_tgl_str).strftime('%d %b %Y')}**")
else:
    df_base = df_hist[
        df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip)
    ].copy()
    _last_date = df_hist["date"].max()
    _last_date_str = pd.to_datetime(_last_date).strftime("%d %b %Y") if pd.notna(_last_date) else "–"
    st.caption(f"Nilai **terbaru** per titik ukur · Data terakhir: **{_last_date_str}**")

if df_base.empty:
    st.warning(
        "Tidak ada data sesuai filter.\n\n"
        "💡 Coba ubah rentang tanggal, pilih unit lain, atau periksa apakah data sudah diupload "
        "di halaman **Data & Kelola**."
    )
    st.stop()

df_base = add_zone_cols(df_base)

latest_all = (
    df_base
    .sort_values("date")
    .groupby(
        ["unit", "equipment", "titik", "direction"],
        as_index=False
    )
    .last()
)

latest      = latest_all[latest_all["direction"] != "T"].copy()
latest_temp = latest_all[latest_all["direction"] == "T"].copy()

total = len(latest)
n_d = int((latest["zone"]=="ZONE D").sum())
n_c = int((latest["zone"]=="ZONE C").sum())
n_b = int((latest["zone"]=="ZONE B").sum())
n_a = int((latest["zone"]=="ZONE A").sum())

# ══════════════════════════════════════════════════════════════════════════════
# KPI
# ══════════════════════════════════════════════════════════════════════════════
kpi_items = [
    ("📊","Total Titik",str(total),"#6366f1"),
    ("🔴","Danger",     str(n_d),  "#dc2626"),
    ("🟡","Warning",    str(n_c),  "#d97706"),
    ("🟢","Pre Warning",str(n_b),  "#16a34a"),
    ("🔵","Accepted",   str(n_a),  "#2563eb"),
]
kpi_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:12px 0 16px">'
for ico, lbl, val, col in kpi_items:
    kpi_html += f"""
<div style="background:{col}18;border:1px solid {col}30;border-radius:12px;
            padding:14px 10px;text-align:center">
  <div style="font-size:26px;font-weight:800;color:{col};line-height:1">{val}</div>
  <div style="font-size:11px;margin-top:5px;opacity:.7;font-weight:500">{ico} {lbl}</div>
</div>"""
kpi_html += "</div>"
st.markdown(kpi_html, unsafe_allow_html=True)

pct = {z: round(n/total*100) if total else 0
       for z,n in zip(["A","B","C","D"],[n_a,n_b,n_c,n_d])}
st.markdown(f"""
<div style="margin-bottom:20px">
  <div style="display:flex;justify-content:space-between;
              font-size:11px;opacity:.5;margin-bottom:5px">
    <span>Distribusi Kondisi</span><span>{total} titik ukur</span>
  </div>
  <div style="height:8px;border-radius:4px;overflow:hidden;display:flex;
              background:rgba(128,128,128,.15)">
    <div style="width:{pct['A']}%;background:#2563eb"></div>
    <div style="width:{pct['B']}%;background:#16a34a"></div>
    <div style="width:{pct['C']}%;background:#d97706"></div>
    <div style="width:{pct['D']}%;background:#dc2626"></div>
  </div>
  <div style="display:flex;gap:14px;font-size:11px;margin-top:6px;flex-wrap:wrap">
    <span style="color:#2563eb;font-weight:600">🔵 Accepted {pct['A']}% ({n_a})</span>
    <span style="color:#16a34a;font-weight:600">🟢 Pre Warning {pct['B']}% ({n_b})</span>
    <span style="color:#d97706;font-weight:600">🟡 Warning {pct['C']}% ({n_c})</span>
    <span style="color:#dc2626;font-weight:600">🔴 Danger {pct['D']}% ({n_d})</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FILTER ZONE
# ══════════════════════════════════════════════════════════════════════════════
_zone_filter_map = {
    "Semua":        None,
    f"🔵 Accepted ({n_a})":    "ZONE A",
    f"🟢 Pre Warning ({n_b})": "ZONE B",
    f"🟡 Warning ({n_c})":     "ZONE C",
    f"🔴 Danger ({n_d})":      "ZONE D",
}
zone_filter_label = st.radio(
    "Filter kartu berdasarkan status", list(_zone_filter_map.keys()),
    horizontal=True, key="zone_filter", label_visibility="collapsed",
)
zone_filter_key = _zone_filter_map[zone_filter_label]

# ══════════════════════════════════════════════════════════════════════════════
# STATUS CARD PER EQUIPMENT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🏭 Status per Equipment")

df_card = df_hist[
    df_hist["unit"].isin(sel_unit) & df_hist["equipment"].isin(sel_equip) &
    df_hist["value"].notna()
].copy()
if sel_tgl_str:
    df_card = df_card[df_card["date"].dt.strftime("%Y-%m-%d")==sel_tgl_str]

if df_card.empty:
    st.warning("Tidak ada data equipment.")
    st.stop()

df_card_lat = latest[
    latest["unit"].isin(sel_unit) &
    latest["equipment"].isin(sel_equip)
].copy()

def _max_dir(df_eq, d):
    sub = df_eq[df_eq["direction"]==d][["value","titik"]].dropna(subset=["value"])
    if sub.empty: return None, None
    idx = sub["value"].idxmax()
    return float(sub.loc[idx,"value"]), str(sub.loc[idx,"titik"])

df_temp_lat = latest_temp[
    latest_temp["unit"].isin(sel_unit) &
    latest_temp["equipment"].isin(sel_equip)
].copy()

def _max_temp(eq):
    sub = df_temp_lat[df_temp_lat["equipment"]==eq][["value","titik"]].dropna(subset=["value"])
    if sub.empty: return None, None
    idx = sub["value"].idxmax()
    return float(sub.loc[idx,"value"]), str(sub.loc[idx,"titik"])

def _temp_pill(equipment, val, titik):
    if val is None or pd.isna(val):
        return (f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;'
                f'background:rgba(128,128,128,.1);border-radius:8px;padding:6px 4px;gap:1px">'
                f'<span style="font-size:12px;font-weight:700;opacity:.4">T</span>'
                f'<span style="font-size:15px;opacity:.3">–</span>'
                f'<span style="font-size:10px;opacity:.25">–</span></div>')
    thr = get_temp_threshold(equipment, titik)
    zk  = get_zone_temp(val, thr)[0]
    c   = ZC.get(zk,"#6b7280")
    bg  = ZB.get(zk,"transparent")
    ts  = (titik[:10]+"…") if titik and len(titik)>11 else (titik or "")
    return (f'<div title="{titik}" style="flex:1;display:flex;flex-direction:column;align-items:center;'
            f'background:{bg};border-radius:8px;padding:6px 4px;gap:1px;cursor:default">'
            f'<span style="font-size:12px;font-weight:700;color:{c};opacity:.8">T°C</span>'
            f'<span style="font-size:15px;font-weight:700;color:{c}">{val:.1f}</span>'
            f'<span style="font-size:10px;color:{c};opacity:.65;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;max-width:100%">{ts}</span></div>')

def _dir_pill(label, val, thr, titik):
    if val is None or pd.isna(val):
        return (f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;'
                f'background:rgba(128,128,128,.1);border-radius:8px;padding:6px 4px;gap:1px">'
                f'<span style="font-size:12px;font-weight:700;opacity:.4">{label}</span>'
                f'<span style="font-size:15px;opacity:.3">–</span>'
                f'<span style="font-size:10px;opacity:.25">–</span></div>')
    zk = get_zone(val, thr)[0]
    c  = ZC.get(zk,"#6b7280")
    bg = ZB.get(zk,"transparent")
    ts = (titik[:10]+"…") if titik and len(titik)>11 else (titik or "")
    return (f'<div title="{titik}" style="flex:1;display:flex;flex-direction:column;align-items:center;'
            f'background:{bg};border-radius:8px;padding:6px 4px;gap:1px;cursor:default">'
            f'<span style="font-size:12px;font-weight:700;color:{c};opacity:.8">{label}</span>'
            f'<span style="font-size:15px;font-weight:700;color:{c}">{val:.3f}</span>'
            f'<span style="font-size:10px;color:{c};opacity:.65;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;max-width:100%">{ts}</span></div>')

eq_rows = []
for eq in sorted(df_card_lat["equipment"].dropna().unique()):
    if eq not in sel_equip: continue
    df_eq = df_card_lat[df_card_lat["equipment"]==eq]
    thr   = get_threshold(eq)
    hv, ht = _max_dir(df_eq,"H")
    vv, vt = _max_dir(df_eq,"V")
    av, at = _max_dir(df_eq,"A")
    all_v  = [x for x in [hv,vv,av] if x is not None and not pd.isna(x)]
    mx     = max(all_v) if all_v else float("nan")
    zk,zi,zl = get_zone(mx, thr)
    tv, tt = _max_temp(eq)
    tgl = pd.to_datetime(df_eq["date"].max()).strftime("%d %b %Y") if pd.notna(df_eq["date"].max()) else "–"
    eq_rows.append(dict(eq=eq, unit=df_eq["unit"].iloc[0],
        H=hv,Ht=ht, V=vv,Vt=vt, A=av,At=at, T=tv,Tt=tt,
        zk=zk,zi=zi,zl=zl, thr=thr, tgl=tgl, mx=mx))

if zone_filter_key:
    eq_rows = [r for r in eq_rows if r["zk"] == zone_filter_key]

@st.fragment(run_every="5s")
def _render_equipment_cards():
    df_runtime_now = get_pump_runtime()

    def _runtime_badge(eq, unit):
        match = df_runtime_now[
            (df_runtime_now["equipment"]==eq) & (df_runtime_now["unit"]==unit)
        ] if not df_runtime_now.empty else pd.DataFrame()
        if match.empty:
            return (
                '<div style="margin-bottom:8px;padding:6px 8px;border-radius:8px;'
                'background:rgba(128,128,128,.1)">'
                '<span style="font-size:11px;opacity:.5">⏱️ Running hours belum diisi — '
                'buka halaman 🛠️ Kelola Pompa</span></div>'
            )
        row_data = match.iloc[0].to_dict()
        hours  = compute_running_hours(row_data)
        status = row_data.get("status", "stopped")
        age    = get_pump_age(row_data.get("install_date"))
        rc = "#16a34a" if status == "running" else "#6b7280"
        dot = "🟢" if status == "running" else "⚪"
        age_html = (
            f'<span style="font-size:10px;opacity:.55">📅 Umur: {age}</span>'
            if age else ""
        )
        return (
            f'<div style="margin-bottom:8px;padding:6px 8px;border-radius:8px;background:{rc}12">'
            f'<div style="display:flex;align-items:center;justify-content:space-between">'
            f'<span style="font-size:11px;font-weight:600;color:{rc}">{dot} '
            f'{"Running" if status=="running" else "Stopped"}</span>'
            f'<span style="font-size:12px;font-weight:700;color:{rc};font-variant-numeric:tabular-nums">'
            f'⏱️ {hours:,.1f} jam</span></div>'
            f'{age_html}</div>'
        )

    for i in range(0, len(eq_rows), 3):
        cols = st.columns(3)
        for col, r in zip(cols, eq_rows[i:i+3]):
            bc  = ZC.get(r["zk"],"#6b7280")
            bg  = ZB.get(r["zk"],"transparent")
            bar = bar_pct(r["mx"], r["thr"]) if not pd.isna(r["mx"]) else 0
            rt_html = _runtime_badge(r["eq"], r["unit"])
            is_danger = r["zk"] == "ZONE D"
            border_w = "6px" if is_danger else "4px"
            shadow   = UI["shadow_danger"] if is_danger else "none"

            with col:
                detail_html = f"""{rt_html}
<div style="display:flex;gap:5px">
  {_dir_pill("H",r['H'],r['thr'],r['Ht'])}
  {_dir_pill("V",r['V'],r['thr'],r['Vt'])}
  {_dir_pill("A",r['A'],r['thr'],r['At'])}
  {_temp_pill(r['eq'],r['T'],r['Tt'])}
</div>"""
                st.markdown(f"""
<div class="eq-card" style="
  border:1px solid {bc}30; border-left:{border_w} solid {bc};
  border-radius:0 {UI['radius_card']} {UI['radius_card']} 0; padding:{UI['pad_card']};
  margin-bottom:10px; background:{bg}; box-shadow:{shadow};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px">
    <div style="font-size:{UI['font_lg']};font-weight:700;line-height:1.3">{r['eq']}</div>
    <div style="font-size:{UI['font_sm']};opacity:.45;white-space:nowrap;margin-left:6px">{r['tgl']}</div>
  </div>
  <div style="font-size:{UI['font_base']};opacity:.45;margin-bottom:8px">{r['unit']}</div>
  <div style="display:flex;align-items:center;justify-content:space-between">
    <span style="font-size:{UI['font_md']};font-weight:700;color:{bc}">{r['zi']} {r['zl']}</span>
    <span style="font-size:{UI['font_base']};font-weight:600;color:{bc};opacity:.8">{r['mx']:.3f} mm/s</span>
  </div>
  <div style="height:3px;border-radius:2px;background:rgba(128,128,128,.2);overflow:hidden;margin-top:6px">
    <div style="height:3px;width:{bar}%;background:{bc};border-radius:2px"></div>
  </div>
  <details style="margin-top:10px">
    <summary style="cursor:pointer;font-size:{UI['font_sm']};font-weight:600;opacity:.6;
                    list-style:none;outline:none">▸ Detail vibrasi &amp; suhu</summary>
    <div style="margin-top:8px">{detail_html}</div>
  </details>
</div>""", unsafe_allow_html=True)

_render_equipment_cards()

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# ALARM AKTIF
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🚨 Alarm Aktif")

latest["zone_label"] = latest.apply(
    lambda r: get_zone(r["value"],THRESHOLD[r["thr_type"]])[1]+" "+
              get_zone(r["value"],THRESHOLD[r["thr_type"]])[2], axis=1)

df_d = latest[latest["zone"]=="ZONE D"]
df_c = latest[latest["zone"]=="ZONE C"]

if df_d.empty and df_c.empty:
    st.success("✅ Tidak ada alarm aktif — semua titik dalam batas normal.")
else:
    def _alarm_tbl(df_alarm, accent):
        rows = ""
        for _,r in df_alarm.sort_values(["equipment","titik"]).iterrows():
            val  = r["value"]
            thr  = get_threshold(r["equipment"])
            bar  = bar_pct(val, thr)
            tc   = ZC.get(r["zone"],"#6b7280")
            rows += (
                f'<tr>'
                f'<td style="padding:9px 12px;font-weight:600;white-space:nowrap">{r["unit"]}</td>'
                f'<td style="padding:9px 12px;font-weight:600">{r["equipment"]}</td>'
                f'<td style="padding:9px 12px">{r["titik"]}</td>'
                f'<td style="padding:9px 12px;text-align:center;font-weight:700">{r["direction"]}</td>'
                f'<td style="padding:9px 12px;text-align:center">'
                f'<span style="font-size:13px;font-weight:800;color:{tc}">{val:.3f}</span>'
                f'<div style="margin-top:3px;height:2px;border-radius:1px;background:rgba(128,128,128,.2)">'
                f'<div style="height:2px;width:{bar}%;background:{tc};border-radius:1px"></div></div></td>'
                f'<td style="padding:9px 12px;font-size:11px;opacity:.55;white-space:nowrap">'
                f'{pd.to_datetime(r["date"]).strftime("%d %b %Y")}</td>'
                f'</tr>'
            )
        return (
            f'<div class="vt-wrap" style="border-color:{accent}40">'
            f'<table class="vt">'
            f'<thead><tr>'
            f'<th style="text-align:left">Unit</th>'
            f'<th style="text-align:left">Equipment</th>'
            f'<th style="text-align:left">Titik Ukur</th>'
            f'<th style="text-align:center">Dir</th>'
            f'<th style="text-align:center;min-width:100px">mm/s</th>'
            f'<th style="text-align:left">Tanggal</th>'
            f'</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )

    if not df_d.empty:
        st.error(f"🔴 **Danger** — {len(df_d)} titik melebihi batas kritis")
        st.markdown(_alarm_tbl(df_d,"#dc2626"), unsafe_allow_html=True)
    if not df_c.empty:
        st.warning(f"🟡 **Warning** — {len(df_c)} titik perlu dipantau")
        st.markdown(_alarm_tbl(df_c,"#d97706"), unsafe_allow_html=True)

# ── Alarm Suhu ───────────────────────────────────────────────────────────────
if not df_temp_lat.empty:
    st.markdown("### 🌡️ Alarm Suhu")
    df_temp_lat["zone_t"] = df_temp_lat.apply(
        lambda r: get_zone_temp(r["value"], get_temp_threshold(r["equipment"], r["titik"]))[0], axis=1)
    df_td = df_temp_lat[df_temp_lat["zone_t"]=="ZONE D"]
    df_tc = df_temp_lat[df_temp_lat["zone_t"]=="ZONE C"]

    if df_td.empty and df_tc.empty:
        st.success("✅ Tidak ada alarm suhu aktif — semua titik dalam batas normal.")
    else:
        def _alarm_tbl_temp(df_alarm, accent):
            rows = ""
            for _,r in df_alarm.sort_values(["equipment","titik"]).iterrows():
                val = r["value"]
                tc  = ZC.get(r["zone_t"],"#6b7280")
                rows += (
                    f'<tr>'
                    f'<td style="padding:9px 12px;font-weight:600;white-space:nowrap">{r["unit"]}</td>'
                    f'<td style="padding:9px 12px;font-weight:600">{r["equipment"]}</td>'
                    f'<td style="padding:9px 12px">{r["titik"]}</td>'
                    f'<td style="padding:9px 12px;text-align:center">'
                    f'<span style="font-size:13px;font-weight:800;color:{tc}">{val:.1f} °C</span></td>'
                    f'<td style="padding:9px 12px;font-size:11px;opacity:.55;white-space:nowrap">'
                    f'{pd.to_datetime(r["date"]).strftime("%d %b %Y")}</td>'
                    f'</tr>'
                )
            return (
                f'<div class="vt-wrap" style="border-color:{accent}40">'
                f'<table class="vt">'
                f'<thead><tr>'
                f'<th style="text-align:left">Unit</th>'
                f'<th style="text-align:left">Equipment</th>'
                f'<th style="text-align:left">Titik Ukur</th>'
                f'<th style="text-align:center;min-width:100px">°C</th>'
                f'<th style="text-align:left">Tanggal</th>'
                f'</tr></thead>'
                f'<tbody>{rows}</tbody></table></div>'
            )

        if not df_td.empty:
            st.error(f"🔴 **Danger** — {len(df_td)} titik suhu melebihi batas kritis")
            st.markdown(_alarm_tbl_temp(df_td,"#dc2626"), unsafe_allow_html=True)
        if not df_tc.empty:
            st.warning(f"🟡 **Warning** — {len(df_tc)} titik suhu perlu dipantau")
            st.markdown(_alarm_tbl_temp(df_tc,"#d97706"), unsafe_allow_html=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# DETAIL PENGUKURAN — SEMUA EQUIPMENT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🔍 Detail Pengukuran — Semua Equipment")

da, db = st.columns([5,3])
with da:
    st.caption("**🏭 Unit**")
    det_unit_opts = ["All"] + sorted(latest["unit"].dropna().unique())
    det_unit_sel  = st.radio("det_unit", det_unit_opts, horizontal=True,
                             key="det_unit", label_visibility="collapsed")
with db:
    st.caption("**📐 Direction**")
    det_dir_sel = st.multiselect(
        "Direction", ["H","V","A"], default=["H","V","A"],
        key="det_dir_multi", label_visibility="collapsed"
    )
    if not det_dir_sel: det_dir_sel = ["H","V","A"]

show_temp_col = st.checkbox("🌡️ Tampilkan kolom Suhu", value=True, key="det_show_temp") \
    if not latest_temp.empty else False

df_det = latest.copy()
df_det_temp = latest_temp.copy()
if det_unit_sel != "All":
    df_det = df_det[df_det["unit"]==det_unit_sel]
    df_det_temp = df_det_temp[df_det_temp["unit"]==det_unit_sel]

if df_det.empty:
    st.warning("Tidak ada data untuk unit yang dipilih. 💡 Coba pilih unit lain atau **All**.")
    st.stop()

def _val_td(val, thr, show=True):
    if not show or val is None or pd.isna(val):
        return '<td style="text-align:center;padding:9px 10px;opacity:.3;font-size:13px">–</td>'
    zk  = get_zone(val, thr)[0]
    tc  = ZC.get(zk,"#6b7280")
    bg  = ZB.get(zk,"transparent")
    bar = bar_pct(val, thr)
    return (
        f'<td style="text-align:center;padding:9px 10px;background:{bg}">'
        f'<span style="font-size:14px;font-weight:700;color:{tc};font-variant-numeric:tabular-nums">'
        f'{val:.3f}</span>'
        f'<div style="margin-top:3px;height:2px;border-radius:1px;background:rgba(128,128,128,.2)">'
        f'<div style="height:2px;width:{bar}%;background:{tc};border-radius:1px"></div>'
        f'</div></td>'
    )

def _val_td_temp(val, thr, show=True):
    if not show or val is None or pd.isna(val):
        return '<td style="text-align:center;padding:9px 10px;opacity:.3;font-size:13px">–</td>'
    zk = get_zone_temp(val, thr)[0]
    tc = ZC.get(zk,"#6b7280")
    bg = ZB.get(zk,"transparent")
    return (
        f'<td style="text-align:center;padding:9px 10px;background:{bg}">'
        f'<span style="font-size:14px;font-weight:700;color:{tc};font-variant-numeric:tabular-nums">'
        f'{val:.1f}°C</span></td>'
    )

def _badge_td(zk, zi, zl):
    tc  = ZC.get(zk,"#6b7280")
    bg  = ZB.get(zk,"transparent")
    full_lbl = ZONE_LABEL.get(zk, zl)
    short_key = zk.replace("ZONE ","") if zk.startswith("ZONE") else zk
    return (
        f'<td style="padding:9px 12px;text-align:center">'
        f'<span style="display:inline-flex;align-items:center;gap:4px;'
        f'background:{bg};color:{tc};border:1px solid {tc}50;'
        f'border-radius:99px;padding:4px 12px;font-size:12px;font-weight:700;'
        f'letter-spacing:.04em;white-space:nowrap">{zi} {short_key} · {full_lbl}</span></td>'
    )

def _render_tbl(df_unit, unit_label, df_unit_temp=None):
    equips = sorted(df_unit["equipment"].dropna().unique())
    if not equips: return ""

    dir_th = "".join(
        f'<th style="text-align:center;min-width:88px">{d} '
        f'<span style="font-size:8px;opacity:.55">mm/s</span></th>'
        for d in ["H","V","A"] if d in det_dir_sel
    )
    temp_th = (
        '<th style="text-align:center;min-width:80px">Temp '
        '<span style="font-size:8px;opacity:.55">°C</span></th>'
    ) if show_temp_col else ""

    rows = ""
    for eq in equips:
        df_eq  = df_unit[df_unit["equipment"]==eq].sort_values("titik")
        thr    = get_threshold(eq)
        titiks = sorted(df_eq["titik"].dropna().unique())

        _all_vals_eq = df_eq["value"].dropna().tolist()
        _worst_zone  = "ZONE A"
        _zone_order  = {"ZONE D":4,"ZONE C":3,"ZONE B":2,"ZONE A":1,"N/A":0}
        for _v in _all_vals_eq:
            _zk = get_zone(_v, thr)[0]
            if _zone_order.get(_zk,0) > _zone_order.get(_worst_zone,0):
                _worst_zone = _zk
        eq_border_color = ZC.get(_worst_zone, "#6b7280")

        for i, titik in enumerate(titiks):
            df_t = df_eq[df_eq["titik"]==titik]

            gv = lambda d, _df=df_t: (
                float(_df[_df["direction"]==d]["value"].dropna().iloc[0])
                if not _df[_df["direction"]==d]["value"].dropna().empty else None
            )

            h,v,a  = gv("H"), gv("V"), gv("A")
            all_v  = [x for x in [h,v,a] if x is not None]
            max_v  = max(all_v) if all_v else float("nan")
            zk,zi,zl = get_zone(max_v, thr)
            tc     = ZC.get(zk,"#6b7280")

            temp_td = ""
            if show_temp_col:
                t_val = None
                if df_unit_temp is not None and not df_unit_temp.empty:
                    sub_t = df_unit_temp[
                        (df_unit_temp["equipment"]==eq) & (df_unit_temp["titik"]==titik)
                    ]["value"].dropna()
                    if not sub_t.empty:
                        t_val = float(sub_t.iloc[0])
                t_thr = get_temp_threshold(eq, titik)
                temp_td = _val_td_temp(t_val, t_thr)

            if zk=="ZONE D":   rb = "rgba(220,38,38,.07)"
            elif zk=="ZONE C": rb = "rgba(217,119,6,.06)"
            elif i%2==1:       rb = "rgba(128,128,128,.04)"
            else:              rb = "transparent"

            tv = df_t["date"].max()
            tgl = pd.to_datetime(tv).strftime("%d %b %Y") if pd.notna(tv) else "–"

            eq_td = ""
            if i == 0:
                eq_td = (
                    f'<td rowspan="{len(titiks)}" style="'
                    f'padding:10px 14px;font-size:13px;font-weight:700;'
                    f'vertical-align:middle;border-left:4px solid {eq_border_color};'
                    f'background:rgba(128,128,128,.04);white-space:nowrap">{eq}</td>'
                )

            rows += (
                f'<tr style="background:{rb};border-bottom:1px solid rgba(128,128,128,.07)">'
                + eq_td
                + f'<td style="padding:9px 14px;font-size:13px;opacity:.8">{titik}</td>'
                + _val_td(h, thr, "H" in det_dir_sel)
                + _val_td(v, thr, "V" in det_dir_sel)
                + _val_td(a, thr, "A" in det_dir_sel)
                + _val_td(max_v, thr)
                + temp_td
                + _badge_td(zk,zi,zl)
                + f'<td style="padding:9px 14px;font-size:11px;opacity:.5;'
                  f'white-space:nowrap;text-align:right">{tgl}</td>'
                + '</tr>'
            )

    return (
        f'<div style="margin-bottom:28px">'
        f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:10px">'
        f'<div style="width:4px;height:18px;border-radius:2px;background:linear-gradient(180deg,#2563eb,#0891b2)"></div>'
        f'<span style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;opacity:.55">{unit_label}</span>'
        f'</div>'
        f'<div class="vt-wrap">'
        f'<table class="vt">'
        f'<thead><tr>'
        f'<th style="text-align:left;min-width:150px">Equipment</th>'
        f'<th style="text-align:left;min-width:120px">Titik Ukur</th>'
        f'{dir_th}'
        f'<th style="text-align:center;min-width:90px">Max <span style="font-size:8px;opacity:.55">mm/s</span></th>'
        f'{temp_th}'
        f'<th style="text-align:center;min-width:110px">Status</th>'
        f'<th style="text-align:right;min-width:100px">Tanggal</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
        f'</div>'
    )

if det_unit_sel == "All":
    for u in sorted(df_det["unit"].dropna().unique()):
        blk = _render_tbl(df_det[df_det["unit"]==u], f"Unit · {u}",
                           df_det_temp[df_det_temp["unit"]==u])
        if blk:
            st.markdown(blk, unsafe_allow_html=True)
else:
    blk = _render_tbl(df_det, f"Unit · {det_unit_sel}", df_det_temp)
    if blk:
        st.markdown(blk, unsafe_allow_html=True)
