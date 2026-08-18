import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from utils import (
    save_to_db, load_history, parse_excel,
    get_zone, get_threshold, THRESHOLD, add_zone_cols,
    render_login_sidebar, check_role,
    get_temp_threshold, get_zone_temp,
    get_pump_runtime, init_pump_runtime, toggle_pump_runtime, compute_running_hours,
)

st.set_page_config(
    page_title="Monitor Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
# Gunakan hanya var Streamlit native yang bekerja di iframe markdown:
#   --text-color, --background-color, --secondary-background-color
# Warna zone & table tidak hardcode dark/light — pakai opacity + warna solid
# agar terlihat di kedua tema.
st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

.eq-card{ cursor:pointer; }
.eq-card:hover{ border-left-width:5px !important; }

/* Tabel: pakai inherit supaya ikut tema Streamlit */
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

# ── Warna zone (solid, terlihat di dark & light) ──────────────────────────────
ZC = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#d97706","ZONE D":"#dc2626","N/A":"#6b7280"}
ZB = {"ZONE A":"rgba(59,130,246,.13)","ZONE B":"rgba(34,197,94,.13)",
      "ZONE C":"rgba(217,119,6,.14)","ZONE D":"rgba(220,38,38,.14)","N/A":"rgba(107,114,128,.1)"}
ZONE_LABEL = {"ZONE A":"Accepted","ZONE B":"Pre Warning","ZONE C":"Warning","ZONE D":"Danger","N/A":"N/A"}
ZONE_ICON  = {"ZONE A":"🔵","ZONE B":"🟢","ZONE C":"🟡","ZONE D":"🔴","N/A":"⬜"}

# FIX 3: Helper bar progress — scale ke threshold ZONE D agar representatif per equipment
def bar_pct(val, thr):
    """Hitung persentase bar berdasarkan threshold ZONE D (batas kritis) equipment."""
    max_scale = thr.get("C", 4.5) * 1.2  # 20% di atas batas Warning sebagai skala max
    return min(int((val / max(max_scale, 0.001)) * 100), 100)

# ── Data ──────────────────────────────────────────────────────────────────────
df_hist = load_history()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    # UX #1: Highlight halaman aktif
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
    # UX #12: Tombol refresh manual
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
        # FIX: baris suhu (direction=="T") pakai threshold suhu, bukan threshold vibrasi
        def _lc_zone(r):
            if r["direction"] == "T":
                return get_zone_temp(r["value"], get_temp_threshold(r["equipment"], r["titik"]))[0]
            return get_zone(r["value"], get_threshold(r["equipment"]))[0]
        zones_lc = lc.apply(_lc_zone, axis=1)
        nd = int((zones_lc=="ZONE D").sum())
        nc = int((zones_lc=="ZONE C").sum())
        if nd>0:   st.error(f"🔴 {nd} titik Danger")
        elif nc>0: st.warning(f"🟡 {nc} titik Warning")
        else:      st.success("✅ Semua titik normal")

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
st.markdown("## 📊 Monitor Vibrasi")

fa, fb, fc = st.columns([2, 3, 3])
with fa:
    st.caption("**🏭 Unit**")
    sel_unit_btn = st.radio("Unit", ["All"]+all_units, horizontal=True,
                            key="mon_unit", label_visibility="collapsed")
    sel_unit = all_units if sel_unit_btn=="All" else [sel_unit_btn]

# FIX 4: Equipment list filter per unit yang dipilih
all_equip = sorted(df_hist[df_hist["unit"].isin(sel_unit)]["equipment"].dropna().unique())

# FIX 8: Reset session_state equipment saat unit berubah
_prev_unit_key = f"_prev_unit_{sel_unit_btn}"
if st.session_state.get("_last_unit") != sel_unit_btn:
    st.session_state["mon_equip"] = all_equip
    st.session_state["_last_unit"] = sel_unit_btn

with fb:
    st.caption("**⚙️ Equipment**")
    with st.expander(f"Filter ({len(all_equip)} equipment)", expanded=False):
        col_selall, _ = st.columns([1,3])
        if col_selall.button("Pilih Semua", key="eq_selall", width="stretch"):
            st.session_state["mon_equip"] = all_equip
        # Pastikan session_state hanya berisi equipment yang valid untuk unit ini —
        # JANGAN pass `default=` bersamaan dengan key yang sudah ada di session_state
        # (itu penyebab warning "created with a default value but also had its value
        # set via Session State API").
        if "mon_equip" in st.session_state:
            st.session_state["mon_equip"] = [
                e for e in st.session_state["mon_equip"] if e in all_equip
            ]
        sel_equip = st.multiselect("Equipment", all_equip,
                                   key="mon_equip", label_visibility="collapsed")
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
    # FIX 6: pakai date comparison bukan string agar tidak rawan locale issue
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

# Hitung latest hanya sekali
latest_all = (
    df_base
    .sort_values("date")
    .groupby(
        ["unit", "equipment", "titik", "direction"],
        as_index=False
    )
    .last()
)

# Pisah vibrasi (H/V/A) vs suhu (T) — beda satuan & skala threshold total.
# `latest` tetap khusus vibrasi supaya semua KPI/kartu/alarm/tabel di bawah
# yang sudah ada TIDAK berubah perilakunya sama sekali.
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

# Progress bar distribusi
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
# RUNNING HOURS POMPA (live, auto-update)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### ⏱️ Running Hours Pompa")

# Jam berjalan otomatis tanpa perlu klik refresh — rerun tiap 30 detik
st_autorefresh(interval=30_000, key="runtime_autorefresh")

_RT_KEYWORDS = ("PUMP", "POMPA", "MOTOR", "FAN")
pump_equips = sorted([e for e in sel_equip if any(k in e.upper() for k in _RT_KEYWORDS)])

# Satu kali panggil (di-cache 15 detik di utils.py), dipakai ulang di section ini
# DAN di badge kartu equipment di bawah — hindari query Supabase dobel per render.
df_runtime_all = get_pump_runtime()

if not pump_equips:
    st.caption("Tidak ada equipment pompa pada filter saat ini.")
else:
    can_edit = check_role() == "editor"
    rt_cols = st.columns(3)

    for i, eq in enumerate(pump_equips):
        eq_unit_rows = df_hist[df_hist["equipment"]==eq]["unit"].dropna()
        unit_eq = eq_unit_rows.iloc[0] if not eq_unit_rows.empty else "-"

        row_match = df_runtime_all[(df_runtime_all["equipment"]==eq) & (df_runtime_all["unit"]==unit_eq)]
        if row_match.empty:
            init_pump_runtime(eq, unit_eq)
            row_data = {"status": "stopped", "accumulated_hours": 0.0,
                        "status_changed_at": pd.Timestamp.now().isoformat()}
        else:
            row_data = row_match.iloc[0].to_dict()

        hours  = compute_running_hours(row_data)
        status = row_data.get("status", "stopped")
        badge_color = "#16a34a" if status == "running" else "#6b7280"

        with rt_cols[i % 3]:
            st.markdown(f"""
<div style="border:1px solid {badge_color}30;border-left:4px solid {badge_color};
    border-radius:0 12px 12px 0;padding:14px;margin-bottom:10px;background:{badge_color}10">
  <div style="font-size:14px;font-weight:700">{eq}</div>
  <div style="font-size:11px;opacity:.5;margin-bottom:8px">{unit_eq}</div>
  <div style="font-size:24px;font-weight:800;color:{badge_color};font-variant-numeric:tabular-nums">
    {hours:,.1f} <span style="font-size:12px;font-weight:600">jam</span></div>
  <div style="font-size:11px;font-weight:700;color:{badge_color};margin-top:2px">
    {'🟢 RUNNING' if status=='running' else '⚪ STOPPED'}</div>
</div>""", unsafe_allow_html=True)

            if can_edit:
                btn_label = "⏹️ Stop" if status == "running" else "▶️ Start"
                if st.button(btn_label, key=f"rt_toggle_{eq}_{unit_eq}", width="stretch"):
                    toggle_pump_runtime(
                        eq, unit_eq, status,
                        float(row_data.get("accumulated_hours", 0) or 0),
                        row_data.get("status_changed_at"),
                    )
                    st.cache_data.clear()
                    st.rerun()

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

# Filter latest sesuai unit & equipment yang dipilih
df_card_lat = latest[
    latest["unit"].isin(sel_unit) &
    latest["equipment"].isin(sel_equip)
].copy()

def _max_dir(df_eq, d):
    sub = df_eq[df_eq["direction"]==d][["value","titik"]].dropna(subset=["value"])
    if sub.empty: return None, None
    idx = sub["value"].idxmax()
    return float(sub.loc[idx,"value"]), str(sub.loc[idx,"titik"])

# Suhu terpanas per equipment (untuk kartu status) — filter sesuai unit & equipment yang dipilih
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
    # UX #6: title attribute untuk tooltip nama titik penuh
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

# Lookup running hours (khusus equipment pompa/motor/fan) untuk ditampilkan di kartu
# Pakai df_runtime_all yang sudah di-load sekali di section Running Hours Pompa di atas.
def _runtime_badge(eq, unit):
    if not any(k in eq.upper() for k in _RT_KEYWORDS):
        return ""
    match = df_runtime_all[
        (df_runtime_all["equipment"]==eq) & (df_runtime_all["unit"]==unit)
    ] if not df_runtime_all.empty else pd.DataFrame()
    if match.empty:
        return ""
    row_data = match.iloc[0].to_dict()
    hours  = compute_running_hours(row_data)
    status = row_data.get("status", "stopped")
    rc = "#16a34a" if status == "running" else "#6b7280"
    dot = "🟢" if status == "running" else "⚪"
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:8px;padding:6px 8px;border-radius:8px;background:{rc}12">'
        f'<span style="font-size:11px;font-weight:600;color:{rc}">{dot} '
        f'{"Running" if status=="running" else "Stopped"}</span>'
        f'<span style="font-size:12px;font-weight:700;color:{rc};font-variant-numeric:tabular-nums">'
        f'⏱️ {hours:,.1f} jam</span></div>'
    )

for i in range(0, len(eq_rows), 3):
    cols = st.columns(3)
    for col, r in zip(cols, eq_rows[i:i+3]):
        bc  = ZC.get(r["zk"],"#6b7280")
        bg  = ZB.get(r["zk"],"transparent")
        bar = bar_pct(r["mx"], r["thr"]) if not pd.isna(r["mx"]) else 0
        rt_html = _runtime_badge(r["eq"], r["unit"])
        col.markdown(f"""
<div class="eq-card" style="
  border:1px solid {bc}30; border-left:4px solid {bc};
  border-radius:0 12px 12px 0; padding:14px; margin-bottom:10px;
  background:{bg};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px">
    <div style="font-size:15px;font-weight:700;line-height:1.3">{r['eq']}</div>
    <div style="font-size:11px;opacity:.45;white-space:nowrap;margin-left:6px">{r['tgl']}</div>
  </div>
  <div style="font-size:12px;opacity:.45;margin-bottom:10px">{r['unit']}</div>
  {rt_html}
  <div style="display:flex;gap:5px;margin-bottom:10px">
    {_dir_pill("H",r['H'],r['thr'],r['Ht'])}
    {_dir_pill("V",r['V'],r['thr'],r['Vt'])}
    {_dir_pill("A",r['A'],r['thr'],r['At'])}
    {_temp_pill(r['eq'],r['T'],r['Tt'])}
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px">
    <span style="font-size:13px;font-weight:700;color:{bc}">{r['zi']} {r['zl']}</span>
    <span style="font-size:12px;font-weight:600;color:{bc};opacity:.8">{r['mx']:.3f} mm/s</span>
  </div>
  <div style="height:3px;border-radius:2px;background:rgba(128,128,128,.2);overflow:hidden">
    <div style="height:3px;width:{bar}%;background:{bc};border-radius:2px"></div>
  </div>
</div>""", unsafe_allow_html=True)


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
            rows += f"""<tr>
  <td style="padding:9px 12px;font-weight:600;white-space:nowrap">{r['unit']}</td>
  <td style="padding:9px 12px;font-weight:600">{r['equipment']}</td>
  <td style="padding:9px 12px">{r['titik']}</td>
  <td style="padding:9px 12px;text-align:center;font-weight:700">{r['direction']}</td>
  <td style="padding:9px 12px;text-align:center">
    <span style="font-size:13px;font-weight:800;color:{tc}">{val:.3f}</span>
    <div style="margin-top:3px;height:2px;border-radius:1px;background:rgba(128,128,128,.2)">
      <div style="height:2px;width:{bar}%;background:{tc};border-radius:1px"></div></div></td>
  <td style="padding:9px 12px;font-size:11px;opacity:.55;white-space:nowrap">
    {pd.to_datetime(r["date"]).strftime("%d %b %Y")}</td>
</tr>"""
        return f"""
<div class="vt-wrap" style="border-color:{accent}40">
<table class="vt">
<thead><tr>
  <th style="text-align:left">Unit</th>
  <th style="text-align:left">Equipment</th>
  <th style="text-align:left">Titik Ukur</th>
  <th style="text-align:center">Dir</th>
  <th style="text-align:center;min-width:100px">mm/s</th>
  <th style="text-align:left">Tanggal</th>
</tr></thead>
<tbody>{rows}</tbody></table></div>"""

    if not df_d.empty:
        st.error(f"🔴 **Danger** — {len(df_d)} titik melebihi batas kritis")
        st.markdown(_alarm_tbl(df_d,"#dc2626"), unsafe_allow_html=True)
    if not df_c.empty:
        st.warning(f"🟡 **Warning** — {len(df_c)} titik perlu dipantau")
        st.markdown(_alarm_tbl(df_c,"#d97706"), unsafe_allow_html=True)

# ── Alarm Suhu — terpisah dari alarm vibrasi (skala & satuan beda) ───────────
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
                rows += f"""<tr>
  <td style="padding:9px 12px;font-weight:600;white-space:nowrap">{r['unit']}</td>
  <td style="padding:9px 12px;font-weight:600">{r['equipment']}</td>
  <td style="padding:9px 12px">{r['titik']}</td>
  <td style="padding:9px 12px;text-align:center">
    <span style="font-size:13px;font-weight:800;color:{tc}">{val:.1f} °C</span></td>
  <td style="padding:9px 12px;font-size:11px;opacity:.55;white-space:nowrap">
    {pd.to_datetime(r["date"]).strftime("%d %b %Y")}</td>
</tr>"""
            return f"""
<div class="vt-wrap" style="border-color:{accent}40">
<table class="vt">
<thead><tr>
  <th style="text-align:left">Unit</th>
  <th style="text-align:left">Equipment</th>
  <th style="text-align:left">Titik Ukur</th>
  <th style="text-align:center;min-width:100px">°C</th>
  <th style="text-align:left">Tanggal</th>
</tr></thead>
<tbody>{rows}</tbody></table></div>"""

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
    # UX #9: pakai multiselect agar konsisten dengan halaman Analisis
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

# ── Helper sel nilai ──────────────────────────────────────────────────────────
def _val_td(val, thr, show=True):
    """
    Render td dengan warna zone.
    KUNCI theme-compatibility: JANGAN hardcode background tabel.
    Hanya beri warna pada teks & background zone (semi-transparan).
    """
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
    """Sel suhu — skala & format beda dari _val_td (°C, 1 desimal, tanpa bar mm/s)."""
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
    # UX #8: tampilkan zone key + label untuk konsistensi
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

    # Header direction
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

        # FIX 5: Hitung zone terburuk dari SEMUA titik equipment untuk warna border kiri
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

            # FIX 2: gv sebagai lambda inline, hindari redefinisi fungsi tiap iterasi
            gv = lambda d, _df=df_t: (
                float(_df[_df["direction"]==d]["value"].dropna().iloc[0])
                if not _df[_df["direction"]==d]["value"].dropna().empty else None
            )

            h,v,a  = gv("H"), gv("V"), gv("A")
            all_v  = [x for x in [h,v,a] if x is not None]
            max_v  = max(all_v) if all_v else float("nan")
            zk,zi,zl = get_zone(max_v, thr)
            tc     = ZC.get(zk,"#6b7280")

            # Nilai suhu titik ini (kalau ada) — lookup terpisah dari df_unit_temp
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

            # Row background: hanya zone warna tipis, TANPA warna solid
            if zk=="ZONE D":   rb = "rgba(220,38,38,.07)"
            elif zk=="ZONE C": rb = "rgba(217,119,6,.06)"
            elif i%2==1:       rb = "rgba(128,128,128,.04)"
            else:              rb = "transparent"

            tv = df_t["date"].max()
            tgl = pd.to_datetime(tv).strftime("%d %b %Y") if pd.notna(tv) else "–"

            eq_td = ""
            if i == 0:
                # FIX 5: pakai eq_border_color (zone terburuk) bukan tc (zone titik pertama)
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

    return f"""
<div style="margin-bottom:28px">
  <div style="display:flex;align-items:center;gap:9px;margin-bottom:10px">
    <div style="width:4px;height:18px;border-radius:2px;
                background:linear-gradient(180deg,#2563eb,#0891b2)"></div>
    <span style="font-size:11px;font-weight:700;letter-spacing:.1em;
                 text-transform:uppercase;opacity:.55">{unit_label}</span>
  </div>
  <div class="vt-wrap">
    <table class="vt">
      <thead><tr>
        <th style="text-align:left;min-width:150px">Equipment</th>
        <th style="text-align:left;min-width:120px">Titik Ukur</th>
        {dir_th}
        <th style="text-align:center;min-width:90px">Max <span style="font-size:8px;opacity:.55">mm/s</span></th>
        {temp_th}
        <th style="text-align:center;min-width:110px">Status</th>
        <th style="text-align:right;min-width:100px">Tanggal</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""

if det_unit_sel == "All":
    for u in sorted(df_det["unit"].dropna().unique()):
        blk = _render_tbl(df_det[df_det["unit"]==u], f"Unit · {u}",
                           df_det_temp[df_det_temp["unit"]==u])
        if blk: st.markdown(blk, unsafe_allow_html=True)
else:
    blk = _render_tbl(df_det, f"Unit · {det_unit_sel}", df_det_temp)
    if blk: st.markdown(blk, unsafe_allow_html=True)
