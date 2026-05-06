import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sqlite3
import os
from datetime import datetime, date

# ─── Konfigurasi halaman ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Monitoring Vibrasi – PLTU TBK",
    page_icon="⚡",
    layout="wide",
)

DB_PATH = "vibration_history.db"

# ─── Threshold ISO 10816 (dari sheet Threshold) ───────────────────────────────
# Zone A: baru dipasang / sangat baik
# Zone B: normal operasi
# Zone C: perlu pemantauan
# Zone D: berbahaya
THRESHOLD = {
    "Turbine": {"A": 3.8, "B": 7.5, "C": 11.8},
    "Pump/Fan": {"A": 1.4, "B": 2.8, "C": 4.5},
}

def get_threshold(equipment: str):
    """Tentukan threshold berdasarkan jenis equipment."""
    name = equipment.upper()
    if "TURBINE" in name:
        return THRESHOLD["Turbine"]
    return THRESHOLD["Pump/Fan"]

def get_zone(value, thr):
    if pd.isna(value):
        return "N/A", "⬜"
    if value <= thr["A"]:
        return "ZONE A", "🟢"
    elif value <= thr["B"]:
        return "ZONE B", "🟡"
    elif value <= thr["C"]:
        return "ZONE C", "🟠"
    else:
        return "ZONE D", "🔴"

# ─── Database ─────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS vibration (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment TEXT,
            unit      TEXT,
            titik     TEXT,
            direction TEXT,
            date      TEXT,
            value     REAL,
            uploaded_at TEXT
        )
    """)
    con.commit()
    con.close()

def save_to_db(df: pd.DataFrame):
    """Simpan data baru ke DB, skip baris duplikat."""
    con = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    rows = df.copy()
    rows["uploaded_at"] = now
    try:
        existing = pd.read_sql(
            "SELECT equipment, unit, titik, direction, date FROM vibration", con
        )
        existing["_key"] = (
            existing["equipment"].astype(str) + "|" +
            existing["unit"].astype(str) + "|" +
            existing["titik"].astype(str) + "|" +
            existing["direction"].astype(str) + "|" +
            pd.to_datetime(existing["date"], errors="coerce").dt.date.astype(str)
        )
        rows["_key"] = (
            rows["equipment"].astype(str) + "|" +
            rows["unit"].astype(str) + "|" +
            rows["titik"].astype(str) + "|" +
            rows["direction"].astype(str) + "|" +
            pd.to_datetime(rows["date"], errors="coerce").dt.date.astype(str)
        )
        rows_new = rows[~rows["_key"].isin(existing["_key"])].drop(columns=["_key"])
    except Exception:
        rows_new = rows.copy()
    saved = len(rows_new)
    if not rows_new.empty:
        rows_new.to_sql("vibration", con, if_exists="append", index=False)
    con.close()
    return saved

def load_history() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM vibration ORDER BY date DESC", con)
    except Exception:
        df = pd.DataFrame()
    con.close()
    return df

# ─── Parse Excel ──────────────────────────────────────────────────────────────
def parse_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file, sheet_name="Vibration_Data")
    # Normalise kolom
    df.columns = [c.strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "equipment" in cl:       col_map[c] = "equipment"
        elif "unit" in cl:          col_map[c] = "unit"
        elif "titik" in cl:         col_map[c] = "titik"
        elif "direction" in cl:     col_map[c] = "direction"
        elif "date" in cl:          col_map[c] = "date"
        elif "value" in cl:         col_map[c] = "value"
    df = df.rename(columns=col_map)
    required = {"equipment", "unit", "titik", "direction", "date", "value"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Kolom tidak ditemukan di file: {missing}")
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[list(required)].dropna(subset=["equipment", "unit", "titik", "direction"])

# ─── Warna zone ───────────────────────────────────────────────────────────────
ZONE_COLOR = {
    "ZONE A": "#22c55e",
    "ZONE B": "#eab308",
    "ZONE C": "#f97316",
    "ZONE D": "#ef4444",
    "N/A":    "#94a3b8",
}

# ═══════════════════════════════════════════════════════════════════════════════
init_db()

st.title("⚡ Dashboard Monitoring Vibrasi — PLTU TBK")
st.caption("ISO 10816 · Vibrasi dalam mm/s RMS")

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Upload Data")
    uploaded = st.file_uploader(
        "Pilih file Excel (.xlsx)",
        type=["xlsx"],
        help="Format: Equipment, Unit, Titik Ukur, Direction, Date, Value (mm/s)"
    )

    st.divider()
    st.subheader("Threshold Kustom (mm/s)")
    t_turbine_a = st.number_input("Turbine – Zone A", value=3.8, step=0.1)
    t_turbine_b = st.number_input("Turbine – Zone B", value=7.5, step=0.1)
    t_turbine_c = st.number_input("Turbine – Zone C", value=11.8, step=0.1)
    t_pump_a    = st.number_input("Pump/Fan – Zone A", value=1.4, step=0.1)
    t_pump_b    = st.number_input("Pump/Fan – Zone B", value=2.8, step=0.1)
    t_pump_c    = st.number_input("Pump/Fan – Zone C", value=4.5, step=0.1)

    THRESHOLD["Turbine"]  = {"A": t_turbine_a, "B": t_turbine_b, "C": t_turbine_c}
    THRESHOLD["Pump/Fan"] = {"A": t_pump_a,    "B": t_pump_b,    "C": t_pump_c}

    st.divider()
    st.caption("Zone ISO 10816")
    st.markdown("""
🟢 **Zone A** – sangat baik  
🟡 **Zone B** – normal  
🟠 **Zone C** – perlu perhatian  
🔴 **Zone D** – bahaya
    """)

# ─── Load data ────────────────────────────────────────────────────────────────
df_new = pd.DataFrame()
if uploaded:
    df_new = parse_excel(uploaded)
    if not df_new.empty:
        saved_count = save_to_db(df_new)
        skipped = len(df_new) - saved_count
        if saved_count > 0 and skipped > 0:
            st.success(f"✅ {saved_count} baris baru disimpan. {skipped} baris duplikat dilewati.")
        elif saved_count > 0:
            st.success(f"✅ {saved_count} baris baru berhasil disimpan.")
        else:
            st.info(f"ℹ️ Semua {len(df_new)} baris sudah ada di histori — tidak ada data baru.")

df_hist = load_history()

# Selalu gunakan SEMUA histori sebagai data kerja (bukan hanya upload terbaru)
if not df_hist.empty:
    df_work = df_hist.copy()
    df_work["date"] = pd.to_datetime(df_work["date"], errors="coerce")
    df_work["value"] = pd.to_numeric(df_work["value"], errors="coerce")
elif not df_new.empty:
    df_work = df_new.copy()
else:
    st.info("📂 Silakan upload file Excel untuk memulai.")
    st.stop()

# ─── Filter ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
all_units = sorted(df_work["unit"].dropna().unique().tolist())
all_equip = sorted(df_work["equipment"].dropna().unique().tolist())

with col_f1:
    sel_unit = st.multiselect("Unit", all_units, default=all_units)
with col_f2:
    sel_equip = st.multiselect("Equipment", all_equip, default=all_equip)
with col_f3:
    sel_dir = st.multiselect("Direction", ["H", "V", "A"], default=["H", "V", "A"])

df_filtered = df_work[
    df_work["unit"].isin(sel_unit) &
    df_work["equipment"].isin(sel_equip) &
    df_work["direction"].isin(sel_dir)
].copy()

if df_filtered.empty:
    st.warning("Tidak ada data sesuai filter.")
    st.stop()

# Tambah kolom zone
df_filtered["thr_type"] = df_filtered["equipment"].apply(
    lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan"
)
df_filtered["zone"] = df_filtered.apply(
    lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0], axis=1
)
df_filtered["zone_icon"] = df_filtered.apply(
    lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1], axis=1
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB
# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Ringkasan Status",
    "📈 Trend Vibrasi",
    "🚨 Alarm & Warning",
    "🗄️ Histori Data",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 · Ringkasan Status
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    # KPI
    total   = len(df_filtered)
    zone_d  = (df_filtered["zone"] == "ZONE D").sum()
    zone_c  = (df_filtered["zone"] == "ZONE C").sum()
    zone_ab = ((df_filtered["zone"] == "ZONE A") | (df_filtered["zone"] == "ZONE B")).sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Titik Ukur", total)
    k2.metric("🔴 Zone D (Bahaya)", zone_d)
    k3.metric("🟠 Zone C (Perhatian)", zone_c)
    k4.metric("🟢 Zone A–B (Normal)", zone_ab)

    st.divider()

    # Tabel status per equipment × titik × direction (nilai terbaru)
    latest = (
        df_filtered.sort_values("date")
        .groupby(["unit", "equipment", "titik", "direction"], as_index=False)
        .last()
    )

    st.subheader("Status Terakhir per Titik Ukur")

    # Pivot: direction jadi kolom
    pivot = latest.pivot_table(
        index=["unit", "equipment", "titik"],
        columns="direction",
        values="value",
        aggfunc="last",
    ).reset_index()
    pivot.columns.name = None

    # Tambah kolom zone max
    dir_cols = [c for c in ["H", "V", "A"] if c in pivot.columns]
    pivot["Max (mm/s)"] = pivot[dir_cols].max(axis=1)
    pivot["Thr. Type"] = pivot["equipment"].apply(
        lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan"
    )
    def _zone_label(r):
        thr = THRESHOLD[r["Thr. Type"]]
        icon = get_zone(r["Max (mm/s)"], thr)[1]
        label = get_zone(r["Max (mm/s)"], thr)[0]
        return f"{icon} {label}"

    pivot["Zone"] = pivot.apply(_zone_label, axis=1).astype(str)
    pivot = pivot.drop(columns=["Thr. Type"])
    pivot = pivot.rename(columns={"unit": "Unit", "equipment": "Equipment", "titik": "Titik Ukur"})
    for c in dir_cols:
        pivot[c] = pivot[c].map(lambda v: f"{v:.2f}" if pd.notna(v) else "–")
    pivot["Max (mm/s)"] = pivot["Max (mm/s)"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "–")

    st.dataframe(pivot, use_container_width=True, hide_index=True)

    # ── Detail per Equipment ──────────────────────────────────────────────────
    st.divider()
    st.subheader("🔍 Detail per Equipment")

    equip_list = sorted(latest["equipment"].dropna().unique().tolist())
    sel_detail = st.selectbox("Pilih Equipment untuk detail", equip_list, key="detail_equip")

    df_detail = latest[latest["equipment"] == sel_detail].copy()
    thr_det = get_threshold(sel_detail)

    # Tabel detail titik ukur equipment terpilih
    df_det_show = df_detail[["unit", "titik", "direction", "value", "date"]].copy()
    df_det_show["Zone"] = df_det_show["value"].apply(
        lambda v: get_zone(v, thr_det)[1] + " " + get_zone(v, thr_det)[0]
    ).astype(str)
    df_det_show["value"] = df_det_show["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
    df_det_show = df_det_show.rename(columns={
        "unit": "Unit", "titik": "Titik Ukur", "direction": "Direction",
        "value": "mm/s", "date": "Tanggal"
    })
    st.dataframe(df_det_show, use_container_width=True, hide_index=True)

    # ── Trend Vibrasi semua equipment ────────────────────────────────────────
    st.divider()
    st.subheader("📈 Trend Vibrasi — Semua Equipment")

    col_tr1, col_tr2, col_tr3 = st.columns([2, 2, 1])
    with col_tr1:
        sel_equip_overview = st.selectbox(
            "Equipment", sorted(df_filtered["equipment"].unique()), key="overview_eq"
        )
    with col_tr2:
        titik_all_opts = ["Semua Titik"] + sorted(
            df_filtered[df_filtered["equipment"] == sel_equip_overview]["titik"].unique().tolist()
        )
        sel_titik_overview = st.selectbox("Titik Ukur", titik_all_opts, key="overview_titik")
    with col_tr3:
        sel_dir_overview = st.multiselect(
            "Direction", ["H", "V", "A"], default=["H", "V", "A"], key="overview_dir"
        )

    # Filter data untuk grafik overview
    df_ov = df_filtered[df_filtered["equipment"] == sel_equip_overview].copy()
    if sel_titik_overview != "Semua Titik":
        df_ov = df_ov[df_ov["titik"] == sel_titik_overview]
    if sel_dir_overview:
        df_ov = df_ov[df_ov["direction"].isin(sel_dir_overview)]
    df_ov = df_ov.sort_values("date")

    thr_ov = get_threshold(sel_equip_overview)
    colors_dir_ov = {"H": "#3b82f6", "V": "#10b981", "A": "#f59e0b"}
    line_styles = ["solid", "dash", "dot", "dashdot"]

    if df_ov.empty:
        st.info("Tidak ada data untuk pilihan ini.")
    else:
        fig_ov = go.Figure()
        titik_list = sorted(df_ov["titik"].unique())
        for i, titik in enumerate(titik_list):
            for d in sel_dir_overview:
                sub = df_ov[(df_ov["titik"] == titik) & (df_ov["direction"] == d)]
                if sub.empty:
                    continue
                fig_ov.add_trace(go.Scatter(
                    x=sub["date"],
                    y=sub["value"],
                    mode="lines+markers",
                    name=f"{titik} – {d}",
                    line=dict(
                        color=colors_dir_ov.get(d, "#888"),
                        width=2,
                        dash=line_styles[i % len(line_styles)],
                    ),
                    marker=dict(size=6),
                    hovertemplate=f"<b>{titik} ({d})</b><br>Tanggal: %{{x|%d-%b-%Y}}<br>Nilai: %{{y:.3f}} mm/s<extra></extra>",
                ))

        # Garis threshold
        fig_ov.add_hline(
            y=thr_ov["A"], line_dash="dot", line_color="#22c55e", line_width=1,
            annotation_text=f"Zone A ({thr_ov['A']})", annotation_position="top left",
            annotation_font_color="#22c55e",
        )
        fig_ov.add_hline(
            y=thr_ov["B"], line_dash="dot", line_color="#eab308", line_width=1,
            annotation_text=f"Zone B ({thr_ov['B']})", annotation_position="top left",
            annotation_font_color="#eab308",
        )
        fig_ov.add_hline(
            y=thr_ov["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
            annotation_text=f"Zone C ({thr_ov['C']})", annotation_position="top left",
            annotation_font_color="#ef4444",
        )

        titik_label = sel_titik_overview if sel_titik_overview != "Semua Titik" else "Semua Titik"
        dir_label = " + ".join(sel_dir_overview) if sel_dir_overview else "–"
        fig_ov.update_layout(
            title=f"{sel_equip_overview}  ·  {titik_label}  ·  Direction: {dir_label}",
            xaxis_title="Tanggal",
            yaxis_title="Vibrasi (mm/s)",
            height=460,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11)),
        )
        st.plotly_chart(fig_ov, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 · Trend Vibrasi
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("📈 Trend Vibrasi per Equipment")

    colors_dir = {"H": "#3b82f6", "V": "#10b981", "A": "#f59e0b"}

    # Mode: satu equipment detail, atau semua equipment ringkasan
    mode_trend = st.radio(
        "Mode tampilan",
        ["Detail satu equipment", "Ringkasan semua equipment"],
        horizontal=True,
        key="mode_trend",
    )

    if mode_trend == "Detail satu equipment":
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            sel_equip_trend = st.selectbox("Equipment", sorted(df_filtered["equipment"].unique()), key="eq_trend")
        with col_t2:
            titik_opts = sorted(df_filtered[df_filtered["equipment"] == sel_equip_trend]["titik"].unique())
            sel_titik_trend = st.selectbox("Titik Ukur", titik_opts, key="titik_trend")

        df_trend = df_filtered[
            (df_filtered["equipment"] == sel_equip_trend) &
            (df_filtered["titik"] == sel_titik_trend)
        ].copy().sort_values("date")

        if df_trend.empty:
            st.info("Tidak ada data untuk pilihan ini.")
        else:
            thr = get_threshold(sel_equip_trend)

            # Tabel nilai per tanggal
            st.markdown(f"**Tabel data — {sel_equip_trend} · {sel_titik_trend}**")
            df_tbl = df_trend[["date", "direction", "value"]].copy()
            df_tbl["Zone"] = df_tbl["value"].apply(
                lambda v: get_zone(v, thr)[1] + " " + get_zone(v, thr)[0]
            ).astype(str)
            df_tbl["value"] = df_tbl["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
            df_tbl = df_tbl.rename(columns={"date": "Tanggal", "direction": "Direction", "value": "mm/s"})
            st.dataframe(df_tbl, use_container_width=True, hide_index=True)

            st.markdown("---")

            # Grafik trend
            fig = go.Figure()
            for d in sorted(df_trend["direction"].unique()):
                sub = df_trend[df_trend["direction"] == d]
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers",
                    name=f"Direction {d}",
                    line=dict(color=colors_dir.get(d, "#888"), width=2),
                    marker=dict(size=7),
                ))
            fig.add_hline(y=thr["A"], line_dash="dot",  line_color="#22c55e", annotation_text=f"Zone A ({thr['A']})", annotation_position="top right")
            fig.add_hline(y=thr["B"], line_dash="dot",  line_color="#eab308", annotation_text=f"Zone B ({thr['B']})", annotation_position="top right")
            fig.add_hline(y=thr["C"], line_dash="dash", line_color="#ef4444", annotation_text=f"Zone C ({thr['C']})", annotation_position="top right")
            fig.update_layout(
                title=f"{sel_equip_trend} – {sel_titik_trend}",
                xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
                height=420,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

    else:
        # ── Ringkasan semua equipment: satu grafik per equipment ──────────────
        all_equip_trend = sorted(df_filtered["equipment"].unique())
        cols_per_row = 2
        rows = [all_equip_trend[i:i+cols_per_row] for i in range(0, len(all_equip_trend), cols_per_row)]

        for row_equips in rows:
            cols = st.columns(cols_per_row)
            for col, eq in zip(cols, row_equips):
                with col:
                    thr = get_threshold(eq)
                    df_eq = df_filtered[df_filtered["equipment"] == eq].copy().sort_values("date")

                    # Tabel ringkasan (nilai terbaru per titik)
                    latest_eq = (
                        df_eq.groupby(["titik", "direction"], as_index=False)
                        .last()[["titik", "direction", "value"]]
                    )
                    latest_eq["Zone"] = latest_eq["value"].apply(
                        lambda v: get_zone(v, thr)[1] + " " + get_zone(v, thr)[0]
                    ).astype(str)
                    latest_eq["value"] = latest_eq["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
                    latest_eq = latest_eq.rename(columns={"titik": "Titik", "direction": "Dir", "value": "mm/s"})

                    st.markdown(f"**{eq}**")
                    st.dataframe(latest_eq, use_container_width=True, hide_index=True, height=180)

                    # Grafik trend semua titik × direction
                    fig_eq = go.Figure()
                    for titik in sorted(df_eq["titik"].unique()):
                        for d in sorted(df_eq["direction"].unique()):
                            sub = df_eq[(df_eq["titik"] == titik) & (df_eq["direction"] == d)]
                            if sub.empty:
                                continue
                            fig_eq.add_trace(go.Scatter(
                                x=sub["date"], y=sub["value"],
                                mode="lines+markers",
                                name=f"{titik} {d}",
                                line=dict(width=1.5),
                                marker=dict(size=5),
                            ))
                    fig_eq.add_hline(y=thr["A"], line_dash="dot",  line_color="#22c55e", line_width=1)
                    fig_eq.add_hline(y=thr["B"], line_dash="dot",  line_color="#eab308", line_width=1)
                    fig_eq.add_hline(y=thr["C"], line_dash="dash", line_color="#ef4444", line_width=1)
                    fig_eq.update_layout(
                        height=300,
                        margin=dict(t=30, b=30, l=30, r=10),
                        yaxis_title="mm/s",
                        showlegend=True,
                        legend=dict(font=dict(size=9), orientation="h"),
                    )
                    st.plotly_chart(fig_eq, use_container_width=True, key=f"fig_{eq}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 · Alarm & Warning
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("🚨 Daftar Alarm & Warning")

    latest_alarm = (
        df_filtered.sort_values("date")
        .groupby(["unit", "equipment", "titik", "direction"], as_index=False)
        .last()
    )
    latest_alarm["thr_type"] = latest_alarm["equipment"].apply(
        lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan"
    )
    latest_alarm["zone_label"] = latest_alarm.apply(
        lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1]
                  + " " +
                  get_zone(r["value"], THRESHOLD[r["thr_type"]])[0],
        axis=1,
    )

    # Zone D
    df_d = latest_alarm[latest_alarm.apply(
        lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0] == "ZONE D", axis=1
    )]
    # Zone C
    df_c = latest_alarm[latest_alarm.apply(
        lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0] == "ZONE C", axis=1
    )]

    if not df_d.empty:
        st.error(f"🔴 **BAHAYA — Zone D**: {len(df_d)} titik ukur melebihi batas kritis!")
        cols_show = ["unit", "equipment", "titik", "direction", "value", "zone_label", "date"]
        st.dataframe(df_d[cols_show].rename(columns={
            "unit": "Unit", "equipment": "Equipment", "titik": "Titik",
            "direction": "Dir", "value": "mm/s", "zone_label": "Zone", "date": "Tanggal",
        }), use_container_width=True, hide_index=True)
    else:
        st.success("✅ Tidak ada titik ukur di Zone D.")

    st.divider()

    if not df_c.empty:
        st.warning(f"🟠 **PERHATIAN — Zone C**: {len(df_c)} titik ukur perlu dipantau.")
        cols_show = ["unit", "equipment", "titik", "direction", "value", "zone_label", "date"]
        st.dataframe(df_c[cols_show].rename(columns={
            "unit": "Unit", "equipment": "Equipment", "titik": "Titik",
            "direction": "Dir", "value": "mm/s", "zone_label": "Zone", "date": "Tanggal",
        }), use_container_width=True, hide_index=True)
    else:
        st.success("✅ Tidak ada titik ukur di Zone C.")

    # Heatmap alarm
    st.subheader("Heatmap Nilai Vibrasi (Nilai Maks per Titik)")
    hm_data = latest_alarm.copy()
    hm_data["label"] = hm_data["titik"] + " " + hm_data["direction"]
    hm_pivot = hm_data.pivot_table(
        index="equipment", columns="label", values="value", aggfunc="max"
    )
    fig_hm = px.imshow(
        hm_pivot,
        color_continuous_scale=["#22c55e", "#eab308", "#f97316", "#ef4444"],
        labels=dict(color="mm/s"),
        aspect="auto",
    )
    fig_hm.update_layout(height=500, title="Nilai Maksimum Vibrasi (mm/s) per Equipment × Titik Ukur")
    st.plotly_chart(fig_hm, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 · Histori Data
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("🗄️ Histori Data Tersimpan")

    if df_hist.empty:
        st.info("Belum ada data historis.")
    else:
        df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
        df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            min_date = df_hist["date"].min().date() if pd.notna(df_hist["date"].min()) else date.today()
            max_date = df_hist["date"].max().date() if pd.notna(df_hist["date"].max()) else date.today()
            date_range = st.date_input("Filter Tanggal", value=(min_date, max_date))
        with col_h2:
            unit_hist = st.multiselect("Filter Unit", sorted(df_hist["unit"].dropna().unique()), default=sorted(df_hist["unit"].dropna().unique()))

        if len(date_range) == 2:
            df_show = df_hist[
                (df_hist["date"].dt.date >= date_range[0]) &
                (df_hist["date"].dt.date <= date_range[1]) &
                (df_hist["unit"].isin(unit_hist))
            ]
        else:
            df_show = df_hist[df_hist["unit"].isin(unit_hist)]

        st.write(f"Menampilkan **{len(df_show):,}** baris data")
        st.dataframe(df_show.drop(columns=["id", "uploaded_at"], errors="ignore"), use_container_width=True, hide_index=True)

        # Download
        csv_bytes = df_show.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name=f"vibration_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        # Export Excel
        import io
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_show.drop(columns=["id", "uploaded_at"], errors="ignore").to_excel(writer, index=False, sheet_name="Vibration_History")
        st.download_button(
            label="⬇️ Download Excel",
            data=buf.getvalue(),
            file_name=f"vibration_history_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.divider()
        st.subheader("🗑️ Hapus Data Historis")

        del_tab1, del_tab2, del_tab3 = st.tabs([
            "Hapus per Tanggal",
            "Hapus per Equipment / Unit",
            "Hapus Semua",
        ])

        # ── Hapus per Tanggal ─────────────────────────────────────────────────
        with del_tab1:
            st.caption("Pilih rentang tanggal yang ingin dihapus.")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                del_date_start = st.date_input(
                    "Dari tanggal", value=df_hist["date"].min().date(), key="del_date_start"
                )
            with col_d2:
                del_date_end = st.date_input(
                    "Sampai tanggal", value=df_hist["date"].max().date(), key="del_date_end"
                )

            # Preview berapa baris yang akan dihapus
            preview_date = df_hist[
                (df_hist["date"].dt.date >= del_date_start) &
                (df_hist["date"].dt.date <= del_date_end)
            ]
            st.warning(f"⚠️ Data yang akan dihapus: **{len(preview_date):,} baris** "
                       f"({del_date_start} s/d {del_date_end})")

            if st.button("🗑️ Hapus Data Tanggal Tersebut", type="secondary", key="btn_del_date"):
                con = sqlite3.connect(DB_PATH)
                con.execute(
                    "DELETE FROM vibration WHERE date(date) BETWEEN ? AND ?",
                    (del_date_start.isoformat(), del_date_end.isoformat())
                )
                con.commit()
                con.close()
                st.success(f"✅ {len(preview_date):,} baris data berhasil dihapus.")
                st.rerun()

        # ── Hapus per Equipment / Unit ────────────────────────────────────────
        with del_tab2:
            st.caption("Pilih equipment atau unit yang ingin dihapus datanya.")
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                del_units = st.multiselect(
                    "Filter Unit",
                    sorted(df_hist["unit"].dropna().unique()),
                    key="del_units"
                )
            with col_e2:
                equip_opts = sorted(df_hist["equipment"].dropna().unique())
                del_equips = st.multiselect(
                    "Filter Equipment",
                    equip_opts,
                    key="del_equips"
                )

            if del_units or del_equips:
                mask = pd.Series([True] * len(df_hist), index=df_hist.index)
                if del_units:
                    mask &= df_hist["unit"].isin(del_units)
                if del_equips:
                    mask &= df_hist["equipment"].isin(del_equips)
                preview_eq = df_hist[mask]
                st.warning(f"⚠️ Data yang akan dihapus: **{len(preview_eq):,} baris**")
                st.dataframe(
                    preview_eq.groupby(["unit", "equipment"])
                    .size().reset_index(name="Jumlah Baris")
                    .rename(columns={"unit": "Unit", "equipment": "Equipment"}),
                    use_container_width=True, hide_index=True
                )

                if st.button("🗑️ Hapus Data Equipment Terpilih", type="secondary", key="btn_del_eq"):
                    con = sqlite3.connect(DB_PATH)
                    if del_units and del_equips:
                        placeholders_u = ",".join("?" * len(del_units))
                        placeholders_e = ",".join("?" * len(del_equips))
                        con.execute(
                            f"DELETE FROM vibration WHERE unit IN ({placeholders_u}) AND equipment IN ({placeholders_e})",
                            del_units + del_equips
                        )
                    elif del_units:
                        placeholders_u = ",".join("?" * len(del_units))
                        con.execute(f"DELETE FROM vibration WHERE unit IN ({placeholders_u})", del_units)
                    elif del_equips:
                        placeholders_e = ",".join("?" * len(del_equips))
                        con.execute(f"DELETE FROM vibration WHERE equipment IN ({placeholders_e})", del_equips)
                    con.commit()
                    con.close()
                    st.success(f"✅ {len(preview_eq):,} baris data berhasil dihapus.")
                    st.rerun()
            else:
                st.info("Pilih minimal satu Unit atau Equipment untuk melanjutkan.")

        # ── Hapus Semua ───────────────────────────────────────────────────────
        with del_tab3:
            st.error(f"⛔ Tindakan ini akan menghapus **semua {len(df_hist):,} baris** data secara permanen dan tidak bisa dibatalkan.")
            konfirmasi = st.text_input(
                "Ketik **HAPUS SEMUA** untuk konfirmasi:", key="konfirmasi_hapus"
            )
            if st.button("🗑️ Hapus Semua Data Historis", type="secondary", key="btn_del_all"):
                if konfirmasi == "HAPUS SEMUA":
                    con = sqlite3.connect(DB_PATH)
                    con.execute("DELETE FROM vibration")
                    con.commit()
                    con.close()
                    st.success("✅ Semua data historis berhasil dihapus.")
                    st.rerun()
                else:
                    st.error("❌ Konfirmasi salah. Ketik HAPUS SEMUA dengan huruf kapital.")
