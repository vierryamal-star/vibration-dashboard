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
.eq-card {
    background: var(--background-color, var(--color-background-secondary));
    border-left: 4px solid var(--card-border, #94a3b8);
    border-radius: 0 10px 10px 0;
    border-top: 0.5px solid var(--color-border-tertiary);
    border-right: 0.5px solid var(--color-border-tertiary);
    border-bottom: 0.5px solid var(--color-border-tertiary);
    padding: 12px 14px;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)

df_hist = load_history()

# ── Sidebar ───────────────────────────────────────────────────────────────────
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

# ── Guard: tidak ada data ─────────────────────────────────────────────────────
if df_hist.empty:
    st.info("📂 Belum ada data. Silakan upload file Excel dari sidebar kiri.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")

all_units = sorted(df_hist["unit"].dropna().unique())
all_equip = sorted(df_hist["equipment"].dropna().unique())

# ── Header & filter unit ──────────────────────────────────────────────────────
st.markdown("## 📊 Ringkasan Status")

# Filter Unit — tombol pill
unit_options = ["All"] + all_units
sel_unit_btn = st.radio(
    "Filter Unit",
    unit_options,
    horizontal=True,
    key="home_unit_radio",
    label_visibility="collapsed"
)

# Filter direction
fc2, fc3 = st.columns([2, 1])
with fc2:
    sel_equip = st.multiselect("Equipment", all_equip, default=all_equip, key="home_equip")
with fc3:
    sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="home_dir")

# Terapkan filter unit
if sel_unit_btn == "All":
    sel_unit = all_units
else:
    sel_unit = [sel_unit_btn]

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

total = len(latest)
n_d   = (latest["zone"] == "ZONE D").sum()
n_c   = (latest["zone"] == "ZONE C").sum()
n_b   = (latest["zone"] == "ZONE B").sum()
n_a   = (latest["zone"] == "ZONE A").sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Titik",    total)
k2.metric("🔴 Danger",      int(n_d))
k3.metric("🟡 Warning",     int(n_c))
k4.metric("🟢 Pre Warning", int(n_b))
k5.metric("🔵 Accepted",    int(n_a))

pct_a = round(n_a / total * 100) if total else 0
pct_b = round(n_b / total * 100) if total else 0
pct_c = round(n_c / total * 100) if total else 0
pct_d = round(n_d / total * 100) if total else 0
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
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Card per Equipment ────────────────────────────────────────────────────────
st.markdown("### Status Terakhir per Equipment")

CARD_BORDER = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#eab308","ZONE D":"#ef4444","N/A":"#94a3b8"}
ZONE_TEXT   = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#eab308","ZONE D":"#ef4444","N/A":"#94a3b8"}

def fmt(v):
    return f"{v:.3f}" if v is not None and not pd.isna(v) else "–"

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

cols_per_row = 3
for i in range(0, len(eq_rows), cols_per_row):
    chunk = eq_rows[i:i+cols_per_row]
    cols  = st.columns(cols_per_row)
    for col, r in zip(cols, chunk):
        border  = CARD_BORDER.get(r["zk"], "#94a3b8")
        ztcolor = ZONE_TEXT.get(r["zk"], "#94a3b8")

        def dir_block(label, val, thr):
            if val is None or pd.isna(val):
                return f"""<div style="flex:1;text-align:center;background:var(--color-background-tertiary);border-radius:6px;padding:5px 4px">
                    <div style="font-size:9px;color:var(--color-text-secondary);margin-bottom:2px">{label}</div>
                    <div style="font-size:13px;color:var(--color-text-secondary)">–</div></div>"""
            zk2 = get_zone(val, thr)[0]
            c2  = CARD_BORDER.get(zk2, "#94a3b8")
            return f"""<div style="flex:1;text-align:center;background:var(--color-background-tertiary);border-radius:6px;padding:5px 4px">
                <div style="font-size:9px;color:var(--color-text-secondary);margin-bottom:2px">{label}</div>
                <div style="font-size:13px;font-weight:500;color:{c2}">{val:.3f}</div></div>"""

        col.markdown(f"""
<div style="border-left:4px solid {border};border-radius:0 10px 10px 0;
border-top:0.5px solid var(--color-border-tertiary);
border-right:0.5px solid var(--color-border-tertiary);
border-bottom:0.5px solid var(--color-border-tertiary);
padding:12px 14px;margin-bottom:4px;
background:var(--color-background-secondary)">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:2px">{r['eq']}</div>
  <div style="font-size:11px;color:var(--color-text-secondary);margin-bottom:10px">{r['unit']}</div>
  <div style="display:flex;gap:6px;margin-bottom:10px">
    {dir_block("H", r['H'], r['thr'])}
    {dir_block("V", r['V'], r['thr'])}
    {dir_block("A", r['A'], r['thr'])}
  </div>
  <div style="font-size:12px;font-weight:500;color:{ztcolor}">{r['zi']} {r['zl']}</div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Detail per Equipment — Tabel B Style ─────────────────────────────────────
st.markdown("### 🔍 Detail per Equipment")

sel_det = st.selectbox("Pilih Equipment", sorted(latest["equipment"].unique()), key="home_det")
thr_det = get_threshold(sel_det)
df_det  = latest[latest["equipment"] == sel_det].copy()
df_det  = df_det.sort_values(["titik","direction"])

# Buat tabel dengan warna baris berdasarkan zone
df_det["zone_key"], df_det["zone_icon"], df_det["zone_label"] = zip(
    *df_det["value"].apply(lambda v: get_zone(v, thr_det))
)
df_det["value_fmt"] = df_det["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
df_det["date_fmt"]  = pd.to_datetime(df_det["date"]).dt.strftime("%d-%b-%Y")
df_det["Status"]    = df_det["zone_icon"] + " " + df_det["zone_label"]

# Pivot per titik — H, V, A sebagai kolom
pivot_det = df_det.pivot_table(
    index=["titik"], columns="direction", values="value", aggfunc="last"
).reset_index()
pivot_det.columns.name = None

dir_cols_d = [c for c in ["H","V","A"] if c in pivot_det.columns]
pivot_det["Max (mm/s)"] = pivot_det[dir_cols_d].max(axis=1)
pivot_det["zone_key"]   = pivot_det["Max (mm/s)"].apply(lambda v: get_zone(v, thr_det)[0])
pivot_det["Status"]     = pivot_det["Max (mm/s)"].apply(
    lambda v: get_zone(v, thr_det)[1] + " " + get_zone(v, thr_det)[2])

# Format nilai
for c in dir_cols_d:
    pivot_det[c] = pivot_det[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
pivot_det["Max (mm/s)"] = pivot_det["Max (mm/s)"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
pivot_det = pivot_det.rename(columns={"titik":"Titik Ukur"})

# Tampilkan tabel dengan highlight berdasarkan zone
def highlight_row(row):
    zk = row.get("zone_key","N/A")
    colors = {
        "ZONE A": "background-color:rgba(59,130,246,0.08);color:inherit",
        "ZONE B": "background-color:rgba(34,197,94,0.08);color:inherit",
        "ZONE C": "background-color:rgba(234,179,8,0.12);color:inherit",
        "ZONE D": "background-color:rgba(239,68,68,0.12);color:inherit",
    }
    style = colors.get(zk,"")
    return [style] * len(row)

show_cols = ["Titik Ukur"] + dir_cols_d + ["Max (mm/s)","Status"]
styled = (
    pivot_det[show_cols + ["zone_key"]]
    .style
    .apply(highlight_row, axis=1)
    .hide(axis="index")
)
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ── Trend Vibrasi ─────────────────────────────────────────────────────────────
st.markdown("### 📈 Trend Vibrasi")

mode_trend = st.radio(
    "Mode", ["Satu Equipment", "Bandingkan 2 Equipment"],
    horizontal=True, key="trend_mode"
)

colors_dir = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
ls_list    = ["solid","dash","dot","dashdot"]

if mode_trend == "Satu Equipment":
    tc1, tc2, tc3, tc4 = st.columns([2,2,1,1])
    with tc1:
        sel_eq_tr = st.selectbox("Equipment", sorted(df_f["equipment"].unique()), key="tr_eq1")
    with tc2:
        titik_opts = ["Semua Titik"] + sorted(df_f[df_f["equipment"]==sel_eq_tr]["titik"].unique())
        sel_titik_tr = st.selectbox("Titik Ukur", titik_opts, key="tr_titik1")
    with tc3:
        sel_dir_tr = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="tr_dir1")
    with tc4:
        trend_range = st.selectbox("Rentang", ["7 Hari","30 Hari","90 Hari","180 Hari","All"], index=1, key="tr_range1")

    df_tr = df_f[df_f["equipment"]==sel_eq_tr].copy()
    if trend_range != "All" and not df_tr.empty:
        days_map = {"7 Hari":7,"30 Hari":30,"90 Hari":90,"180 Hari":180}
        end_date   = df_tr["date"].max()
        start_date = end_date - timedelta(days=days_map[trend_range])
        df_tr = df_tr[(df_tr["date"] >= start_date) & (df_tr["date"] <= end_date)]
    if sel_titik_tr != "Semua Titik":
        df_tr = df_tr[df_tr["titik"]==sel_titik_tr]
    if sel_dir_tr:
        df_tr = df_tr[df_tr["direction"].isin(sel_dir_tr)]
    df_tr = df_tr.sort_values("date")

    thr_tr = get_threshold(sel_eq_tr)
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

else:
    # Mode bandingkan 2 equipment
    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("**Equipment 1**")
        eq1 = st.selectbox("Equipment 1", sorted(df_f["equipment"].unique()), key="cmp_eq1")
        titik1_opts = ["Semua Titik"] + sorted(df_f[df_f["equipment"]==eq1]["titik"].unique())
        titik1 = st.selectbox("Titik Ukur 1", titik1_opts, key="cmp_titik1")
        dir1   = st.multiselect("Direction 1", ["H","V","A"], default=["H"], key="cmp_dir1")
    with bc2:
        st.markdown("**Equipment 2**")
        eq2 = st.selectbox("Equipment 2", sorted(df_f["equipment"].unique()), index=min(1,len(sorted(df_f["equipment"].unique()))-1), key="cmp_eq2")
        titik2_opts = ["Semua Titik"] + sorted(df_f[df_f["equipment"]==eq2]["titik"].unique())
        titik2 = st.selectbox("Titik Ukur 2", titik2_opts, key="cmp_titik2")
        dir2   = st.multiselect("Direction 2", ["H","V","A"], default=["H"], key="cmp_dir2")

    cmp_range = st.selectbox("Rentang Waktu", ["7 Hari","30 Hari","90 Hari","180 Hari","All"], index=1, key="cmp_range")

    fig_cmp = go.Figure()
    colors_eq = ["#3b82f6","#ef4444","#10b981","#f59e0b"]

    for eq_idx, (eq, titik, dirs) in enumerate([(eq1,titik1,dir1),(eq2,titik2,dir2)]):
        df_eq = df_f[df_f["equipment"]==eq].copy()
        if cmp_range != "All" and not df_eq.empty:
            days_map = {"7 Hari":7,"30 Hari":30,"90 Hari":90,"180 Hari":180}
            end_d   = df_eq["date"].max()
            start_d = end_d - timedelta(days=days_map[cmp_range])
            df_eq   = df_eq[(df_eq["date"] >= start_d) & (df_eq["date"] <= end_d)]
        if titik != "Semua Titik":
            df_eq = df_eq[df_eq["titik"]==titik]
        if dirs:
            df_eq = df_eq[df_eq["direction"].isin(dirs)]
        df_eq = df_eq.sort_values("date")

        color_base = colors_eq[eq_idx*2]
        color_alt  = colors_eq[eq_idx*2+1]
        ls         = "solid" if eq_idx == 0 else "dash"

        for i, titik_val in enumerate(sorted(df_eq["titik"].unique())):
            for d in dirs:
                sub = df_eq[(df_eq["titik"]==titik_val)&(df_eq["direction"]==d)]
                if sub.empty: continue
                fig_cmp.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers",
                    name=f"[{eq_idx+1}] {eq} – {titik_val} ({d})",
                    line=dict(color=color_base if i%2==0 else color_alt, width=2, dash=ls),
                    marker=dict(size=6),
                    hovertemplate=f"<b>{eq} – {titik_val} ({d})</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
                ))

    thr_ref = get_threshold(eq1)
    fig_cmp.add_hline(y=thr_ref["A"], line_dash="dot",  line_color="#3b82f6", line_width=1,
                      annotation_text=f"Accepted ({thr_ref['A']})", annotation_position="top left")
    fig_cmp.add_hline(y=thr_ref["B"], line_dash="dot",  line_color="#22c55e", line_width=1,
                      annotation_text=f"Pre Warning ({thr_ref['B']})", annotation_position="top left")
    fig_cmp.add_hline(y=thr_ref["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
                      annotation_text=f"Warning ({thr_ref['C']})", annotation_position="top left")
    fig_cmp.update_layout(
        title=f"Perbandingan: {eq1} vs {eq2}",
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
        height=460, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_cmp, use_container_width=True)
