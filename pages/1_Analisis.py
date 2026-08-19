import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import timedelta
import io, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, get_zone, get_threshold, THRESHOLD, render_login_sidebar,
    get_temp_threshold, get_zone_temp,
)

st.set_page_config(page_title="Analisis — PLTU TBK", page_icon="📈", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
div[data-testid="stRadio"] > div { gap: 8px; }
.stat-card {
    border-radius: 10px; padding: 14px 16px;
    border: 1px solid rgba(128,128,128,.15); height: 100%;
}
.stat-val  { font-size: 24px; font-weight: 800; line-height: 1.1; margin-bottom: 3px; }
.stat-lbl  { font-size: 11px; opacity: .55; font-weight: 500; }
.stat-sub  { font-size: 11px; font-weight: 600; margin-top: 4px; }
.zbadge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 99px; padding: 3px 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .03em; border: 1px solid transparent;
}
.zt { width:100%; border-collapse:collapse; font-size:13px; }
.zt thead tr { border-bottom: 2px solid rgba(128,128,128,.15); }
.zt thead th {
    padding: 10px 12px; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .08em; opacity: .5; text-align: left;
}
.zt tbody tr { border-bottom: 1px solid rgba(128,128,128,.07); }
.zt tbody tr:hover { filter: brightness(1.06); }
.zt td { padding: 9px 12px; vertical-align: middle; }
.sec-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.sec-bar {
    width: 4px; height: 20px; border-radius: 2px;
    background: linear-gradient(180deg, #2563eb, #0891b2); flex-shrink: 0;
}
.sec-title { font-size: 15px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

ZC = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#d97706","ZONE D":"#dc2626","N/A":"#6b7280"}
ZB = {"ZONE A":"rgba(59,130,246,.13)","ZONE B":"rgba(34,197,94,.13)",
      "ZONE C":"rgba(217,119,6,.14)","ZONE D":"rgba(220,38,38,.14)","N/A":"rgba(107,114,128,.1)"}
ZONE_LABEL = {"ZONE A":"Accepted","ZONE B":"Pre Warning","ZONE C":"Warning","ZONE D":"Danger","N/A":"N/A"}
COLORS_DIR = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
LS_LIST    = ["solid","dash","dot","dashdot"]
DAYS_MAP   = {"7 Hari":7,"30 Hari":30,"90 Hari":90,"180 Hari":180}

with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                 label="📊 Monitor")
    st.page_link("pages/1_Analisis.py",    label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py", label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py",label="🛠️ Kelola Pompa")
    st.divider()
    if st.button("🔄 Refresh Data", key="sb_refresh_a", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

st.markdown("## 📈 Analisis Vibrasi")

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
df_hist = df_hist.dropna(subset=["date","value"])

mode = st.radio(
    "Mode", ["📈 Trend Detail","⚖️ Bandingkan Equipment","🔮 Prediksi Trend"],
    horizontal=True, key="analisis_mode", label_visibility="collapsed"
)

def apply_range(df, col, rng, cf=None, ct=None):
    if df.empty: return df
    if rng == "Custom":
        if cf is None or ct is None: return df
        s = pd.to_datetime(cf)
        e = pd.to_datetime(ct) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        return df[(df[col]>=s)&(df[col]<=e)]
    if rng == "All": return df
    end = df[col].max()
    return df[(df[col]>=end-timedelta(days=DAYS_MAP[rng]))&(df[col]<=end)]

def add_threshold_lines(fig, thr):
    styles = [
        (thr["A"], "#2563eb", "dot",  1,   f"Zone A ≤{thr['A']}"),
        (thr["B"], "#16a34a", "dot",  1,   f"Zone B ≤{thr['B']}"),
        (thr["C"], "#dc2626", "dash", 1.5, f"Zone C ≤{thr['C']}"),
    ]
    for y, col, dash, w, lbl in styles:
        fig.add_hline(y=y, line_dash=dash, line_color=col, line_width=w,
                      annotation_text=lbl, annotation_position="top left",
                      annotation_font_size=10, annotation_font_color=col)
    return fig

def plotly_theme():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.1)", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.1)", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font_size=11),
        hovermode="x unified",
        margin=dict(l=0, r=0, t=48, b=0),
    )

def rng_filter_ui(key_prefix):
    rng = st.radio("Rentang", ["7 Hari","30 Hari","90 Hari","180 Hari","All","Custom"],
                   index=1, horizontal=True, key=f"{key_prefix}_rng", label_visibility="collapsed")
    cf = ct = None
    if rng == "Custom":
        min_d = df_hist["date"].min().date()
        max_d = df_hist["date"].max().date()
        ca, cb, _ = st.columns([1,1,2])
        with ca: cf = st.date_input("Dari",   value=min_d, key=f"{key_prefix}_from")
        with cb: ct = st.date_input("Sampai", value=max_d, key=f"{key_prefix}_to")
        if cf > ct:
            st.error("Tanggal awal tidak boleh melebihi tanggal akhir.")
            st.stop()
    return rng, cf, ct

def zone_badge(zk, zi, zl):
    tc = ZC.get(zk,"#6b7280"); bg = ZB.get(zk,"transparent")
    full_lbl  = ZONE_LABEL.get(zk, zl)
    short_key = zk.replace("ZONE ","") if zk.startswith("ZONE") else zk
    return f'<span class="zbadge" style="background:{bg};color:{tc};border-color:{tc}40">{zi} {short_key} · {full_lbl}</span>'

def render_zone_table(df_tbl, thr, cols_show):
    header = "".join(f'<th style="text-align:{"center" if c in ["Dir","mm/s","Max","Δ (mm/s)","Δ/hari"] else "left"}">{c}</th>'
                     for c in cols_show)
    rows = []
    for i, (_, r) in enumerate(df_tbl.iterrows()):
        try: v = float(str(r.get("mm/s", r.get("Max",""))).replace("–",""))
        except: v = float("nan")
        zk,zi,zl = get_zone(v, thr) if not pd.isna(v) else ("N/A","⬜","N/A")
        rb = "rgba(220,38,38,.07)" if zk=="ZONE D" else ("rgba(217,119,6,.06)" if zk=="ZONE C" else ("rgba(128,128,128,.03)" if i%2==1 else "transparent"))
        tc = ZC.get(zk,"#6b7280"); bg = ZB.get(zk,"transparent")
        cells = ""
        for c in cols_show:
            val_raw = r.get(c,"")
            if c in ["mm/s","Max"]:
                try:
                    fv = float(str(val_raw).replace("–",""))
                    bar = min(int((fv/4.5)*100),100)
                    cells += (f'<td style="text-align:center;background:{bg};padding:9px 10px">'
                              f'<span style="font-weight:700;color:{tc};font-variant-numeric:tabular-nums">{val_raw}</span>'
                              f'<div style="margin-top:3px;height:2px;background:rgba(128,128,128,.15);border-radius:1px">'
                              f'<div style="height:2px;width:{bar}%;background:{tc};border-radius:1px"></div></div></td>')
                except:
                    cells += f'<td style="text-align:center;padding:9px 10px">{val_raw}</td>'
            elif c == "Status":
                cells += f'<td style="padding:9px 10px;text-align:left">{zone_badge(zk,zi,zl)}</td>'
            elif c in ["Δ (mm/s)","Δ/hari"]:
                try:
                    dv = float(str(val_raw).replace("+","").replace("–",""))
                    dc = "#dc2626" if dv>0 else ("#16a34a" if dv<0 else "#6b7280")
                    sym = "↑" if dv>0 else ("↓" if dv<0 else "→")
                    cells += f'<td style="text-align:center;padding:9px 10px;font-weight:600;color:{dc}">{sym} {val_raw}</td>'
                except:
                    cells += f'<td style="text-align:center;padding:9px 10px">{val_raw}</td>'
            elif c == "Dir":
                dc2 = COLORS_DIR.get(str(val_raw),"#6b7280")
                cells += f'<td style="text-align:center;padding:9px 10px;font-weight:700;color:{dc2}">{val_raw}</td>'
            else:
                cells += f'<td style="padding:9px 10px">{val_raw}</td>'
        rows.append(f'<tr style="background:{rb};border-bottom:1px solid rgba(128,128,128,.07)">{cells}</tr>')
    return (f'<div style="border-radius:10px;overflow:hidden;border:1px solid rgba(128,128,128,.15);'
            f'box-shadow:0 2px 12px rgba(0,0,0,.1)"><table class="zt"><thead><tr>{header}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')

def df_to_csv(df): return df.to_csv(index=False).encode("utf-8")

def sec_header(title):
    st.markdown(f'<div class="sec-head"><div class="sec-bar"></div>'
                f'<span class="sec-title">{title}</span></div>', unsafe_allow_html=True)

# ── MODE 1 ────────────────────────────────────────────────────────────────────
if mode == "📈 Trend Detail":
    dtype = st.radio("Jenis Data", ["📳 Vibrasi (mm/s)", "🌡️ Suhu (°C)"], horizontal=True, key="td_dtype")
    is_temp = dtype.startswith("🌡️")
    df_type = (df_hist[df_hist["direction"]=="T"] if is_temp else df_hist[df_hist["direction"].isin(["H","V","A"])])

    if df_type.empty:
        st.info("📂 Belum ada data.")
        st.stop()

    c1, c2, c3 = st.columns([2,2,1])
    with c1: sel_eq = st.selectbox("Equipment", sorted(df_type["equipment"].unique()), key="td_eq")
    with c2:
        titik_opts = ["Semua Titik"] + sorted(df_type[df_type["equipment"]==sel_eq]["titik"].unique())
        sel_titik  = st.selectbox("Titik Ukur", titik_opts, key="td_titik")
    with c3:
        if is_temp: sel_dir = ["T"]
        else: sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="td_dir")

    rng, cf, ct = rng_filter_ui("td")

    df_tr = df_type[df_type["equipment"]==sel_eq].copy()
    df_tr = apply_range(df_tr, "date", rng, cf, ct)
    if sel_titik != "Semua Titik": df_tr = df_tr[df_tr["titik"]==sel_titik]
    if sel_dir: df_tr = df_tr[df_tr["direction"].isin(sel_dir)]
    df_tr = df_tr.sort_values("date")

    if df_tr.empty:
        st.warning("Tidak ada data untuk pilihan ini.")
        st.stop()

    thr = get_threshold(sel_eq) if not is_temp else (get_temp_threshold(sel_eq, sel_titik) if sel_titik != "Semua Titik" else None)
    unit_label = "°C" if is_temp else "mm/s"

    sec_header("Grafik Trend")
    fig = go.Figure()
    for i, titik in enumerate(sorted(df_tr["titik"].unique())):
        for d in (sel_dir or []):
            sub = df_tr[(df_tr["titik"]==titik)&(df_tr["direction"]==d)]
            if sub.empty: continue
            trace_color = "#f97316" if is_temp else COLORS_DIR.get(d,"#888")
            fig.add_trace(go.Scatter(
                x=sub["date"], y=sub["value"], mode="lines+markers",
                name=titik if is_temp else f"{titik} – {d}",
                line=dict(color=trace_color, width=2, dash=LS_LIST[i%4]),
                marker=dict(size=6),
            ))
    if not is_temp and thr is not None:
        fig = add_threshold_lines(fig, thr)

    fig.update_layout(title=dict(text=sel_eq, font_size=14), xaxis_title="Tanggal",
                         yaxis_title=f"Vibrasi ({unit_label})", height=420, **plotly_theme())
    st.plotly_chart(fig, use_container_width=True)

# ── MODE 2 ────────────────────────────────────────────────────────────────────
elif mode == "⚖️ Bandingkan Equipment":
    eq_list = sorted(df_hist["equipment"].dropna().unique())
    bc1, bc2 = st.columns(2)
    with bc1: eq1 = st.selectbox("Equipment 1", eq_list, key="cmp_eq1")
    with bc2: eq2 = st.selectbox("Equipment 2", eq_list, index=min(1,len(eq_list)-1), key="cmp_eq2")
    rng_cmp, cmp_from, cmp_to = rng_filter_ui("cmp")
    
    sec_header("Perbandingan")
    g1, g2 = st.columns(2)
    for col_g, eq in zip([g1, g2], [eq1, eq2]):
        df_eq = apply_range(df_hist[df_hist["equipment"]==eq].sort_values("date"), "date", rng_cmp, cmp_from, cmp_to)
        fig_eq = go.Figure()
        for tv in df_eq["titik"].unique():
            sub = df_eq[df_eq["titik"]==tv]
            fig_eq.add_trace(go.Scatter(x=sub["date"], y=sub["value"], name=tv))
        fig_eq.update_layout(title=eq, height=380, **plotly_theme())
        with col_g: st.plotly_chart(fig_eq, use_container_width=True)

# ── MODE 3 (PREDIKSI + R-SQUARED) ─────────────────────────────────────────────
else:
    pc1, pc2, pc3 = st.columns([2,2,1])
    with pc1: sel_eq_p = st.selectbox("Equipment", sorted(df_hist["equipment"].unique()), key="pred_eq")
    with pc2:
        titik_p_opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==sel_eq_p]["titik"].unique())
        sel_titik_p  = st.selectbox("Titik Ukur", titik_p_opts, key="pred_titik")
    with pc3: sel_dir_p = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="pred_dir")

    pred_rng, pred_from, pred_to = rng_filter_ui("pred")
    n_days = st.slider("Hari prediksi ke depan", 1, 90, 14)
    thr_p  = get_threshold(sel_eq_p)

    df_sel = df_hist[(df_hist["equipment"]==sel_eq_p) & (df_hist["direction"].isin(sel_dir_p))].copy()
    if sel_titik_p != "Semua Titik": df_sel = df_sel[df_sel["titik"]==sel_titik_p]
    df_sel = apply_range(df_sel, "date", pred_rng, pred_from, pred_to)

    if df_sel.empty:
        st.warning("Tidak ada data untuk pilihan ini.")
        st.stop()

    def predict_ols(df_d, n):
        df_s = df_d.sort_values("date").copy()
        df_s["t"] = (df_s["date"]-df_s["date"].min()).dt.days.astype(float)
        x, y = df_s["t"].values, df_s["value"].values
        xb, yb = x.mean(), y.mean()
        slope     = ((x-xb)*(y-yb)).sum() / max(((x-xb)**2).sum(), 1e-9)
        intercept = yb - slope*xb
        
        # Hitung R-squared
        y_pred_hist = intercept + slope * x
        ss_res = ((y - y_pred_hist) ** 2).sum()
        ss_tot = ((y - yb) ** 2).sum()
        r2 = 1.0 - (ss_res / max(ss_tot, 1e-9)) if ss_tot > 0 else 0.0

        last_t, last_date = x.max(), df_s["date"].max()
        pred_dates = [last_date+pd.Timedelta(days=i+1) for i in range(n)]
        pred_t     = [last_t+i+1 for i in range(n)]
        pred_vals  = [max(0, intercept+slope*t) for t in pred_t]
        std_res    = max((y-(intercept+slope*x)).std(), 0)
        pred_upper = [v+std_res for v in pred_vals]
        pred_lower = [max(0,v-std_res) for v in pred_vals]
        return pred_dates, pred_vals, pred_upper, pred_lower, slope, r2

    sec_header("Rate of Change & Model Fit")
    roc_cols = st.columns(len(sel_dir_p) or 1)
    for col_roc, d in zip(roc_cols, sel_dir_p):
        df_d = df_sel[df_sel["direction"]==d].sort_values("date")
        if len(df_d) < 3:
            col_roc.caption(f"Direction {d}: data < 3 baris")
            continue
        p_dates, p_vals, p_up, p_low, slope, r2 = predict_ols(df_d, n_days)
        dc = COLORS_DIR.get(d,"#6b7280")
        col_roc.markdown(f"""
<div class="stat-card" style="border-color:{dc}30">
  <div style="font-size:11px;font-weight:700;color:{dc};margin-bottom:6px">Direction {d}</div>
  <div class="stat-val">{slope:+.4f} <span style="font-size:11px;opacity:.6">mm/s·hari</span></div>
  <div style="font-size:11px;opacity:.7">Model Fit (R²): <b>{r2:.2f}</b></div>
</div>""", unsafe_allow_html=True)
