import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
from utils import (
    save_to_db, load_history, parse_excel,
    get_zone, get_threshold, THRESHOLD, add_zone_cols,
    render_login_sidebar, check_role
)

st.set_page_config(
    page_title="Monitor Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{display:none;}
section[data-testid="stSidebar"]>div:first-child{padding-top:1rem;}

.eq-card{
    transition: all 0.2s ease;
    cursor: pointer;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.04), 0 4px 14px rgba(0,0,0,0.35);
    backdrop-filter: blur(6px);
}
.eq-card:hover{
    transform: translateY(-3px);
    box-shadow: 0 0 0 1px rgba(255,255,255,0.08), 0 10px 28px rgba(0,0,0,0.45);
    border-left-width: 6px !important;
}
</style>
""", unsafe_allow_html=True)

df_hist = load_history()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                  label="📊 Monitor Vibrasi")
    st.page_link("pages/1_Analisis.py",      label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py",   label="🗄️ Data & Kelola")
    render_login_sidebar()
    st.divider()
    if not df_hist.empty:
        df_chk = df_hist.copy()
        df_chk["value"] = pd.to_numeric(df_chk["value"], errors="coerce")
        lc = df_chk.sort_values("date").groupby(
            ["unit","equipment","titik","direction"], as_index=False).last()
        nd = sum(1 for _,r in lc.iterrows()
            if get_zone(r["value"], THRESHOLD["Turbine" if "turbine" in str(r["equipment"]).lower() else "Pump/Fan"])[0]=="ZONE D")
        nc = sum(1 for _,r in lc.iterrows()
            if get_zone(r["value"], THRESHOLD["Turbine" if "turbine" in str(r["equipment"]).lower() else "Pump/Fan"])[0]=="ZONE C")
        if nd > 0:   st.error(f"🔴 {nd} titik Danger aktif")
        elif nc > 0: st.warning(f"🟡 {nc} titik Warning aktif")
        else:        st.success("✅ Semua titik normal")

# ── Guard no data ─────────────────────────────────────────────────────────────
if df_hist.empty:
    st.info("📂 Belum ada data. Upload file Excel di halaman **Data & Kelola**.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
all_units = sorted(df_hist["unit"].dropna().unique())
all_equip = sorted(df_hist["equipment"].dropna().unique())
all_dates_sorted = sorted(df_hist["date"].dt.date.dropna().unique(), reverse=True)

st.markdown("## 📊 Monitor Vibrasi")

# ── Filter Unit (pill) ────────────────────────────────────────────────────────
unit_opts    = ["All"] + all_units
sel_unit_btn = st.radio("Unit", unit_opts, horizontal=True, key="mon_unit", label_visibility="collapsed")
sel_unit     = all_units if sel_unit_btn == "All" else [sel_unit_btn]

# ── Filter Equipment & Direction (collapsible) ────────────────────────────────
with st.expander("⚙️ Filter Equipment & Direction", expanded=False):
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        sel_equip = st.multiselect("Equipment", all_equip, default=all_equip, key="mon_equip")
    with fc2:
        sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="mon_dir")

# ── Filter Mode Tanggal ───────────────────────────────────────────────────────
st.markdown("**Tampilkan data pengukuran:**")
date_mode = st.radio(
    "Mode tanggal",
    ["🕐 Terbaru (per equipment)", "📅 Pilih tanggal spesifik"],
    horizontal=True, key="mon_date_mode", label_visibility="collapsed"
)

sel_tgl = None
if date_mode == "📅 Pilih tanggal spesifik":
    min_date = min(all_dates_sorted)
    max_date = max(all_dates_sorted)
    sel_tgl_raw = st.date_input(
        "📅 Pilih tanggal pengukuran",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="mon_tgl_select"
    )
    sel_tgl = pd.to_datetime(sel_tgl_raw).strftime("%Y-%m-%d")
    df_base = df_hist[
        df_hist["unit"].isin(sel_unit) &
        df_hist["equipment"].isin(sel_equip) &
        df_hist["direction"].isin(sel_dir) &
        (df_hist["date"].dt.strftime("%Y-%m-%d") == sel_tgl)
    ].copy()
    st.caption(f"Menampilkan data pengukuran tanggal **{pd.to_datetime(sel_tgl).strftime('%d %b %Y')}**")
else:
    df_base = df_hist[
        df_hist["unit"].isin(sel_unit) &
        df_hist["equipment"].isin(sel_equip) &
        df_hist["direction"].isin(sel_dir)
    ].copy()
    st.caption("Menampilkan **nilai terbaru** per equipment · titik · direction")

if df_base.empty:
    st.warning("Tidak ada data sesuai filter.")
    st.stop()

df_base = add_zone_cols(df_base)
latest  = df_base.sort_values("date").groupby(
    ["unit","equipment","titik","direction"], as_index=False).last()

# ── KPI ───────────────────────────────────────────────────────────────────────
total = len(latest)
n_d = (latest["zone"]=="ZONE D").sum()
n_c = (latest["zone"]=="ZONE C").sum()
n_b = (latest["zone"]=="ZONE B").sum()
n_a = (latest["zone"]=="ZONE A").sum()

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Total titik",    total)
k2.metric("🔴 Danger",      int(n_d))
k3.metric("🟡 Warning",     int(n_c))
k4.metric("🟢 Pre Warning", int(n_b))
k5.metric("🔵 Accepted",    int(n_a))

pct_a = round(n_a/total*100) if total else 0
pct_b = round(n_b/total*100) if total else 0
pct_c = round(n_c/total*100) if total else 0
pct_d = round(n_d/total*100) if total else 0
st.markdown(f"""
<div style="margin:4px 0 16px">
<div style="height:12px;border-radius:6px;overflow:hidden;display:flex;background:var(--color-background-tertiary)">
<div style="width:{pct_a}%;background:#3b82f6"></div>
<div style="width:{pct_b}%;background:#22c55e"></div>
<div style="width:{pct_c}%;background:#eab308"></div>
<div style="width:{pct_d}%;background:#ef4444"></div>
</div>
<div style="display:flex;gap:16px;font-size:12px;margin-top:5px;color:var(--color-text-secondary)">
<span style="color:#3b82f6">🔵 Accepted {pct_a}%</span>
<span style="color:#22c55e">🟢 Pre Warning {pct_b}%</span>
<span style="color:#eab308">🟡 Warning {pct_c}%</span>
<span style="color:#ef4444">🔴 Danger {pct_d}%</span>
</div></div>
""", unsafe_allow_html=True)

st.divider()

# ── Card per Equipment ────────────────────────────────────────────────────────
st.markdown("### Status per Equipment")

CBORDER = {
    "ZONE A":"#3b82f6","ZONE B":"#22c55e",
    "ZONE C":"#eab308","ZONE D":"#ef4444","N/A":"#94a3b8"
}

def dir_block(label, val, thr):
    if val is None or pd.isna(val):
        return (f'<div style="flex:1;text-align:center;background:var(--color-background-tertiary);'
                f'border-radius:6px;padding:5px 2px">'
                f'<div style="font-size:10px;color:var(--color-text-secondary)">{label}</div>'
                f'<div style="font-size:13px;color:var(--color-text-secondary)">–</div></div>')
    zk2 = get_zone(val, thr)[0]
    c2  = CBORDER.get(zk2,"#94a3b8")
    return (f'<div style="flex:1;text-align:center;background:var(--color-background-tertiary);'
            f'border-radius:6px;padding:5px 2px">'
            f'<div style="font-size:10px;color:var(--color-text-secondary)">{label}</div>'
            f'<div style="font-size:13px;font-weight:500;color:{c2}">{val:.3f}</div></div>')

# Pakai semua histori tanpa filter direction agar H/V/A semua equipment muncul
df_card_base = df_hist[
    df_hist["unit"].isin(sel_unit) &
    df_hist["equipment"].isin(sel_equip) &
    df_hist["value"].notna()
].copy()

# Filter tanggal jika mode pilih tanggal
if date_mode == "📅 Pilih tanggal spesifik" and sel_tgl:
    df_card_base = df_card_base[
        df_card_base["date"].dt.strftime("%Y-%m-%d") == sel_tgl
    ]

if df_card_base.empty:
    st.warning("Tidak ada data equipment pada tanggal tersebut.")
    st.stop()

df_card_latest = df_card_base.sort_values("date").groupby(
    ["unit","equipment","titik","direction"], as_index=False).last()
df_card_latest = add_zone_cols(df_card_latest)

# Bangun daftar card — FIX: max_dir pakai default arg untuk hindari closure bug
eq_rows = []
for eq in sorted(df_card_latest["equipment"].dropna().unique()):
    if eq not in sel_equip:
        continue
    df_eq = df_card_latest[df_card_latest["equipment"]==eq].copy()
    unit  = df_eq["unit"].iloc[0]
    thr   = get_threshold(eq)

    # FIX closure bug: _df=df_eq sebagai default argument
    def max_dir(d, _df=df_eq):
        sub = _df[_df["direction"]==d]["value"].dropna()
        return float(sub.max()) if not sub.empty else None

    h_val   = max_dir("H")
    v_val   = max_dir("V")
    a_val   = max_dir("A")
    all_v   = [v for v in [h_val,v_val,a_val] if v is not None]
    max_val = max(all_v) if all_v else float("nan")
    zk,zi,zl = get_zone(max_val, thr)
    tgl_eq  = (pd.to_datetime(df_eq["date"].max()).strftime("%d-%b-%Y")
               if pd.notna(df_eq["date"].max()) else "–")
    eq_rows.append({
        "eq":eq,"unit":unit,
        "H":h_val,"V":v_val,"A":a_val,
        "zk":zk,"zi":zi,"zl":zl,"thr":thr,"tgl":tgl_eq
    })

# Render card 3 kolom
for i in range(0, len(eq_rows), 3):
    chunk = eq_rows[i:i+3]
    cols  = st.columns(3)
    for col, r in zip(cols, chunk):
        border = CBORDER.get(r["zk"],"#94a3b8")
        ztc    = CBORDER.get(r["zk"],"#94a3b8")
        # FIX background: pakai var(--color-background-secondary) agar visible di light & dark mode
        col.markdown(f"""
<div class="eq-card" style="
    border: 0.5px solid var(--color-border-tertiary);
    border-left: 4px solid {border};
    border-radius: 0 10px 10px 0;
    padding: 12px 14px;
    margin-bottom: 10px;
    background: var(--color-background-secondary);
">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px">
    <div style="font-size:13px;font-weight:500;color:var(--color-text-primary)">{r['eq']}</div>
    <div style="font-size:10px;color:var(--color-text-secondary)">{r['tgl']}</div>
  </div>
  <div style="font-size:11px;color:var(--color-text-secondary);margin-bottom:10px">{r['unit']}</div>
  <div style="display:flex;gap:6px;margin-bottom:10px">
    {dir_block("H",r['H'],r['thr'])}
    {dir_block("V",r['V'],r['thr'])}
    {dir_block("A",r['A'],r['thr'])}
  </div>
  <div style="font-size:12px;font-weight:500;color:{ztc}">{r['zi']} {r['zl']}</div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Alarm Aktif ───────────────────────────────────────────────────────────────
st.markdown("### 🚨 Alarm Aktif")

latest["zone_label"] = latest.apply(
    lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1]+" "+
              get_zone(r["value"], THRESHOLD[r["thr_type"]])[2], axis=1
).astype(str)

df_d = latest[latest["zone"]=="ZONE D"]
df_c = latest[latest["zone"]=="ZONE C"]

if df_d.empty and df_c.empty:
    st.success("✅ Tidak ada alarm aktif — semua titik dalam batas normal.")
else:
    if not df_d.empty:
        st.error(f"🔴 **Danger** — {len(df_d)} titik ukur melebihi batas kritis")
        sd = df_d[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
        sd["value"] = sd["value"].map(lambda v: f"{v:.3f}")
        sd["date"]  = pd.to_datetime(sd["date"]).dt.strftime("%d-%b-%Y")
        sd = sd.rename(columns={"unit":"Unit","equipment":"Equipment","titik":"Titik",
                                 "direction":"Dir","value":"mm/s","zone_label":"Status","date":"Tanggal"})
        st.dataframe(sd, use_container_width=True, hide_index=True)
    if not df_c.empty:
        st.warning(f"🟡 **Warning** — {len(df_c)} titik ukur perlu dipantau")
        sc = df_c[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
        sc["value"] = sc["value"].map(lambda v: f"{v:.3f}")
        sc["date"]  = pd.to_datetime(sc["date"]).dt.strftime("%d-%b-%Y")
        sc = sc.rename(columns={"unit":"Unit","equipment":"Equipment","titik":"Titik",
                                 "direction":"Dir","value":"mm/s","zone_label":"Status","date":"Tanggal"})
        st.dataframe(sc, use_container_width=True, hide_index=True)

st.divider()

# ── Detail per Equipment ──────────────────────────────────────────────────────
st.markdown("### 🔍 Detail per Equipment")

sel_det = st.selectbox("Pilih Equipment", sorted(latest["equipment"].unique()), key="mon_det")
thr_det = get_threshold(sel_det)
df_det  = latest[latest["equipment"]==sel_det].copy().sort_values(["titik","direction"])

pivot_det = df_det.pivot_table(
    index="titik", columns="direction", values="value", aggfunc="last"
).reset_index()
pivot_det.columns.name = None

dir_cols_d = [c for c in ["H","V","A"] if c in pivot_det.columns]
pivot_det["Max (mm/s)"] = pivot_det[dir_cols_d].max(axis=1)
pivot_det["Status"] = pivot_det["Max (mm/s)"].apply(
    lambda v: get_zone(v,thr_det)[1]+" "+get_zone(v,thr_det)[2])

for c in dir_cols_d:
    pivot_det[c] = pivot_det[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
pivot_det["Max (mm/s)"] = pivot_det["Max (mm/s)"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
pivot_det = pivot_det.rename(columns={"titik":"Titik Ukur"})

show_cols = ["Titik Ukur"] + dir_cols_d + ["Max (mm/s)","Status"]
st.dataframe(pivot_det[show_cols], use_container_width=True, hide_index=True)
