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
    st.markdown("### 🗂️ Navigasi")
    st.page_link("app.py",               label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py",     label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py",     label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py",   label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py",label="⚙️ Pengaturan")

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
    lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1]+" "+
              get_zone(r["value"], THRESHOLD[r["thr_type"]])[0], axis=1
).astype(str)

df_d = latest[latest["zone"]=="ZONE D"]
df_c = latest[latest["zone"]=="ZONE C"]

# ── Zone D ────────────────────────────────────────────────────────────────────
if not df_d.empty:
    st.error(f"🔴 **BAHAYA — Zone D**: {len(df_d)} titik ukur melebihi batas kritis!")
    show_d = df_d[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
    show_d["value"] = show_d["value"].map(lambda v: f"{v:.3f}")
    show_d = show_d.rename(columns={
        "unit":"Unit","equipment":"Equipment","titik":"Titik",
        "direction":"Dir","value":"mm/s","zone_label":"Zone","date":"Tanggal"
    })
    st.dataframe(show_d, use_container_width=True, hide_index=True)
else:
    st.success("✅ Tidak ada titik ukur di Zone D.")

st.divider()

# ── Zone C ────────────────────────────────────────────────────────────────────
if not df_c.empty:
    st.warning(f"🟠 **PERHATIAN — Zone C**: {len(df_c)} titik ukur perlu dipantau.")
    show_c = df_c[["unit","equipment","titik","direction","value","zone_label","date"]].copy()
    show_c["value"] = show_c["value"].map(lambda v: f"{v:.3f}")
    show_c = show_c.rename(columns={
        "unit":"Unit","equipment":"Equipment","titik":"Titik",
        "direction":"Dir","value":"mm/s","zone_label":"Zone","date":"Tanggal"
    })
    st.dataframe(show_c, use_container_width=True, hide_index=True)
else:
    st.success("✅ Tidak ada titik ukur di Zone C.")

st.divider()

# ── Heatmap ───────────────────────────────────────────────────────────────────
st.markdown("### Heatmap Nilai Vibrasi Maksimum")
hm = latest.copy()
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
