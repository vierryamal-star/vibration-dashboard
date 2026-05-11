import streamlit as st
import pandas as pd
from utils import (
    load_history, add_zone_cols, get_zone, get_threshold,
    render_login_sidebar, check_role
)

st.set_page_config(
    page_title="Monitor — PLTU TBK",
    page_icon="⚡",
    layout="wide"
)

# ====================== SIDEBAR ======================
with st.sidebar:
    try:
        st.image("assets/logo_pln_ip.png", width=200)
    except:
        st.markdown("### ⚡ PLTU TBK")
    
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    
    st.markdown("### Navigasi")
    st.page_link("app.py", label="📊 Monitor", icon="1️⃣")
    st.page_link("pages/2_Analisis.py", label="📈 Analisis", icon="2️⃣")
    st.page_link("pages/3_Data_Kelola.py", label="🗄️ Data & Kelola", icon="3️⃣")
    
    render_login_sidebar()

# ====================== LOAD DATA ======================
df_hist = load_history()

if df_hist.empty:
    st.info("📂 Belum ada data. Silakan upload di halaman Data & Kelola.")
    st.stop()

df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
df_hist = add_zone_cols(df_hist)

# ====================== FILTER GLOBAL ======================
st.markdown("# 📊 Monitor Vibrasi PLTU TBK")

unit_options = ["All"] + sorted(df_hist["unit"].dropna().unique())
sel_unit_btn = st.radio("Filter Unit", unit_options, horizontal=True, label_visibility="collapsed")

if sel_unit_btn == "All":
    df_f = df_hist.copy()
else:
    df_f = df_hist[df_hist["unit"] == sel_unit_btn].copy()

latest = df_f.sort_values("date").groupby(
    ["unit", "equipment", "titik", "direction"], as_index=False
).last()

# ====================== KPI RINGKAS ======================
st.markdown("### Seksi 1 — KPI Ringkas")

total = len(latest)
n_d = (latest["zone"] == "ZONE D").sum()
n_c = (latest["zone"] == "ZONE C").sum()
n_b = (latest["zone"] == "ZONE B").sum()
n_a = (latest["zone"] == "ZONE A").sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Titik Ukur", f"{total:,}")
k2.metric("🔴 Danger", int(n_d), delta=None)
k3.metric("🟡 Warning", int(n_c), delta=None)
k4.metric("🟢 Pre Warning", int(n_b), delta=None)
k5.metric("🔵 Accepted", int(n_a), delta=None)

# Progress Bar
pct_a = round(n_a / total * 100) if total else 0
pct_b = round(n_b / total * 100) if total else 0
pct_c = round(n_c / total * 100) if total else 0
pct_d = round(n_d / total * 100) if total else 0

st.markdown(f"""
<div style="margin: 10px 0 20px">
  <div style="height:14px; border-radius:8px; overflow:hidden; background:#e2e8f0; display:flex">
    <div style="width:{pct_a}%; background:#3b82f6"></div>
    <div style="width:{pct_b}%; background:#22c55e"></div>
    <div style="width:{pct_c}%; background:#eab308"></div>
    <div style="width:{pct_d}%; background:#ef4444"></div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ====================== STATUS PER EQUIPMENT ======================
st.markdown("### Seksi 2 — Status per Equipment")

eq_rows = []
for eq in sorted(latest["equipment"].unique()):
    df_eq = latest[latest["equipment"] == eq]
    unit = df_eq["unit"].iloc[0]
    max_val = df_eq["value"].max()
    thr = get_threshold(eq)
    zone_key, icon, label = get_zone(max_val, thr)
    
    h = df_eq[df_eq["direction"]=="H"]["value"].max()
    v = df_eq[df_eq["direction"]=="V"]["value"].max()
    a = df_eq[df_eq["direction"]=="A"]["value"].max()
    
    eq_rows.append({
        "equipment": eq,
        "unit": unit,
        "H": h, "V": v, "A": a,
        "max": max_val,
        "zone_key": zone_key,
        "icon": icon,
        "label": label
    })

cols = st.columns(3)
for i, r in enumerate(eq_rows):
    with cols[i % 3]:
        color = {
            "ZONE A": "#3b82f6", "ZONE B": "#22c55e",
            "ZONE C": "#eab308", "ZONE D": "#ef4444"
        }.get(r["zone_key"], "#94a3b8")
        
        st.markdown(f"""
        <div style="border:2px solid {color}; border-radius:12px; padding:16px; margin-bottom:12px; background:var(--background-color)">
            <div style="font-weight:600; font-size:1.1em;">{r['equipment']}</div>
            <div style="color:gray; font-size:0.9em;">{r['unit']}</div>
            
            <div style="display:flex; gap:8px; margin:12px 0;">
                <div style="flex:1; text-align:center; background:#f8fafc; padding:8px; border-radius:8px;">
                    <small>H</small><br><b style="color:{color}">{r['H']:.3f if pd.notna(r['H']) else '–'}</b>
                </div>
                <div style="flex:1; text-align:center; background:#f8fafc; padding:8px; border-radius:8px;">
                    <small>V</small><br><b style="color:{color}">{r['V']:.3f if pd.notna(r['V']) else '–'}</b>
                </div>
                <div style="flex:1; text-align:center; background:#f8fafc; padding:8px; border-radius:8px;">
                    <small>A</small><br><b style="color:{color}">{r['A']:.3f if pd.notna(r['A']) else '–'}</b>
                </div>
            </div>
            
            <div style="text-align:center; font-size:1.1em; color:{color}; font-weight:600;">
                {r['icon']} {r['label']}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ====================== ALARM AKTIF ======================
st.divider()
st.markdown("### Seksi 3 — Alarm Aktif")

if n_d > 0:
    st.error(f"🔴 **DANGER** — Ada {n_d} titik ukur dalam kondisi bahaya!")
elif n_c > 0:
    st.warning(f"🟡 **WARNING** — Ada {n_c} titik ukur perlu perhatian!")

st.divider()

# ====================== DETAIL EQUIPMENT ======================
st.markdown("### Seksi 4 — Detail Equipment")

sel_eq = st.selectbox("Pilih Equipment", sorted(latest["equipment"].unique()))

thr = get_threshold(sel_eq)
df_det = latest[latest["equipment"] == sel_eq].copy()

# Pivot Table
pivot = df_det.pivot_table(
    index="titik", 
    columns="direction", 
    values="value", 
    aggfunc="last"
).reset_index()

dir_cols = [c for c in ["H","V","A"] if c in pivot.columns]
pivot["Max (mm/s)"] = pivot[dir_cols].max(axis=1)
pivot["Status"] = pivot["Max (mm/s)"].apply(lambda x: get_zone(x, thr)[1] + " " + get_zone(x, thr)[2])

for c in dir_cols + ["Max (mm/s)"]:
    pivot[c] = pivot[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else "–")

st.dataframe(
    pivot.rename(columns={"titik": "Titik Ukur"}),
    use_container_width=True,
    hide_index=True
)

st.caption(f"Terakhir diperbarui: {df_hist['date'].max().strftime('%d %B %Y') if not df_hist.empty else '-'}")
