import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
import io, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import load_history, get_zone, get_threshold, THRESHOLD, add_zone_cols, render_login_sidebar

st.set_page_config(page_title="Analisis — PLTU TBK", page_icon="📈", layout="wide")

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }

/* Mode selector pill */
div[data-testid="stRadio"] > div { gap: 8px; }

/* KPI stat card */
.stat-card {
    border-radius: 10px;
    padding: 14px 16px;
    border: 1px solid rgba(128,128,128,.15);
    height: 100%;
}
.stat-val  { font-size: 24px; font-weight: 800; line-height: 1.1; margin-bottom: 3px; }
.stat-lbl  { font-size: 11px; opacity: .55; font-weight: 500; }
.stat-sub  { font-size: 11px; font-weight: 600; margin-top: 4px; }

/* Zone badge inline */
.zbadge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 99px; padding: 3px 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .03em;
    border: 1px solid transparent;
}

/* Tabel zone-aware */
.zt { width:100%; border-collapse:collapse; font-size:13px; }
.zt thead tr { border-bottom: 2px solid rgba(128,128,128,.15); }
.zt thead th {
    padding: 10px 12px; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: .08em; opacity: .5;
    text-align: left;
}
.zt tbody tr { border-bottom: 1px solid rgba(128,128,128,.07); }
.zt tbody tr:hover { filter: brightness(1.06); }
.zt td { padding: 9px 12px; vertical-align: middle; }

/* Section header accent */
.sec-head {
    display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.sec-bar {
    width: 4px; height: 20px; border-radius: 2px;
    background: linear-gradient(180deg, #2563eb, #0891b2);
    flex-shrink: 0;
}
.sec-title { font-size: 15px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ── Konstanta ─────────────────────────────────────────────────────────────────
ZC = {"ZONE A":"#3b82f6","ZONE B":"#22c55e","ZONE C":"#d97706","ZONE D":"#dc2626","N/A":"#6b7280"}
ZB = {"ZONE A":"rgba(59,130,246,.13)","ZONE B":"rgba(34,197,94,.13)",
      "ZONE C":"rgba(217,119,6,.14)","ZONE D":"rgba(220,38,38,.14)","N/A":"rgba(107,114,128,.1)"}
ZONE_LABEL = {"ZONE A":"Accepted","ZONE B":"Pre Warning","ZONE C":"Warning","ZONE D":"Danger","N/A":"N/A"}
ZONE_ICON  = {"ZONE A":"🔵","ZONE B":"🟢","ZONE C":"🟡","ZONE D":"🔴","N/A":"⬜"}
COLORS_DIR = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
LS_LIST    = ["solid","dash","dot","dashdot"]
DAYS_MAP   = {"7 Hari":7,"30 Hari":30,"90 Hari":90,"180 Hari":180}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    # UX #1: Highlight halaman Analisis sebagai aktif
    st.markdown("""
<style>
[data-testid="stPageLink"]:has(p:contains("📈 Analisis")) {
    background: rgba(59,130,246,.12);
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
}
</style>""", unsafe_allow_html=True)
    st.page_link("app.py",                 label="📊 Monitor")
    st.page_link("pages/1_Analisis.py",    label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py", label="🗄️ Data & Kelola")
    st.divider()
    if st.button("🔄 Refresh Data", key="sb_refresh_a", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

st.markdown("## 📈 Analisis Vibrasi")

# ── Load data ─────────────────────────────────────────────────────────────────
df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data.")
    st.stop()

df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
df_hist = df_hist.dropna(subset=["date","value"])

# ── Mode selector ─────────────────────────────────────────────────────────────
mode = st.radio(
    "Mode", ["📈 Trend Detail","⚖️ Bandingkan Equipment","🔮 Prediksi Trend"],
    horizontal=True, key="analisis_mode", label_visibility="collapsed"
)
# UX #2: Deskripsi singkat sesuai mode aktif
_mode_desc = {
    "📈 Trend Detail":       "Lihat grafik dan tabel historis untuk satu equipment & titik ukur.",
    "⚖️ Bandingkan Equipment": "Bandingkan vibrasi dua equipment secara berdampingan.",
    "🔮 Prediksi Trend":     "Proyeksi nilai vibrasi ke depan menggunakan regresi linier.",
}
st.caption(_mode_desc.get(mode, ""))
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.1)", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.1)", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font_size=11),
        hovermode="x unified",
        margin=dict(l=0, r=0, t=48, b=0),
    )

def rng_filter_ui(key_prefix):
    """Render rentang waktu radio + custom date. Return (rng, cf, ct)."""
    rng = st.radio("Rentang", ["7 Hari","30 Hari","90 Hari","180 Hari","All","Custom"],
                   index=1, horizontal=True, key=f"{key_prefix}_rng",
                   label_visibility="collapsed")
    cf = ct = None
    if rng == "Custom":
        min_d = df_hist["date"].min().date()
        max_d = df_hist["date"].max().date()
        ca, cb, _ = st.columns([1,1,2])
        with ca: cf = st.date_input("Dari",    value=min_d, key=f"{key_prefix}_from")
        with cb: ct = st.date_input("Sampai",  value=max_d, key=f"{key_prefix}_to")
        if cf > ct:
            st.error("Tanggal awal tidak boleh melebihi tanggal akhir.")
            st.stop()
    return rng, cf, ct

def zone_badge(zk, zi, zl):
    tc  = ZC.get(zk,"#6b7280"); bg = ZB.get(zk,"transparent")
    # UX #8: tampilkan key singkat + label lengkap untuk konsistensi
    full_lbl  = ZONE_LABEL.get(zk, zl)
    short_key = zk.replace("ZONE ","") if zk.startswith("ZONE") else zk
    return (f'<span class="zbadge" style="background:{bg};color:{tc};border-color:{tc}40">'
            f'{zi} {short_key} · {full_lbl}</span>')

def zone_row_bg(zk, i):
    if zk=="ZONE D": return "rgba(220,38,38,.07)"
    if zk=="ZONE C": return "rgba(217,119,6,.06)"
    return "rgba(128,128,128,.03)" if i%2==1 else "transparent"

def val_td(val, thr, show=True):
    if not show or val is None or pd.isna(val):
        return '<td style="text-align:center;padding:9px 10px;opacity:.3">–</td>'
    zk = get_zone(val,thr)[0]; tc = ZC.get(zk,"#6b7280"); bg = ZB.get(zk,"transparent")
    bar = min(int((val/4.5)*100),100)
    return (f'<td style="text-align:center;padding:9px 10px;background:{bg}">'
            f'<span style="font-size:13px;font-weight:700;color:{tc};font-variant-numeric:tabular-nums">'
            f'{val:.3f}</span>'
            f'<div style="margin-top:3px;height:2px;border-radius:1px;background:rgba(128,128,128,.18)">'
            f'<div style="height:2px;width:{bar}%;background:{tc};border-radius:1px"></div>'
            f'</div></td>')

def render_zone_table(df_tbl, thr, cols_show):
    """Render HTML tabel dengan highlight zone."""
    header = "".join(f'<th style="text-align:{"center" if c in ["Dir","mm/s","Max","Δ (mm/s)","Δ/hari"] else "left"}">{c}</th>'
                     for c in cols_show)
    rows = ""
    for i, (_, r) in enumerate(df_tbl.iterrows()):
        try:
            v = float(str(r.get("mm/s", r.get("Max",""))).replace("–",""))
        except: v = float("nan")
        zk,zi,zl = get_zone(v, thr) if not pd.isna(v) else ("N/A","⬜","N/A")
        rb = zone_row_bg(zk, i)
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
                    cells += (f'<td style="text-align:center;padding:9px 10px;font-weight:600;color:{dc}">'
                              f'{sym} {val_raw}</td>')
                except:
                    cells += f'<td style="text-align:center;padding:9px 10px">{val_raw}</td>'
            elif c == "Dir":
                dc2 = COLORS_DIR.get(str(val_raw),"#6b7280")
                cells += (f'<td style="text-align:center;padding:9px 10px;'
                          f'font-weight:700;color:{dc2}">{val_raw}</td>')
            else:
                cells += f'<td style="padding:9px 10px">{val_raw}</td>'
        rows += f'<tr style="background:{rb};border-bottom:1px solid rgba(128,128,128,.07)">{cells}</tr>'
    return (f'<div style="border-radius:10px;overflow:hidden;border:1px solid rgba(128,128,128,.15);'
            f'box-shadow:0 2px 12px rgba(0,0,0,.1)">'
            f'<table class="zt"><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>')

def df_to_csv(df): return df.to_csv(index=False).encode("utf-8")

def sec_header(title):
    st.markdown(f'<div class="sec-head"><div class="sec-bar"></div>'
                f'<span class="sec-title">{title}</span></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — TREND DETAIL
# ══════════════════════════════════════════════════════════════════════════════
if mode == "📈 Trend Detail":

    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        sel_eq = st.selectbox("Equipment", sorted(df_hist["equipment"].unique()), key="td_eq")
    with c2:
        titik_opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==sel_eq]["titik"].unique())
        sel_titik  = st.selectbox("Titik Ukur", titik_opts, key="td_titik")
    with c3:
        sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="td_dir")

    rng, cf, ct = rng_filter_ui("td")

    thr   = get_threshold(sel_eq)
    df_tr = df_hist[df_hist["equipment"]==sel_eq].copy()
    df_tr = apply_range(df_tr, "date", rng, cf, ct)
    if sel_titik != "Semua Titik":
        df_tr = df_tr[df_tr["titik"]==sel_titik]
    if sel_dir:
        df_tr = df_tr[df_tr["direction"].isin(sel_dir)]
    df_tr = df_tr.sort_values("date")

    if df_tr.empty:
        st.warning("Tidak ada data untuk pilihan ini.")
        st.stop()

    # ── KPI ringkas ───────────────────────────────────────────────────────────
    # Hitung per direction untuk titik terpilih
    kpi_data = []
    for d in (sel_dir or ["H","V","A"]):
        sub = df_tr[df_tr["direction"]==d].sort_values("date")
        if sub.empty: continue
        last_val  = sub["value"].iloc[-1]
        max_val   = sub["value"].max()
        min_val   = sub["value"].min()
        zk,zi,zl  = get_zone(last_val, thr)
        # delta vs pengukuran sebelumnya
        delta = last_val - sub["value"].iloc[-2] if len(sub)>=2 else None
        kpi_data.append(dict(d=d, last=last_val, mx=max_val, mn=min_val,
                             zk=zk, zi=zi, zl=zl, delta=delta))

    if kpi_data:
        sec_header("Kondisi Terkini")
        kcols = st.columns(len(kpi_data))
        for col, k in zip(kcols, kpi_data):
            tc  = ZC.get(k["zk"],"#6b7280")
            bg  = ZB.get(k["zk"],"transparent")
            dc  = COLORS_DIR.get(k["d"],"#6b7280")
            delta_html = ""
            if k["delta"] is not None:
                arrow = "↑" if k["delta"]>0 else ("↓" if k["delta"]<0 else "→")
                dcol  = "#dc2626" if k["delta"]>0 else ("#16a34a" if k["delta"]<0 else "#6b7280")
                delta_html = f'<div class="stat-sub" style="color:{dcol}">{arrow} {k["delta"]:+.3f} vs sebelumnya</div>'
            col.markdown(f"""
<div class="stat-card" style="background:{bg};border-color:{tc}30">
  <div style="font-size:11px;font-weight:700;color:{dc};opacity:.8;margin-bottom:6px">Direction {k['d']}</div>
  <div class="stat-val" style="color:{tc}">{k['last']:.3f} <span style="font-size:13px;font-weight:500;opacity:.6">mm/s</span></div>
  <div style="margin:4px 0">{zone_badge(k['zk'],k['zi'],k['zl'])}</div>
  <div style="font-size:10px;opacity:.5;margin-top:6px">Max: <b>{k['mx']:.3f}</b> · Min: <b>{k['mn']:.3f}</b></div>
  {delta_html}
</div>""", unsafe_allow_html=True)
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    # ── Chart ─────────────────────────────────────────────────────────────────
    sec_header("Grafik Trend")
    fig = go.Figure()
    for i, titik in enumerate(sorted(df_tr["titik"].unique())):
        for d in (sel_dir or []):
            sub = df_tr[(df_tr["titik"]==titik)&(df_tr["direction"]==d)]
            if sub.empty: continue
            fig.add_trace(go.Scatter(
                x=sub["date"], y=sub["value"],
                mode="lines+markers",
                name=f"{titik} – {d}",
                line=dict(color=COLORS_DIR.get(d,"#888"), width=2, dash=LS_LIST[i%4]),
                marker=dict(size=6),
                hovertemplate=f"<b>{titik} ({d})</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
            ))
    fig = add_threshold_lines(fig, thr)
    fig.update_layout(
        title=dict(text=sel_eq + (f" — {sel_titik}" if sel_titik!="Semua Titik" else ""), font_size=14),
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)", height=420,
        **plotly_theme()
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Tabel + Export ────────────────────────────────────────────────────────
    sec_header("Tabel Data")
    df_tbl = df_tr[["date","titik","direction","value"]].copy()
    df_tbl["mm/s"]   = df_tbl["value"].map(lambda v: f"{v:.3f}")
    df_tbl["Status"] = df_tbl.apply(lambda r: get_zone(r["value"],thr)[1]+" "+get_zone(r["value"],thr)[2], axis=1)
    df_tbl["Tanggal"]= df_tbl["date"].dt.strftime("%d %b %Y")
    df_tbl = df_tbl.rename(columns={"titik":"Titik","direction":"Dir"})
    show_cols = ["Tanggal","Titik","Dir","mm/s","Status"]

    st.markdown(render_zone_table(df_tbl, thr, show_cols), unsafe_allow_html=True)

    # Export
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    ex1, _ = st.columns([1, 3])
    with ex1:
        csv_bytes = df_to_csv(df_tbl[show_cols])
        st.download_button("⬇️ Download CSV", csv_bytes,
                           file_name=f"trend_{sel_eq.replace(' ','_')}.csv",
                           mime="text/csv", use_container_width=True)
    st.caption("💡 Download chart: gunakan tombol 📷 di sudut kanan atas grafik.")

# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — BANDINGKAN EQUIPMENT
# ══════════════════════════════════════════════════════════════════════════════
elif mode == "⚖️ Bandingkan Equipment":

    bc1, bc2 = st.columns(2)
    eq_list  = sorted(df_hist["equipment"].unique())

    with bc1:
        st.markdown("**Equipment 1**")
        eq1    = st.selectbox("Equipment 1", eq_list, key="cmp_eq1", label_visibility="collapsed")
        t1opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==eq1]["titik"].unique())
        t1     = st.selectbox("Titik Ukur", t1opts, key="cmp_t1")
        d1     = st.multiselect("Direction", ["H","V","A"], default=["H"], key="cmp_d1")
    with bc2:
        st.markdown("**Equipment 2**")
        eq2    = st.selectbox("Equipment 2", eq_list, index=min(1,len(eq_list)-1), key="cmp_eq2", label_visibility="collapsed")
        t2opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==eq2]["titik"].unique())
        t2     = st.selectbox("Titik Ukur", t2opts, key="cmp_t2")
        d2     = st.multiselect("Direction", ["H","V","A"], default=["H"], key="cmp_d2")

    rng_cmp, cmp_from, cmp_to = rng_filter_ui("cmp")

    # Toggle overlay
    overlay = st.toggle("Overlay dalam satu grafik", value=False, key="cmp_overlay")
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    pairs = [(eq1,t1,d1,"#3b82f6"),(eq2,t2,d2,"#ef4444")]

    def build_traces(eq, titik, dirs, base_color):
        df_eq = df_hist[df_hist["equipment"]==eq].copy()
        df_eq = apply_range(df_eq,"date",rng_cmp,cmp_from,cmp_to)
        if titik!="Semua Titik": df_eq = df_eq[df_eq["titik"]==titik]
        if dirs: df_eq = df_eq[df_eq["direction"].isin(dirs)]
        df_eq = df_eq.sort_values("date")
        traces = []
        for i,tv in enumerate(sorted(df_eq["titik"].unique())):
            for d in dirs:
                sub = df_eq[(df_eq["titik"]==tv)&(df_eq["direction"]==d)]
                if sub.empty: continue
                traces.append((sub, tv, d, LS_LIST[i%4]))
        return df_eq, traces

    if overlay:
        # Satu grafik bersama
        sec_header("Grafik Perbandingan (Overlay)")
        fig_ov = go.Figure()
        for eq, titik, dirs, main_col in pairs:
            thr_eq = get_threshold(eq)
            _, traces = build_traces(eq, titik, dirs, main_col)
            for sub, tv, d, ls in traces:
                fig_ov.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers", name=f"{eq} · {tv} ({d})",
                    line=dict(color=COLORS_DIR.get(d,main_col), width=2, dash=ls),
                    marker=dict(size=5),
                    hovertemplate=f"<b>{eq} · {tv} ({d})</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
                ))
        # pakai threshold equipment 1 sebagai referensi
        fig_ov = add_threshold_lines(fig_ov, get_threshold(eq1))
        fig_ov.update_layout(title="Perbandingan Vibrasi", xaxis_title="Tanggal",
                             yaxis_title="Vibrasi (mm/s)", height=420, **plotly_theme())
        st.plotly_chart(fig_ov, use_container_width=True)
    else:
        # Dua grafik terpisah side-by-side
        sec_header("Grafik Perbandingan")
        g1, g2 = st.columns(2)
        for col_g, (eq, titik, dirs, main_col) in zip([g1,g2], pairs):
            thr_eq = get_threshold(eq)
            df_eq, traces = build_traces(eq, titik, dirs, main_col)
            fig_eq = go.Figure()
            for sub, tv, d, ls in traces:
                fig_eq.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers", name=f"{tv} ({d})",
                    line=dict(color=COLORS_DIR.get(d,main_col), width=2, dash=ls),
                    marker=dict(size=5),
                    hovertemplate=f"<b>{tv} ({d})</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
                ))
            fig_eq = add_threshold_lines(fig_eq, thr_eq)
            fig_eq.update_layout(title=eq, xaxis_title="Tanggal",
                                 yaxis_title="Vibrasi (mm/s)", height=400, **plotly_theme())
            with col_g:
                st.plotly_chart(fig_eq, use_container_width=True)

    # ── Tabel nilai terbaru + export ──────────────────────────────────────────
    sec_header("Nilai Terbaru")
    tbl1, tbl2 = st.columns(2)
    all_export = []
    for col_t, (eq, titik, dirs, _) in zip([tbl1,tbl2], pairs):
        thr_eq = get_threshold(eq)
        df_eq  = df_hist[df_hist["equipment"]==eq].copy()
        if titik!="Semua Titik": df_eq=df_eq[df_eq["titik"]==titik]
        if dirs: df_eq=df_eq[df_eq["direction"].isin(dirs)]
        lat = df_eq.sort_values("date").groupby(["titik","direction"],as_index=False).last()
        lat["mm/s"]   = lat["value"].map(lambda v:f"{v:.3f}")
        lat["Status"] = lat["value"].apply(lambda v:get_zone(v,thr_eq)[1]+" "+get_zone(v,thr_eq)[2])
        lat["Tanggal"]= pd.to_datetime(lat["date"]).dt.strftime("%d %b %Y")
        lat = lat.rename(columns={"titik":"Titik","direction":"Dir"})
        all_export.append(lat[["Titik","Dir","mm/s","Status","Tanggal"]].assign(Equipment=eq))
        with col_t:
            st.markdown(f"**{eq}**")
            st.markdown(render_zone_table(lat, thr_eq, ["Titik","Dir","mm/s","Status","Tanggal"]),
                        unsafe_allow_html=True)

    # Export gabungan
    ex_df = pd.concat(all_export, ignore_index=True)
    st.download_button("⬇️ Download CSV Perbandingan", df_to_csv(ex_df),
                       file_name="perbandingan_equipment.csv", mime="text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# MODE 3 — PREDIKSI TREND
# ══════════════════════════════════════════════════════════════════════════════
else:
    pc1, pc2, pc3 = st.columns([2,2,1])
    with pc1:
        # FIX: filter equipment per unit yang sama dengan df_hist (tidak ada filter unit di sini)
        sel_eq_p = st.selectbox("Equipment", sorted(df_hist["equipment"].unique()), key="pred_eq")
    with pc2:
        titik_p_opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==sel_eq_p]["titik"].unique())
        sel_titik_p  = st.selectbox("Titik Ukur", titik_p_opts, key="pred_titik")
    with pc3:
        sel_dir_p = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="pred_dir")

    pred_rng, pred_from, pred_to = rng_filter_ui("pred")

    n_days = st.slider("Hari prediksi ke depan", 1, 90, 14,
                       help="Slide untuk mengatur berapa hari ke depan ingin diprediksi")

    thr_p  = get_threshold(sel_eq_p)
    df_sel = df_hist[
        (df_hist["equipment"]==sel_eq_p)&
        (df_hist["direction"].isin(sel_dir_p))
    ].copy()
    # Filter titik ukur jika bukan "Semua Titik"
    if sel_titik_p != "Semua Titik":
        df_sel = df_sel[df_sel["titik"]==sel_titik_p]

    # FIX: apply_range pakai global max date dari equipment tsb (bukan dari subset titik)
    # supaya window 30/90 hari konsisten untuk semua titik ukur, termasuk DE Pump
    # yang mungkin jarang diukur sehingga max date-nya lebih lama dari titik lain
    df_eq_all = df_hist[df_hist["equipment"]==sel_eq_p]
    global_end = df_eq_all["date"].max()

    def apply_range_fixed(df, end_date, rng, cf=None, ct=None):
        if df.empty: return df
        if rng == "Custom":
            if cf is None or ct is None: return df
            s = pd.to_datetime(cf)
            e = pd.to_datetime(ct) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            return df[(df["date"]>=s)&(df["date"]<=e)]
        if rng == "All": return df
        return df[(df["date"] >= end_date - timedelta(days=DAYS_MAP[rng])) &
                  (df["date"] <= end_date)]

    df_sel = apply_range_fixed(df_sel, global_end, pred_rng, pred_from, pred_to)

    if df_sel.empty:
        st.warning("Tidak ada data untuk pilihan ini.")
        st.stop()

    # Hitung jumlah data per direction untuk diagnostik
    dir_counts = {d: len(df_sel[df_sel["direction"]==d]) for d in sel_dir_p}

    # Filter hanya direction yang punya data cukup (≥ 3 titik)
    dir_valid   = [d for d in sel_dir_p if dir_counts.get(d, 0) >= 3]
    dir_skipped = [d for d in sel_dir_p if d not in dir_valid]

    if not dir_valid:
        # Tampilkan diagnostik lengkap agar user tahu penyebabnya
        st.warning(
            f"⚠️ Data historis terlalu sedikit dalam rentang **{pred_rng}** "
            f"untuk semua direction yang dipilih.\n\n"
            + "\n".join(
                f"- Direction **{d}**: ditemukan **{dir_counts.get(d,0)}** titik "
                f"{'✅' if dir_counts.get(d,0)>=3 else '❌ (min 3)'}"
                for d in sel_dir_p
            )
            + "\n\n💡 Coba perluas rentang waktu ke **90 Hari**, **180 Hari**, atau **All**."
        )
        st.stop()

    if dir_skipped:
        skipped_info = ", ".join(
            f"**{d}** ({dir_counts.get(d,0)} titik)" for d in dir_skipped
        )
        st.info(
            f"ℹ️ Direction {skipped_info} dilewati karena data < 3 titik "
            f"dalam rentang **{pred_rng}**. Perluas rentang waktu jika ingin "
            f"menyertakan direction ini."
        )

    sel_dir_p = dir_valid  # hanya proses direction yang valid

    # ── Fungsi prediksi linier ────────────────────────────────────────────────
    def predict(df_d, n):
        df_s = df_d.sort_values("date").copy()
        df_s["t"] = (df_s["date"]-df_s["date"].min()).dt.days.astype(float)
        x, y = df_s["t"].values, df_s["value"].values
        xb, yb = x.mean(), y.mean()
        slope     = ((x-xb)*(y-yb)).sum() / max(((x-xb)**2).sum(), 1e-9)
        intercept = yb - slope*xb
        last_t, last_date = x.max(), df_s["date"].max()
        pred_dates = [last_date+pd.Timedelta(days=i+1) for i in range(n)]
        pred_t     = [last_t+i+1 for i in range(n)]
        pred_vals  = [max(0, intercept+slope*t) for t in pred_t]
        std_res    = max((y-(intercept+slope*x)).std(), 0)
        pred_upper = [v+std_res for v in pred_vals]
        pred_lower = [max(0,v-std_res) for v in pred_vals]
        # Hitung rate of change
        n_obs      = len(df_s)
        obs_span   = (df_s["date"].max()-df_s["date"].min()).days or 1
        roc_per_day= slope                          # mm/s per hari
        roc_pct    = (slope / max(yb,0.001)) * 100  # % per hari relatif ke mean
        # Estimasi waktu ke threshold (days from last date)
        def days_to_thr(level):
            target = thr_p[level]
            last_v = y[-1]
            if last_v >= target: return -1   # sudah melewati threshold
            if slope <= 0: return None        # trend menurun / flat, tidak akan tercapai
            return (target - last_v) / slope
        eta_b = days_to_thr("B")
        eta_c = days_to_thr("C")
        return (pred_dates, pred_vals, pred_upper, pred_lower, slope,
                roc_per_day, roc_pct, eta_b, eta_c, n_obs)

    # ── KPI Rate of Change ────────────────────────────────────────────────────
    sec_header("Rate of Change")
    roc_cols = st.columns(len(sel_dir_p) if sel_dir_p else 1)
    roc_summaries = {}

    for col_roc, d in zip(roc_cols, sel_dir_p):
        df_d = df_sel[df_sel["direction"]==d].sort_values("date")
        if len(df_d) < 3: continue
        (pred_dates, pred_vals, pred_upper, pred_lower, slope,
         roc_per_day, roc_pct, eta_b, eta_c, n_obs) = predict(df_d, n_days)
        roc_summaries[d] = (pred_dates, pred_vals, pred_upper, pred_lower,
                            slope, roc_per_day, roc_pct, eta_b, eta_c)
        dc  = COLORS_DIR.get(d,"#6b7280")
        vc  = "#dc2626" if roc_per_day>0.01 else ("#16a34a" if roc_per_day<-0.01 else "#6b7280")
        arr = "↑" if roc_per_day>0.001 else ("↓" if roc_per_day<-0.001 else "→")
        # ETA badge
        eta_html = ""
        if eta_c == -1:
            eta_html += ('<div style="margin-top:6px;font-size:11px;color:#dc2626;font-weight:600">'
                         '🚨 Sudah melewati batas <b>Warning</b></div>')
        elif eta_b == -1:
            eta_html += ('<div style="margin-top:6px;font-size:11px;color:#d97706;font-weight:600">'
                         '⚠️ Sudah melewati batas <b>Pre Warning</b></div>')
        elif eta_c is not None:
            eta_html += (f'<div style="margin-top:6px;font-size:11px;color:#dc2626;font-weight:600">'
                         f'⚠️ Est. masuk Warning: <b>~{int(eta_c)} hari</b></div>')
        elif eta_b is not None:
            eta_html += (f'<div style="margin-top:6px;font-size:11px;color:#d97706;font-weight:600">'
                         f'⏱ Est. masuk Pre Warning: <b>~{int(eta_b)} hari</b></div>')
        else:
            eta_html += '<div style="margin-top:6px;font-size:11px;color:#16a34a;font-weight:600">✅ Trend aman</div>'

        col_roc.markdown(f"""
<div class="stat-card" style="border-color:{dc}30">
  <div style="font-size:11px;font-weight:700;color:{dc};margin-bottom:8px">Direction {d}</div>
  <div class="stat-val" style="color:{vc}">{arr} {abs(roc_per_day):.4f}
    <span style="font-size:12px;font-weight:500;opacity:.6">mm/s·hari</span></div>
  <div style="font-size:11px;opacity:.55;margin-top:3px">
    {abs(roc_pct):.2f}% per hari · basis {n_obs} titik
  </div>
  {eta_html}
</div>""", unsafe_allow_html=True)

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    # ── Chart prediksi ────────────────────────────────────────────────────────
    sec_header("Grafik Prediksi")
    fig_pred = go.Figure()
    PRED_COLORS = {"H":"#93c5fd","V":"#6ee7b7","A":"#fcd34d"}

    for d in sel_dir_p:
        if d not in roc_summaries: continue
        pred_dates, pred_vals, pred_upper, pred_lower, slope, *_ = roc_summaries[d]
        df_d = df_sel[df_sel["direction"]==d].sort_values("date")
        # Historis
        fig_pred.add_trace(go.Scatter(
            x=df_d["date"], y=df_d["value"],
            mode="lines+markers", name=f"{d} — historis",
            line=dict(color=COLORS_DIR.get(d,"#888"), width=2.5),
            marker=dict(size=6),
            hovertemplate=f"<b>{d} historis</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
        ))
        last_d, last_v = df_d["date"].iloc[-1], df_d["value"].iloc[-1]
        xf  = [last_d]+pred_dates
        yf  = [last_v]+pred_vals
        yuf = [last_v]+pred_upper
        ylf = [last_v]+pred_lower
        # CI band
        fig_pred.add_trace(go.Scatter(
            x=xf+xf[::-1], y=yuf+ylf[::-1],
            fill="toself", fillcolor=PRED_COLORS.get(d,"#ccc"),
            opacity=0.2, line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        # Garis prediksi
        fig_pred.add_trace(go.Scatter(
            x=xf, y=yf, mode="lines+markers", name=f"{d} — prediksi",
            line=dict(color=COLORS_DIR.get(d,"#888"), width=2, dash="dash"),
            marker=dict(size=8, symbol="diamond"),
            hovertemplate=f"<b>{d} prediksi</b><br>%{{x|%d %b %Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
        ))

    if not df_sel.empty:
        last_d_pred = df_sel["date"].max()
        fig_pred.add_vrect(
            x0=last_d_pred, x1=last_d_pred+pd.Timedelta(days=n_days),
            fillcolor="rgba(100,100,200,.04)", line_width=0,
            annotation_text="Zona Prediksi", annotation_position="top left",
            annotation_font_size=10,
        )

    fig_pred = add_threshold_lines(fig_pred, thr_p)
    fig_pred.update_layout(
        title=dict(text=f"Prediksi {n_days} hari — {sel_eq_p} · "
                        f"{'Semua Titik' if sel_titik_p=='Semua Titik' else sel_titik_p}",
                   font_size=14, pad=dict(b=8)),
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
        height=520,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.1)", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.1)", zeroline=False),
        hovermode="x unified",
        margin=dict(l=0, r=0, t=50, b=140),
        legend=dict(
            orientation="h", yanchor="top", y=-0.22,
            xanchor="left", x=0, font_size=11,
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
        ),
    )
    st.plotly_chart(fig_pred, use_container_width=True)

    # ── Alert prediksi ────────────────────────────────────────────────────────
    any_danger  = any(get_zone(v,thr_p)[0]=="ZONE D"
                      for d in roc_summaries for v in roc_summaries[d][1])
    any_warning = any(get_zone(v,thr_p)[0]=="ZONE C"
                      for d in roc_summaries for v in roc_summaries[d][1])
    if any_danger:
        st.error("⚠️ Prediksi menunjukkan kemungkinan **Danger** — rekomendasikan pemeriksaan segera.")
    elif any_warning:
        st.warning("⚠️ Prediksi menunjukkan kemungkinan **Warning** — pantau lebih intensif.")
    else:
        st.success("✅ Prediksi menunjukkan vibrasi tetap dalam batas normal.")

    # ── Tabel ringkasan prediksi ──────────────────────────────────────────────
    sec_header("Ringkasan Prediksi")
    pred_rows = []
    for d in sel_dir_p:
        if d not in roc_summaries: continue
        pred_dates, pred_vals, *rest = roc_summaries[d]
        # roc_summaries[d] = (pred_dates, pred_vals, pred_upper, pred_lower,
        #                      slope, roc_per_day, roc_pct, eta_b, eta_c)
        # rest[0]=pred_upper, rest[1]=pred_lower, rest[2]=slope, rest[3]=roc_per_day
        slope_d = rest[3]  # roc_per_day (mm/s per hari)
        for dt, val in zip(pred_dates, pred_vals):
            zk,zi,zl = get_zone(val, thr_p)
            pred_rows.append({
                "Dir": d,
                "Tanggal Prediksi": dt.strftime("%d %b %Y"),
                "mm/s": f"{val:.3f}",
                "Status": f"{zi} {zl}",
                "Δ/hari": f"{slope_d:+.4f}",
            })

    if pred_rows:
        df_pred = pd.DataFrame(pred_rows)
        st.markdown(render_zone_table(df_pred, thr_p, ["Dir","Tanggal Prediksi","mm/s","Status","Δ/hari"]),
                    unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        st.download_button("⬇️ Download CSV Prediksi", df_to_csv(df_pred),
                           file_name=f"prediksi_{sel_eq_p.replace(' ','_')}.csv", mime="text/csv")

    st.caption("Prediksi menggunakan regresi linier (OLS). Bersifat indikatif — tidak menggantikan analisis teknisi.")
