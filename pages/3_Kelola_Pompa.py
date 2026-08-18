import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dtime
from utils import (
    load_history, render_login_sidebar, require_editor,
    get_pump_runtime, init_pump_runtime,
    start_pump_runtime, stop_pump_runtime,
    compute_running_hours, get_pump_age, update_pump_install_date,
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

eq_unit_pairs = (
    df_hist[["equipment", "unit"]].dropna().drop_duplicates()
    .sort_values(["unit", "equipment"])
)

df_runtime_all = get_pump_runtime()

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
