import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import load_history, get_zone, get_threshold, THRESHOLD, add_zone_cols, render_login_sidebar

st.set_page_config(page_title="Prediksi Trend — PLTU TBK", page_icon="🔮", layout="wide")
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

st.markdown("## 🔮 Prediksi Trend Vibrasi")
st.caption("Prediksi 3 hari ke depan menggunakan regresi linier berdasarkan data historis.")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data historis.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce").dt.normalize()
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
df_hist = df_hist.dropna(subset=["date","value"])

# ── Filter ────────────────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns(3)
with fc1:
    sel_eq = st.selectbox("Equipment", sorted(df_hist["equipment"].unique()), key="pred_eq")
with fc2:
    titik_opts = sorted(df_hist[df_hist["equipment"]==sel_eq]["titik"].unique())
    sel_titik  = st.selectbox("Titik Ukur", titik_opts, key="pred_titik")
with fc3:
    sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="pred_dir")

n_days = st.slider("Jumlah hari prediksi ke depan", min_value=1, max_value=7, value=3)

df_sel = df_hist[
    (df_hist["equipment"]==sel_eq) &
    (df_hist["titik"]==sel_titik) &
    (df_hist["direction"].isin(sel_dir))
].copy()

if df_sel.empty:
    st.warning("Tidak ada data untuk pilihan ini.")
    st.stop()

min_data = df_sel.groupby("direction").size().min()
if min_data < 3:
    st.warning(f"Data historis terlalu sedikit untuk prediksi (minimum 3 titik per direction). Saat ini hanya ada {min_data} titik.")
    st.stop()

thr = get_threshold(sel_eq)
colors_dir = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
colors_pred = {"H":"#93c5fd","V":"#6ee7b7","A":"#fcd34d"}

# ── Fungsi prediksi linear regression ────────────────────────────────────────
def predict_trend(df_dir: pd.DataFrame, n_days: int):
    df_s = df_dir.sort_values("date").copy()
    df_s["t"] = (df_s["date"] - df_s["date"].min()).dt.days.astype(float)
    x = df_s["t"].values
    y = df_s["value"].values
    # Linear regression manual (tidak butuh sklearn)
    n    = len(x)
    xbar = x.mean(); ybar = y.mean()
    slope = ((x - xbar) * (y - ybar)).sum() / ((x - xbar)**2).sum()
    intercept = ybar - slope * xbar
    # Prediksi
    last_t    = x.max()
    last_date = df_s["date"].max()
    pred_dates  = [last_date + pd.Timedelta(days=i+1) for i in range(n_days)]
    pred_t      = [last_t + i + 1 for i in range(n_days)]
    pred_values = [max(0, intercept + slope * t) for t in pred_t]
    # Interval kepercayaan (±1 std residual)
    residuals = y - (intercept + slope * x)
    std_res   = residuals.std()
    pred_upper = [v + std_res for v in pred_values]
    pred_lower = [max(0, v - std_res) for v in pred_values]
    return pred_dates, pred_values, pred_upper, pred_lower, slope

# ── Buat grafik ───────────────────────────────────────────────────────────────
fig = go.Figure()
pred_summary = []

for d in sel_dir:
    df_d = df_sel[df_sel["direction"]==d].sort_values("date")
    if len(df_d) < 3:
        continue

    # Data historis
    fig.add_trace(go.Scatter(
        x=df_d["date"], y=df_d["value"],
        mode="lines+markers", name=f"{d} — historis",
        line=dict(color=colors_dir.get(d,"#888"), width=2),
        marker=dict(size=6),
        hovertemplate=f"<b>Direction {d} (historis)</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
    ))

    # Prediksi
    pred_dates, pred_vals, pred_upper, pred_lower, slope = predict_trend(df_d, n_days)

    # Titik sambung historis → prediksi
    last_actual_date  = df_d["date"].iloc[-1]
    last_actual_value = df_d["value"].iloc[-1]

    x_pred_full  = [last_actual_date] + pred_dates
    y_pred_full  = [last_actual_value] + pred_vals
    yu_full      = [last_actual_value] + pred_upper
    yl_full      = [last_actual_value] + pred_lower

    # Area interval kepercayaan
    fig.add_trace(go.Scatter(
        x=x_pred_full + x_pred_full[::-1],
        y=yu_full + yl_full[::-1],
        fill="toself",
        fillcolor=colors_pred.get(d,"#ccc"),
        opacity=0.25,
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
        name=f"{d} — interval",
    ))

    # Garis prediksi
    fig.add_trace(go.Scatter(
        x=x_pred_full, y=y_pred_full,
        mode="lines+markers", name=f"{d} — prediksi",
        line=dict(color=colors_dir.get(d,"#888"), width=2, dash="dash"),
        marker=dict(size=8, symbol="diamond"),
        hovertemplate=f"<b>Direction {d} (prediksi)</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
    ))

    # Simpan ringkasan prediksi
    for dt, val in zip(pred_dates, pred_vals):
        zone_lbl, zone_icon = get_zone(val, thr)
        pred_summary.append({
            "Direction": d,
            "Tanggal Prediksi": dt.strftime("%d-%b-%Y"),
            "Nilai Prediksi (mm/s)": f"{val:.3f}",
            "Trend": f"{'⬆️ Naik' if slope > 0 else '⬇️ Turun'} ({slope:+.4f} mm/s/hari)",
            "Zone Prediksi": f"{zone_icon} {zone_lbl}",
        })

# Threshold lines
fig.add_hline(y=thr["A"], line_dash="dot",  line_color="#22c55e", line_width=1,
              annotation_text=f"Zone A ({thr['A']})", annotation_position="top left")
fig.add_hline(y=thr["B"], line_dash="dot",  line_color="#eab308", line_width=1,
              annotation_text=f"Zone B ({thr['B']})", annotation_position="top left")
fig.add_hline(y=thr["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
              annotation_text=f"Zone C ({thr['C']})", annotation_position="top left")

# Shading area prediksi
if df_sel[df_sel["direction"].isin(sel_dir)].shape[0] > 0:
    last_date = df_sel["date"].max()
    fig.add_vrect(
        x0=last_date, x1=last_date + pd.Timedelta(days=n_days),
        fillcolor="rgba(100,100,200,0.05)", line_width=0,
        annotation_text="Zona prediksi", annotation_position="top left",
    )

fig.update_layout(
    title=f"Prediksi {n_days} hari — {sel_eq} · {sel_titik}",
    xaxis_title="Tanggal",
    yaxis_title="Vibrasi (mm/s)",
    height=480,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# ── Tabel ringkasan prediksi ──────────────────────────────────────────────────
if pred_summary:
    st.markdown("### 📋 Ringkasan Hasil Prediksi")
    df_pred = pd.DataFrame(pred_summary)

    # Highlight Zone D/C
    has_danger = any("ZONE D" in str(r) for r in df_pred["Zone Prediksi"])
    has_warn   = any("ZONE C" in str(r) for r in df_pred["Zone Prediksi"])
    if has_danger:
        st.error("⚠️ Prediksi menunjukkan kemungkinan **Zone D** dalam periode ini — rekomendasikan pemeriksaan segera.")
    elif has_warn:
        st.warning("⚠️ Prediksi menunjukkan kemungkinan **Zone C** — pantau lebih intensif.")
    else:
        st.success("✅ Prediksi menunjukkan vibrasi tetap dalam batas normal.")

    st.dataframe(df_pred, use_container_width=True, hide_index=True)

st.divider()
st.caption("""
**Catatan metodologi:** Prediksi menggunakan regresi linier sederhana (Ordinary Least Squares) 
berdasarkan seluruh data historis yang tersedia. Area abu-abu menunjukkan interval ±1 standar deviasi residual. 
Prediksi ini bersifat indikatif dan tidak menggantikan analisis vibrasi menyeluruh oleh teknisi.
""")
