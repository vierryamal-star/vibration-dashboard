import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dtime
from utils import (
    load_history, render_login_sidebar, require_editor,
    get_pump_runtime, init_pump_runtime,
    start_pump_runtime, stop_pump_runtime,
    reset_pump_runtime, reset_pump_install_date,
    compute_running_hours, get_pump_age, update_pump_install_date,
    get_bearing_install, update_bearing_install, BEARING_POSISI,
)

st.set_page_config(
    page_title="Kelola Pompa — PLTU TBK",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sembunyikan navigasi multipage bawaan Streamlit (sama seperti di app.py) —
# tanpa ini, daftar halaman default muncul di ATAS logo/menu custom di sidebar.
st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar (konsisten dengan app.py) ─────────────────────────────────────────
with st.sidebar:
    try: st.image("assets/logo_pln_ip.png", width=200)
    except: pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Kelola Pompa")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                 label="📊 Monitor Vibrasi")
    st.page_link("pages/1_Analisis.py",    label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py", label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py",label="🛠️ Kelola Pompa")
    st.divider()
    if st.button("🔄 Refresh Data", key="kp_refresh", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

st.markdown("## 🛠️ Kelola Pompa")
st.caption("Catat tanggal & jam **mulai**/**berhenti** operasi dan tanggal instalasi (umur) "
           "untuk setiap equipment. Berlaku untuk **semua equipment**, tidak dibatasi jenisnya. "
           "Perubahan langsung terlihat di halaman **Monitor Vibrasi**.")

# Halaman ini khusus Editor — akan menghentikan render kalau bukan Editor
if not require_editor():
    st.stop()

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data equipment. Upload dulu di halaman **Data & Kelola**.")
    st.stop()

# ── Filter Unit (mempercepat input, tidak perlu scroll semua equipment) ──────
all_units_kp = sorted(df_hist["unit"].dropna().unique())
sel_unit_kp = st.radio("**🏭 Filter Unit**", ["All"] + all_units_kp,
                       horizontal=True, key="kp_unit_filter")

eq_unit_pairs = (
    df_hist[["equipment", "unit"]].dropna().drop_duplicates()
    .sort_values(["unit", "equipment"])
)
if sel_unit_kp != "All":
    eq_unit_pairs = eq_unit_pairs[eq_unit_pairs["unit"] == sel_unit_kp]

if eq_unit_pairs.empty:
    st.warning(f"Tidak ada equipment untuk unit **{sel_unit_kp}**.")
    st.stop()

def _de_nde_latest(equipment: str) -> pd.DataFrame:
    """Ambil nilai TERBARU per titik ukur yang mengandung 'DE' (mencakup DE & NDE)
    untuk equipment ini — dipivot titik x direction supaya ringkas dibaca."""
    df_eq = df_hist[df_hist["equipment"]==equipment].copy()
    if df_eq.empty:
        return pd.DataFrame()
    df_eq["date"] = pd.to_datetime(df_eq["date"], errors="coerce")
    df_eq = df_eq[df_eq["titik"].astype(str).str.upper().str.contains("DE")]
    if df_eq.empty:
        return pd.DataFrame()
    df_eq = df_eq.sort_values("date", ascending=False)
    latest = df_eq.groupby(["titik","direction"], as_index=False).first()
    try:
        piv = latest.pivot(index="titik", columns="direction", values="value")
        return piv
    except Exception:
        return latest[["titik","direction","value"]]

df_runtime_all = get_pump_runtime()
df_bearing_all = get_bearing_install()

st.divider()

for _, r in eq_unit_pairs.iterrows():
    eq, unit = r["equipment"], r["unit"]
    match = df_runtime_all[(df_runtime_all["equipment"]==eq) & (df_runtime_all["unit"]==unit)]
    if match.empty:
        init_pump_runtime(eq, unit)
        st.cache_data.clear()
        row_data = {"status": "stopped", "accumulated_hours": 0.0,
                    "status_changed_at": datetime.now().isoformat(), "install_date": None}
    else:
        row_data = match.iloc[0].to_dict()

    status    = row_data.get("status", "stopped")
    hours_now = compute_running_hours(row_data)
    age       = get_pump_age(row_data.get("install_date"))

    with st.expander(
        f"⚙️ **{eq}** · {unit}  —  "
        f"{'🟢 Running' if status=='running' else '⚪ Stopped'} · "
        f"⏱️ {hours_now:,.1f} jam · 📅 {age or 'umur belum diisi'}"
    ):
        # ── Data vibrasi titik DE & NDE (referensi, read-only) ────────────────
        st.markdown("**📍 Data Vibrasi Terkini — Titik DE & NDE**")
        de_nde_df = _de_nde_latest(eq)
        if de_nde_df.empty:
            st.caption("Tidak ada titik ukur DE/NDE untuk equipment ini.")
        else:
            st.dataframe(de_nde_df, width="stretch")

        c1, c2, c3 = st.columns(3)

        # ── Catat waktu MULAI ─────────────────────────────────────────────────
        with c1:
            st.markdown("**▶️ Mulai Operasi**")
            start_d = st.date_input("Tanggal mulai", value=date.today(), key=f"kp_start_d_{eq}_{unit}")
            start_t = st.time_input("Jam mulai", value=dtime(0,0), key=f"kp_start_t_{eq}_{unit}")
            if st.button("💾 Catat Mulai", key=f"kp_start_btn_{eq}_{unit}", width="stretch"):
                start_dt = datetime.combine(start_d, start_t)
                start_pump_runtime(eq, unit, start_dt)
                st.cache_data.clear()
                st.success(f"Dicatat mulai: {start_dt.strftime('%d %b %Y %H:%M')}")
                st.rerun()

        # ── Catat waktu BERHENTI ─────────────────────────────────────────────
        with c2:
            st.markdown("**⏹️ Berhenti Operasi**")
            stop_d = st.date_input("Tanggal berhenti", value=date.today(), key=f"kp_stop_d_{eq}_{unit}")
            stop_t = st.time_input("Jam berhenti", value=dtime(0,0), key=f"kp_stop_t_{eq}_{unit}")
            if st.button("💾 Catat Berhenti", key=f"kp_stop_btn_{eq}_{unit}", width="stretch"):
                stop_dt = datetime.combine(stop_d, stop_t)
                stop_pump_runtime(
                    eq, unit, stop_dt, status,
                    float(row_data.get("accumulated_hours", 0) or 0),
                    row_data.get("status_changed_at"),
                )
                st.cache_data.clear()
                st.success(f"Dicatat berhenti: {stop_dt.strftime('%d %b %Y %H:%M')}")
                st.rerun()

        # ── Tanggal instalasi / umur pompa ───────────────────────────────────
        with c3:
            st.markdown("**📅 Umur Pompa**")
            st.metric("Umur saat ini", age or "–")
            st.caption(f"Status: {'🟢 Running' if status=='running' else '⚪ Stopped'} · "
                       f"Total: {hours_now:,.1f} jam")
            existing_date = None
            if row_data.get("install_date"):
                try:
                    existing_date = pd.to_datetime(row_data["install_date"]).date()
                except Exception:
                    existing_date = None
            new_date = st.date_input(
                "Tanggal instalasi", value=existing_date or date.today(),
                key=f"kp_date_{eq}_{unit}",
            )
            if st.button("💾 Simpan tanggal", key=f"kp_save_date_{eq}_{unit}", width="stretch"):
                update_pump_install_date(eq, unit, new_date)
                st.cache_data.clear()
                st.success("Tanggal instalasi tersimpan.")
                st.rerun()

        # ── Reset (dipakai saat equipment/peralatan diganti fisik) ────────────
        st.markdown("---")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.caption("⚠️ Reset running hours ke 0 jam & status Stopped — "
                       "dipakai kalau equipment fisik diganti baru.")
            confirm_rt = st.checkbox("Saya yakin reset running hours",
                                     key=f"kp_confirm_rt_{eq}_{unit}")
            if st.button("🔄 Reset Running Hours", key=f"kp_reset_rt_{eq}_{unit}",
                        width="stretch", disabled=not confirm_rt):
                reset_pump_runtime(eq, unit)
                st.cache_data.clear()
                st.success("Running hours direset ke 0.")
                st.rerun()
        with rc2:
            st.caption("⚠️ Reset umur pompa (tanggal instalasi → hari ini) — "
                       "dipakai kalau equipment fisik diganti baru.")
            confirm_age = st.checkbox("Saya yakin reset umur pompa",
                                      key=f"kp_confirm_age_{eq}_{unit}")
            if st.button("🔄 Reset Umur Pompa", key=f"kp_reset_age_{eq}_{unit}",
                        width="stretch", disabled=not confirm_age):
                reset_pump_install_date(eq, unit)
                st.cache_data.clear()
                st.success("Umur pompa direset (tanggal instalasi = hari ini).")
                st.rerun()

        # ── Umur Bearing per posisi (DE/NDE Motor & Pompa/Fan) ────────────────
        st.markdown("---")
        st.markdown("**🔩 Umur Bearing (per posisi)**")
        st.caption("Tanggal instalasi/penggantian bearing bisa berbeda-beda per posisi — "
                   "terpisah dari tanggal instalasi equipment di atas.")
        bcols = st.columns(4)
        for bi, posisi in enumerate(BEARING_POSISI):
            b_match = df_bearing_all[
                (df_bearing_all["equipment"]==eq) & (df_bearing_all["unit"]==unit) &
                (df_bearing_all["posisi"]==posisi)
            ] if not df_bearing_all.empty else pd.DataFrame()
            b_existing_date = None
            if not b_match.empty and b_match.iloc[0].get("install_date"):
                try:
                    b_existing_date = pd.to_datetime(b_match.iloc[0]["install_date"]).date()
                except Exception:
                    b_existing_date = None
            b_age = get_pump_age(b_existing_date) if b_existing_date else None

            with bcols[bi]:
                st.markdown(f"**{posisi}**")
                st.caption(f"Umur: {b_age or '–'}")
                b_new_date = st.date_input(
                    "Tgl instalasi", value=b_existing_date or date.today(),
                    key=f"kp_bearing_date_{eq}_{unit}_{posisi}", label_visibility="collapsed",
                )
                if st.button("💾 Simpan", key=f"kp_bearing_save_{eq}_{unit}_{posisi}", width="stretch"):
                    update_bearing_install(eq, unit, posisi, b_new_date)
                    st.cache_data.clear()
                    st.success(f"Tanggal instalasi {posisi} tersimpan.")
                    st.rerun()
