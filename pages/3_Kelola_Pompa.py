import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, check_role,
    get_pump_runtime, init_pump_runtime, clear_runtime_caches,
    start_pump_runtime, stop_pump_runtime, edit_pump_hours,
    compute_running_hours, to_wib_naive, fmt_wib,
    now_wib,
    render_page_header, render_section_header, render_app_sidebar, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Kelola Jam Operasi — PLTU TBK",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

.badge-running { background: rgba(34,197,94,.15); color: #16a34a; border: 1px solid #16a34a50; padding: 4px 12px; border-radius: 99px; font-weight: 800; font-size: 12px; }
.badge-stopped { background: rgba(107,114,128,.15); color: #6b7280; border: 1px solid #6b728050; padding: 4px 12px; border-radius: 99px; font-weight: 800; font-size: 12px; }

.rh-kpi-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-bottom:14px; }
.rh-kpi { border-radius:12px; padding:12px 14px; border:1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
          background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color)); }
.rh-kpi .v { font-size:22px; font-weight:800; line-height:1.15; }
.rh-kpi .l { font-size:10.5px; font-weight:700; opacity:.6; text-transform:uppercase; letter-spacing:.05em; margin-top:2px; }
@media (max-width: 992px) { .rh-kpi-grid { grid-template-columns:repeat(2,1fr); } }
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("🛠️ Kelola Jam Operasi (Running Hours)")
st.caption("Semua waktu dicatat dalam WIB (GMT+7).")

# ── Helper ──────────────────────────────────────────────────────────────────
def flash(kind: str, msg: str) -> None:
    st.session_state.setdefault("_kp_flash", []).append((kind, msg))

def run_action(fn, *args, **kwargs) -> None:
    ok, msg = fn(*args, **kwargs)
    clear_runtime_caches()
    flash("success" if ok else "error", msg)
    st.rerun()

def fmt_duration(hours) -> str:
    if hours is None or pd.isna(hours):
        return "–"
    if hours < 1:
        return f"{hours * 60:.0f} mnt"
    if hours < 48:
        return f"{hours:.1f} jam"
    return f"{int(hours // 24)} hari {int(hours % 24)} jam"

def num(x) -> float:
    try:
        v = float(x)
        return 0.0 if pd.isna(v) else v
    except (TypeError, ValueError):
        return 0.0

for kind, msg in st.session_state.pop("_kp_flash", []):
    getattr(st, kind)(msg)

is_editor = check_role() == "editor"

# ── Data Setup ──────────────────────────────────────────────────────────────
df_hist = load_history()
df_rt = get_pump_runtime()

pair_set = set()
if not df_hist.empty:
    pair_set |= {(str(e), str(u)) for e, u in df_hist[["equipment", "unit"]].dropna().drop_duplicates().to_numpy()}
if not df_rt.empty:
    pair_set |= {(str(e), str(u)) for e, u in df_rt[["equipment", "unit"]].dropna().drop_duplicates().to_numpy()}
all_pairs = sorted(pair_set, key=lambda p: (p[1], p[0]))

if not all_pairs:
    st.info("📂 Belum ada data equipment. Silakan upload data terlebih dahulu di menu **Data & Kelola**.")
    st.stop()

col_f, _ = st.columns([2, 3])
with col_f:
    all_units = sorted({u for _, u in all_pairs})
    sel_unit_f = st.selectbox("🏭 **Filter Bagian Unit**", ["Semua Bagian Unit"] + all_units, key="kp_unit_filter")
pairs_f = [p for p in all_pairs if sel_unit_f == "Semua Bagian Unit" or p[1] == sel_unit_f]

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — RINGKASAN
# ═════════════════════════════════════════════════════════════════════════════
def build_summary(pairs, df_runtime) -> pd.DataFrame:
    rt = {}
    if not df_runtime.empty:
        rt = {(str(r["equipment"]), str(r["unit"])): r for r in df_runtime.to_dict("records")}
    now = now_wib()
    rows = []
    for eq, unit in pairs:
        r = rt.get((eq, unit))
        if r is None:
            rows.append({"Equipment": eq, "Bagian Unit": unit, "Status": "– Belum diatur",
                         "Total Jam": None, "Status Sejak": "–", "Durasi Status": "–"})
            continue
        status = r.get("status") or "stopped"
        try:
            since = to_wib_naive(r.get("status_changed_at"))
            dur = max((now - since).total_seconds() / 3600.0, 0.0)
            since_txt = fmt_wib(since)
        except Exception:
            dur, since_txt = None, "–"
        rows.append({
            "Equipment": eq, "Bagian Unit": unit,
            "Status": "🟢 Running" if status == "running" else "⚪ Stopped",
            "Total Jam": compute_running_hours(r),
            "Status Sejak": since_txt, "Durasi Status": fmt_duration(dur),
        })
    return pd.DataFrame(rows)

@st.fragment(run_every="30s")
def render_summary(pairs):
    df_sum = build_summary(pairs, get_pump_runtime())
    if df_sum.empty:
        st.info("Tidak ada equipment pada filter ini.")
        return

    total = len(df_sum)
    n_run = int((df_sum["Status"] == "🟢 Running").sum())
    n_stop = int((df_sum["Status"] == "⚪ Stopped").sum())
    n_unset = int((df_sum["Status"] == "– Belum diatur").sum())
    hours = df_sum["Total Jam"].dropna()
    tot_h = float(hours.sum()) if not hours.empty else 0.0
    avg_h = float(hours.mean()) if not hours.empty else 0.0

    st.markdown(f"""
<div class="rh-kpi-grid">
  <div class="rh-kpi"><div class="v">{total}</div><div class="l">Equipment Terdaftar</div></div>
  <div class="rh-kpi"><div class="v" style="color:#16a34a;">🟢 {n_run} <span style="font-size:13px;opacity:.6;">/ {total}</span></div><div class="l">Sedang Running</div></div>
  <div class="rh-kpi"><div class="v">⚪ {n_stop}</div><div class="l">Stopped</div></div>
  <div class="rh-kpi"><div class="v">{tot_h:,.0f} <span style="font-size:12px;opacity:.6;">jam</span></div><div class="l">Total Akumulasi · Rata-rata {avg_h:,.0f} jam</div></div>
  <div class="rh-kpi"><div class="v" style="color:{'#d97706' if n_unset else 'inherit'};">{n_unset}</div><div class="l">Belum Diatur</div></div>
</div>""", unsafe_allow_html=True)

    c_a, c_b = st.columns([1, 1])
    with c_a:
        status_filter = st.radio("Tampilkan", ["Semua", "Running", "Stopped", "Belum diatur"],
                                 horizontal=True, key="kp_sum_status")
    with c_b:
        search = st.text_input("Cari equipment", key="kp_sum_search", placeholder="mis. BFP, Fan, CWP ...")

    df_view = df_sum.copy()
    if status_filter != "Semua":
        key = {"Running": "Running", "Stopped": "Stopped", "Belum diatur": "Belum"}[status_filter]
        df_view = df_view[df_view["Status"].str.contains(key)]
    if search.strip():
        df_view = df_view[df_view["Equipment"].str.contains(search.strip(), case=False, regex=False)]
    df_view = df_view.sort_values("Total Jam", ascending=False, na_position="last")

    max_h = float(hours.max()) if not hours.empty and hours.max() > 0 else 1.0
    st.dataframe(
        df_view, hide_index=True, width="stretch",
        column_config={
            "Total Jam": st.column_config.ProgressColumn(
                "Total Jam", format="%.1f jam", min_value=0.0, max_value=max_h),
        },
    )

    if not hours.empty:
        render_section_header("Running Hours Tertinggi")
        top = df_sum[df_sum["Total Jam"].notna()].nlargest(15, "Total Jam").sort_values("Total Jam")
        labels = [f"{e} ({u})" for e, u in zip(top["Equipment"], top["Bagian Unit"])]
        colors = ["#16a34a" if s == "🟢 Running" else "#94a3b8" for s in top["Status"]]
        fig = go.Figure(go.Bar(
            x=top["Total Jam"], y=labels, orientation="h", marker_color=colors,
            text=[f"{h:,.0f}" for h in top["Total Jam"]], textposition="outside",
            hovertemplate="%{y}<br>%{x:,.1f} jam<extra></extra>",
        ))
        fig.update_layout(
            height=max(260, 28 * len(top) + 70),
            margin=dict(l=10, r=40, t=10, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Total Running Hours (jam) · hijau = sedang running",
                       showgrid=True, gridcolor="rgba(128,128,128,.15)"),
            font=dict(size=12, color="gray"),
        )
        st.plotly_chart(fig, width="stretch")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — KELOLA EQUIPMENT (RINGKAS)
# ═════════════════════════════════════════════════════════════════════════════
def render_manage(pairs):
    if not pairs:
        st.warning("Tidak ada equipment yang ditemukan.")
        return

    label_to_pair = {f"{e} ({u})": (e, u) for e, u in pairs}
    sel_label = st.selectbox("🎯 **Pilih Equipment:**", list(label_to_pair), key="kp_sel_eq")
    sel_eq, sel_unit = label_to_pair[sel_label]
    ek = f"{sel_eq}|{sel_unit}"

    rt_now = get_pump_runtime()
    match = rt_now[(rt_now["equipment"] == sel_eq) & (rt_now["unit"] == sel_unit)] if not rt_now.empty else pd.DataFrame()
    if match.empty:
        init_pump_runtime(sel_eq, sel_unit)
        clear_runtime_caches()
        row = {"status": "stopped", "accumulated_hours": 0.0, "status_changed_at": now_wib().isoformat()}
    else:
        row = match.iloc[0].to_dict()
        row["accumulated_hours"] = num(row.get("accumulated_hours"))

    status = row.get("status") or "stopped"
    hours_now = compute_running_hours(row)
    accum = num(row.get("accumulated_hours"))
    try:
        changed_at = to_wib_naive(row.get("status_changed_at"))
    except Exception:
        changed_at = None

    wib_now = now_wib()

    # Status & Metrik
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Status Saat Ini:**")
        if status == "running":
            st.markdown('<span class="badge-running">🟢 RUNNING</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-stopped">⚪ STOPPED</span>', unsafe_allow_html=True)
    with c2:
        st.markdown("**Total Jam Operasi:**")
        st.markdown(f"⏱️ **{hours_now:,.1f} jam**")
    with c3:
        st.markdown("**Sejak:**")
        since_txt = fmt_wib(changed_at) + " WIB" if changed_at is not None else "–"
        st.markdown(f"🕒 **{since_txt}**")

    st.markdown("---")

    # Kontrol Operasi Cepat (Start / Stop)
    col_ctrl, col_edit = st.columns(2)

    with col_ctrl:
        st.markdown("#### ⚡ Kontrol Cepat")
        if status == "running":
            st.caption(f"Sesi berjalan: **{fmt_duration(hours_now - accum)}**")
            if st.button("⏹️ Stop Sekarang", key=f"kp_stop_{ek}", type="primary", width="stretch"):
                run_action(stop_pump_runtime, sel_eq, sel_unit, wib_now, "Operator")
        else:
            st.caption("Peralatan sedang standby / tidak beroperasi.")
            if st.button("▶️ Start Sekarang", key=f"kp_start_{ek}", type="primary", width="stretch"):
                run_action(start_pump_runtime, sel_eq, sel_unit, wib_now, "Operator")

    with col_edit:
        st.markdown("#### ✏️ Sesuaikan Total Jam")
        new_hours = st.number_input(
            "Set Total Jam (DCS / Kalibrasi / Reset Overhaul ke 0)",
            min_value=0.0,
            value=round(hours_now, 1),
            step=1.0,
            key=f"kp_adj_{ek}",
        )
        if st.button("💾 Simpan Penyesuaian", key=f"kp_save_adj_{ek}", width="stretch"):
            if abs(new_hours - hours_now) < 0.05:
                st.info("Nilai jam sama dengan kondisi saat ini.")
            else:
                run_action(edit_pump_hours, sel_eq, sel_unit, new_total=new_hours, note="Koreksi manual", actor="Operator")

# ═════════════════════════════════════════════════════════════════════════════
# LAYOUT UTAMA
# ═════════════════════════════════════════════════════════════════════════════
tab_sum, tab_manage = st.tabs([
    "📊 Ringkasan Running Hours",
    "🛠️ Kelola Equipment",
])

with tab_sum:
    render_summary(pairs_f)

with tab_manage:
    if is_editor:
        render_manage(pairs_f)
    else:
        st.warning("🔒 Mengelola jam operasi hanya tersedia untuk Editor. Login melalui sidebar.")
