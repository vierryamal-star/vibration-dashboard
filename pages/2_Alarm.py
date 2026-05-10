import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history,
    get_zone,
    get_threshold,
    THRESHOLD,
    add_zone_cols,
    render_login_sidebar
)

st.set_page_config(page_title="Alarm & Warning — PLTU TBK", page_icon="🚨", layout="wide")
st.markdown("""<style>[data-testid="stSidebarNav"]{display:none;}</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py",      label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py",      label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py",    label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py", label="⚙️ Pengaturan")
    st.page_link("pages/5_Prediksi.py",   label="🔮 Prediksi Trend")
    render_login_sidebar()

st.markdown("## 🚨 Alarm & Warning")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
df_hist = add_zone_cols(df_hist)

latest = df_hist.sort_values("date").groupby(
    ["unit","equipment","titik","direction"], as_index=False).last()
latest["zone_label"] = latest.apply(
    lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1] + " " +
              get_zone(r["value"], THRESHOLD[r["thr_type"]])[2], axis=1
).astype(str)

# ── Filter — 2 baris rapi ─────────────────────────────────────────────────────
st.markdown("#### Filter")

# Baris 1: Unit (pill) + Zone
all_units = sorted(latest["unit"].dropna().unique())
unit_options = ["All"] + all_units

f_row1a, f_row1b = st.columns([3, 2])
with f_row1a:
    sel_unit_btn = st.radio("Unit", unit_options, horizontal=True, key="alm_unit_radio", label_visibility="collapsed")
with f_row1b:
    sel_zone = st.multiselect(
        "Status",
        ["Danger","Warning","Pre Warning","Accepted"],
        default=["Danger","Warning"],
        key="alm_zone"
    )

# Baris 2: Equipment + Direction + Tanggal
f_row2a, f_row2b, f_row2c = st.columns([2, 1, 2])
with f_row2a:
    all_equip = sorted(latest["equipment"].dropna().unique())
    sel_equip = st.multiselect("Equipment", all_equip, default=all_equip, key="alm_equip")
with f_row2b:
    sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="alm_dir")
with f_row2c:
    min_date = latest["date"].min().date()
    max_date = latest["date"].max().date()
    sel_date = st.date_input("Tanggal", value=(min_date, max_date), key="alarm_date")

# Map label → zone key
zone_map = {"Danger":"ZONE D","Warning":"ZONE C","Pre Warning":"ZONE B","Accepted":"ZONE A"}
sel_zone_keys = [zone_map[z] for z in sel_zone if z in zone_map]
sel_unit = all_units if sel_unit_btn == "All" else [sel_unit_btn]

df_f = latest[
    latest["unit"].isin(sel_unit) &
    latest["equipment"].isin(sel_equip) &
    latest["direction"].isin(sel_dir) &
    latest["zone"].isin(sel_zone_keys)
].copy()

if len(sel_date) == 2:
    df_f = df_f[
        (df_f["date"].dt.date >= sel_date[0]) &
        (df_f["date"].dt.date <= sel_date[1])
    ]

st.divider()

# ── KPI ringkas ───────────────────────────────────────────────────────────────
n_d = (df_f["zone"]=="ZONE D").sum()
n_c = (df_f["zone"]=="ZONE C").sum()
n_b = (df_f["zone"]=="ZONE B").sum()
n_a = (df_f["zone"]=="ZONE A").sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Titik", len(df_f))
k2.metric("🔴 Danger",      int(n_d))
k3.metric("🟡 Warning",     int(n_c))
k4.metric("🟢 Pre Warning", int(n_b))
k5.metric("🔵 Accepted",    int(n_a))

st.divider()

# ── Tabel per status ──────────────────────────────────────────────────────────
STATUS_CONFIG = [
    ("ZONE D", "Danger",      "error",   "🔴"),
    ("ZONE C", "Warning",     "warning", "🟡"),
    ("ZONE B", "Pre Warning", "info",    "🟢"),
    ("ZONE A", "Accepted",    "success", "🔵"),
]

for zk, zl, fn, zi in STATUS_CONFIG:
    if zk not in sel_zone_keys:
        continue
    df_z = df_f[df_f["zone"]==zk]
    if df_z.empty:
        getattr(st, fn)(f"{zi} Tidak ada titik {zl}.")
        continue

    getattr(st, fn)(f"{zi} **{zl}** — {len(df_z)} titik ukur")
    show = df_z[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
    show["value"] = show["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
    show["date"]  = pd.to_datetime(show["date"]).dt.strftime("%d-%b-%Y")
    show = show.rename(columns={
        "unit":"Unit","equipment":"Equipment","titik":"Titik",
        "direction":"Dir","value":"mm/s","zone_label":"Status","date":"Tanggal"})
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.markdown("")

st.divider()

# ── Heatmap — bar chart horizontal per equipment ──────────────────────────────
st.markdown("### Heatmap Nilai Vibrasi")
st.caption("Nilai maksimum per equipment × titik ukur — warna menunjukkan tingkat keparahan")

hm = latest[latest["unit"].isin(sel_unit) & latest["equipment"].isin(sel_equip)].copy()

if hm.empty:
    st.info("Tidak ada data untuk heatmap.")
    st.stop()

# Pivot: equipment × (titik+dir) → nilai max
hm["label"] = hm["titik"] + " · " + hm["direction"]
hm_pivot = hm.pivot_table(
    index="equipment", columns="label", values="value", aggfunc="max"
).reset_index()

# Buat bar chart horizontal per equipment
fig_hm = go.Figure()

ZONE_COLORS_HM = {
    "ZONE A": "#3b82f6",
    "ZONE B": "#22c55e",
    "ZONE C": "#eab308",
    "ZONE D": "#ef4444",
    "N/A":    "#94a3b8",
}

titik_cols = [c for c in hm_pivot.columns if c != "equipment"]

for _, row in hm_pivot.iterrows():
    eq_name = row["equipment"]
    thr = get_threshold(eq_name)
    vals   = []
    labels = []
    colors_bar = []
    texts  = []

    for col in titik_cols:
        v = row[col]
        if pd.isna(v):
            continue
        zk = get_zone(v, thr)[0]
        vals.append(v)
        labels.append(col)
        colors_bar.append(ZONE_COLORS_HM.get(zk, "#94a3b8"))
        texts.append(f"{v:.2f}")

    if not vals:
        continue

    fig_hm.add_trace(go.Bar(
        name=eq_name,
        y=[f"{eq_name} — {l}" for l in labels],
        x=vals,
        orientation="h",
        marker_color=colors_bar,
        text=texts,
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Nilai: %{x:.3f} mm/s<extra></extra>",
    ))

# Garis threshold
thr_ref = list(THRESHOLD.values())[0]
fig_hm.add_vline(x=thr_ref["A"], line_dash="dot",  line_color="#3b82f6", line_width=1,
                 annotation_text="Accepted", annotation_position="top")
fig_hm.add_vline(x=thr_ref["B"], line_dash="dot",  line_color="#22c55e", line_width=1,
                 annotation_text="Pre Warning", annotation_position="top")
fig_hm.add_vline(x=thr_ref["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
                 annotation_text="Warning", annotation_position="top")

n_rows = sum(1 for _, row in hm_pivot.iterrows()
             for col in titik_cols if not pd.isna(row[col]))
chart_height = max(400, n_rows * 28 + 80)

fig_hm.update_layout(
    xaxis_title="Nilai Vibrasi (mm/s)",
    yaxis_title="",
    height=chart_height,
    showlegend=False,
    barmode="relative",
    yaxis=dict(autorange="reversed"),
    margin=dict(l=10, r=80, t=20, b=40),
)
st.plotly_chart(fig_hm, use_container_width=True)

# Legenda warna
st.markdown("""
<div style="display:flex;gap:16px;font-size:12px;color:var(--color-text-secondary)">
  <span style="color:#3b82f6">🔵 Accepted (&lt; 1.4)</span>
  <span style="color:#22c55e">🟢 Pre Warning (1.4–2.8)</span>
  <span style="color:#eab308">🟡 Warning (2.8–4.5)</span>
  <span style="color:#ef4444">🔴 Danger (&gt; 4.5)</span>
</div>
""", unsafe_allow_html=True)
