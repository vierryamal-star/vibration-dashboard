import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import (
    load_history, render_login_sidebar, require_editor,
    get_pump_runtime, init_pump_runtime, toggle_pump_runtime,
    compute_running_hours, get_pump_age, update_pump_install_date,
    set_pump_runtime_manual,
)

st.set_page_config(
    page_title="Kelola Pompa — PLTU TBK",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
st.caption("Edit tanggal instalasi (umur pompa) dan koreksi running hours per equipment "
           "pompa/motor/fan. Perubahan di sini langsung terlihat di halaman **Monitor Vibrasi**.")

# Halaman ini khusus Editor — akan menghentikan render kalau bukan Editor
if not require_editor():
    st.stop()

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data equipment. Upload dulu di halaman **Data & Kelola**.")
    st.stop()

_RT_KEYWORDS = ("PUMP", "POMPA", "MOTOR", "FAN")

eq_unit_pairs = df_hist[["equipment", "unit"]].dropna().drop_duplicates()
eq_unit_pairs = eq_unit_pairs[
    eq_unit_pairs["equipment"].str.upper().apply(lambda x: any(k in x for k in _RT_KEYWORDS))
].sort_values(["unit", "equipment"])

if eq_unit_pairs.empty:
    st.warning("Tidak ada equipment pompa/motor/fan terdeteksi dari data vibrasi "
               "(nama equipment harus mengandung kata PUMP/POMPA/MOTOR/FAN).")
    st.stop()

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

    with st.expander(f"⚙️ **{eq}** · {unit}  —  {'🟢 Running' if status=='running' else '⚪ Stopped'} · ⏱️ {hours_now:,.1f} jam · 📅 {age or 'umur belum diisi'}"):
        c1, c2, c3 = st.columns(3)

        # ── Kontrol Start/Stop ────────────────────────────────────────────────
        with c1:
            st.markdown("**Status Pompa**")
            st.metric("Status saat ini", "🟢 Running" if status=="running" else "⚪ Stopped")
            btn_label = "⏹️ Stop" if status == "running" else "▶️ Start"
            if st.button(btn_label, key=f"kp_toggle_{eq}_{unit}", width="stretch"):
                toggle_pump_runtime(
                    eq, unit, status,
                    float(row_data.get("accumulated_hours", 0) or 0),
                    row_data.get("status_changed_at"),
                )
                st.cache_data.clear()
                st.rerun()

        # ── Koreksi running hours manual ─────────────────────────────────────
        with c2:
            st.markdown("**Koreksi Running Hours**")
            st.metric("Jam berjalan (live)", f"{hours_now:,.1f} jam")
            new_hours = st.number_input(
                "Akumulasi jam (koreksi)", min_value=0.0,
                value=float(row_data.get("accumulated_hours", 0) or 0),
                step=1.0, key=f"kp_hours_{eq}_{unit}",
                help="Ubah kalau operator telat mencatat Start/Stop atau ada kesalahan input.",
            )
            if st.button("💾 Simpan koreksi jam", key=f"kp_save_hours_{eq}_{unit}", width="stretch"):
                set_pump_runtime_manual(eq, unit, status, new_hours)
                st.cache_data.clear()
                st.success("Running hours tersimpan.")
                st.rerun()

        # ── Tanggal instalasi / umur pompa ───────────────────────────────────
        with c3:
            st.markdown("**Umur Pompa**")
            st.metric("Umur saat ini", age or "–")
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
