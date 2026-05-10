import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from utils import (
    init_db, save_to_db, load_history, parse_excel,
    get_zone, get_threshold, THRESHOLD, ZONE_COLOR, add_zone_cols,
    render_login_sidebar, check_role
)

st.set_page_config(
    page_title="Monitoring Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS: rapikan sidebar & sembunyikan default nav label ──────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"] {display: none;}
section[data-testid="stSidebar"] > div:first-child {padding-top: 1rem;}
[data-testid="stSidebar"] hr {margin: 0.5rem 0;}
</style>
""", unsafe_allow_html=True)

# Load data sekali saja
df_hist = load_history()
# ── Sidebar: navigasi + upload + status ───────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
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
    st.page_link("app.py",                    label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py",           label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py",           label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py",         label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py",      label="⚙️ Pengaturan")
    st.page_link("pages/5_Prediksi.py",        label="🔮 Prediksi Trend")

    render_login_sidebar()

    st.divider()

    # Status ringkas
    df_check = df_hist.copy()
    if not df_check.empty:
        df_check["value"] = pd.to_numeric(df_check["value"], errors="coerce")
        latest_c = df_check.sort_values("date").groupby(
            ["unit","equipment","titik","direction"], as_index=False).last()
        n_d = sum(
            1 for _, r in latest_c.iterrows()
            if get_zone(r["value"], THRESHOLD["Turbine" if "turbine" in str(r["equipment"]).lower() else "Pump/Fan"])[0] == "ZONE D"
        )
        n_c = sum(
            1 for _, r in latest_c.iterrows()
            if get_zone(r["value"], THRESHOLD["Turbine" if "turbine" in str(r["equipment"]).lower() else "Pump/Fan"])[0] == "ZONE C"
        )
        if n_d > 0:
            st.error(f"🔴 {n_d} titik Zone D aktif")
        elif n_c > 0:
            st.warning(f"🟠 {n_c} titik Zone C aktif")
        else:
            st.success("✅ Semua titik normal")

# ── Proses upload (Editor only) ───────────────────────────────────────────────
if uploaded:
    if check_role() != "editor":
        st.warning("🔒 Upload data hanya tersedia untuk **Editor**. Silakan login di sidebar kiri.")
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

                st.success(
                    f"✅ {file.name}: {saved} baris disimpan · {skipped} duplikat"
                )

        if total_saved > 0:
            st.success(
                f"🎉 Total {total_saved} baris baru berhasil disimpan."
            )
            st.cache_data.clear()
            st.rerun()

        if total_skipped > 0:
            st.info(
                f"ℹ️ Total {total_skipped} baris duplikat dilewati."
            )
# ── Load & filter ─────────────────────────────────────────────────────────────

if df_hist.empty:
    st.info("📂 Belum ada data. Silakan upload file Excel dari sidebar kiri.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")

all_units = sorted(df_hist["unit"].dropna().unique())
all_equip = sorted(df_hist["equipment"].dropna().unique())

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown("## 📊 Ringkasan Status")
fc1, fc2, fc3 = st.columns(3)
with fc1:
    sel_unit  = st.multiselect("Unit",       all_units,        default=all_units,        key="home_unit")
with fc2:
    sel_equip = st.multiselect("Equipment",  all_equip,        default=all_equip,        key="home_equip")
with fc3:
    sel_dir   = st.multiselect("Direction",  ["H","V","A"],    default=["H","V","A"],    key="home_dir")

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
n_norm = ((latest["zone"] == "ZONE A") | (latest["zone"] == "ZONE B")).sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Titik Ukur",     total)
k2.metric("🔴 Zone D — Bahaya",   int(n_d),    delta=None)
k3.metric("🟠 Zone C — Perhatian",int(n_c),    delta=None)
k4.metric("🟢 Zone A–B — Normal", int(n_norm), delta=None)

# Status bar proporsi
pct_ok = round(n_norm / total * 100) if total else 0
pct_c  = round(n_c    / total * 100) if total else 0
pct_d  = round(n_d    / total * 100) if total else 0
st.markdown(
    f"""
    <div style="margin:4px 0 12px">
      <div style="height:10px;border-radius:5px;overflow:hidden;display:flex;background:var(--secondary-background-color)">
        <div style="width:{pct_ok}%;background:#22c55e"></div>
        <div style="width:{pct_c}%;background:#f97316"></div>
        <div style="width:{pct_d}%;background:#ef4444"></div>
      </div>
      <div style="display:flex;gap:16px;font-size:12px;margin-top:4px;color:gray">
        <span style="color:#22c55e">Normal {pct_ok}%</span>
        <span style="color:#f97316">Zone C {pct_c}%</span>
        <span style="color:#ef4444">Zone D {pct_d}%</span>
      </div>
    </div>
    """, unsafe_allow_html=True
)

st.divider()

# ── Tabel status terakhir ─────────────────────────────────────────────────────
st.markdown("### Status Terakhir per Titik Ukur")

pivot = latest.pivot_table(
    index=["unit","equipment","titik"],
    columns="direction", values="value", aggfunc="last"
).reset_index()
pivot.columns.name = None

dir_cols = [c for c in ["H","V","A"] if c in pivot.columns]
pivot["Max (mm/s)"] = pivot[dir_cols].max(axis=1)
pivot["Thr"] = pivot["equipment"].apply(
    lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan"
)

def _zlabel(r):
    icon = get_zone(r["Max (mm/s)"], THRESHOLD[r["Thr"]])[1]
    lbl  = get_zone(r["Max (mm/s)"], THRESHOLD[r["Thr"]])[0]
    return f"{icon} {lbl}"

pivot["Zone"] = pivot.apply(_zlabel, axis=1).astype(str)
pivot = pivot.drop(columns=["Thr"])
pivot = pivot.rename(columns={"unit":"Unit","equipment":"Equipment","titik":"Titik Ukur"})
for c in dir_cols:
    pivot[c] = pivot[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
pivot["Max (mm/s)"] = pivot["Max (mm/s)"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")

st.dataframe(pivot, use_container_width=True, hide_index=True)

st.divider()

# ── Detail equipment ──────────────────────────────────────────────────────────
st.markdown("### 🔍 Detail per Equipment")
sel_det = st.selectbox("Pilih Equipment", sorted(latest["equipment"].unique()), key="home_det")
thr_det = get_threshold(sel_det)
df_det  = latest[latest["equipment"] == sel_det][["unit","titik","direction","value","date"]].copy()
df_det["Zone"] = df_det["value"].apply(
    lambda v: get_zone(v, thr_det)[1] + " " + get_zone(v, thr_det)[0]
).astype(str)
df_det["value"] = df_det["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
df_det = df_det.rename(columns={"unit":"Unit","titik":"Titik","direction":"Dir","value":"mm/s","date":"Tanggal"})
df_det["Tanggal"] = pd.to_datetime(df_det["Tanggal"]).dt.strftime("%Y-%m-%d")
st.dataframe(df_det, use_container_width=True, hide_index=True)

st.divider()

# ── Trend ringkasan (semua equipment) ────────────────────────────────────────
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

    trend_range = st.selectbox(
        "Rentang",
        ["7 Hari", "30 Hari", "90 Hari", "180 Hari", "All"],
        index=0,
        key="home_range_tr"
    )

df_tr = df_f[df_f["equipment"]==sel_eq_tr].copy()
# Filter rentang trend
if trend_range != "All":

    days_map = {
        "7 Hari": 7,
        "30 Hari": 30,
        "90 Hari": 90,
        "180 Hari": 180
    }

    end_date = df_tr["date"].max()
    start_date = end_date - timedelta(days=days_map[trend_range])

    df_tr = df_tr[
        (df_tr["date"] >= start_date) &
        (df_tr["date"] <= end_date)
    ]
    
if sel_titik_tr != "Semua Titik":
    df_tr = df_tr[df_tr["titik"]==sel_titik_tr]
if sel_dir_tr:
    df_tr = df_tr[df_tr["direction"].isin(sel_dir_tr)]
df_tr = df_tr.sort_values("date")

thr_tr = get_threshold(sel_eq_tr)
colors_dir = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
ls_list = ["solid","dash","dot","dashdot"]

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
    fig.add_hline(y=thr_tr["A"], line_dash="dot",  line_color="#22c55e", line_width=1,
                  annotation_text=f"Zone A ({thr_tr['A']})", annotation_position="top left")
    fig.add_hline(y=thr_tr["B"], line_dash="dot",  line_color="#eab308", line_width=1,
                  annotation_text=f"Zone B ({thr_tr['B']})", annotation_position="top left")
    fig.add_hline(y=thr_tr["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
                  annotation_text=f"Zone C ({thr_tr['C']})", annotation_position="top left")
    fig.update_layout(
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
        height=420, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
