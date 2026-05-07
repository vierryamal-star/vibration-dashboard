import streamlit as st
import pandas as pd
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import load_history, get_zone, THRESHOLD, add_zone_cols, ZONE_COLOR

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

st.markdown("## 🚨 Alarm & Warning")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
df_hist = add_zone_cols(df_hist)

# Ambil data terakhir per titik ukur
latest = df_hist.sort_values("date").groupby(
    ["unit","equipment","titik","direction"], as_index=False).last()
latest["zone_label"] = latest.apply(
    lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1]+" "+
              get_zone(r["value"], THRESHOLD[r["thr_type"]])[0], axis=1
).astype(str)

# ── Filter ────────────────────────────────────────────────────────────────────
st.markdown("### Filter")
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    all_units = sorted(latest["unit"].dropna().unique())
    sel_unit  = st.multiselect("Unit", all_units, default=all_units, key="alm_unit")
with fc2:
    all_equip = sorted(latest["equipment"].dropna().unique())
    sel_equip = st.multiselect("Equipment", all_equip, default=all_equip, key="alm_equip")
with fc3:
    sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="alm_dir")
with fc4:
    sel_zone = st.multiselect("Zone", ["ZONE D","ZONE C","ZONE B","ZONE A"],
                               default=["ZONE D","ZONE C"], key="alm_zone")

df_f = latest[
    latest["unit"].isin(sel_unit) &
    latest["equipment"].isin(sel_equip) &
    latest["direction"].isin(sel_dir) &
    latest["zone"].isin(sel_zone)
].copy()

# ── KPI ringkas ───────────────────────────────────────────────────────────────
n_d = (df_f["zone"]=="ZONE D").sum()
n_c = (df_f["zone"]=="ZONE C").sum()
k1, k2, k3 = st.columns(3)
k1.metric("Total titik (sesuai filter)", len(df_f))
k2.metric("🔴 Zone D", int(n_d))
k3.metric("🟠 Zone C", int(n_c))

st.divider()

# ── Tabel Zone D ──────────────────────────────────────────────────────────────
df_d = df_f[df_f["zone"]=="ZONE D"]
if not df_d.empty:
    st.error(f"🔴 **BAHAYA — Zone D**: {len(df_d)} titik ukur melebihi batas kritis!")
    show_d = df_d[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
    show_d["value"] = show_d["value"].map(lambda v: f"{v:.3f}")
    show_d = show_d.rename(columns={
        "unit":"Unit","equipment":"Equipment","titik":"Titik",
        "direction":"Dir","value":"mm/s","zone_label":"Zone","date":"Tanggal"})
    st.dataframe(show_d, use_container_width=True, hide_index=True)
else:
    if "ZONE D" in sel_zone:
        st.success("✅ Tidak ada titik ukur di Zone D.")

st.divider()

# ── Tabel Zone C ──────────────────────────────────────────────────────────────
df_c = df_f[df_f["zone"]=="ZONE C"]
if not df_c.empty:
    st.warning(f"🟠 **PERHATIAN — Zone C**: {len(df_c)} titik ukur perlu dipantau.")
    show_c = df_c[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
    show_c["value"] = show_c["value"].map(lambda v: f"{v:.3f}")
    show_c = show_c.rename(columns={
        "unit":"Unit","equipment":"Equipment","titik":"Titik",
        "direction":"Dir","value":"mm/s","zone_label":"Zone","date":"Tanggal"})
    st.dataframe(show_c, use_container_width=True, hide_index=True)
else:
    if "ZONE C" in sel_zone:
        st.success("✅ Tidak ada titik ukur di Zone C.")

# ── Zone B & A jika dipilih ───────────────────────────────────────────────────
for zone_name, color_fn in [("ZONE B", st.info), ("ZONE A", st.success)]:
    if zone_name in sel_zone:
        df_z = df_f[df_f["zone"]==zone_name]
        if not df_z.empty:
            st.divider()
            color_fn(f"{'🟡' if zone_name=='ZONE B' else '🟢'} **{zone_name}**: {len(df_z)} titik ukur")
            show_z = df_z[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
            show_z["value"] = show_z["value"].map(lambda v: f"{v:.3f}")
            show_z = show_z.rename(columns={
                "unit":"Unit","equipment":"Equipment","titik":"Titik",
                "direction":"Dir","value":"mm/s","zone_label":"Zone","date":"Tanggal"})
            st.dataframe(show_z, use_container_width=True, hide_index=True)

st.divider()

# ── Heatmap ───────────────────────────────────────────────────────────────────
st.markdown("### Heatmap Nilai Vibrasi Maksimum")
hm = latest[latest["unit"].isin(sel_unit) & latest["equipment"].isin(sel_equip)].copy()
hm["label"] = hm["titik"] + " " + hm["direction"]
hm_pivot = hm.pivot_table(index="equipment", columns="label", values="value", aggfunc="max")
if not hm_pivot.empty:
    fig_hm = px.imshow(
        hm_pivot,
        color_continuous_scale=["#22c55e","#eab308","#f97316","#ef4444"],
        labels=dict(color="mm/s"), aspect="auto",
    )
    fig_hm.update_layout(
        height=max(300, len(hm_pivot)*40+100),
        title="Nilai Maksimum (mm/s) per Equipment × Titik Ukur",
    )
    st.plotly_chart(fig_hm, use_container_width=True)
