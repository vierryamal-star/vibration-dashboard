import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta

from utils import (
    save_to_db,
    load_history,
    parse_excel,
    get_zone,
    get_threshold,
    THRESHOLD,
    add_zone_cols,
    render_login_sidebar,
    check_role
)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Monitoring Vibrasi — PLTU TBK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"] {
    display:none;
}

section[data-testid="stSidebar"] > div:first-child {
    padding-top:1rem;
}

[data-testid="stSidebar"] hr {
    margin:0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
df_hist = load_history()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:

    try:
        st.image("assets/logo_pln_ip.png", width=220)
    except:
        pass

    st.markdown("## ⚡ PLTU TBK")
    st.caption("Dashboard Monitoring Vibrasi · ISO 10816")

    st.divider()

    # Upload
    st.markdown("### 📂 Upload Data")

    uploaded = st.file_uploader(
        "File Excel (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Sheet: Vibration_Data"
    )

    st.divider()

    # Navigation
    st.markdown("### Navigasi")

    st.page_link("app.py", label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py", label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py", label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py", label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py", label="⚙️ Pengaturan")
    st.page_link("pages/5_Prediksi.py", label="🔮 Prediksi Trend")

    render_login_sidebar()

# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD PROCESS
# ─────────────────────────────────────────────────────────────────────────────
if uploaded:

    if check_role() != "editor":

        st.warning("🔒 Upload hanya untuk Editor.")

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
                    f"✅ {file.name}: "
                    f"{saved} baris disimpan · "
                    f"{skipped} duplikat"
                )

        if total_saved > 0:

            st.success(
                f"🎉 Total {total_saved} baris berhasil disimpan."
            )

            st.cache_data.clear()
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# EMPTY CHECK
# ─────────────────────────────────────────────────────────────────────────────
if df_hist.empty:

    st.info("📂 Belum ada data.")

    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# CLEAN DATA
# ─────────────────────────────────────────────────────────────────────────────
df_hist["date"] = pd.to_datetime(
    df_hist["date"],
    errors="coerce"
)

df_hist["value"] = pd.to_numeric(
    df_hist["value"],
    errors="coerce"
)

all_units = sorted(
    df_hist["unit"].dropna().unique()
)

all_equip = sorted(
    df_hist["equipment"].dropna().unique()
)

# ─────────────────────────────────────────────────────────────────────────────
# FILTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## 📊 Ringkasan Status")

fc1, fc2, fc3 = st.columns(3)

with fc1:

    sel_unit = st.multiselect(
        "Unit",
        all_units,
        default=all_units
    )

with fc2:

    sel_equip = st.multiselect(
        "Equipment",
        all_equip,
        default=all_equip
    )

with fc3:

    sel_dir = st.multiselect(
        "Direction",
        ["H", "V", "A"],
        default=["H", "V", "A"]
    )

df_f = df_hist[
    df_hist["unit"].isin(sel_unit)
    &
    df_hist["equipment"].isin(sel_equip)
    &
    df_hist["direction"].isin(sel_dir)
].copy()

if df_f.empty:

    st.warning("Tidak ada data.")

    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# ZONE
# ─────────────────────────────────────────────────────────────────────────────
df_f = add_zone_cols(df_f)

latest = df_f.sort_values("date").groupby(
    ["unit", "equipment", "titik", "direction"],
    as_index=False
).last()

# ─────────────────────────────────────────────────────────────────────────────
# TBK FILTER
# ─────────────────────────────────────────────────────────────────────────────
shared_filter = st.radio(
    "Filter Area",
    ["All Equipment", "TBK #1", "TBK #2", "TBK COM"],
    horizontal=True
)

if shared_filter == "TBK #1":

    latest_filtered = latest[
        latest["unit"].str.contains(
            "TBK #1|TBK1|UNIT 1",
            case=False,
            na=False
        )
    ]

elif shared_filter == "TBK #2":

    latest_filtered = latest[
        latest["unit"].str.contains(
            "TBK #2|TBK2|UNIT 2",
            case=False,
            na=False
        )
    ]

elif shared_filter == "TBK COM":

    latest_filtered = latest[
        latest["unit"].str.contains(
            "COM|COMMON",
            case=False,
            na=False
        )
    ]

else:

    latest_filtered = latest.copy()

# ─────────────────────────────────────────────────────────────────────────────
# KPI
# ─────────────────────────────────────────────────────────────────────────────
total = len(latest_filtered)

n_a = (latest_filtered["zone"] == "ZONE A").sum()
n_b = (latest_filtered["zone"] == "ZONE B").sum()
n_c = (latest_filtered["zone"] == "ZONE C").sum()
n_d = (latest_filtered["zone"] == "ZONE D").sum()

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Titik", total)
k2.metric("🔴 Danger", int(n_d))
k3.metric("🟡 Warning", int(n_c))
k4.metric("🟢 Pre Warning", int(n_b))
k5.metric("🔵 Accepted", int(n_a))

# ─────────────────────────────────────────────────────────────────────────────
# PERCENT BAR
# ─────────────────────────────────────────────────────────────────────────────
pct_a = round((n_a / total) * 100) if total else 0
pct_b = round((n_b / total) * 100) if total else 0
pct_c = round((n_c / total) * 100) if total else 0
pct_d = round((n_d / total) * 100) if total else 0

st.markdown(f"""
<div style="margin:4px 0 16px">

    <div style="
        height:12px;
        border-radius:6px;
        overflow:hidden;
        display:flex;
        background:var(--secondary-background-color);
    ">

        <div style="width:{pct_a}%;background:#3b82f6"></div>
        <div style="width:{pct_b}%;background:#22c55e"></div>
        <div style="width:{pct_c}%;background:#eab308"></div>
        <div style="width:{pct_d}%;background:#ef4444"></div>

    </div>

</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# STATUS EQUIPMENT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### Status Terakhir per Equipment")

def fmt(v):

    if pd.isna(v):
        return "-"

    return f"{v:.2f}"

eq_rows = []

for eq in sorted(latest_filtered["equipment"].unique()):

    df_eq = latest_filtered[
        latest_filtered["equipment"] == eq
    ]

    if df_eq.empty:
        continue

    thr = get_threshold(eq)

    max_val = df_eq["value"].max()

    zk, zi, zl = get_zone(max_val, thr)

    unit = df_eq["unit"].iloc[0]

    h_val = df_eq[
        df_eq["direction"] == "H"
    ]["value"].max()

    v_val = df_eq[
        df_eq["direction"] == "V"
    ]["value"].max()

    a_val = df_eq[
        df_eq["direction"] == "A"
    ]["value"].max()

    eq_rows.append({
        "equipment": eq,
        "unit": unit,
        "zone": zk,
        "icon": zi,
        "label": zl,
        "max": max_val,
        "h": h_val,
        "v": v_val,
        "a": a_val
    })

cols_per_row = 2

for i in range(0, len(eq_rows), cols_per_row):

    chunk = eq_rows[i:i + cols_per_row]

    cols = st.columns(cols_per_row)

    for col, r in zip(cols, chunk):

        color = "#3b82f6"

        if r["zone"] == "ZONE B":
            color = "#22c55e"

        elif r["zone"] == "ZONE C":
            color = "#eab308"

        elif r["zone"] == "ZONE D":
            color = "#ef4444"

        card_html = f"""
<div style="
    border-left:6px solid {color};
    padding:16px;
    border-radius:12px;
    background:rgba(255,255,255,0.03);
    margin-bottom:12px;
">

    <div style="
        font-size:22px;
        font-weight:700;
        color:var(--text-color);
    ">
        {r['icon']} {r['equipment']}
    </div>

    <div style="
        font-size:13px;
        color:gray;
        margin-bottom:14px;
    ">
        {r['unit']}
    </div>

    <div style="
        font-size:34px;
        font-weight:800;
        color:{color};
    ">
        {fmt(r['max'])} mm/s
    </div>

    <div style="
        margin-top:6px;
        margin-bottom:14px;
        color:{color};
        font-weight:700;
    ">
        {r['label']}
    </div>

    <div style="
        display:flex;
        gap:10px;
    ">

        <div style="flex:1;text-align:center">
            <div style="font-size:11px;color:gray">H</div>
            <div style="font-size:18px;font-weight:700">
                {fmt(r['h'])}
            </div>
        </div>

        <div style="flex:1;text-align:center">
            <div style="font-size:11px;color:gray">V</div>
            <div style="font-size:18px;font-weight:700">
                {fmt(r['v'])}
            </div>
        </div>

        <div style="flex:1;text-align:center">
            <div style="font-size:11px;color:gray">A</div>
            <div style="font-size:18px;font-weight:700">
                {fmt(r['a'])}
            </div>
        </div>

    </div>

</div>
"""

        col.markdown(
            card_html,
            unsafe_allow_html=True
        )

# ─────────────────────────────────────────────────────────────────────────────
# DETAIL EQUIPMENT
# ─────────────────────────────────────────────────────────────────────────────
st.divider()

st.markdown("### 🔍 Detail per Equipment")

sel_det = st.selectbox(
    "Pilih Equipment",
    sorted(latest_filtered["equipment"].unique())
)

thr_det = get_threshold(sel_det)

df_det = latest_filtered[
    latest_filtered["equipment"] == sel_det
][
    ["unit", "titik", "direction", "value", "date"]
].copy()

df_det["Status"] = df_det["value"].apply(
    lambda v: (
        get_zone(v, thr_det)[1]
        +
        " "
        +
        get_zone(v, thr_det)[2]
    )
)

df_det["value"] = df_det["value"].map(
    lambda v: f"{v:.3f}"
)

df_det["date"] = pd.to_datetime(
    df_det["date"]
).dt.strftime("%Y-%m-%d")

df_det = df_det.rename(columns={
    "unit": "Unit",
    "titik": "Titik",
    "direction": "Dir",
    "value": "mm/s",
    "date": "Tanggal"
})

st.dataframe(
    df_det,
    use_container_width=True,
    hide_index=True
)

# ─────────────────────────────────────────────────────────────────────────────
# TREND
# ─────────────────────────────────────────────────────────────────────────────
st.divider()

st.markdown("### 📈 Trend Vibrasi")

tc1, tc2, tc3, tc4 = st.columns([2,2,1,1])

with tc1:

    sel_eq_tr = st.selectbox(
        "Equipment",
        sorted(df_f["equipment"].unique())
    )

with tc2:

    titik_opts = ["Semua Titik"] + sorted(
        df_f[
            df_f["equipment"] == sel_eq_tr
        ]["titik"].unique()
    )

    sel_titik_tr = st.selectbox(
        "Titik Ukur",
        titik_opts
    )

with tc3:

    sel_dir_tr = st.multiselect(
        "Direction",
        ["H", "V", "A"],
        default=["H", "V", "A"]
    )

with tc4:

    trend_range = st.selectbox(
        "Rentang",
        ["7 Hari", "30 Hari", "90 Hari", "180 Hari", "All"],
        index=1
    )

df_tr = df_f[
    df_f["equipment"] == sel_eq_tr
].copy()

if trend_range != "All":

    days_map = {
        "7 Hari": 7,
        "30 Hari": 30,
        "90 Hari": 90,
        "180 Hari": 180
    }

    end_date = df_tr["date"].max()

    start_date = end_date - timedelta(
        days=days_map[trend_range]
    )

    df_tr = df_tr[
        (df_tr["date"] >= start_date)
        &
        (df_tr["date"] <= end_date)
    ]

if sel_titik_tr != "Semua Titik":

    df_tr = df_tr[
        df_tr["titik"] == sel_titik_tr
    ]

if sel_dir_tr:

    df_tr = df_tr[
        df_tr["direction"].isin(sel_dir_tr)
    ]

df_tr = df_tr.sort_values("date")

thr_tr = get_threshold(sel_eq_tr)

if not df_tr.empty:

    fig = go.Figure()

    colors_dir = {
        "H": "#3b82f6",
        "V": "#22c55e",
        "A": "#f59e0b"
    }

    for d in sel_dir_tr:

        sub = df_tr[
            df_tr["direction"] == d
        ]

        if sub.empty:
            continue

        fig.add_trace(go.Scatter(
            x=sub["date"],
            y=sub["value"],
            mode="lines+markers",
            name=d,
            line=dict(
                color=colors_dir[d],
                width=2
            )
        ))

    fig.add_hline(
        y=thr_tr["A"],
        line_dash="dot",
        line_color="#3b82f6"
    )

    fig.add_hline(
        y=thr_tr["B"],
        line_dash="dot",
        line_color="#22c55e"
    )

    fig.add_hline(
        y=thr_tr["C"],
        line_dash="dash",
        line_color="#ef4444"
    )

    fig.update_layout(
        height=420,
        hovermode="x unified",
        xaxis_title="Tanggal",
        yaxis_title="Vibrasi (mm/s)"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

else:

    st.info("Tidak ada data trend.")
