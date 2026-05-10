import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import (
    load_history,
    get_zone,
    get_threshold,
    render_login_sidebar
)

st.set_page_config(
    page_title="Trend Vibrasi — PLTU TBK",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="stSidebarNav"] {display: none;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")

    st.divider()

    st.markdown("### Navigasi")

    st.page_link("app.py", label="📊 Ringkasan Status")
    st.page_link("pages/1_Trend.py", label="📈 Trend Vibrasi")
    st.page_link("pages/2_Alarm.py", label="🚨 Alarm & Warning")
    st.page_link("pages/3_Histori.py", label="🗄️ Histori Data")
    st.page_link("pages/4_Pengaturan.py", label="⚙️ Pengaturan")
    st.page_link("pages/5_Prediksi.py", label="🔮 Prediksi Trend")

    render_login_sidebar()

# ── Load Data ────────────────────────────────────────────────────────────────
st.markdown("## 📈 Trend Vibrasi")

df_hist = load_history()

if df_hist.empty:
    st.info("📂 Belum ada data.")
    st.stop()

df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")

min_date = df_hist["date"].min().date()
max_date = df_hist["date"].max().date()

sel_date = st.date_input(
    "Filter Tanggal",
    value=(min_date, max_date),
    key="trend_date"
)

mode = st.radio(
    "Mode tampilan",
    ["Detail satu equipment", "Ringkasan semua equipment"],
    horizontal=True
)

colors_dir = {
    "H": "#3b82f6",
    "V": "#10b981",
    "A": "#f59e0b"
}

ls_list = ["solid", "dash", "dot", "dashdot"]

# ── DETAIL EQUIPMENT ─────────────────────────────────────────────────────────
if mode == "Detail satu equipment":

    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:

        sel_eq = st.selectbox(
            "Equipment",
            sorted(df_hist["equipment"].dropna().unique())
        )

    with c2:

        titik_opts = sorted(
            df_hist[df_hist["equipment"] == sel_eq]["titik"].dropna().unique()
        )

        sel_titik = st.selectbox(
            "Titik Ukur",
            titik_opts
        )

    with c3:

        sel_dir = st.multiselect(
            "Direction",
            ["H", "V", "A"],
            default=["H", "V", "A"]
        )

    df_tr = df_hist[
        (df_hist["equipment"] == sel_eq) &
        (df_hist["titik"] == sel_titik) &
        (df_hist["direction"].isin(sel_dir))
    ].copy()

    # Filter tanggal
    if len(sel_date) == 2:

        start_date, end_date = sel_date

        df_tr = df_tr[
            (df_tr["date"] >= pd.to_datetime(start_date)) &
            (df_tr["date"] <= pd.to_datetime(end_date))
        ]

    df_tr = df_tr.sort_values("date")

    thr = get_threshold(sel_eq)

    # ── Table ────────────────────────────────────────────────────────────────
    st.markdown(f"### {sel_eq} · {sel_titik}")

    df_tbl = df_tr[["date", "direction", "value"]].copy()

    df_tbl["Zone"] = df_tbl["value"].apply(
        lambda v: get_zone(v, thr)[1] + " " + get_zone(v, thr)[0]
    )

    df_tbl["value"] = df_tbl["value"].map(
        lambda v: f"{v:.3f}" if pd.notna(v) else "-"
    )

    df_tbl = df_tbl.rename(columns={
        "date": "Tanggal",
        "direction": "Dir",
        "value": "mm/s"
    })

    df_tbl["Tanggal"] = pd.to_datetime(
        df_tbl["Tanggal"]
    ).dt.strftime("%Y-%m-%d")

    st.dataframe(
        df_tbl,
        use_container_width=True,
        hide_index=True
    )

    # ── Grafik ───────────────────────────────────────────────────────────────
    fig = go.Figure()

    for d in sel_dir:

        sub = df_tr[df_tr["direction"] == d]

        if sub.empty:
            continue

        fig.add_trace(go.Scatter(
            x=sub["date"],
            y=sub["value"],
            mode="lines+markers",
            name=f"Direction {d}",
            line=dict(
                color=colors_dir.get(d, "#888"),
                width=2
            ),
            marker=dict(size=7)
        ))

    fig.add_hline(
        y=thr["A"],
        line_dash="dot",
        line_color="#22c55e",
        annotation_text=f"Zone A ({thr['A']})"
    )

    fig.add_hline(
        y=thr["B"],
        line_dash="dot",
        line_color="#eab308",
        annotation_text=f"Zone B ({thr['B']})"
    )

    fig.add_hline(
        y=thr["C"],
        line_dash="dash",
        line_color="#ef4444",
        annotation_text=f"Zone C ({thr['C']})"
    )

    fig.update_layout(
        title=f"{sel_eq} — {sel_titik}",
        xaxis_title="Tanggal",
        yaxis_title="Vibrasi (mm/s)",
        height=450,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02
        )
    )

    st.plotly_chart(fig, use_container_width=True)

# ── RINGKASAN ────────────────────────────────────────────────────────────────
else:

    all_eq = sorted(df_hist["equipment"].dropna().unique())

    cols_per_row = 2

    rows = [
        all_eq[i:i + cols_per_row]
        for i in range(0, len(all_eq), cols_per_row)
    ]

    for row_equips in rows:

        cols = st.columns(cols_per_row)

        for col, eq in zip(cols, row_equips):

            with col:

                thr = get_threshold(eq)

                df_eq = df_hist[
                    df_hist["equipment"] == eq
                ].sort_values("date")

                latest_eq = df_eq.groupby(
                    ["titik", "direction"],
                    as_index=False
                ).last()[["titik", "direction", "value"]]

                latest_eq["Zone"] = latest_eq["value"].apply(
                    lambda v: get_zone(v, thr)[1] + " " + get_zone(v, thr)[0]
                )

                latest_eq["value"] = latest_eq["value"].map(
                    lambda v: f"{v:.3f}" if pd.notna(v) else "-"
                )

                latest_eq = latest_eq.rename(columns={
                    "titik": "Titik",
                    "direction": "Dir",
                    "value": "mm/s"
                })

                st.markdown(f"### {eq}")

                st.dataframe(
                    latest_eq,
                    use_container_width=True,
                    hide_index=True,
                    height=180
                )

                fig_eq = go.Figure()

                for i, titik in enumerate(sorted(df_eq["titik"].unique())):

                    for d in ["H", "V", "A"]:

                        sub = df_eq[
                            (df_eq["titik"] == titik) &
                            (df_eq["direction"] == d)
                        ]

                        if sub.empty:
                            continue

                        fig_eq.add_trace(go.Scatter(
                            x=sub["date"],
                            y=sub["value"],
                            mode="lines+markers",
                            name=f"{titik} {d}",
                            line=dict(
                                color=colors_dir.get(d, "#888"),
                                width=1.5,
                                dash=ls_list[i % 4]
                            ),
                            marker=dict(size=5)
                        ))

                fig_eq.add_hline(
                    y=thr["A"],
                    line_dash="dot",
                    line_color="#22c55e"
                )

                fig_eq.add_hline(
                    y=thr["B"],
                    line_dash="dot",
                    line_color="#eab308"
                )

                fig_eq.add_hline(
                    y=thr["C"],
                    line_dash="dash",
                    line_color="#ef4444"
                )

                fig_eq.update_layout(
                    height=300,
                    margin=dict(t=20, b=20, l=30, r=10),
                    yaxis_title="mm/s",
                    showlegend=True,
                    legend=dict(
                        font=dict(size=9),
                        orientation="h"
                    )
                )

                st.plotly_chart(
                    fig_eq,
                    use_container_width=True,
                    key=f"fig_{eq}"
                )
