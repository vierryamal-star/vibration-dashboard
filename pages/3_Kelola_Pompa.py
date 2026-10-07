import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, time as dtime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, check_role,
    get_pump_runtime, init_pump_runtime, clear_runtime_caches,
    start_pump_runtime, stop_pump_runtime, edit_pump_hours, reset_pump_runtime,
    validate_start, validate_stop, session_hours,
    compute_running_hours, get_pump_age, to_wib_naive, fmt_wib,
    get_pump_log, PUMP_LOG_SQL,
    get_bearing_install, update_bearing_install, BEARING_POSISI,
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

.badge-running { background: rgba(34,197,94,.15); color: #16a34a; border: 1px solid #16a34a50; padding: 3px 10px; border-radius: 99px; font-weight: 800; font-size: 11px; }
.badge-stopped { background: rgba(107,114,128,.15); color: #6b7280; border: 1px solid #6b728050; padding: 3px 10px; border-radius: 99px; font-weight: 800; font-size: 11px; }

.rh-kpi-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-bottom:14px; }
.rh-kpi { border-radius:12px; padding:12px 14px; border:1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
          background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color)); }
.rh-kpi .v { font-size:22px; font-weight:800; line-height:1.15; }
.rh-kpi .l { font-size:10.5px; font-weight:700; opacity:.6; text-transform:uppercase; letter-spacing:.05em; margin-top:2px; }
@media (max-width: 992px) { .rh-kpi-grid { grid-template-columns:repeat(2,1fr); } }
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

# Render Sidebar Terpusat
render_app_sidebar()

render_page_header("🛠️ Kelola Jam Operasi (Running Hours)")
st.caption("Semua waktu dicatat dalam WIB (GMT+7), dibulatkan ke menit.")


# ── Helper ──────────────────────────────────────────────────────────────────
def flash(kind: str, msg: str) -> None:
    """Pesan yang bertahan melewati st.rerun() (st.success + rerun langsung hilang)."""
    st.session_state.setdefault("_kp_flash", []).append((kind, msg))


def run_action(fn, *args, on_ok=None, **kwargs) -> None:
    ok, msg = fn(*args, **kwargs)
    clear_runtime_caches()
    flash("success" if ok else "error", msg)
    if ok and on_ok:
        on_ok()
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


def safe_date(value):
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()
    except Exception:
        return None


for kind, msg in st.session_state.pop("_kp_flash", []):
    getattr(st, kind)(msg)

is_editor = check_role() == "editor"

# ── Data ────────────────────────────────────────────────────────────────────
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
    if n_unset:
        st.caption(f"ℹ️ {n_unset} equipment belum punya catatan jam operasi — pilih equipment tersebut di tab "
                   "**Kelola Equipment** untuk mulai mencatat.")

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
    st.download_button(
        "⬇️ Unduh Ringkasan (CSV)",
        df_view.to_csv(index=False).encode("utf-8"),
        file_name=f"running_hours_{now_wib().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv", key="kp_sum_dl",
    )

    if not hours.empty:
        c1, c2 = st.columns([3, 2])
        with c1:
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
        with c2:
            render_section_header("Ringkasan per Bagian Unit")
            df_u = df_sum.copy()
            df_u["Running"] = (df_u["Status"] == "🟢 Running").astype(int)
            g = (df_u.groupby("Bagian Unit")
                 .agg(Equipment=("Equipment", "count"), Running=("Running", "sum"),
                      Total_Jam=("Total Jam", "sum"))
                 .reset_index().rename(columns={"Total_Jam": "Total Jam"}))
            st.dataframe(g, hide_index=True, width="stretch",
                         column_config={"Total Jam": st.column_config.NumberColumn(format="%.0f")})
    st.caption(f"Diperbarui otomatis tiap 30 detik · {now_wib().strftime('%d %b %Y %H:%M:%S')} WIB")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — KELOLA EQUIPMENT
# ═════════════════════════════════════════════════════════════════════════════
def render_manage(pairs):
    if not pairs:
        st.warning("Tidak ada equipment yang ditemukan.")
        return

    c_sel, c_act = st.columns([3, 2])
    with c_sel:
        label_to_pair = {f"{e} ({u})": (e, u) for e, u in pairs}     # dict, bukan parsing teks
        sel_label = st.selectbox("🎯 **Pilih Equipment yang Akan Dikelola:**", list(label_to_pair),
                                 key="kp_sel_eq")
        sel = label_to_pair[sel_label]
    with c_act:
        actor = st.text_input("👷 **Nama Petugas**", key="kp_actor",
                              placeholder="Wajib untuk Edit Jam & Reset",
                              help="Tercatat di Riwayat Aktivitas bersama setiap perubahan.").strip()
    sel_eq, sel_unit = sel
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

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Status Saat Ini:**")
        if status == "running":
            st.markdown('<span class="badge-running">🟢 RUNNING (BEROPERASI)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-stopped">⚪ STOPPED (STANDBY/MATI)</span>', unsafe_allow_html=True)
    with c2:
        st.markdown("**Total Running Hours:**")
        st.markdown(f"⏱️ **{hours_now:,.1f} jam**")
    with c3:
        st.markdown("**Running sejak:**" if status == "running" else "**Stop terakhir:**")
        since_txt = fmt_wib(changed_at) + " WIB" if changed_at is not None else "–"
        extra = f" · {fmt_duration(hours_now - accum)} berjalan" if status == "running" else ""
        st.markdown(f"🕒 **{since_txt}**{extra}")

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    tab_op, tab_edit, tab_bearing, tab_maint = st.tabs([
        "⏱️ Start / Stop",
        "✏️ Edit Running Hours",
        "🔩 Umur Bearing",
        "⚠️ Overhaul & Reset",
    ])
    wib_now = now_wib()
    today = wib_now.date()          # satu sumber waktu (hindari selisih di sekitar tengah malam)

    # ── Start / Stop ────────────────────────────────────────────────────────
    with tab_op:
        st.caption(
            "Aturan: **Stop tidak boleh sebelum waktu Start**, dan **Start tidak boleh sebelum Stop terakhir** "
            "(agar periode yang sama tidak terhitung dua kali). Waktu di masa depan juga ditolak. "
            "Saat Stop, durasi sesi otomatis ditambahkan ke total."
        )
        col_run, col_stop = st.columns(2)

        with col_run:
            st.markdown("#### ▶️ Mulai Operasi (Start)")
            if status == "running":
                st.info("Equipment sedang Running. Stop dulu sebelum Start lagi.")
            if st.button("⚡ Start Sekarang", key=f"kp_qstart_{ek}", width="stretch",
                         disabled=(status == "running")):
                run_action(start_pump_runtime, sel_eq, sel_unit, wib_now, actor)

            with st.expander("Opsi Tanggal & Jam Manual (Start)"):
                s_date = st.date_input("Tanggal Mulai", value=today, max_value=today, key=f"kp_s_date_{ek}")
                s_time = st.time_input("Jam Mulai", value=dtime(wib_now.hour, wib_now.minute), key=f"kp_s_time_{ek}")
                start_dt = datetime.combine(s_date, s_time)
                err_s = validate_start(row, start_dt) if status != "running" else None
                if status != "running":
                    if err_s:
                        st.error(err_s)
                    else:
                        st.caption(f"Running dihitung sejak **{fmt_wib(start_dt)} WIB** "
                                   f"(≈ {max((wib_now - start_dt).total_seconds() / 3600, 0):,.1f} jam sampai sekarang).")
                if st.button("💾 Simpan Manual Start", key=f"kp_mstart_{ek}", width="stretch",
                             disabled=(status == "running" or err_s is not None)):
                    run_action(start_pump_runtime, sel_eq, sel_unit, start_dt, actor)

        with col_stop:
            st.markdown("#### ⏹️ Hentikan Operasi (Stop)")
            if status != "running":
                st.info("Equipment sedang Stopped. Start dulu sebelum bisa di-Stop.")
            else:
                st.caption(f"Sesi berjalan sejak {fmt_wib(changed_at)} WIB → {fmt_duration(hours_now - accum)} "
                           f"akan ditambahkan ke total.")
            if st.button("⚡ Stop Sekarang", key=f"kp_qstop_{ek}", width="stretch",
                         disabled=(status != "running")):
                run_action(stop_pump_runtime, sel_eq, sel_unit, wib_now, actor)

            with st.expander("Opsi Tanggal & Jam Manual (Stop)"):
                min_d = min(changed_at.date(), today) if (status == "running" and changed_at is not None) else None
                e_date = st.date_input("Tanggal Berhenti", value=today,
                                       min_value=min_d, max_value=today, key=f"kp_e_date_{ek}")
                e_time = st.time_input("Jam Berhenti", value=dtime(wib_now.hour, wib_now.minute), key=f"kp_e_time_{ek}")
                stop_dt = datetime.combine(e_date, e_time)
                err_e = validate_stop(row, stop_dt) if status == "running" else None
                if status == "running":
                    if err_e:
                        st.error(err_e)
                    else:
                        add_h = session_hours(row, stop_dt)
                        st.caption(f"Durasi sesi **{add_h:,.2f} jam** akan ditambahkan → total "
                                   f"**{accum + add_h:,.1f} jam**.")
                if st.button("💾 Simpan Manual Stop", key=f"kp_mstop_{ek}", width="stretch",
                             disabled=(status != "running" or err_e is not None)):
                    run_action(stop_pump_runtime, sel_eq, sel_unit, stop_dt, actor)

    # ── Edit Running Hours ──────────────────────────────────────────────────
    with tab_edit:
        st.markdown("#### ✏️ Edit Running Hours")
        st.caption(
            "Untuk penyetelan awal (mis. menyamakan dengan counter DCS/logbook) atau koreksi kesalahan catat. "
            "Setiap perubahan **wajib beralasan** dan tercatat di tab Riwayat Aktivitas."
        )
        nonce = st.session_state.get("_kp_edit_nonce", 0)
        live_part = hours_now - accum        # bagian sesi yang sedang berjalan (0 jika Stopped)

        st.metric("Total Running Hours Saat Ini", f"{hours_now:,.1f} jam")
        mode = st.radio("Metode", ["Atur total ke nilai tertentu", "Tambah / kurangi jam (koreksi)"],
                        horizontal=True, key=f"kp_edit_mode_{ek}")
        if mode.startswith("Atur"):
            val = st.number_input("Total Running Hours baru (jam)", min_value=0.0,
                                  value=round(hours_now, 1), step=1.0, format="%.1f",
                                  key=f"kp_edit_total_{ek}_{nonce}")
            target = float(val)
        else:
            val = st.number_input("Penyesuaian (jam) — boleh negatif", value=0.0, step=1.0, format="%.1f",
                                  key=f"kp_edit_delta_{ek}_{nonce}")
            target = hours_now + float(val)
        note = st.text_input("Alasan perubahan (wajib)", key=f"kp_edit_note_{ek}_{nonce}",
                             placeholder="mis. Penyamaan dengan counter DCS / koreksi lupa stop 3 Okt").strip()

        problems = []
        if target < 0:
            problems.append("Total hasil perubahan tidak boleh negatif.")
        elif target - live_part < -1e-9:
            problems.append(f"Total tidak boleh lebih kecil dari sesi Running yang sedang berjalan "
                            f"({live_part:,.1f} jam). Stop dulu jika perlu.")
        if abs(target - hours_now) < 0.05:
            problems.append("Tidak ada perubahan.")
        if not actor:
            problems.append("Isi **Nama Petugas** di atas.")
        if not note:
            problems.append("Isi alasan perubahan.")

        st.info(f"Setelah disimpan: **{hours_now:,.1f} → {target:,.1f} jam** ({target - hours_now:+,.1f})")
        if status == "running":
            st.caption("Equipment sedang Running: sesi yang berjalan tetap dihitung otomatis, "
                       "jadi total yang tampil akan sama dengan nilai di atas.")
        for p in problems:
            st.warning(p, icon="⚠️")
        if st.button("💾 Simpan Perubahan Running Hours", key=f"kp_edit_save_{ek}", type="primary",
                     width="stretch", disabled=bool(problems)):
            reset_inputs = lambda: st.session_state.update(_kp_edit_nonce=nonce + 1)   # kosongkan isian jika sukses
            if mode.startswith("Atur"):
                run_action(edit_pump_hours, sel_eq, sel_unit, new_total=target, note=note, actor=actor,
                           on_ok=reset_inputs)
            else:
                run_action(edit_pump_hours, sel_eq, sel_unit, delta=float(val), note=note, actor=actor,
                           on_ok=reset_inputs)

    # ── Umur Bearing ────────────────────────────────────────────────────────
    with tab_bearing:
        st.markdown("#### 🔩 Penggantian & Umur Bearing per Posisi")
        st.caption("Tanggal pasang bearing dicatat terpisah per posisi.")
        df_bearing_all = get_bearing_install()
        b_cols = st.columns(4)
        for bi, posisi in enumerate(BEARING_POSISI):
            b_match = df_bearing_all[
                (df_bearing_all["equipment"] == sel_eq)
                & (df_bearing_all["unit"] == sel_unit)
                & (df_bearing_all["posisi"] == posisi)
            ] if not df_bearing_all.empty else pd.DataFrame()
            b_existing = safe_date(b_match.iloc[0].get("install_date") if not b_match.empty else None)
            b_age = get_pump_age(b_existing) if b_existing else None

            with b_cols[bi]:
                st.markdown(f"**{posisi}**")
                st.caption(f"Umur: **{b_age or 'belum diatur'}**")
                b_val = st.date_input(
                    "Tgl Pasang", value=b_existing, max_value=today,
                    key=f"b_input_{ek}_{bi}", label_visibility="collapsed",
                )
                if st.button("💾 Simpan", key=f"b_btn_{ek}_{bi}", width="stretch", disabled=(b_val is None)):
                    update_bearing_install(sel_eq, sel_unit, posisi, b_val)
                    clear_runtime_caches()
                    flash("success", f"Tanggal pasang bearing {posisi} tersimpan.")
                    st.rerun()

    # ── Overhaul & Reset ────────────────────────────────────────────────────
    with tab_maint:
        st.markdown("#### ⚠️ Reset Running Hours / Overhaul Unit")
        st.caption("Gunakan hanya jika peralatan fisik diganti baru atau selesai overhaul total. "
                   "Status menjadi Stopped dan total kembali 0. Nilai sebelumnya tersimpan di Riwayat.")
        st.error(f"Total saat ini **{hours_now:,.1f} jam** akan direset ke 0.0 jam.")
        reason = st.text_input("Alasan reset (wajib)", key=f"kp_reset_note_{ek}",
                               placeholder="mis. Overhaul total selesai, rotor diganti baru").strip()
        confirm = st.checkbox("Konfirmasi: kembalikan Running Hours ke 0.0 jam", key=f"kp_reset_chk_{ek}")
        if not actor:
            st.warning("Isi **Nama Petugas** di atas.", icon="⚠️")
        if st.button("🔄 Eksekusi Reset Jam Operasi", key=f"kp_reset_btn_{ek}", width="stretch",
                     disabled=not (confirm and reason and actor)):
            run_action(reset_pump_runtime, sel_eq, sel_unit, note=reason, actor=actor)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — RIWAYAT AKTIVITAS
# ═════════════════════════════════════════════════════════════════════════════
ACTION_LABEL = {
    "start": "▶️ Start", "stop": "⏹️ Stop",
    "edit_hours": "✏️ Edit Jam", "reset_hours": "🔄 Reset",
}


def render_history(pairs):
    df_log, err = get_pump_log(1000)
    if err:
        st.info("Riwayat aktivitas belum tersedia — tabel `pump_runtime_log` belum dibuat atau tidak dapat dibaca. "
                "Start/Stop/Edit tetap berjalan normal; hanya pencatatan riwayatnya yang belum aktif.")
        with st.expander("Buat tabel riwayat (jalankan sekali di Supabase → SQL Editor)"):
            st.code(PUMP_LOG_SQL, language="sql")
            st.caption(f"Detail teknis: {err[:200]}")
        return
    if df_log.empty:
        st.info("Belum ada aktivitas tercatat.")
        return

    ts = pd.to_datetime(df_log["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Jakarta")
    df_log = df_log.assign(
        Dicatat=ts.dt.strftime("%d %b %Y %H:%M"),
        Aksi=df_log["action"].map(ACTION_LABEL).fillna(df_log["action"]),
        Kejadian=pd.to_datetime(df_log["event_time"], errors="coerce").dt.strftime("%d %b %Y %H:%M"),
        Selisih=pd.to_numeric(df_log["hours_after"], errors="coerce") - pd.to_numeric(df_log["hours_before"], errors="coerce"),
    )
    allowed = {p[0] for p in pairs}
    df_log = df_log[df_log["equipment"].isin(allowed)] if pairs else df_log

    f1, f2 = st.columns(2)
    with f1:
        eq_pick = st.selectbox("Equipment", ["Semua"] + sorted(df_log["equipment"].dropna().unique()), key="kp_hist_eq")
    with f2:
        act_pick = st.multiselect("Jenis aksi", list(ACTION_LABEL.values()), default=list(ACTION_LABEL.values()),
                                  key="kp_hist_act")
    if eq_pick != "Semua":
        df_log = df_log[df_log["equipment"] == eq_pick]
    df_log = df_log[df_log["Aksi"].isin(act_pick)]

    df_show = df_log.rename(columns={
        "equipment": "Equipment", "unit": "Bagian Unit", "hours_before": "Jam Sebelum",
        "hours_after": "Jam Sesudah", "note": "Catatan", "actor": "Petugas",
    })[["Dicatat", "Equipment", "Bagian Unit", "Aksi", "Kejadian", "Jam Sebelum", "Jam Sesudah",
        "Selisih", "Catatan", "Petugas"]]
    st.dataframe(df_show, hide_index=True, width="stretch",
                 column_config={
                     "Jam Sebelum": st.column_config.NumberColumn(format="%.1f"),
                     "Jam Sesudah": st.column_config.NumberColumn(format="%.1f"),
                     "Selisih": st.column_config.NumberColumn(format="%+.1f"),
                 })
    st.caption("Untuk aksi Stop, Jam Sebelum/Sesudah = akumulasi sebelum & sesudah sesi ditambahkan. "
               "Untuk Edit/Reset = total running hours.")
    st.download_button("⬇️ Unduh Riwayat (CSV)", df_show.to_csv(index=False).encode("utf-8"),
                       file_name=f"riwayat_jam_operasi_{now_wib().strftime('%Y%m%d')}.csv",
                       mime="text/csv", key="kp_hist_dl")


# ═════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═════════════════════════════════════════════════════════════════════════════
tab_sum, tab_manage, tab_hist = st.tabs([
    "📊 Ringkasan Running Hours",
    "🛠️ Kelola Equipment",
    "📜 Riwayat Aktivitas",
])

with tab_sum:
    render_summary(pairs_f)

with tab_manage:
    if is_editor:
        render_manage(pairs_f)
    else:
        st.warning("🔒 Mengelola jam operasi hanya tersedia untuk Editor. Login melalui sidebar.")

with tab_hist:
    if is_editor:
        render_history(pairs_f)
    else:
        st.warning("🔒 Riwayat aktivitas hanya tersedia untuk Editor. Login melalui sidebar.")
