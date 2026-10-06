import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.colors import qualitative
from datetime import timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, get_zone, get_threshold,
    get_temp_threshold, get_zone_temp, now_wib,
    ZC, ZB, render_page_header, render_section_header,
    render_app_sidebar, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Analisis Vibrasi — PLTU TBK",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

.stat-card {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color));
    height: 100%;
}
.stat-val { font-size: 22px; font-weight: 800; line-height: 1.1; margin-bottom: 4px; }
.stat-lbl { font-size: 11px; opacity: .65; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

# Render Sidebar Terpusat
render_app_sidebar()

render_page_header("📈 Analisis & Tren Vibrasi")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data historis. Silakan upload data di halaman **Data & Kelola**.")
    st.stop()

df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"], errors="coerce")
df_hist = df_hist.dropna(subset=["date", "value"])

VIB_DIRS = ["H", "V", "A"]
COLORS_DIR = {"H": "#3b82f6", "V": "#10b981", "A": "#f59e0b", "T": "#f97316"}
LS_LIST = ["solid", "dash", "dot", "dashdot"]
DAYS_MAP = {"7 Hari": 7, "30 Hari": 30, "90 Hari": 90}
PALETTE = qualitative.Plotly
SLOPE_EPS = 0.005   # mm/s per hari — di bawah ini dianggap "stabil"


def apply_range(df, col, rng, cf=None, ct=None):
    if df.empty:
        return df
    if rng == "Kustom":
        if cf is None or ct is None:
            return df
        s = pd.to_datetime(cf)
        e = pd.to_datetime(ct) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        return df[(df[col] >= s) & (df[col] <= e)]

    # Batasi rentang berdasarkan pilihan (7, 30, atau 90 hari)
    days_limit = DAYS_MAP.get(rng, 90)
    end = df[col].max()
    return df[(df[col] >= end - timedelta(days=days_limit)) & (df[col] <= end)]


def plotly_theme():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12, color="gray"),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(128,128,128,.15)",
            zeroline=False,
            type="date",
            tickformat="%d %b %Y",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(128,128,128,.15)",
            zeroline=False
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            font_size=11
        ),
        hovermode="x unified",
        margin=dict(l=10, r=10, t=60, b=80),
    )


def chart_title(text, size=14, with_pos=False):
    # Plotly tidak mengenal CSS var(--text-color), jadi warna dibiarkan default tema.
    t = dict(text=text, font=dict(size=size))
    if with_pos:
        t.update(x=0, y=0.98, xanchor="left", yanchor="top")
    return t


def add_threshold_bands(fig, thr):
    fig.add_hrect(y0=0, y1=thr["A"], fillcolor="rgba(37,99,235,0.06)", line_width=0, annotation_text="Zone A (Good)", annotation_position="top left", annotation_font_size=9, annotation_font_color="#2563eb")
    fig.add_hrect(y0=thr["A"], y1=thr["B"], fillcolor="rgba(22,163,74,0.06)", line_width=0, annotation_text="Zone B (Pre-Warning)", annotation_position="top left", annotation_font_size=9, annotation_font_color="#16a34a")
    fig.add_hrect(y0=thr["B"], y1=thr["C"], fillcolor="rgba(217,119,6,0.06)", line_width=0, annotation_text="Zone C (Warning)", annotation_position="top left", annotation_font_size=9, annotation_font_color="#d97706")
    fig.add_hline(y=thr["C"], line_dash="dash", line_color="#dc2626", line_width=1.5, annotation_text="Zone D (Danger Limit)", annotation_position="top left", annotation_font_size=9, annotation_font_color="#dc2626")
    return fig


def add_threshold_bands_temp(fig, thr):
    fig.add_hrect(y0=0, y1=thr["normal"], fillcolor="rgba(37,99,235,0.06)", line_width=0, annotation_text="Normal Range", annotation_position="top left", annotation_font_size=9, annotation_font_color="#2563eb")
    fig.add_hrect(y0=thr["normal"], y1=thr["danger"], fillcolor="rgba(217,119,6,0.06)", line_width=0, annotation_text="Warning Range", annotation_position="top left", annotation_font_size=9, annotation_font_color="#d97706")
    fig.add_hline(y=thr["danger"], line_dash="dash", line_color="#dc2626", line_width=1.5, annotation_text="Critical Limit", annotation_position="top left", annotation_font_size=9, annotation_font_color="#dc2626")
    return fig


def rng_filter_ui(key_prefix):
    r_col1, r_col2 = st.columns([2, 2])
    with r_col1:
        rng = st.radio(
            "Rentang Waktu (Maks. 90 Hari)",
            ["90 Hari", "30 Hari", "7 Hari", "Kustom"],
            index=0,
            horizontal=True,
            key=f"{key_prefix}_rng"
        )
    cf = ct = None
    with r_col2:
        if rng == "Kustom":
            max_d = df_hist["date"].max().date()
            default_start = max(df_hist["date"].min().date(), max_d - timedelta(days=90))
            ca, cb = st.columns(2)
            with ca: cf = st.date_input("Dari", value=default_start, key=f"{key_prefix}_from")
            with cb: ct = st.date_input("Sampai", value=max_d, key=f"{key_prefix}_to")
    return rng, cf, ct


def df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


def stat_card(label, value_html, sub_html="", accent=None):
    border = f"border-left:4px solid {accent};" if accent else ""
    return f"""
<div class="stat-card" style="{border}">
  <div class="stat-lbl">{label}</div>
  {value_html}
  {sub_html}
</div>"""


# ==============================================================================
# MODE 1: TREN & RIWAYAT DETAIL
# ==============================================================================
def render_trend_tab():
    col_t1, col_t2, col_t3, col_t4 = st.columns([1.5, 2, 2, 1.5])

    with col_t1:
        dtype = st.selectbox("Parameter", ["📳 Vibrasi (mm/s)", "🌡️ Suhu (°C)"], key="td_dtype")
        is_temp = dtype.startswith("🌡️")
        df_mode1 = df_hist[df_hist["direction"] == "T"] if is_temp else df_hist[df_hist["direction"].isin(VIB_DIRS)]

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

    df_tr = apply_range(df_mode1.copy(), "date", rng, cf, ct)
    if sel_titik != "Semua Titik":
        df_tr = df_tr[df_tr["titik"] == sel_titik]
    df_tr = df_tr.sort_values("date")

    if df_tr.empty:
        st.warning("Tidak ada data untuk kombinasi filter yang dipilih.")
        return

    if not is_temp:
        thr = get_threshold(sel_eq)
    elif sel_titik != "Semua Titik":
        thr = get_temp_threshold(sel_eq, sel_titik)
    else:
        thr = None

    render_section_header("Ringkasan Statistik Pengukuran")

    unit_sym = "°C" if is_temp else "mm/s"
    dec = 1 if is_temp else 3
    dec_mean = 1 if is_temp else 2

    # "Nilai terakhir" dihitung PER SERI (titik × arah). Kalau ada beberapa seri,
    # yang ditampilkan adalah seri dengan nilai terakhir tertinggi — beserta
    # deviasinya terhadap pengukuran sebelumnya DARI SERI YANG SAMA.
    series_last = (
        df_tr.groupby(["titik", "direction"], as_index=False).tail(1).reset_index(drop=True)
    )
    focus = series_last.loc[series_last["value"].idxmax()]
    f_titik, f_dir = focus["titik"], focus["direction"]
    f_series = df_tr[(df_tr["titik"] == f_titik) & (df_tr["direction"] == f_dir)]
    v_latest = float(f_series["value"].iloc[-1])
    delta = float(v_latest - f_series["value"].iloc[-2]) if len(f_series) >= 2 else 0.0
    f_date = f_series["date"].iloc[-1].strftime("%d %b %Y")
    f_label = str(f_titik) if is_temp else f"{f_titik} ({f_dir})"
    multi = len(series_last) > 1

    v_max = float(df_tr["value"].max())
    v_mean = float(df_tr["value"].mean())
    v_min = float(df_tr["value"].min())

    if not is_temp:
        zk, zi, zl = get_zone(v_latest, thr)
    else:
        t_thr_latest = thr if thr else get_temp_threshold(sel_eq, f_titik)
        zk, zi, zl = get_zone_temp(v_latest, t_thr_latest)
    c_accent = ZC.get(zk, "#6b7280")

    d_col = "#dc2626" if delta > 0 else ("#16a34a" if delta < 0 else "#6b7280")
    d_sym = "↑" if delta > 0 else ("↓" if delta < 0 else "→")

    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.markdown(stat_card(
            "Terakhir · Tertinggi" if multi else "Nilai Terakhir",
            f'<div class="stat-val" style="color:{c_accent};">{v_latest:.{dec}f} <span style="font-size:12px;opacity:.6;">{unit_sym}</span></div>',
            f'<div style="font-size:11px;font-weight:700;color:{c_accent};">{zi} {zl}</div>'
            f'<div style="font-size:10px;opacity:.6;">{f_label} · {f_date}</div>',
            accent=c_accent,
        ), unsafe_allow_html=True)

    with stat_cols[1]:
        st.markdown(stat_card(
            "Tertinggi (Peak)",
            f'<div class="stat-val">{v_max:.{dec}f} <span style="font-size:12px;opacity:.6;">{unit_sym}</span></div>',
            f'<div style="font-size:11px;opacity:.6;">Rata-rata: {v_mean:.{dec_mean}f} {unit_sym}</div>',
        ), unsafe_allow_html=True)

    with stat_cols[2]:
        st.markdown(stat_card(
            "Deviasi vs Sebelumnya",
            f'<div class="stat-val" style="color:{d_col};">{d_sym} {abs(delta):.{dec}f}</div>',
            f'<div style="font-size:11px;opacity:.6;">Terendah: {v_min:.{dec_mean}f} {unit_sym}</div>'
            f'<div style="font-size:10px;opacity:.6;">Seri: {f_label}</div>',
        ), unsafe_allow_html=True)

    with stat_cols[3]:
        d_first = df_tr["date"].iloc[0].strftime("%d/%m/%y")
        d_last = df_tr["date"].iloc[-1].strftime("%d/%m/%y")
        st.markdown(stat_card(
            "Jumlah Sampel",
            f'<div class="stat-val">{len(df_tr):,} <span style="font-size:12px;opacity:.6;">titik data</span></div>',
            f'<div style="font-size:11px;opacity:.6;">Rentang: {d_first} - {d_last}</div>',
        ), unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    render_section_header("Kurva Historis")
    fig = go.Figure()

    for i, t_val in enumerate(sorted(df_tr["titik"].unique())):
        for d in (["T"] if is_temp else VIB_DIRS):
            sub = df_tr[(df_tr["titik"] == t_val) & (df_tr["direction"] == d)]
            if sub.empty:
                continue
            color = COLORS_DIR.get(d, "#3b82f6")
            fig.add_trace(go.Scatter(
                x=sub["date"], y=sub["value"],
                mode="lines+markers",
                name=t_val if is_temp else f"{t_val} ({d})",
                line=dict(color=color, width=2, dash=LS_LIST[i % 4]),
                marker=dict(size=6),
                hovertemplate=f"<b>{t_val} ({d})</b><br>Tgl: %{{x|%d %b %Y}}<br>Nilai: %{{y:.3f}} {unit_sym}<extra></extra>"
            ))

    if not is_temp:
        fig = add_threshold_bands(fig, thr)
    elif thr is not None:
        fig = add_threshold_bands_temp(fig, thr)

    fig.update_layout(
        title=chart_title(f"<b>Tren Vibrasi / Suhu:</b> {sel_eq} ({sel_unit})", with_pos=True),
        xaxis_title="Tanggal Pengukuran",
        yaxis_title=f"Besaran ({unit_sym})",
        height=460,
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
            file_name=f"analisis_{sel_eq}_{now_wib().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch"
        )


# ==============================================================================
# MODE 2: KOMPARASI LINTAS EQUIPMENT
# ==============================================================================
def _cmp_thresholds(fig, is_temp_c, targets):
    """
    Tambahkan band threshold ke grafik komparasi.
    targets: list of (equipment, titik). Band hanya digambar kalau tidak ambigu.
    """
    if is_temp_c:
        specific = [(e, t) for e, t in targets if t != "Semua Titik"]
        if len(specific) == len(targets):
            thrs = [get_temp_threshold(e, t) for e, t in specific]
            if all(x == thrs[0] for x in thrs):
                add_threshold_bands_temp(fig, thrs[0])
        return fig
    thrs = [get_threshold(e) for e, _ in targets]
    if all(x == thrs[0] for x in thrs):
        add_threshold_bands(fig, thrs[0])
    else:
        for (e, _), thr in zip(targets, thrs):
            fig.add_hline(y=thr["C"], line_dash="dash", line_color="#dc2626", line_width=1,
                          annotation_text=f"Danger {e}", annotation_position="top left",
                          annotation_font_size=9, annotation_font_color="#dc2626")
    return fig


def render_compare_tab():
    cmp_dtype = st.radio("Parameter Perbandingan", ["📳 Vibrasi (mm/s)", "🌡️ Suhu (°C)"], horizontal=True, key="cmp_dtype_sel")
    is_temp_c = cmp_dtype.startswith("🌡️")
    df_cmp = df_hist[df_hist["direction"] == "T"] if is_temp_c else df_hist[df_hist["direction"].isin(VIB_DIRS)]

    eq_all_list = sorted(df_cmp["equipment"].dropna().unique())
    if not eq_all_list:
        st.info("Belum ada data untuk parameter ini.")
        return

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown("##### 🔵 Equipment Primer (Referensi)")
        eq1 = st.selectbox("Pilih Mesin A", eq_all_list, key="cmp_eq1")
        t1_opts = ["Semua Titik"] + sorted(df_cmp[df_cmp["equipment"] == eq1]["titik"].dropna().unique())
        t1 = st.selectbox("Titik Ukur Mesin A", t1_opts, key="cmp_t1")

    with col_c2:
        st.markdown("##### 🔴 Equipment Pembanding")
        eq2 = st.selectbox("Pilih Mesin B", eq_all_list, index=min(1, len(eq_all_list) - 1), key="cmp_eq2")
        t2_opts = ["Semua Titik"] + sorted(df_cmp[df_cmp["equipment"] == eq2]["titik"].dropna().unique())
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

    def _add_traces(fig, sub, label, with_hover=True):
        for t_v in sorted(sub["titik"].unique()):
            s_t = sub[sub["titik"] == t_v]
            kw = dict(
                x=s_t["date"], y=s_t["value"], mode="lines+markers",
                name=f"{label} - {t_v}", marker=dict(size=5),
            )
            if with_hover:
                kw["hovertemplate"] = f"<b>{label} ({t_v})</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} {unit_sym_c}<extra></extra>"
            fig.add_trace(go.Scatter(**kw))

    if overlay:
        fig_cmp = go.Figure()
        _add_traces(fig_cmp, df_sub1, eq1)
        _add_traces(fig_cmp, df_sub2, eq2)
        _cmp_thresholds(fig_cmp, is_temp_c, [(eq1, t1), (eq2, t2)])
        fig_cmp.update_layout(
            title=chart_title("<b>Perbandingan Tren Langsung</b>"),
            yaxis_title=f"Besaran ({unit_sym_c})",
            height=460,
            **plotly_theme()
        )
        st.plotly_chart(fig_cmp, width="stretch")
    else:
        g1, g2 = st.columns(2)
        for col, sub, eq, t in [(g1, df_sub1, eq1, t1), (g2, df_sub2, eq2, t2)]:
            with col:
                fig_i = go.Figure()
                _add_traces(fig_i, sub, eq, with_hover=False)
                _cmp_thresholds(fig_i, is_temp_c, [(eq, t)])
                fig_i.update_layout(
                    title=chart_title(f"<b>{eq}</b>", size=13),
                    yaxis_title=f"Besaran ({unit_sym_c})",
                    height=380,
                    **plotly_theme()
                )
                st.plotly_chart(fig_i, width="stretch")


# ==============================================================================
# MODE 3: PROYEKSI & PREDIKSI LINIER
# ==============================================================================
def _fit_series(name, d, n_forward):
    """
    Regresi linier untuk SATU seri pengukuran (d: DataFrame terurut dengan kolom date, value).
    Return dict hasil, atau None kalau data tidak cukup (min. 3 data dari 2 tanggal berbeda).
    """
    d = d.sort_values("date")
    if len(d) < 3:
        return None
    t0 = d["date"].min()
    x = ((d["date"] - t0).dt.total_seconds() / 86400.0).to_numpy(dtype=float)
    y = d["value"].to_numpy(dtype=float)
    if np.ptp(x) < 1e-9:
        return None

    slope, intercept = np.polyfit(x, y, 1)
    if abs(slope) < 1e-9:      # hindari tampilan "-0.0000" pada seri datar
        slope = 0.0
    y_hat = intercept + slope * x
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else np.nan

    x_last = float(x.max())
    last_d = d["date"].max()
    fut_x = x_last + np.arange(1, n_forward + 1)
    return dict(
        name=name, n=len(d), dates=d["date"], values=y,
        slope=float(slope), intercept=float(intercept), r2=r2,
        last_date=last_d, last_val=float(y[-1]),
        fitted_last=float(intercept + slope * x_last),
        fut_dates=[last_d + pd.Timedelta(days=k) for k in range(1, n_forward + 1)],
        fut_y=np.maximum(0.0, intercept + slope * fut_x),
    )


def _days_to_limit(fit, limit):
    """Perkiraan hari sampai garis tren melewati `limit`. 0 = sudah lewat, inf = tidak tercapai."""
    if fit["last_val"] > limit:
        return 0.0
    if fit["slope"] <= 1e-9:
        return np.inf
    return max((limit - fit["fitted_last"]) / fit["slope"], 0.0)


def _fmt_days(days, last_date):
    if days <= 0:
        return "Sudah terlampaui"
    if np.isinf(days):
        return "Tidak tercapai (tren datar/turun)"
    if days > 365:
        return "> 1 tahun"
    return f"± {days:.0f} hari ({(last_date + pd.Timedelta(days=float(days))).strftime('%d %b %Y')})"


def _reliability(fit):
    if np.isnan(fit["r2"]):
        return "Stabil (data konstan)"
    if fit["n"] < 5 or fit["r2"] < 0.5:
        return "⚠️ Rendah"
    return "✔️ Baik"


def _trend_label(slope):
    return "Meningkat (Perlu Perhatian)" if slope > SLOPE_EPS else ("Menurun (Membaik)" if slope < -SLOPE_EPS else "Stabil")


def render_pred_tab():
    df_vib = df_hist[df_hist["direction"].isin(VIB_DIRS)]
    eq_list = sorted(df_vib["equipment"].dropna().unique())
    if not eq_list:
        st.info("Belum ada data vibrasi (H/V/A) untuk dibuat proyeksi.")
        return

    col_p1, col_p2, col_p3 = st.columns([2, 2, 1.5])
    with col_p1:
        eq_p = st.selectbox("Equipment Sasaran", eq_list, key="pred_eq_sel")
    with col_p2:
        t_p_opts = ["Semua Titik"] + sorted(df_vib[df_vib["equipment"] == eq_p]["titik"].dropna().unique())
        titik_p = st.selectbox("Titik Ukur", t_p_opts, key="pred_titik_sel")
    with col_p3:
        dirs_p = st.multiselect("Arah Getar", VIB_DIRS, default=VIB_DIRS, key="pred_dir_sel")

    col_m, col_h = st.columns([2, 2])
    with col_m:
        basis = st.radio(
            "Basis Regresi",
            ["Maksimum per tanggal (kasus terburuk)", "Per seri (titik × arah)"],
            horizontal=True, key="pred_basis",
            help="Regresi sebaiknya dilakukan pada satu seri pengukuran. 'Maksimum per tanggal' "
                 "memakai nilai tertinggi dari semua titik/arah terpilih (sama dengan acuan alarm "
                 "di kartu monitor). 'Per seri' membuat satu garis tren untuk tiap titik × arah.",
        )
    with col_h:
        n_forward = st.slider("Hari Prediksi ke Depan", 3, 30, 14, key="pred_n_forward",
                              help="Pilih rentang horizon waktu prediksi regresi.")

    rng_p, p_from, p_to = rng_filter_ui("pred")

    if not dirs_p:
        st.warning("Pilih minimal satu arah getar.")
        return

    df_p = df_vib[(df_vib["equipment"] == eq_p) & (df_vib["direction"].isin(dirs_p))].copy()
    if titik_p != "Semua Titik":
        df_p = df_p[df_p["titik"] == titik_p]
    df_p = apply_range(df_p, "date", rng_p, p_from, p_to).sort_values("date")

    if df_p.empty:
        st.warning("Tidak ada data pada filter yang dipilih.")
        return

    # Susun seri → regresi per seri
    fits, skipped = [], []
    if basis.startswith("Maksimum"):
        env = df_p.groupby("date", as_index=False)["value"].max()
        name = "Maks. " + (titik_p if titik_p != "Semua Titik" else "semua titik") + f" ({'/'.join(dirs_p)})"
        fit = _fit_series(name, env, n_forward)
        (fits if fit else skipped).append(fit or name)
    else:
        for (t_v, d_v), g in df_p.groupby(["titik", "direction"]):
            name = f"{t_v} ({d_v})"
            fit = _fit_series(name, g[["date", "value"]], n_forward)
            (fits if fit else skipped).append(fit or name)

    if not fits:
        st.warning(
            "⚠️ Data historis tidak cukup untuk regresi linier — dibutuhkan minimal 3 data "
            "dari 2 tanggal berbeda pada rentang waktu yang dipilih."
        )
        return

    thr_p = get_threshold(eq_p)

    # Grafik
    fig_p = go.Figure()
    for i, f in enumerate(fits):
        color = PALETTE[i % len(PALETTE)] if len(fits) > 1 else None
        hist_kw = dict(line=dict(width=2), marker=dict(size=6))
        proj_kw = dict(line=dict(width=2, dash="dash"), marker=dict(symbol="diamond", size=6))
        if color:
            hist_kw["line"]["color"] = color
            proj_kw["line"]["color"] = color
        else:
            hist_kw["line"]["color"] = "#3b82f6"
            proj_kw["line"]["color"] = "#f59e0b"
        fig_p.add_trace(go.Scatter(
            x=f["dates"], y=f["values"], mode="lines+markers",
            name=f"{f['name']} · aktual", **hist_kw))
        fig_p.add_trace(go.Scatter(
            x=[f["last_date"]] + f["fut_dates"], y=[f["last_val"]] + list(f["fut_y"]),
            mode="lines+markers", name=f"{f['name']} · proyeksi", **proj_kw))
    fig_p = add_threshold_bands(fig_p, thr_p)
    fig_p.update_layout(
        title=chart_title(f"<b>Proyeksi Tren Vibrasi {n_forward} Hari ke Depan</b> ({eq_p})"),
        yaxis_title="Vibrasi RMS (mm/s)",
        height=460,
        **plotly_theme()
    )
    st.plotly_chart(fig_p, width="stretch")

    # Tabel hasil per seri
    rows = []
    for f in fits:
        rows.append({
            "Seri": f["name"],
            "Data": f["n"],
            "Laju (mm/s/hari)": f"{f['slope']:+.4f}",
            "Arah Tren": _trend_label(f["slope"]),
            "R²": "–" if np.isnan(f["r2"]) else f"{f['r2']:.2f}",
            "Nilai Terakhir": f"{f['last_val']:.3f}",
            f"Estimasi +{n_forward} hari": f"{f['fut_y'][-1]:.3f}",
            f"Menuju Zone C (> {thr_p['B']:g})": _fmt_days(_days_to_limit(f, thr_p["B"]), f["last_date"]),
            f"Menuju Zone D (> {thr_p['C']:g})": _fmt_days(_days_to_limit(f, thr_p["C"]), f["last_date"]),
            "Keandalan": _reliability(f),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if skipped:
        st.caption("Dilewati (data kurang dari 3 titik / 2 tanggal): " + ", ".join(skipped))

    # Ringkasan untuk seri dengan proyeksi terburuk
    focus = max(fits, key=lambda f: f["fut_y"][-1])
    d_c = _days_to_limit(focus, thr_p["B"])
    d_d = _days_to_limit(focus, thr_p["C"])
    span = f"{focus['dates'].min().strftime('%d %b %Y')} – {focus['last_date'].strftime('%d %b %Y')}"
    r2_txt = "–" if np.isnan(focus["r2"]) else f"{focus['r2']:.2f}"

    msg = (
        f"📊 **Hasil Analisis Tren — {focus['name']}** (basis data: {span}, {focus['n']} data)\n"
        f"* Laju perubahan: **{focus['slope']:+.4f} mm/s per hari** — {_trend_label(focus['slope'])}\n"
        f"* Estimasi nilai pada hari ke-{n_forward}: **{focus['fut_y'][-1]:.3f} mm/s**\n"
        f"* Menuju Zone C (> {thr_p['B']:g} mm/s): **{_fmt_days(d_c, focus['last_date'])}**\n"
        f"* Menuju Zone D (> {thr_p['C']:g} mm/s): **{_fmt_days(d_d, focus['last_date'])}**\n"
        f"* Keandalan regresi: R² = {r2_txt} · {_reliability(focus)}"
    )
    if d_d <= 0:
        st.error(msg)
    elif d_c <= 0 or d_d <= n_forward:
        st.warning(msg)
    else:
        st.info(msg)
    st.caption(
        "Regresi linier sederhana pada data historis — hanya indikasi awal, bukan pengganti "
        "analisis spektrum/diagnosa. Hati-hati bila R² rendah atau jumlah data sedikit."
    )


# ==============================================================================
# TAB
# ==============================================================================
t_trend, t_compare, t_pred = st.tabs([
    "📈 Tren & Riwayat Detail",
    "⚖️ Komparasi Lintas Equipment",
    "🔮 Proyeksi & Prediksi Linier",
])
with t_trend:
    render_trend_tab()
with t_compare:
    render_compare_tab()
with t_pred:
    render_pred_tab()
