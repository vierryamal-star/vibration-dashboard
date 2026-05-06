import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
import io
from datetime import datetime, date

st.set_page_config(
    page_title="Dashboard Vibrasi – PLTU TBK",
    page_icon="⚡",
    layout="wide",
)

# ─── Custom CSS — Alternatif A: sidebar ikon ──────────────────────────────────
st.markdown("""
<style>
/* Sembunyikan sidebar bawaan Streamlit & ganti dengan icon rail kiri */
[data-testid="stSidebar"] {
    min-width: 68px !important;
    max-width: 68px !important;
    background: #f8f7f4;
    border-right: 0.5px solid #e2e0d8;
}
[data-testid="stSidebar"] .stFileUploader label { display: none; }
[data-testid="stSidebarNav"] { display: none; }

/* Hilangkan padding default halaman */
.block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; }

/* KPI card berwarna */
.kpi-card { border-radius: 10px; padding: 14px 16px; margin-bottom: 4px; }
.kpi-card .num { font-size: 28px; font-weight: 500; line-height: 1; }
.kpi-card .lbl { font-size: 11px; margin-top: 4px; opacity: 0.85; }
.kpi-total  { background: #f1efea; }
.kpi-total .num  { color: #2c2c2a; }
.kpi-total .lbl  { color: #5f5e5a; }
.kpi-danger { background: #fcebeb; border-left: 4px solid #e24b4a; }
.kpi-danger .num { color: #a32d2d; }
.kpi-danger .lbl { color: #791f1f; }
.kpi-warn   { background: #faeeda; border-left: 4px solid #ef9f27; }
.kpi-warn .num   { color: #854f0b; }
.kpi-warn .lbl   { color: #633806; }
.kpi-ok     { background: #eaf3de; border-left: 4px solid #97c459; }
.kpi-ok .num     { color: #3b6d11; }
.kpi-ok .lbl     { color: #27500a; }

/* Alarm banner */
.alarm-d { background:#fcebeb; border-left:4px solid #e24b4a; border-radius:0 8px 8px 0;
           padding:8px 12px; margin-bottom:6px; font-size:13px; }
.alarm-c { background:#faeeda; border-left:4px solid #ef9f27; border-radius:0 8px 8px 0;
           padding:8px 12px; margin-bottom:6px; font-size:13px; }
.alarm-title { font-weight:500; color:#2c2c2a; }
.alarm-d .alarm-title { color:#791f1f; }
.alarm-c .alarm-title { color:#633806; }
.alarm-sub { font-size:11px; color:#5f5e5a; margin-top:2px; }

/* Zone pills di tabel */
.za { display:inline-block; background:#eaf3de; color:#3b6d11;
      padding:2px 8px; border-radius:8px; font-size:11px; font-weight:500; }
.zb { display:inline-block; background:#faeeda; color:#854f0b;
      padding:2px 8px; border-radius:8px; font-size:11px; font-weight:500; }
.zc { display:inline-block; background:#faece7; color:#993c1d;
      padding:2px 8px; border-radius:8px; font-size:11px; font-weight:500; }
.zd { display:inline-block; background:#fcebeb; color:#a32d2d;
      padding:2px 8px; border-radius:8px; font-size:11px; font-weight:500; }

/* Status bar distribusi */
.status-bar-wrap { background:#f1efea; border-radius:6px; overflow:hidden;
                   display:flex; height:10px; margin:6px 0 4px; }
.sb-ok  { background:#639922; }
.sb-c   { background:#ef9f27; }
.sb-d   { background:#e24b4a; }
.sb-legend { display:flex; gap:12px; font-size:11px; }

/* Upload info box */
.upload-info { background:#e1f5ee; border:0.5px solid #5dcaa5; border-radius:8px;
               padding:8px 12px; font-size:12px; color:#0f6e56; margin-top:8px; }

/* Topbar */
.topbar { display:flex; align-items:center; justify-content:space-between;
          padding:10px 0 12px; border-bottom:0.5px solid #e2e0d8; margin-bottom:14px; }
.topbar-title { font-size:16px; font-weight:500; color:#2c2c2a; }
.topbar-sub   { font-size:11px; color:#888780; margin-top:2px; }
.topbar-alarm { background:#fcebeb; color:#a32d2d; border:0.5px solid #f09595;
                border-radius:20px; padding:4px 12px; font-size:12px; font-weight:500; }
</style>
""", unsafe_allow_html=True)

# ─── Konstanta & helpers ──────────────────────────────────────────────────────
DB_PATH = "vibration_history.db"

THRESHOLD = {
    "Turbine": {"A": 3.8, "B": 7.5, "C": 11.8},
    "Pump/Fan": {"A": 1.4, "B": 2.8, "C": 4.5},
}

def get_threshold(equipment: str):
    if "turbine" in str(equipment).lower():
        return THRESHOLD["Turbine"]
    return THRESHOLD["Pump/Fan"]

def get_zone(value, thr):
    if pd.isna(value):
        return "N/A", "–"
    if value <= thr["A"]:   return "ZONE A", "🟢"
    elif value <= thr["B"]: return "ZONE B", "🟡"
    elif value <= thr["C"]: return "ZONE C", "🟠"
    else:                   return "ZONE D", "🔴"

def zone_html(value, thr):
    z, _ = get_zone(value, thr)
    cls = {"ZONE A": "za", "ZONE B": "zb", "ZONE C": "zc", "ZONE D": "zd"}.get(z, "")
    return f'<span class="{cls}">{z}</span>' if cls else z

ZONE_COLOR = {"ZONE A": "#22c55e", "ZONE B": "#eab308", "ZONE C": "#f97316", "ZONE D": "#ef4444", "N/A": "#94a3b8"}

# ─── Database ─────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS vibration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT, unit TEXT, titik TEXT, direction TEXT,
        date TEXT, value REAL, uploaded_at TEXT
    )""")
    con.commit(); con.close()

def save_to_db(df: pd.DataFrame):
    con = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    rows = df.copy(); rows["uploaded_at"] = now
    try:
        existing = pd.read_sql("SELECT equipment,unit,titik,direction,date FROM vibration", con)
        existing["_key"] = (existing["equipment"].astype(str)+"|"+existing["unit"].astype(str)+"|"+
                            existing["titik"].astype(str)+"|"+existing["direction"].astype(str)+"|"+
                            pd.to_datetime(existing["date"],errors="coerce").dt.date.astype(str))
        rows["_key"] = (rows["equipment"].astype(str)+"|"+rows["unit"].astype(str)+"|"+
                        rows["titik"].astype(str)+"|"+rows["direction"].astype(str)+"|"+
                        pd.to_datetime(rows["date"],errors="coerce").dt.date.astype(str))
        rows_new = rows[~rows["_key"].isin(existing["_key"])].drop(columns=["_key"])
    except Exception:
        rows_new = rows.copy()
    saved = len(rows_new)
    if not rows_new.empty:
        rows_new.to_sql("vibration", con, if_exists="append", index=False)
    con.close(); return saved

def load_history():
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM vibration ORDER BY date DESC", con)
    except Exception:
        df = pd.DataFrame()
    con.close(); return df

# ─── Parse Excel ──────────────────────────────────────────────────────────────
def parse_excel(file):
    df = pd.read_excel(file, sheet_name="Vibration_Data")
    df.columns = [c.strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "equipment" in cl:   col_map[c] = "equipment"
        elif "unit" in cl:      col_map[c] = "unit"
        elif "titik" in cl:     col_map[c] = "titik"
        elif "direction" in cl: col_map[c] = "direction"
        elif "date" in cl:      col_map[c] = "date"
        elif "value" in cl:     col_map[c] = "value"
    df = df.rename(columns=col_map)
    required = {"equipment","unit","titik","direction","date","value"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Kolom tidak ditemukan: {missing}"); return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[list(required)].dropna(subset=["equipment","unit","titik","direction"])

# ─── Init ─────────────────────────────────────────────────────────────────────
init_db()

# ─── SIDEBAR — ikon navigasi + upload + threshold ─────────────────────────────
with st.sidebar:
    st.markdown("### ⚡")
    st.markdown("---")

    # Navigasi halaman via session state
    if "page" not in st.session_state:
        st.session_state.page = "Ringkasan"

    pages = {
        "Ringkasan":  "📊",
        "Trend":      "📈",
        "Alarm":      "🚨",
        "Histori":    "🗄️",
        "Upload":     "📤",
        "Pengaturan": "⚙️",
    }
    for p, icon in pages.items():
        active = st.session_state.page == p
        if st.button(f"{icon}", key=f"nav_{p}", help=p,
                     type="primary" if active else "secondary",
                     use_container_width=True):
            st.session_state.page = p
            st.rerun()

page = st.session_state.page

# ─── PENGATURAN THRESHOLD (sidebar bawah saat halaman Pengaturan) ─────────────
with st.sidebar:
    st.markdown("---")
    if page == "Pengaturan":
        st.caption("Threshold (mm/s)")
        THRESHOLD["Turbine"]["A"]  = st.number_input("Turb A", value=3.8,  step=0.1, key="ta")
        THRESHOLD["Turbine"]["B"]  = st.number_input("Turb B", value=7.5,  step=0.1, key="tb")
        THRESHOLD["Turbine"]["C"]  = st.number_input("Turb C", value=11.8, step=0.1, key="tc")
        THRESHOLD["Pump/Fan"]["A"] = st.number_input("Pump A", value=1.4,  step=0.1, key="pa")
        THRESHOLD["Pump/Fan"]["B"] = st.number_input("Pump B", value=2.8,  step=0.1, key="pb")
        THRESHOLD["Pump/Fan"]["C"] = st.number_input("Pump C", value=4.5,  step=0.1, key="pc")
    st.caption("🟢 A · 🟡 B · 🟠 C · 🔴 D")

# ─── HALAMAN UPLOAD ────────────────────────────────────────────────────────────
if page == "Upload":
    st.markdown('<div class="topbar"><div><div class="topbar-title">📤 Upload Data Vibrasi</div><div class="topbar-sub">Format: sheet Vibration_Data · kolom Equipment, Unit, Titik Ukur, Direction, Date, Value (mm/s)</div></div></div>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Pilih file Excel (.xlsx)", type=["xlsx"])
    if uploaded:
        df_new = parse_excel(uploaded)
        if not df_new.empty:
            saved = save_to_db(df_new)
            skipped = len(df_new) - saved
            if saved > 0 and skipped > 0:
                st.success(f"✅ {saved} baris baru disimpan. {skipped} baris duplikat dilewati.")
            elif saved > 0:
                st.success(f"✅ {saved} baris baru berhasil disimpan.")
            else:
                st.info(f"ℹ️ Semua {len(df_new)} baris sudah ada — tidak ada data baru.")
            st.markdown(f'<div class="upload-info">📁 <b>{uploaded.name}</b> · {len(df_new)} baris · diupload {datetime.now().strftime("%d %b %Y %H:%M")}</div>', unsafe_allow_html=True)
            st.dataframe(df_new.head(20), use_container_width=True, hide_index=True)
    st.stop()

# ─── LOAD DATA ────────────────────────────────────────────────────────────────
df_hist = load_history()

if df_hist.empty:
    st.info("📂 Belum ada data. Klik 📤 di sidebar untuk upload file Excel.")
    st.stop()

df_work = df_hist.copy()
df_work["date"]  = pd.to_datetime(df_work["date"],  errors="coerce")
df_work["value"] = pd.to_numeric(df_work["value"], errors="coerce")

# ─── TOPBAR INFO ──────────────────────────────────────────────────────────────
all_units = sorted(df_work["unit"].dropna().unique().tolist())
all_equip = sorted(df_work["equipment"].dropna().unique().tolist())

df_work["thr_type"] = df_work["equipment"].apply(lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan")
df_work["zone"]     = df_work.apply(lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0], axis=1)

latest_all = df_work.sort_values("date").groupby(["unit","equipment","titik","direction"], as_index=False).last()
zone_d_count = (latest_all["zone"] == "ZONE D").sum()
zone_c_count = (latest_all["zone"] == "ZONE C").sum()
total_count  = len(latest_all)
normal_count = total_count - zone_d_count - zone_c_count
last_date    = df_work["date"].max().strftime("%d %b %Y") if pd.notna(df_work["date"].max()) else "–"

alarm_badge = f'<span class="topbar-alarm">🔴 {zone_d_count} Zone D aktif</span>' if zone_d_count > 0 else ""
st.markdown(f"""
<div class="topbar">
  <div>
    <div class="topbar-title">⚡ Dashboard Monitoring Vibrasi — PLTU TBK</div>
    <div class="topbar-sub">ISO 10816 · mm/s RMS · Data terakhir: {last_date}</div>
  </div>
  {alarm_badge}
</div>
""", unsafe_allow_html=True)

# ─── FILTER BAR (ditampilkan di semua halaman kecuali Pengaturan & Upload) ────
if page not in ("Pengaturan", "Upload"):
    fc1, fc2, fc3 = st.columns([2, 3, 2])
    with fc1:
        sel_unit = st.multiselect("Unit", all_units, default=all_units, key="f_unit")
    with fc2:
        sel_equip = st.multiselect("Equipment", all_equip, default=all_equip, key="f_equip")
    with fc3:
        sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="f_dir")

    df_filtered = df_work[
        df_work["unit"].isin(sel_unit) &
        df_work["equipment"].isin(sel_equip) &
        df_work["direction"].isin(sel_dir)
    ].copy()

    if df_filtered.empty:
        st.warning("Tidak ada data sesuai filter."); st.stop()

    latest = df_filtered.sort_values("date").groupby(["unit","equipment","titik","direction"], as_index=False).last()
    zone_d  = (latest["zone"] == "ZONE D").sum()
    zone_c  = (latest["zone"] == "ZONE C").sum()
    total   = len(latest)
    normal  = total - zone_d - zone_c

# ═══════════════════════════════════════════════════════════════════════════════
# HALAMAN: RINGKASAN STATUS
# ═══════════════════════════════════════════════════════════════════════════════
if page == "Ringkasan":

    # KPI cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="kpi-card kpi-total"><div class="num">{total}</div><div class="lbl">Total titik ukur</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi-card kpi-danger"><div class="num">{zone_d}</div><div class="lbl">Zone D — bahaya</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi-card kpi-warn"><div class="num">{zone_c}</div><div class="lbl">Zone C — perhatian</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="kpi-card kpi-ok"><div class="num">{normal}</div><div class="lbl">Zone A–B — normal</div></div>', unsafe_allow_html=True)

    # Status bar distribusi
    pct_ok = round(normal / total * 100) if total else 0
    pct_c  = round(zone_c  / total * 100) if total else 0
    pct_d  = round(zone_d  / total * 100) if total else 0
    st.markdown(f"""
    <div class="status-bar-wrap">
      <div class="sb-ok" style="width:{pct_ok}%"></div>
      <div class="sb-c"  style="width:{pct_c}%"></div>
      <div class="sb-d"  style="width:{pct_d}%"></div>
    </div>
    <div class="sb-legend">
      <span style="color:#3b6d11">Normal {pct_ok}%</span>
      <span style="color:#854f0b">Zone C {pct_c}%</span>
      <span style="color:#a32d2d">Zone D {pct_d}%</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Pill filter cepat per equipment (warna sesuai zone terburuk)
    def worst_zone(eq):
        sub = latest[latest["equipment"] == eq]["zone"]
        if (sub == "ZONE D").any(): return "danger"
        if (sub == "ZONE C").any(): return "warn"
        return "ok"

    zone_pill_css = {
        "danger": "background:#fcebeb;color:#a32d2d;border:0.5px solid #f09595",
        "warn":   "background:#faeeda;color:#854f0b;border:0.5px solid #ef9f27",
        "ok":     "background:#eaf3de;color:#3b6d11;border:0.5px solid #97c459",
    }
    pills_html = ""
    for eq in sorted(latest["equipment"].unique()):
        wz = worst_zone(eq)
        pills_html += f'<span style="display:inline-block;padding:3px 12px;border-radius:10px;font-size:12px;margin:3px;{zone_pill_css[wz]}">{eq}</span>'
    st.markdown(f'<div style="margin-bottom:10px">{pills_html}</div>', unsafe_allow_html=True)

    # Tabel status terbaru — pivot direction
    st.subheader("Status terakhir per titik ukur")
    pivot = latest.pivot_table(index=["unit","equipment","titik"], columns="direction", values="value", aggfunc="last").reset_index()
    pivot.columns.name = None
    dir_cols = [c for c in ["H","V","A"] if c in pivot.columns]
    pivot["Max (mm/s)"] = pivot[dir_cols].max(axis=1)
    pivot["Thr. Type"] = pivot["equipment"].apply(lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan")

    def _zone_label(r):
        thr = THRESHOLD[r["Thr. Type"]]
        icon, label = get_zone(r["Max (mm/s)"], thr)[1], get_zone(r["Max (mm/s)"], thr)[0]
        return f"{icon} {label}"
    pivot["Zone"] = pivot.apply(_zone_label, axis=1).astype(str)
    pivot = pivot.drop(columns=["Thr. Type"])
    pivot = pivot.rename(columns={"unit":"Unit","equipment":"Equipment","titik":"Titik Ukur"})
    for c in dir_cols:
        pivot[c] = pivot[c].map(lambda v: f"{v:.2f}" if pd.notna(v) else "–")
    pivot["Max (mm/s)"] = pivot["Max (mm/s)"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "–")
    st.dataframe(pivot, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Detail per equipment
    st.subheader("Detail per equipment")
    sel_det = st.selectbox("Pilih equipment", sorted(latest["equipment"].unique()), key="det_eq")
    df_det = latest[latest["equipment"] == sel_det].copy()
    thr_det = get_threshold(sel_det)
    df_det["Zone"] = df_det["value"].apply(lambda v: get_zone(v, thr_det)[1]+" "+get_zone(v, thr_det)[0]).astype(str)
    df_det["value"] = df_det["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
    df_det = df_det.rename(columns={"unit":"Unit","titik":"Titik Ukur","direction":"Direction","value":"mm/s","date":"Tanggal"})
    st.dataframe(df_det[["Unit","Titik Ukur","Direction","mm/s","Zone","Tanggal"]], use_container_width=True, hide_index=True)

    st.markdown("---")

    # Trend overview
    st.subheader("Trend vibrasi")
    oc1, oc2, oc3 = st.columns([2,2,1])
    with oc1:
        ov_eq = st.selectbox("Equipment", sorted(df_filtered["equipment"].unique()), key="ov_eq")
    with oc2:
        titik_opts = ["Semua Titik"] + sorted(df_filtered[df_filtered["equipment"]==ov_eq]["titik"].unique().tolist())
        ov_titik = st.selectbox("Titik Ukur", titik_opts, key="ov_titik")
    with oc3:
        ov_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="ov_dir")

    df_ov = df_filtered[df_filtered["equipment"]==ov_eq].copy()
    if ov_titik != "Semua Titik":
        df_ov = df_ov[df_ov["titik"]==ov_titik]
    if ov_dir:
        df_ov = df_ov[df_ov["direction"].isin(ov_dir)]
    df_ov = df_ov.sort_values("date")
    thr_ov = get_threshold(ov_eq)
    colors_d = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
    line_styles = ["solid","dash","dot","dashdot"]

    if df_ov.empty:
        st.info("Tidak ada data.")
    else:
        fig = go.Figure()
        for i, titik in enumerate(sorted(df_ov["titik"].unique())):
            for d in ov_dir:
                sub = df_ov[(df_ov["titik"]==titik)&(df_ov["direction"]==d)]
                if sub.empty: continue
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"], mode="lines+markers",
                    name=f"{titik} – {d}",
                    line=dict(color=colors_d.get(d,"#888"), width=2, dash=line_styles[i%len(line_styles)]),
                    marker=dict(size=6),
                    hovertemplate=f"<b>{titik} ({d})</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
                ))
        fig.add_hline(y=thr_ov["A"], line_dash="dot",  line_color="#22c55e", line_width=1, annotation_text=f"Zone A ({thr_ov['A']})", annotation_font_color="#22c55e")
        fig.add_hline(y=thr_ov["B"], line_dash="dot",  line_color="#eab308", line_width=1, annotation_text=f"Zone B ({thr_ov['B']})", annotation_font_color="#eab308")
        fig.add_hline(y=thr_ov["C"], line_dash="dash", line_color="#ef4444", line_width=1.5, annotation_text=f"Zone C ({thr_ov['C']})", annotation_font_color="#ef4444")
        fig.update_layout(
            xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
            height=420, hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11)),
            margin=dict(t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# HALAMAN: TREND VIBRASI
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "Trend":
    st.subheader("📈 Trend Vibrasi per Equipment")
    colors_d = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
    line_styles = ["solid","dash","dot","dashdot"]

    mode = st.radio("Mode", ["Detail satu equipment","Ringkasan semua equipment"], horizontal=True)

    if mode == "Detail satu equipment":
        tc1, tc2 = st.columns(2)
        with tc1:
            t_eq = st.selectbox("Equipment", sorted(df_filtered["equipment"].unique()), key="t_eq")
        with tc2:
            t_titik_opts = sorted(df_filtered[df_filtered["equipment"]==t_eq]["titik"].unique())
            t_titik = st.selectbox("Titik Ukur", t_titik_opts, key="t_titik")

        df_trend = df_filtered[(df_filtered["equipment"]==t_eq)&(df_filtered["titik"]==t_titik)].copy().sort_values("date")

        if df_trend.empty:
            st.info("Tidak ada data.")
        else:
            thr = get_threshold(t_eq)
            df_tbl = df_trend[["date","direction","value"]].copy()
            df_tbl["Zone"] = df_tbl["value"].apply(lambda v: get_zone(v,thr)[1]+" "+get_zone(v,thr)[0]).astype(str)
            df_tbl["value"] = df_tbl["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
            df_tbl = df_tbl.rename(columns={"date":"Tanggal","direction":"Direction","value":"mm/s"})
            st.dataframe(df_tbl, use_container_width=True, hide_index=True)
            st.markdown("---")

            fig = go.Figure()
            for d in sorted(df_trend["direction"].unique()):
                sub = df_trend[df_trend["direction"]==d]
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"], mode="lines+markers",
                    name=f"Direction {d}", line=dict(color=colors_d.get(d,"#888"), width=2),
                    marker=dict(size=7),
                ))
            fig.add_hline(y=thr["A"], line_dash="dot",  line_color="#22c55e", line_width=1, annotation_text=f"Zone A ({thr['A']})")
            fig.add_hline(y=thr["B"], line_dash="dot",  line_color="#eab308", line_width=1, annotation_text=f"Zone B ({thr['B']})")
            fig.add_hline(y=thr["C"], line_dash="dash", line_color="#ef4444", line_width=1.5, annotation_text=f"Zone C ({thr['C']})")
            fig.update_layout(
                title=f"{t_eq} — {t_titik}",
                xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)", height=440,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        all_eq = sorted(df_filtered["equipment"].unique())
        rows = [all_eq[i:i+2] for i in range(0, len(all_eq), 2)]
        for row_eq in rows:
            cols = st.columns(2)
            for col, eq in zip(cols, row_eq):
                with col:
                    thr = get_threshold(eq)
                    df_eq = df_filtered[df_filtered["equipment"]==eq].copy().sort_values("date")
                    lt_eq = df_eq.groupby(["titik","direction"], as_index=False).last()[["titik","direction","value"]]
                    lt_eq["Zone"] = lt_eq["value"].apply(lambda v: get_zone(v,thr)[1]+" "+get_zone(v,thr)[0]).astype(str)
                    lt_eq["value"] = lt_eq["value"].map(lambda v: f"{v:.3f}" if pd.notna(v) else "–")
                    lt_eq = lt_eq.rename(columns={"titik":"Titik","direction":"Dir","value":"mm/s"})
                    st.markdown(f"**{eq}**")
                    st.dataframe(lt_eq, use_container_width=True, hide_index=True, height=180)
                    fig_eq = go.Figure()
                    for i, titik in enumerate(sorted(df_eq["titik"].unique())):
                        for d in sorted(df_eq["direction"].unique()):
                            sub = df_eq[(df_eq["titik"]==titik)&(df_eq["direction"]==d)]
                            if sub.empty: continue
                            fig_eq.add_trace(go.Scatter(
                                x=sub["date"], y=sub["value"], mode="lines+markers",
                                name=f"{titik} {d}",
                                line=dict(color=colors_d.get(d,"#888"), width=1.5, dash=line_styles[i%len(line_styles)]),
                                marker=dict(size=5),
                            ))
                    fig_eq.add_hline(y=thr["A"], line_dash="dot",  line_color="#22c55e", line_width=1)
                    fig_eq.add_hline(y=thr["B"], line_dash="dot",  line_color="#eab308", line_width=1)
                    fig_eq.add_hline(y=thr["C"], line_dash="dash", line_color="#ef4444", line_width=1)
                    fig_eq.update_layout(height=300, margin=dict(t=30,b=30,l=30,r=10),
                                         yaxis_title="mm/s", legend=dict(font=dict(size=9), orientation="h"))
                    st.plotly_chart(fig_eq, use_container_width=True, key=f"fig_{eq}")

# ═══════════════════════════════════════════════════════════════════════════════
# HALAMAN: ALARM & WARNING
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "Alarm":
    st.subheader("🚨 Alarm & Warning")

    latest_alarm = df_filtered.sort_values("date").groupby(["unit","equipment","titik","direction"], as_index=False).last()
    latest_alarm["thr_type"] = latest_alarm["equipment"].apply(lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan")

    df_d = latest_alarm[latest_alarm.apply(lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0]=="ZONE D", axis=1)]
    df_c = latest_alarm[latest_alarm.apply(lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0]=="ZONE C", axis=1)]

    # Banner alarm Zone D
    if not df_d.empty:
        st.markdown(f'<div class="alarm-d"><div class="alarm-title">🔴 Zone D — Bahaya ({len(df_d)} titik ukur)</div><div class="alarm-sub">Segera lakukan pemeriksaan lapangan!</div></div>', unsafe_allow_html=True)
        for _, r in df_d.iterrows():
            thr = THRESHOLD[r["thr_type"]]
            batas = thr["C"]
            st.markdown(f'<div class="alarm-d"><div class="alarm-title">{r["equipment"]} · {r["titik"]} · Direction {r["direction"]}</div><div class="alarm-sub">Nilai: {r["value"]:.3f} mm/s · Batas Zone C: {batas} mm/s · Unit: {r["unit"]} · {str(r["date"])[:10]}</div></div>', unsafe_allow_html=True)
    else:
        st.success("✅ Tidak ada titik ukur di Zone D.")

    st.markdown("---")

    # Banner Zone C
    if not df_c.empty:
        st.markdown(f'<div class="alarm-c"><div class="alarm-title">🟠 Zone C — Perlu Perhatian ({len(df_c)} titik ukur)</div><div class="alarm-sub">Monitor secara berkala dan jadwalkan inspeksi.</div></div>', unsafe_allow_html=True)
        for _, r in df_c.iterrows():
            thr = THRESHOLD[r["thr_type"]]
            batas = thr["B"]
            st.markdown(f'<div class="alarm-c"><div class="alarm-title">{r["equipment"]} · {r["titik"]} · Direction {r["direction"]}</div><div class="alarm-sub">Nilai: {r["value"]:.3f} mm/s · Batas Zone B: {batas} mm/s · Unit: {r["unit"]} · {str(r["date"])[:10]}</div></div>', unsafe_allow_html=True)
    else:
        st.success("✅ Tidak ada titik ukur di Zone C.")

    st.markdown("---")

    # Heatmap
    st.subheader("Heatmap nilai vibrasi (maks per titik)")
    hm = latest_alarm.copy()
    hm["label"] = hm["titik"] + " " + hm["direction"]
    hm_pivot = hm.pivot_table(index="equipment", columns="label", values="value", aggfunc="max")
    fig_hm = px.imshow(hm_pivot, color_continuous_scale=["#22c55e","#eab308","#f97316","#ef4444"],
                       labels=dict(color="mm/s"), aspect="auto")
    fig_hm.update_layout(height=500, title="Nilai maksimum vibrasi (mm/s)")
    st.plotly_chart(fig_hm, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# HALAMAN: HISTORI DATA
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "Histori":
    st.subheader("🗄️ Histori Data Tersimpan")

    df_hist2 = load_history()
    if df_hist2.empty:
        st.info("Belum ada data historis.")
        st.stop()

    df_hist2["date"]  = pd.to_datetime(df_hist2["date"],  errors="coerce")
    df_hist2["value"] = pd.to_numeric(df_hist2["value"], errors="coerce")

    hc1, hc2 = st.columns(2)
    with hc1:
        min_d = df_hist2["date"].min().date() if pd.notna(df_hist2["date"].min()) else date.today()
        max_d = df_hist2["date"].max().date() if pd.notna(df_hist2["date"].max()) else date.today()
        date_range = st.date_input("Filter tanggal", value=(min_d, max_d))
    with hc2:
        unit_hist = st.multiselect("Filter unit", sorted(df_hist2["unit"].dropna().unique()),
                                   default=sorted(df_hist2["unit"].dropna().unique()))

    if len(date_range) == 2:
        df_show = df_hist2[
            (df_hist2["date"].dt.date >= date_range[0]) &
            (df_hist2["date"].dt.date <= date_range[1]) &
            (df_hist2["unit"].isin(unit_hist))
        ]
    else:
        df_show = df_hist2[df_hist2["unit"].isin(unit_hist)]

    st.write(f"Menampilkan **{len(df_show):,}** baris data")
    st.dataframe(df_show.drop(columns=["id","uploaded_at"], errors="ignore"), use_container_width=True, hide_index=True)

    dc1, dc2 = st.columns(2)
    with dc1:
        csv_bytes = df_show.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", data=csv_bytes,
                           file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
    with dc2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_show.drop(columns=["id","uploaded_at"], errors="ignore").to_excel(writer, index=False, sheet_name="Vibration_History")
        st.download_button("⬇️ Download Excel", data=buf.getvalue(),
                           file_name=f"vibration_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    st.subheader("🗑️ Hapus Data Historis")

    dt1, dt2, dt3 = st.tabs(["Hapus per Tanggal","Hapus per Equipment / Unit","Hapus Semua"])

    with dt1:
        d1, d2 = st.columns(2)
        with d1: del_start = st.date_input("Dari", value=df_hist2["date"].min().date(), key="ds")
        with d2: del_end   = st.date_input("Sampai", value=df_hist2["date"].max().date(), key="de")
        prev = df_hist2[(df_hist2["date"].dt.date>=del_start)&(df_hist2["date"].dt.date<=del_end)]
        st.warning(f"⚠️ Akan menghapus **{len(prev):,} baris** ({del_start} s/d {del_end})")
        if st.button("🗑️ Hapus Data Tanggal Tersebut", type="secondary", key="btn_dt"):
            con = sqlite3.connect(DB_PATH)
            con.execute("DELETE FROM vibration WHERE date(date) BETWEEN ? AND ?", (del_start.isoformat(), del_end.isoformat()))
            con.commit(); con.close()
            st.success(f"✅ {len(prev):,} baris dihapus."); st.rerun()

    with dt2:
        e1, e2 = st.columns(2)
        with e1: del_units  = st.multiselect("Filter Unit", sorted(df_hist2["unit"].dropna().unique()), key="du")
        with e2: del_equips = st.multiselect("Filter Equipment", sorted(df_hist2["equipment"].dropna().unique()), key="de2")
        if del_units or del_equips:
            mask = pd.Series([True]*len(df_hist2), index=df_hist2.index)
            if del_units:  mask &= df_hist2["unit"].isin(del_units)
            if del_equips: mask &= df_hist2["equipment"].isin(del_equips)
            prev_eq = df_hist2[mask]
            st.warning(f"⚠️ Akan menghapus **{len(prev_eq):,} baris**")
            st.dataframe(prev_eq.groupby(["unit","equipment"]).size().reset_index(name="Jumlah").rename(columns={"unit":"Unit","equipment":"Equipment"}), use_container_width=True, hide_index=True)
            if st.button("🗑️ Hapus Data Terpilih", type="secondary", key="btn_eq"):
                con = sqlite3.connect(DB_PATH)
                if del_units and del_equips:
                    con.execute(f"DELETE FROM vibration WHERE unit IN ({','.join('?'*len(del_units))}) AND equipment IN ({','.join('?'*len(del_equips))})", del_units+del_equips)
                elif del_units:
                    con.execute(f"DELETE FROM vibration WHERE unit IN ({','.join('?'*len(del_units))})", del_units)
                elif del_equips:
                    con.execute(f"DELETE FROM vibration WHERE equipment IN ({','.join('?'*len(del_equips))})", del_equips)
                con.commit(); con.close()
                st.success(f"✅ {len(prev_eq):,} baris dihapus."); st.rerun()
        else:
            st.info("Pilih minimal satu unit atau equipment.")

    with dt3:
        st.error(f"⛔ Akan menghapus **semua {len(df_hist2):,} baris** data secara permanen.")
        konfirmasi = st.text_input("Ketik HAPUS SEMUA untuk konfirmasi:", key="konfirmasi")
        if st.button("🗑️ Hapus Semua Data", type="secondary", key="btn_all"):
            if konfirmasi == "HAPUS SEMUA":
                con = sqlite3.connect(DB_PATH)
                con.execute("DELETE FROM vibration"); con.commit(); con.close()
                st.success("✅ Semua data berhasil dihapus."); st.rerun()
            else:
                st.error("❌ Konfirmasi salah. Ketik HAPUS SEMUA dengan huruf kapital.")

# ═══════════════════════════════════════════════════════════════════════════════
# HALAMAN: PENGATURAN
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "Pengaturan":
    st.subheader("⚙️ Pengaturan Threshold")
    st.info("Threshold dapat diubah melalui input di sidebar kiri. Perubahan berlaku langsung tanpa perlu restart.")
    st.markdown("---")
    st.subheader("Referensi ISO 10816")
    thr_ref = pd.DataFrame({
        "Tipe Equipment": ["Turbine","Pump / Fan"],
        "Zone A (mm/s)": [3.8, 1.4],
        "Zone B (mm/s)": [7.5, 2.8],
        "Zone C (mm/s)": [11.8, 4.5],
        "Zone D": ["> 11.8", "> 4.5"],
    })
    st.dataframe(thr_ref, use_container_width=True, hide_index=True)
    st.markdown("""
**Keterangan zone ISO 10816:**
- 🟢 **Zone A** — kondisi sangat baik, baru dipasang atau setelah overhaul
- 🟡 **Zone B** — kondisi normal, dapat beroperasi terus
- 🟠 **Zone C** — perlu pemantauan intensif, jadwalkan inspeksi
- 🔴 **Zone D** — kondisi berbahaya, hentikan operasi dan lakukan pemeriksaan
    """)
