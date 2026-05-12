import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import load_history, get_zone, get_threshold, THRESHOLD, add_zone_cols, render_login_sidebar
 
st.set_page_config(page_title="Analisis — PLTU TBK", page_icon="📈", layout="wide")
st.markdown("""<style>[data-testid="stSidebarNav"]{display:none;}</style>""", unsafe_allow_html=True)
 
with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Monitoring Vibrasi · ISO 10816")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                  label="📊 Monitor")
    st.page_link("pages/1_Analisis.py",      label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py",   label="🗄️ Data & Kelola")
    render_login_sidebar()
 
st.markdown("## 📈 Analisis")
 
df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data.")
    st.stop()
 
df_hist["date"]  = pd.to_datetime(df_hist["date"],  errors="coerce")
df_hist["value"] = pd.to_numeric(df_hist["value"],  errors="coerce")
df_hist = df_hist.dropna(subset=["date","value"])
 
mode = st.radio(
    "Mode",
    ["📈 Trend Detail", "⚖️ Bandingkan 2 Equipment", "🔮 Prediksi Trend"],
    horizontal=True, key="analisis_mode"
)
 
colors_dir = {"H":"#3b82f6","V":"#10b981","A":"#f59e0b"}
ls_list    = ["solid","dash","dot","dashdot"]
 
def add_threshold_lines(fig, thr):
    fig.add_hline(y=thr["A"], line_dash="dot",  line_color="#3b82f6", line_width=1,
                  annotation_text=f"Accepted ({thr['A']})", annotation_position="top left")
    fig.add_hline(y=thr["B"], line_dash="dot",  line_color="#22c55e", line_width=1,
                  annotation_text=f"Pre Warning ({thr['B']})", annotation_position="top left")
    fig.add_hline(y=thr["C"], line_dash="dash", line_color="#ef4444", line_width=1.5,
                  annotation_text=f"Warning ({thr['C']})", annotation_position="top left")
    return fig
 
DAYS_MAP = {"7 Hari":7,"30 Hari":30,"90 Hari":90,"180 Hari":180}
 
def apply_range(df, col, rng, custom_from=None, custom_to=None):
    if df.empty: return df
    if rng == "Custom" and custom_from and custom_to:
        return df[(df[col].dt.date >= custom_from) & (df[col].dt.date <= custom_to)]
    if rng == "All": return df
    end   = df[col].max()
    start = end - timedelta(days=DAYS_MAP[rng])
    return df[(df[col]>=start)&(df[col]<=end)]
 
# ── MODE 1: Trend Detail ──────────────────────────────────────────────────────
if mode == "📈 Trend Detail":
    st.divider()
 
    # Baris 1: Equipment + Titik + Direction
    c1, c2, c3 = st.columns([2,2,1])
    with c1:
        sel_eq = st.selectbox("Equipment", sorted(df_hist["equipment"].unique()), key="td_eq")
    with c2:
        titik_opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==sel_eq]["titik"].unique())
        sel_titik  = st.selectbox("Titik Ukur", titik_opts, key="td_titik")
    with c3:
        sel_dir = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="td_dir")
 
    # Baris 2: Filter rentang waktu — pill
    rng_opts = ["7 Hari","30 Hari","90 Hari","180 Hari","All","Custom"]
    rng = st.radio("Rentang waktu", rng_opts, index=1, horizontal=True, key="td_rng", label_visibility="collapsed")
 
    custom_from = custom_to = None
    if rng == "Custom":
        min_date = df_hist["date"].min().date()
        max_date = df_hist["date"].max().date()
        col_cf, col_ct, _ = st.columns([1,1,2])
        with col_cf:
            custom_from = st.date_input("Dari", value=min_date, key="td_from")
        with col_ct:
            custom_to   = st.date_input("Sampai", value=max_date, key="td_to")
 
    df_tr = df_hist[df_hist["equipment"]==sel_eq].copy()
    df_tr = apply_range(df_tr, "date", rng, custom_from, custom_to)
    if sel_titik != "Semua Titik":
        df_tr = df_tr[df_tr["titik"]==sel_titik]
    if sel_dir:
        df_tr = df_tr[df_tr["direction"].isin(sel_dir)]
    df_tr = df_tr.sort_values("date")
 
    thr = get_threshold(sel_eq)
 
    if df_tr.empty:
        st.warning("Tidak ada data untuk pilihan ini.")
    else:
        fig = go.Figure()
        for i, titik in enumerate(sorted(df_tr["titik"].unique())):
            for d in sel_dir:
                sub = df_tr[(df_tr["titik"]==titik)&(df_tr["direction"]==d)]
                if sub.empty: continue
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers", name=f"{titik} – {d}",
                    line=dict(color=colors_dir.get(d,"#888"), width=2, dash=ls_list[i%4]),
                    marker=dict(size=6),
                    hovertemplate=f"<b>{titik} ({d})</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
                ))
        fig = add_threshold_lines(fig, thr)
        fig.update_layout(
            title=f"{sel_eq}" + (f" — {sel_titik}" if sel_titik != "Semua Titik" else ""),
            xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
            height=440, hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)
 
        # Tabel nilai
        st.markdown("**Tabel data**")
        df_tbl = df_tr[["date","titik","direction","value"]].copy()
        df_tbl["Status"] = df_tbl["value"].apply(lambda v: get_zone(v,thr)[1]+" "+get_zone(v,thr)[2])
        df_tbl["value"]  = df_tbl["value"].map(lambda v: f"{v:.3f}")
        df_tbl["date"]   = df_tbl["date"].dt.strftime("%d-%b-%Y")
        df_tbl = df_tbl.rename(columns={"date":"Tanggal","titik":"Titik","direction":"Dir","value":"mm/s"})
        st.dataframe(df_tbl, use_container_width=True, hide_index=True)
 
# ── MODE 2: Bandingkan 2 Equipment ───────────────────────────────────────────
elif mode == "⚖️ Bandingkan 2 Equipment":
    st.divider()
    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("**Equipment 1**")
        eq1    = st.selectbox("Equipment 1", sorted(df_hist["equipment"].unique()), key="cmp_eq1")
        t1opts = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==eq1]["titik"].unique())
        t1     = st.selectbox("Titik Ukur 1", t1opts, key="cmp_t1")
        d1     = st.multiselect("Direction 1", ["H","V","A"], default=["H"], key="cmp_d1")
    with bc2:
        st.markdown("**Equipment 2**")
        eq_list = sorted(df_hist["equipment"].unique())
        eq2     = st.selectbox("Equipment 2", eq_list, index=min(1,len(eq_list)-1), key="cmp_eq2")
        t2opts  = ["Semua Titik"] + sorted(df_hist[df_hist["equipment"]==eq2]["titik"].unique())
        t2      = st.selectbox("Titik Ukur 2", t2opts, key="cmp_t2")
        d2      = st.multiselect("Direction 2", ["H","V","A"], default=["H"], key="cmp_d2")
 
    rng_cmp = st.radio("Rentang waktu", ["7 Hari","30 Hari","90 Hari","180 Hari","All","Custom"],
                        index=1, horizontal=True, key="cmp_rng", label_visibility="collapsed")
    cmp_from = cmp_to = None
    if rng_cmp == "Custom":
        min_date = df_hist["date"].min().date()
        max_date = df_hist["date"].max().date()
        col_cf2, col_ct2, _ = st.columns([1,1,2])
        with col_cf2:
            cmp_from = st.date_input("Dari", value=min_date, key="cmp_from")
        with col_ct2:
            cmp_to   = st.date_input("Sampai", value=max_date, key="cmp_to")
 
    COLORS_EQ = [["#3b82f6","#1d4ed8"],["#ef4444","#b91c1c"]]
    fig_cmp = go.Figure()
 
    for idx,(eq,titik,dirs) in enumerate([(eq1,t1,d1),(eq2,t2,d2)]):
        df_eq = df_hist[df_hist["equipment"]==eq].copy()
        df_eq = apply_range(df_eq,"date",rng_cmp,cmp_from,cmp_to)
        if titik != "Semua Titik": df_eq = df_eq[df_eq["titik"]==titik]
        if dirs: df_eq = df_eq[df_eq["direction"].isin(dirs)]
        df_eq = df_eq.sort_values("date")
        ls = "solid" if idx==0 else "dash"
        for i,t_val in enumerate(sorted(df_eq["titik"].unique())):
            for d in dirs:
                sub = df_eq[(df_eq["titik"]==t_val)&(df_eq["direction"]==d)]
                if sub.empty: continue
                fig_cmp.add_trace(go.Scatter(
                    x=sub["date"], y=sub["value"],
                    mode="lines+markers",
                    name=f"[{idx+1}] {eq} – {t_val} ({d})",
                    line=dict(color=COLORS_EQ[idx][i%2], width=2, dash=ls),
                    marker=dict(size=6),
                    hovertemplate=f"<b>{eq} – {t_val} ({d})</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
                ))
 
    thr_ref = get_threshold(eq1)
    fig_cmp = add_threshold_lines(fig_cmp, thr_ref)
    fig_cmp.update_layout(
        title=f"Perbandingan: {eq1} vs {eq2}",
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
        height=460, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_cmp, use_container_width=True)
 
    # Tabel nilai terbaru kedua equipment
    st.markdown("**Nilai terbaru**")
    tc1, tc2 = st.columns(2)
    for col_out, eq, titik, dirs in [(tc1,eq1,t1,d1),(tc2,eq2,t2,d2)]:
        thr = get_threshold(eq)
        df_eq = df_hist[df_hist["equipment"]==eq].copy()
        if titik != "Semua Titik": df_eq = df_eq[df_eq["titik"]==titik]
        if dirs: df_eq = df_eq[df_eq["direction"].isin(dirs)]
        lat = df_eq.sort_values("date").groupby(["titik","direction"],as_index=False).last()
        lat["Status"] = lat["value"].apply(lambda v: get_zone(v,thr)[1]+" "+get_zone(v,thr)[2])
        lat["value"]  = lat["value"].map(lambda v: f"{v:.3f}")
        lat["date"]   = pd.to_datetime(lat["date"]).dt.strftime("%d-%b-%Y")
        lat = lat.rename(columns={"titik":"Titik","direction":"Dir","value":"mm/s","date":"Tanggal"})
        with col_out:
            st.markdown(f"**{eq}**")
            st.dataframe(lat[["Titik","Dir","mm/s","Status","Tanggal"]], use_container_width=True, hide_index=True)
 
# ── MODE 3: Prediksi Trend ────────────────────────────────────────────────────
else:
    st.divider()
    pc1, pc2, pc3 = st.columns([2,2,1])
    with pc1:
        sel_eq_p  = st.selectbox("Equipment", sorted(df_hist["equipment"].unique()), key="pred_eq")
    with pc2:
        titik_p   = sorted(df_hist[df_hist["equipment"]==sel_eq_p]["titik"].unique())
        sel_titik_p = st.selectbox("Titik Ukur", titik_p, key="pred_titik")
    with pc3:
        sel_dir_p = st.multiselect("Direction", ["H","V","A"], default=["H","V","A"], key="pred_dir")
 
    n_days = st.slider("Hari prediksi ke depan", 1, 7, 3)
 
    df_sel = df_hist[
        (df_hist["equipment"]==sel_eq_p) &
        (df_hist["titik"]==sel_titik_p) &
        (df_hist["direction"].isin(sel_dir_p))
    ].copy()
 
    if df_sel.empty:
        st.warning("Tidak ada data untuk pilihan ini.")
        st.stop()
 
    if df_sel.groupby("direction").size().min() < 3:
        st.warning("Data historis terlalu sedikit (minimum 3 titik per direction).")
        st.stop()
 
    thr_p = get_threshold(sel_eq_p)
    colors_pred = {"H":"#93c5fd","V":"#6ee7b7","A":"#fcd34d"}
 
    def predict(df_d, n):
        df_s = df_d.sort_values("date").copy()
        df_s["t"] = (df_s["date"]-df_s["date"].min()).dt.days.astype(float)
        x,y = df_s["t"].values, df_s["value"].values
        xb,yb = x.mean(),y.mean()
        slope = ((x-xb)*(y-yb)).sum()/((x-xb)**2).sum()
        intercept = yb-slope*xb
        last_t, last_date = x.max(), df_s["date"].max()
        pred_dates  = [last_date+pd.Timedelta(days=i+1) for i in range(n)]
        pred_t      = [last_t+i+1 for i in range(n)]
        pred_vals   = [max(0, intercept+slope*t) for t in pred_t]
        std_res     = (y-(intercept+slope*x)).std()
        pred_upper  = [v+std_res for v in pred_vals]
        pred_lower  = [max(0,v-std_res) for v in pred_vals]
        return pred_dates, pred_vals, pred_upper, pred_lower, slope
 
    fig_pred = go.Figure()
    pred_summary = []
 
    for d in sel_dir_p:
        df_d = df_sel[df_sel["direction"]==d].sort_values("date")
        if len(df_d) < 3: continue
        fig_pred.add_trace(go.Scatter(
            x=df_d["date"], y=df_d["value"],
            mode="lines+markers", name=f"{d} — historis",
            line=dict(color=colors_dir.get(d,"#888"), width=2),
            marker=dict(size=6),
            hovertemplate=f"<b>Direction {d} (historis)</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
        ))
        pred_dates, pred_vals, pred_upper, pred_lower, slope = predict(df_d, n_days)
        last_d, last_v = df_d["date"].iloc[-1], df_d["value"].iloc[-1]
        xf = [last_d]+pred_dates
        yf = [last_v]+pred_vals
        yuf= [last_v]+pred_upper
        ylf= [last_v]+pred_lower
        fig_pred.add_trace(go.Scatter(
            x=xf+xf[::-1], y=yuf+ylf[::-1],
            fill="toself", fillcolor=colors_pred.get(d,"#ccc"),
            opacity=0.2, line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig_pred.add_trace(go.Scatter(
            x=xf, y=yf, mode="lines+markers", name=f"{d} — prediksi",
            line=dict(color=colors_dir.get(d,"#888"), width=2, dash="dash"),
            marker=dict(size=8, symbol="diamond"),
            hovertemplate=f"<b>Direction {d} (prediksi)</b><br>%{{x|%d-%b-%Y}}<br>%{{y:.3f}} mm/s<extra></extra>",
        ))
        for dt,val in zip(pred_dates, pred_vals):
            zk,zi,zl = get_zone(val, thr_p)
            pred_summary.append({
                "Direction":d,
                "Tanggal Prediksi":dt.strftime("%d-%b-%Y"),
                "Nilai (mm/s)":f"{val:.3f}",
                "Trend":f"{'⬆️ Naik' if slope>0 else '⬇️ Turun'} ({slope:+.4f}/hari)",
                "Status":f"{zi} {zl}",
            })
 
    if not df_sel.empty:
        last_date_pred = df_sel["date"].max()
        fig_pred.add_vrect(
            x0=last_date_pred, x1=last_date_pred+pd.Timedelta(days=n_days),
            fillcolor="rgba(100,100,200,0.05)", line_width=0,
            annotation_text="Zona prediksi", annotation_position="top left",
        )
 
    fig_pred = add_threshold_lines(fig_pred, thr_p)
    fig_pred.update_layout(
        title=f"Prediksi {n_days} hari — {sel_eq_p} · {sel_titik_p}",
        xaxis_title="Tanggal", yaxis_title="Vibrasi (mm/s)",
        height=460, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_pred, use_container_width=True)
 
    if pred_summary:
        st.markdown("### Ringkasan Prediksi")
        df_pred = pd.DataFrame(pred_summary)
        has_d = any("Danger" in str(r) for r in df_pred["Status"])
        has_c = any("Warning" in str(r) for r in df_pred["Status"])
        if has_d:
            st.error("⚠️ Prediksi menunjukkan kemungkinan **Danger** — rekomendasikan pemeriksaan segera.")
        elif has_c:
            st.warning("⚠️ Prediksi menunjukkan kemungkinan **Warning** — pantau lebih intensif.")
        else:
            st.success("✅ Prediksi menunjukkan vibrasi tetap dalam batas normal.")
        st.dataframe(df_pred, use_container_width=True, hide_index=True)
 
    st.caption("Prediksi menggunakan regresi linier (OLS). Bersifat indikatif, tidak menggantikan analisis teknisi.")
