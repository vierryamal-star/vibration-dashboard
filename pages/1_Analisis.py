import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, get_zone, get_threshold, THRESHOLD, add_zone_cols, render_login_sidebar,
    get_temp_threshold, get_zone_temp,
    ZC, ZB, ZONE_LABEL, ZONE_ICON, UI, render_page_header, render_section_header, GLOBAL_UI_CSS,
)

st.set_page_config(page_title="Analisis Vibrasi — PLTU TBK", page_icon="📈", layout="wide")

# ── Global Styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

/* Stat card */
.stat-card {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color));
    height: 100%;
}
.stat-val { font-size: 22px; font-weight: 800; line-height: 1.1; margin-bottom: 4px; }
.stat-lbl { font-size: 11px; opacity: .65; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }

/* Zone badge inline */
.zbadge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 99px; padding: 3px 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .03em;
    border: 1px solid transparent;
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try:
        st.image("assets/logo_pln_ip.png", width=200)
    except Exception:
        pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                  label="📊 Monitor Vibrasi")
    st.page_link("pages/1_Analisis.py",     label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py",  label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py", label="🛠️ Kelola Pompa")
    st.divider()
    if st.button("🔄 Refresh Data", key="sb_refresh_a", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

render_page_header("📈 Analisis & Tren Vibrasi")

# ── Load Data ─────────────────────────────────────────────────────────────────
df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data historis. Silakan upload data di halaman **Data & Kelola**.")
    st.stop()

df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
df_hist = df_hist.dropna(subset=["date", "value"])

COLORS_DIR = {"H": "#3b82f6", "V": "#10b981", "A": "#f59e0b", "T": "#f97316"}
LS_LIST = ["solid", "dash", "dot", "dashdot"]
DAYS_MAP = {"7 Hari": 7, "30 Hari": 30, "90 Hari": 90, "180 Hari": 180}

def apply_range(df, col, rng, cf=None, ct=None):
    if df.empty or rng == "Semua Data":
        return df
    if rng == "Kustom":
        if cf is None or ct is None: return df
        s = pd.to_datetime(cf)
        e = pd.to_datetime(ct) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        return df[(df[col] >= s) & (df[col] <= e)]
    end = df[col].max()
    return df[(df[col] >= end - timedelta(days=DAYS_MAP[rng])) & (df[col] <= end)]

def plotly_theme():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12, color="gray"),
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.15)", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.15)", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font_size=11),
        hovermode="x unified",
        margin=dict(l=10, r=10, t=50, b=10),
    )

def add_threshold_lines(fig, thr):
    styles = [
        (thr["A"], "#2563eb", "dot",  1, f"Zone A ≤{thr['A']}"),
        (thr["B"], "#16a34a", "dot",  1, f"Zone B ≤{thr['B']}"),
        (thr["C"], "#dc2626", "dash", 1.5, f"Zone C ≤{thr['C']}"),
    ]
    for y, col, dash, w, lbl in styles:
        fig.add_hline(y=y, line_dash=dash, line_color=col, line_width=w,
                      annotation_text=lbl, annotation_position="top left",
                      annotation_font_size=10, annotation_font_color=col)
    return fig

def add_threshold_lines_temp(fig, thr):
    styles = [
        (thr["normal"], "#2563eb", "dot", 1, f"Normal ≤{thr['normal']}°C"),
        (thr["danger"], "#dc2626", "dash", 1.5, f"Danger >{thr['danger']}°C"),
    ]
    for y, col, dash, w, lbl in styles:
        fig.add_hline(y=y, line_dash=dash, line_color=col, line_width=w,
                      annotation_text=lbl, annotation_position="top left",
                      annotation_font_size=10, annotation_font_color=col)
    return fig

def rng_filter_ui(key_prefix):
    r_col1, r_col2 = st.columns([2, 2])
    with r_col1:
        rng = st.radio(
            "Rentang Waktu",
            ["7 Hari", "30 Hari", "90 Hari", "180 Hari", "Semua Data", "Kustom"],
            index=1, horizontal=True, key=f"{key_prefix}_rng"
        )
    cf = ct = None
    with r_col2:
        if rng == "Kustom":
            min_d = df_hist["date"].min().date()
            max_d = df_hist["date"].max().date()
            ca, cb = st.columns(2)
            with ca: cf = st.date_input("Dari", value=min_d, key=f"{key_prefix}_from")
            with cb: ct = st.date_input("Sampai", value=max_d, key=f"{key_prefix}_to")
    return rng, cf, ct

def df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# ── Tabs Navigasi Mode Analisis ───────────────────────────────────────────────
t_trend, t_compare, t_pred = st.tabs([
    "📈 Tren & Riwayat Detail",
    "⚖️ Komparasi Lintas Equipment",
    "🔮 Proyeksi & Prediksi Linier",
])

# ==============================================================================
# MODE 1: TREN & RIWAYAT DETAIL
# ==============================================================================
with t_trend:
    col_t1, col_t2, col_t3, col_t4 = st.columns([1.5, 2, 2, 1.5])
    
    with col_t1:
        dtype = st.selectbox("Parameter", ["📳 Vibrasi (mm/s)", "🌡️ Suhu (°C)"], key="td_dtype")
        is_temp = dtype.startswith("🌡️")
        df_mode1 = df_hist[df_hist["direction"] == "T"] if is_temp else df_hist[df_hist["direction"].isin(["H", "V", "A"])]

    with col_t2:
        unit_opts = sorted(df_mode1["unit"].dropna().unique())
        sel_unit = st.selectbox("Bagian Unit", unit_opts, key="td_unit")
        df_mode1 = df_mode1[df_mode1["unit"] == sel_unit]

    with col_t3:
        eq_opts = sorted(df_mode1["equipment"].dropna().unique())
        sel_eq = st.selectbox("Equipment", eq_opts, key="td_eq")
        df_mode1 = df_mode1[df_mode1["equipment"] == sel_eq]

    with col_t4:
        titik_opts = ["Semua Titik"] + sorted(df_mode1["titik"].dropna().unique())
        sel_titik = st.selectbox("Titik Ukur", titik_opts, key="td_titik")

    rng, cf, ct = rng_filter_ui("td")

    df_tr = df_mode1.copy()
    df_tr = apply_range(df_tr, "date", rng, cf, ct)
    if sel_titik != "Semua Titik":
        df_tr = df_tr[df_tr["titik"] == sel_titik]
    df_tr = df_tr.sort_values("date")

    if df_tr.empty:
        st.warning("Tidak ada data untuk kombinasi filter yang dipilih.")
    else:
        if not is_temp:
            thr = get_threshold(sel_eq)
        elif sel_titik != "Semua Titik":
            thr = get_temp_threshold(sel_eq, sel_titik)
        else:
            thr = None

        render_section_header("Ringkasan Statistik Pengukuran")
        
        stat_cols = st.columns(4)
        v_latest = df_tr["value"].iloc[-1]
        v_max = df_tr["value"].max()
        v_mean = df_tr["value"].mean()
        v_min = df_tr["value"].min()
        unit_sym = "°C" if is_temp else "mm/s"

        fmt_latest = f"{v_latest:.1f}" if is_temp else f"{v_latest:.3f}"
        fmt_max = f"{v_max:.1f}" if is_temp else f"{v_max:.3f}"
        fmt_mean = f"{v_mean:.1f}" if is_temp else f"{v_mean:.2f}"
        fmt_min = f"{v_min:.1f}" if is_temp else f"{v_min:.2f}"

        if not is_temp:
            zk, zi, zl = get_zone(v_latest, thr)
        else:
            t_thr_latest = thr if thr else get_temp_threshold(sel_eq, df_tr["titik"].iloc[-1])
            zk, zi, zl = get_zone_temp(v_latest, t_thr_latest)

        c_accent = ZC.get(zk, "#6b7280")
        
        with stat_cols[0]:
            st.markdown(f"""
<div class="stat-card" style="border-left:4px solid {c_accent};">
  <div class="stat-lbl">Nilai Terakhir</div>
  <div class="stat-val" style="color:{c_accent};">{fmt_latest} <span style="font-size:12px;opacity:.6;">{unit_sym}</span></div>
  <div style="font-size:11px;font-weight:700;color:{c_accent};">{zi} {zl}</div>
</div>""", unsafe_allow_html=True)
            
        with stat_cols[1]:
            st.markdown(f"""
<div class="stat-card">
  <div class="stat-lbl">Tertinggi (Peak)</div>
  <div class="stat-val">{fmt_max} <span style="font-size:12px;opacity:.6;">{unit_sym}</span></div>
  <div style="font-size:11px;opacity:.6;">Rata-rata: {fmt_mean} {unit_sym}</div>
</div>""", unsafe_allow_html=True)

        with stat_cols[2]:
            delta = (v_latest - df_tr["value"].iloc[-2]) if len(df_tr) >= 2 else 0.0
            d_col = "#dc2626" if delta > 0 else ("#16a34a" if delta < 0 else "#6b7280")
            d_sym = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
            fmt_delta = f"{abs(delta):.1f}" if is_temp else f"{abs(delta):.3f}"
            st.markdown(f"""
<div class="stat-card">
  <div class="stat-lbl">Deviasi vs Sebelumnya</div>
  <div class="stat-val" style="color:{d_col};">{d_sym} {fmt_delta}</div>
  <div style="font-size:11px;opacity:.6;">Terendah: {fmt_min} {unit_sym}</div>
</div>""", unsafe_allow_html=True)

        with stat_cols[3]:
            st.markdown(f"""
<div class="stat-card">
  <div class="stat-lbl">Jumlah Sampel</div>
  <div class="stat-val">{len(df_tr):,} <span style="font-size:12px;opacity:.6;">titik data</span></div>
  <div style="font-size:11px;opacity:.6;">Rentang: {df_tr['date'].dt.strftime('%d/%m/%y').iloc[0]} - {df_tr['date'].dt.strftime('%d/%m/%y').iloc[-1]}</div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

        render_section_header("Kurva Historis")
        fig = go.Figure()
        
        for i, t_val in enumerate(sorted(df_tr["titik"].unique())):
            for d in (["T"] if is_temp else ["H", "V", "A"]):
                sub = df_tr[(df_tr["titik"] == t_val) & (df_tr["direction"] == d)]
                if sub.empty: continue
                color = COLORS_DIR.get(d, "#3b82f6")
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers",
                    name=t_val if is_temp else f"{t_val} ({d})",
                    line=dict(color=color, width=2, dash=LS_LIST[i % 4]),
                    marker=dict(size=5),
                    hovertemplate=f"<b>{t_val} ({d})</b><br>Tgl: %{{x|%d %b %Y}}<br>Nilai: %{{y:.3f}} {unit_sym}<extra></extra>"
                ))

        if not is_temp:
            fig = add_threshold_lines(fig, thr)
        elif thr is not None:
            fig = add_threshold_lines_temp(fig, thr)

        fig.update_layout(
            title=dict(text=f"Tren {sel_eq} ({sel_unit})", font_size=14),
            xaxis_title="Tanggal Pengukuran",
            yaxis_title=f"Besaran ({unit_sym})",
            height=430,
            **plotly_theme()
        )
        st.plotly_chart(fig, width="stretch")

        with st.expander("📋 **Lihat Log & Ekspor Data Mentah**"):
            df_export = df_tr[["date", "equipment", "unit", "titik", "direction", "value"]].copy()
            df_export["date"] = df_export["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(df_export, width="stretch", hide_index=True)
            st.download_button(
                "⬇️ Unduh Data (CSV)",
                df_to_csv(df_export),
                file_name=f"analisis_{sel_eq}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch"
            )

# ==============================================================================
# MODE 2: KOMPARASI LINTAS EQUIPMENT
# ==============================================================================
with t_compare:
    cmp_dtype = st.radio("Parameter Perbandingan", ["📳 Vibrasi (mm/s)", "🌡️ Suhu (°C)"], horizontal=True, key="cmp_dtype_sel")
    is_temp_c = cmp_dtype.startswith("🌡️")
    df_cmp = df_hist[df_hist["direction"] == "T"] if is_temp_c else df_hist[df_hist["direction"].isin(["H", "V", "A"])]

    col_c1, col_c2 = st.columns(2)
    eq_all_list = sorted(df_cmp["equipment"].unique())

    with col_c1:
        st.markdown("##### 🔵 Equipment Primer (Referensi)")
        eq1 = st.selectbox("Pilih Mesin A", eq_all_list, key="cmp_eq1")
        t1_opts = ["Semua Titik"] + sorted(df_cmp[df_cmp["equipment"] == eq1]["titik"].unique())
        t1 = st.selectbox("Titik Ukur Mesin A", t1_opts, key="cmp_t1")

    with col_c2:
        st.markdown("##### 🔴 Equipment Pembanding")
        eq2 = st.selectbox("Pilih Mesin B", eq_all_list, index=min(1, len(eq_all_list)-1), key="cmp_eq2")
        t2_opts = ["Semua Titik"] + sorted(df_cmp[df_cmp["equipment"] == eq2]["titik"].unique())
        t2 = st.selectbox("Titik Ukur Mesin B", t2_opts, key="cmp_t2")

    rng_c, c_from, c_to = rng_filter_ui("cmp")
    overlay = st.toggle("Gabungkan dalam Satu Grafik (Overlay)", value=True, key="cmp_overlay_tog")

    def get_cmp_traces(eq, titik):
        df_sub = df_cmp[df_cmp["equipment"] == eq].copy()
        df_sub = apply_range(df_sub, "date", rng_c, c_from, c_to)
        if titik != "Semua Titik":
            df_sub = df_sub[df_sub["titik"] == titik]
        return df_sub.sort_values("date")

    df_sub1 = get_cmp_traces(eq1, t1)
    df_sub2 = get_cmp_traces(eq2, t2)

    unit_sym_c = "°C" if is_temp_c else "mm/s"

    if overlay:
        fig_cmp = go.Figure()
        for sub, label in [(df_sub1, eq1), (df_sub2, eq2)]:
            for t_v in sorted(sub["titik"].unique()):
                s_t = sub[sub["titik"] == t_v]
                fig_cmp.add_trace(go.Scatter(
                    x=s_t["date"], y=s_t["value"],
                    mode="lines+markers",
                    name=f"{label} - {t_v}",
                    marker=dict(size=5),
                    hovertemplate=f"<b>{label} ({t_v})</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} {unit_sym_c}<extra></extra>"
                ))
        fig_cmp.update_layout(title="Perbandingan Langsung", yaxis_title=f"Besaran ({unit_sym_c})", height=450, **plotly_theme())
        st.plotly_chart(fig_cmp, width="stretch")
    else:
        g1, g2 = st.columns(2)
        with g1:
            fig1 = go.Figure()
            for t_v in sorted(df_sub1["titik"].unique()):
                s_t = df_sub1[df_sub1["titik"] == t_v]
                fig1.add_trace(go.Scatter(x=s_t["date"], y=s_t["value"], mode="lines+markers", name=t_v))
            fig1.update_layout(title=f"{eq1}", yaxis_title=f"Besaran ({unit_sym_c})", height=380, **plotly_theme())
            st.plotly_chart(fig1, width="stretch")
        with g2:
            fig2 = go.Figure()
            for t_v in sorted(df_sub2["titik"].unique()):
                s_t = df_sub2[df_sub2["titik"] == t_v]
                fig2.add_trace(go.Scatter(x=s_t["date"], y=s_t["value"], mode="lines+markers", name=t_v))
            fig2.update_layout(title=f"{eq2}", yaxis_title=f"Besaran ({unit_sym_c})", height=380, **plotly_theme())
            st.plotly_chart(fig2, width="stretch")

# ==============================================================================
# MODE 3: PROYEKSI & PREDIKSI LINIER
# ==============================================================================
with t_pred:
    col_p1, col_p2, col_p3 = st.columns([2, 2, 1.5])
    with col_p1:
        eq_p = st.selectbox("Equipment Sasaran", sorted(df_hist["equipment"].unique()), key="pred_eq_sel")
    with col_p2:
        t_p_opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"] == eq_p]["titik"].unique())
        titik_p = st.selectbox("Titik Ukur", t_p_opts, key="pred_titik_sel")
    with col_p3:
        dirs_p = st.multiselect("Arah Getar", ["H", "V", "A"], default=["H", "V", "A"], key="pred_dir_sel")

    rng_p, p_from, p_to = rng_filter_ui("pred")
    n_forward = st.slider("Hari Prediksi ke Depan", 3, 60, 14, help="Pilih rentang horizon waktu prediksi regresi.")

    df_p_data = df_hist[(df_hist["equipment"] == eq_p) & (df_hist["direction"].isin(dirs_p))].copy()
    if titik_p != "Semua Titik":
        df_p_data = df_p_data[df_p_data["titik"] == titik_p]
    df_p_data = apply_range(df_p_data, "date", rng_p, p_from, p_to).sort_values("date")

    n_unique_dates = df_p_data["date"].dt.date.nunique()
    if len(df_p_data) < 3 or n_unique_dates < 2:
        st.warning("⚠️ Data historis tidak cukup untuk membuat regresi linier (minimal dibutuhkan data dari 2 tanggal berbeda). Coba ubah rentang waktu ke 'Semua Data'.")
    else:
        thr_p = get_threshold(eq_p)
        
        df_p_data["t_day"] = (df_p_data["date"] - df_p_data["date"].min()).dt.total_seconds() / 86400.0
        x = df_p_data["t_day"].values.astype(float)
        y = df_p_data["value"].values.astype(float)
        
        x_mean, y_mean = np.mean(x), np.mean(y)
        var_x = np.sum((x - x_mean) ** 2)
        
        if var_x > 1e-9:
            slope = np.sum((x - x_mean) * (y - y_mean)) / var_x
            intercept = y_mean - slope * x_mean
        else:
            slope = 0.0
            intercept = y_mean
        
        last_t = x.max()
        last_d = df_p_data["date"].max()
        
        fut_x = np.arange(last_t + 1, last_t + n_forward + 1)
        fut_dates = [last_d + pd.Timedelta(days=int(d - last_t)) for d in fut_x]
        fut_y = np.maximum(0, intercept + slope * fut_x)

        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(
            x=df_p_data["date"], y=df_p_data["value"],
            mode="lines+markers", name="Historis Aktual",
            line=dict(color="#3b82f6", width=2), marker=dict(size=6)
        ))
        
        fig_p.add_trace(go.Scatter(
            x=[last_d] + fut_dates, y=[y[-1]] + list(fut_y),
            mode="lines+markers", name="Proyeksi Tren",
            line=dict(color="#f59e0b", width=2, dash="dash"),
            marker=dict(symbol="diamond", size=6)
        ))
        
        fig_p = add_threshold_lines(fig_p, thr_p)
        fig_p.update_layout(
            title=f"Proyeksi Nilai Vibrasi {n_forward} Hari ke Depan ({eq_p})",
            yaxis_title="Vibrasi RMS (mm/s)",
            height=430,
            **plotly_theme()
        )
        st.plotly_chart(fig_p, width="stretch")

        roc_daily = slope
        st.info(f"""
📊 **Hasil Analisis Tren:**
* Laju Perubahan: **{roc_daily:+.4f} mm/s per hari**
* Arah Tren: **{'Meningkat (Perlu Perhatian)' if roc_daily > 0.005 else ('Menurun (Membaik)' if roc_daily < -0.005 else 'Stabil')}**
* Estimasi Nilai pada Hari ke-{n_forward}: **{fut_y[-1]:.3f} mm/s**
""")
