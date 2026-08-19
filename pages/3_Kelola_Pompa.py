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

st.set_page_config(page_title="Kelola Pompa — PLTU TBK", page_icon="🛠️", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }
</style>
""", unsafe_allow_html=True)

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
    if st.button("🔄 Refresh Data", key="kp_refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

st.markdown("## 🛠️ Kelola Pompa")

if not require_editor():
    st.stop()

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data equipment.")
    st.stop()

all_units_kp = sorted(df_hist["unit"].dropna().unique())
sel_unit_kp = st.radio("**🏭 Filter Unit**", ["All"] + all_units_kp, horizontal=True, key="kp_unit_filter")

eq_unit_pairs = df_hist[["equipment", "unit"]].dropna().drop_duplicates().sort_values(["unit", "equipment"])
if sel_unit_kp != "All":
    eq_unit_pairs = eq_unit_pairs[eq_unit_pairs["unit"] == sel_unit_kp]

def _safe_date(value):
    if value is None or value == "" or pd.isna(value):
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        return parsed.date() if not pd.isna(parsed) else None
    except Exception:
        return None

df_runtime_all = get_pump_runtime()
df_bearing_all = get_bearing_install()

st.divider()

for _, r in eq_unit_pairs.iterrows():
    eq, unit = r["equipment"], r["unit"]
    match = df_runtime_all[(df_runtime_all["equipment"]==eq) & (df_runtime_all["unit"]==unit)]
    if match.empty:
        init_pump_runtime(eq, unit)
        row_data = {"status": "stopped", "accumulated_hours": 0.0,
                    "status_changed_at": datetime.now().isoformat(), "install_date": None}
    else:
        row_data = match.iloc[0].to_dict()

    status    = row_data.get("status", "stopped")
    hours_now = compute_running_hours(row_data)
    age       = get_pump_age(row_data.get("install_date"))

    with st.expander(f"⚙️ **{eq}** · {unit} — {'🟢 Running' if status=='running' else '⚪ Stopped'} · ⏱️ {hours_now:,.1f} jam · 📅 {age or 'umur belum diisi'}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**▶️ Mulai Operasi**")
            start_d = st.date_input("Tanggal mulai", value=date.today(), key=f"kp_start_d_{eq}_{unit}")
            start_t = st.time_input("Jam mulai", value=dtime(0,0), key=f"kp_start_t_{eq}_{unit}")
            if st.button("💾 Catat Mulai", key=f"kp_start_btn_{eq}_{unit}", use_container_width=True):
                start_pump_runtime(eq, unit, datetime.combine(start_d, start_t))
                st.cache_data.clear()
                st.success("Waktu mulai tersimpan.")
                st.rerun()

        with c2:
            st.markdown("**⏹️ Berhenti Operasi**")
            stop_d = st.date_input("Tanggal berhenti", value=date.today(), key=f"kp_stop_d_{eq}_{unit}")
            stop_t = st.time_input("Jam berhenti", value=dtime(0,0), key=f"kp_stop_t_{eq}_{unit}")
            if st.button("💾 Catat Berhenti", key=f"kp_stop_btn_{eq}_{unit}", use_container_width=True):
                stop_pump_runtime(
                    eq, unit, datetime.combine(stop_d, stop_t), status,
                    float(row_data.get("accumulated_hours", 0) or 0),
                    row_data.get("status_changed_at")
                )
                st.cache_data.clear()
                st.success("Waktu berhenti tersimpan.")
                st.rerun()

        with c3:
            st.markdown("**📅 Umur Pompa**")
            st.metric("Umur saat ini", age or "–")
            existing_date = _safe_date(row_data.get("install_date"))
            new_date = st.date_input("Tanggal instalasi", value=existing_date or date.today(), key=f"kp_date_{eq}_{unit}")
            if st.button("💾 Simpan tanggal", key=f"kp_save_date_{eq}_{unit}", use_container_width=True):
                update_pump_install_date(eq, unit, new_date)
                st.cache_data.clear()
                st.success("Tanggal instalasi tersimpan.")
                st.rerun()

        st.markdown("---")
        st.markdown("**🔩 Umur Bearing (per posisi)**")
        bcols = st.columns(4)
        for bi, posisi in enumerate(BEARING_POSISI):
            b_match = df_bearing_all[
                (df_bearing_all["equipment"]==eq) & (df_bearing_all["unit"]==unit) & (df_bearing_all["posisi"]==posisi)
            ] if not df_bearing_all.empty else pd.DataFrame()
            b_existing_date = _safe_date(b_match.iloc[0].get("install_date") if not b_match.empty else None)
            b_age = get_pump_age(b_existing_date) if b_existing_date else None

            with bcols[bi]:
                st.markdown(f"**{posisi}**")
                st.caption(f"Umur: {b_age or '–'}")
                b_new_date = st.date_input("Tgl instalasi", value=b_existing_date or date.today(),
                                           key=f"kp_bearing_date_{eq}_{unit}_{posisi}", label_visibility="collapsed")
                if st.button("💾 Simpan", key=f"kp_bearing_save_{eq}_{unit}_{posisi}", use_container_width=True):
                    update_bearing_install(eq, unit, posisi, b_new_date)
                    st.cache_data.clear()
                    st.success("Tersimpan.")
                    st.rerun()
