import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils import (
    save_to_db, load_history, parse_excel,
    get_zone, get_threshold, THRESHOLD, ZONE_COLOR, add_zone_cols,
    render_login_sidebar, check_role
)

st.set_page_config(
    page_title="Dashboard Monitoring Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"] {display: none;}
section[data-testid="stSidebar"] > div:first-child {padding-top: 1rem;}
[data-testid="stSidebar"] hr {margin: 0.5rem 0;}
</style>
""", unsafe_allow_html=True)

df_hist = load_history()

with st.sidebar:
    try:
        st.image("assets/logo_pln_ip.png", width=220)
    except:
        pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Dashboard Monitoring Vibrasi · ISO 10816")
    st.divider()

    st.markdown("### 📂 Upload Data")
    uploaded = st.file_uploader(
        "File Excel (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Sheet: Vibration_Data — kolom: Equipment, Unit, Titik Ukur, Direction, Date, Value"
    )

    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                   label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py",          label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py",          label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py",        label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py",     label="⚙️ Pengaturan")
    st.page_link("pages/5_Prediksi.py",       label="🔮 Prediksi Trend")

    render_login_sidebar()
    st.divider()

    if not df_hist.empty:
        df_check = df_hist.copy()
        df_check["value"] = pd.to_numeric(df_check["value"], errors="coerce")
        latest_c = df_check.sort_values("date").groupby(
            ["unit","equipment","titik","direction"], as_index=False).last()
        n_d = sum(1 for _, r in latest_c.iterrows()
            if get_zone(r["value"], THRESHOLD["Turbine" if "turbine" in str(r["equipment"]).lower() else "Pump/Fan"])[0] == "ZONE D")
        n_c = sum(1 for _, r in latest_c.iterrows()
            if get_zone(r["value"], THRESHOLD["Turbine" if "turbine" in str(r["equipment"]).lower() else "Pump/Fan"])[0] == "ZONE C")
        if n_d > 0:
            st.error(f"🔴 {n_d} titik Danger aktif")
        elif n_c > 0:
            st.warning(f"🟡 {n_c} titik Warning aktif")
        else:
            st.success("✅ Semua titik normal")

# ── Proses upload ─────────────────────────────────────────────────────────────
if uploaded:
    if check_role() != "editor":
        st.warning("🔒 Upload hanya untuk Editor. Silakan login di sidebar.")
    else:
        total_saved = 0
        total_skipped = 0
        for file in uploaded:
            df_new = parse_excel(file)
            if not df_new.empty:
                saved = save_to_db(df_new)
                skipped = len(df_new) - saved
                total_saved += saved
                total_skipped += skipped
                st.success(f"✅ {file.name}: {saved} baris disimpan · {skipped} duplikat")
        if total_saved > 0:
            st.success(f"🎉 Total {total_saved} baris baru berhasil disimpan.")
            st.cache_data.clear()
            st.rerun()
        if total_skipped > 0:
            st.info(f"ℹ️ Total {total_skipped} baris duplikat dilewati.")

# ── Load data ─────────────────────────────────────────────────────────────────
if df_hist.empty:
    st.info("📂 Belum ada data. Silakan upload file Excel dari sidebar kiri.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")

all_units = sorted(df_hist["unit"].dropna().unique())
all_equip = sorted(df_hist["equipment"].dropna().unique())

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown("## 📊 Ringkasan Status")
fc1, fc2, fc3 = st.columns(3)
with fc1:
    sel_unit  = st.multiselect("Unit",      all_units,     default=all_units,     key="home_unit")
with fc2:
    sel_equip = st.multiselect("Equipment", all_equip,     default=all_equip,     key="home_equip")
with fc3:
    sel_dir   = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="home_dir")

df_f = df_hist[
    df_hist["unit"].isin(sel_unit) &
    df_hist["equipment"].isin(sel_equip) &
    df_hist["direction"].isin(sel_dir)
].copy()

if df_f.empty:
    st.warning("Tidak ada data sesuai filter.")
    st.stop()

df_f = add_zone_cols(df_f)

# ── KPI ───────────────────────────────────────────────────────────────────────
latest = df_f.sort_values("date").groupby(
    ["unit","equipment","titik","direction"], as_index=False).last()

total  = len(latest)
n_d    = (latest["zone"] == "ZONE D").sum()
n_c    = (latest["zone"] == "ZONE C").sum()
n_b    = (latest["zone"] == "ZONE B").sum()
n_a    = (latest["zone"] == "ZONE A").sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Titik",      total)
k2.metric("🔴 Danger",        int(n_d))
k3.metric("🟡 Warning",       int(n_c))
k4.metric("🟢 Pre Warning",   int(n_b))
k5.metric("🔵 Accepted",      int(n_a))

pct_a = round(n_a / total * 100) if total else 0
pct_b = round(n_b / total * 100) if total else 0
pct_c = round(n_c / total * 100) if total else 0
pct_d = round(n_d / total * 100) if total else 0
st.markdown(f"""
<div style="margin:4px 0 16px">
  <div style="height:12px;border-radius:6px;overflow:hidden;display:flex;background:#e5e7eb">
    <div style="width:{pct_a}%;background:#3b82f6" title="Accepted {pct_a}%"></div>
    <div style="width:{pct_b}%;background:#22c55e" title="Pre Warning {pct_b}%"></div>
    <div style="width:{pct_c}%;background:#eab308" title="Warning {pct_c}%"></div>
    <div style="width:{pct_d}%;background:#ef4444" title="Danger {pct_d}%"></div>
  </div>
  <div style="display:flex;gap:16px;font-size:12px;margin-top:5px">
    <span style="color:#1d4ed8">🔵 Accepted {pct_a}%</span>
    <span style="color:#15803d">🟢 Pre Warning {pct_b}%</span>
    <span style="color:#a16207">🟡 Warning {pct_c}%</span>
    <span style="color:#b91c1c">🔴 Danger {pct_d}%</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Card per Equipment (Alternatif A) ─────────────────────────────────────────
st.markdown("### Status Terakhir per Equipment")

CARD_BORDER = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#eab308","ZONE D":"#ef4444","N/A":"#94a3b8"}
CARD_BG     = {"ZONE A":"#eff6ff","ZONE B":"#f0fdf4","ZONE C":"#fefce8","ZONE D":"#fef2f2","N/A":"#f8fafc"}
ZONE_TEXT   = {"ZONE A":"#1d4ed8","ZONE B":"#15803d","ZONE C":"#a16207","ZONE D":"#b91c1c","N/A":"#64748b"}
DIR_COLOR   = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#eab308","ZONE D":"#ef4444","N/A":"#94a3b8"}

def fmt(v):
    return f"{v:.3f}" if v is not None and not pd.isna(v) else "–"

def dir_html(val, thr):
    if val is None or pd.isna(val):
        return "<span style='color:#94a3b8'>–</span>"
    zk = get_zone(val, thr)[0]
    color = DIR_COLOR.get(zk, "#888")
    return f"<span style='color:{color};font-weight:500'>{val:.3f}</span>"

# Kumpulkan data per equipment
eq_rows = []
for eq in sorted(latest["equipment"].unique()):
    df_eq = latest[latest["equipment"] == eq]
    unit  = df_eq["unit"].iloc[0]
    thr   = get_threshold(eq)
    h_val = df_eq[df_eq["direction"]=="H"]["value"].max() if not df_eq[df_eq["direction"]=="H"].empty else None
    v_val = df_eq[df_eq["direction"]=="V"]["value"].max() if not df_eq[df_eq["direction"]=="V"].empty else None
    a_val = df_eq[df_eq["direction"]=="A"]["value"].max() if not df_eq[df_eq["direction"]=="A"].empty else None
    max_val = df_eq["value"].max()
    zk, zi, zl = get_zone(max_val, thr)
    eq_rows.append({"eq":eq,"unit":unit,"H":h_val,"V":v_val,"A":a_val,
                    "max":max_val,"zk":zk,"zi":zi,"zl":zl,"thr":thr})

# Tampilkan card 3 kolom
cols_per_row = 3
for i in range(0, len(eq_rows), cols_per_row):
    chunk = eq_rows[i:i+cols_per_row]
    cols  = st.columns(cols_per_row)
    for col, r in zip(cols, chunk):
        border  = CARD_BORDER.get(r["zk"], "#94a3b8")
        bg      = CARD_BG.get(r["zk"], "#f8fafc")
        ztcolor = ZONE_TEXT.get(r["zk"], "#64748b")
        col.markdown(f"""
<div style="
    background:{bg};
    border-left:4px solid {border};
    border-radius:0 10px 10px 0;
    padding:12px 14px;
    margin-bottom:4px;
    border-top:0.5px solid {border}33;
    border-right:0.5px solid {border}33;
    border-bottom:0.5px solid {border}33;
">
  <div style="font-size:13px;font-weight:500;color:#1e293b;margin-bottom:2px">{r['eq']}</div>
  <div style="font-size:11px;color:#64748b;margin-bottom:10px">{r['unit']}</div>
  <div style="display:flex;gap:8px;margin-bottom:10px">
    <div style="flex:1;text-align:center;background:rgba(255,255,255,0.7);border-radius:6px;padding:5px 4px">
      <div style="font-size:9px;color:#94a3b8;margin-bottom:2px">H</div>
      <div style="font-size:13px;font-weight:500;color:{DIR_COLOR.get(get_zone(r['H'],r['thr'])[0],'#888') if r['H'] is not None and not pd.isna(r['H']) else '#94a3b8'}">{fmt(r['H'])}</div>
    </div>
    <div style="flex:1;text-align:center;background:rgba(255,255,255,0.7);border-radius:6px;padding:5px 4px">
      <div style="font-size:9px;color:#94a3b8;margin-bottom:2px">V</div>
      <div style="font-size:13px;font-weight:500;color:{DIR_COLOR.get(get_zone(r['V'],r['thr'])[0],'#888') if r['V'] is not None and not pd.isna(r['V']) else '#94a3b8'}">{fmt(r['V'])}</div>
    </div>
    <div style="flex:1;text-align:center;background:rgba(255,255,255,0.7);border-radius:6px;padding:5px 4px">
      <div style="font-size:9px;color:#94a3b8;margin-bottom:2px">A</div>
      <div style="font-size:13px;font-weight:500;color:{DIR_COLOR.get(get_zone(r['A'],r['thr'])[0],'#888') if r['A'] is not None and not pd.isna(r['A']) else '#94a3b8'}">{fmt(r['A'])}</div>
    </div>
  </div>
  <div style="font-size:12px;font-weight:500;color:{ztcolor}">{r['zi']} {r['zl']}</div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Detail per Equipment ──────────────────────────────────────────────────────
st.markdown("### 🔍 Detail per Equipment")
sel_det = st.selectbox("Pilih Equipment", sorted(latest["equipment"].unique()), key="home_det")
thr_det = get_threshold(sel_det)
df_det  = latest[latest["equipment"] == sel_det][["unit","titik","direction","value","date"]].copy()
df_det["Status"] = df_det["value"].apply(
    lambda v: get_zone(v, thr_det)[1] + " " + get_zone(v, thr_det)[2]
).astype(str)
df_det["value"] = df_det["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
df_det["date"]  = pd.to_datetime(df_det["date"]).dt.strftime("%Y-%m-%d")
df_det = df_det.rename(columns={"unit":"Unit","titik":"Titik","direction":"Dir","value":"mm/s","date":"Tanggal"})
st.dataframe(df_det, use_container_width=True, hide_index=True)

st.divider()

# ── Trend Vibrasi ─────────────────────────────────────────────────────────────
st.markdown("### 📈 Trend Vibrasi")
tc1, tc2, tc3, tc4 = st.columns([2,2,1,1])
with tc1:
    sel_eq_tr = st.selectbox("Equipment", sorted(df_f["equipment"].unique()), key="home_eq_tr")
with tc2:
    titik_opts = ["Semua Titik"] + sorted(df_f[df_f["equipment"]==sel_eq_tr]["titik"].unique())
    sel_titik_tr = st.selectbox("Titik Ukur", titik_opts, key="home_titik_tr")
with tc3:
    sel_dir_tr = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="home_dir_tr")
with tc4:
    trend_range = st.selectbox("Rentang", ["7 Hari","30 Hari","90 Hari","180 Hari","All"], index=1, key="home_range_tr")

df_tr = df_f[df_f["equipment"]==sel_eq_tr].copy()
if trend_range != "All":
    days_map = {"7 Hari":7,"30 Hari":30,"90 Hari":90,"180 Hari":180}
    if not df_tr.empty:
        end_date   = df_tr["date"].max()
        start_date = end_date - timedelta(days=days_map[trend_range])
        df_tr = df_tr[(df_tr["date"] >= start_date) & (df_tr["date"] <= end_date)]

if sel_titik_tr != "Semua Titik":
    df_tr = df_tr[df_tr["titik"]==sel_titik_tr]
if sel_dir_tr:
    df_tr = df_tr[df_tr["direction"].isin(sel_dir_tr)]
df_tr = df_tr.sort_values("date")

thr_tr = get_threshold(sel_eq_tr)
colors_dir = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
ls_list    = ["solid","dash","dot","dashdot"]

if not df_tr.empty:
    fig = go.Figure()
    for i, titik in enumerate(sorted(df_tr["titik"].unique())):
        for d in sel_dir_tr:
            sub = df_tr[(df_tr["titik"]==titik)&(df_tr["direction"]==d)]
            if sub.empty: continue
            fig.add_trace(go.Scatter(
                x=sub["date"], y=sub["value"],
                mode="lines+markers", name=f"{titik} – {d}",
                line=dict(color=colors_dir.get(d,"#888"), width=2, dash=ls_list[i%4]),
                marker=dict(size=6),
                hovertemplate=f"<b>{titik} ({d})</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
            ))
    fig.add_hline(y=thr_tr["A"], line_dash="dot",  line_color="#3b82f6", line_width=1,
                  annotation_text=f"Accepted ({thr_tr['A']})", annotation_position="top left")
    fig.add_hline(y=thr_tr["B"], line_dash="dot",  line_color="#22c55e", line_width=1,
                  annotation_text=f"Pre Warning ({thr_tr['B']})", annotation_position="top left")
    fig.add_hline(y=thr_tr["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
                  annotation_text=f"Warning ({thr_tr['C']})", annotation_position="top left")
    fig.update_layout(
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
        height=420, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Tidak ada data untuk pilihan ini.")
