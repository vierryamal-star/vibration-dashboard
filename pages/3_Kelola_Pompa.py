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
    render_page_header, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Kelola Pompa — PLTU TBK",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

.badge-running { background: rgba(34,197,94,.15); color: #16a34a; border: 1px solid #16a34a50; padding: 2px 8px; border-radius: 99px; font-weight: 700; font-size: 11px; }
.badge-stopped { background: rgba(107,114,128,.15); color: #6b7280; border: 1px solid #6b728050; padding: 2px 8px; border-radius: 99px; font-weight: 700; font-size: 11px; }
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

with st.sidebar:
    try:
        st.image("assets/logo_pln_ip.png", width=200)
    except Exception:
        pass
    st.markdown("## ⚡ PLTU TBK")
    st.caption("Kelola Peralatan & Pompa")
    st.divider()
    st.markdown("### Navigasi")
    st.page_link("app.py",                  label="📊 Monitor Vibrasi")
    st.page_link("pages/1_Analisis.py",     label="📈 Analisis")
    st.page_link("pages/2_Data_Kelola.py",  label="🗄️ Data & Kelola")
    st.page_link("pages/3_Kelola_Pompa.py", label="🛠️ Kelola Pompa")
    st.divider()
    if st.button("🔄 Refresh Data", key="kp_refresh", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    render_login_sidebar()

render_page_header("🛠️ Kelola Jam Operasi & Umur Komponen")

if not require_editor():
    st.stop()

df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data equipment. Silakan upload data terlebih dahulu di menu **Data & Kelola**.")
    st.stop()

def _safe_date(value):
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()
    except Exception:
        return None

df_runtime_all = get_pump_runtime()
df_bearing_all = get_bearing_install()

eq_unit_pairs = (
    df_hist[["equipment", "unit"]].dropna().drop_duplicates()
    .sort_values(["unit", "equipment"])
)

col_filt, col_kpi1, col_kpi2 = st.columns([2, 1, 1])

all_units_kp = sorted(df_hist["unit"].dropna().unique())
with col_filt:
    sel_unit_kp = st.selectbox("🏭 **Filter Bagian Unit**", ["Semua Bagian Unit"] + all_units_kp, key="kp_unit_filter")

pairs_filtered = eq_unit_pairs.copy()
if sel_unit_kp != "Semua Bagian Unit":
    pairs_filtered = pairs_filtered[pairs_filtered["unit"] == sel_unit_kp]

total_eq = len(pairs_filtered)
running_cnt = 0
for _, r in pairs_filtered.iterrows():
    m = df_runtime_all[(df_runtime_all["equipment"] == r["equipment"]) & (df_runtime_all["unit"] == r["unit"])]
    if not m.empty and m.iloc[0].get("status") == "running":
        running_cnt += 1

with col_kpi1:
    st.metric("Equipment Terdaftar", f"{total_eq}")
with col_kpi2:
    st.metric("Status Running", f"🟢 {running_cnt} / {total_eq}")

st.divider()

eq_options = [f"{r['equipment']} ({r['unit']})" for _, r in pairs_filtered.iterrows()]

if not eq_options:
    st.warning("Tidak ada equipment yang ditemukan.")
    st.stop()

selected_eq_str = st.selectbox("🎯 **Pilih Equipment yang Akan Dikelola / Diedit:**", eq_options)
sel_eq = selected_eq_str.split(" (")[0]
sel_unit = selected_eq_str.split(" (")[1].replace(")", "")

match = df_runtime_all[(df_runtime_all["equipment"] == sel_eq) & (df_runtime_all["unit"] == sel_unit)]
if match.empty:
    init_pump_runtime(sel_eq, sel_unit)
    st.cache_data.clear()
    row_data = {"status": "stopped", "accumulated_hours": 0.0,
                "status_changed_at": datetime.now().isoformat(), "install_date": None}
else:
    row_data = match.iloc[0].to_dict()

status = row_data.get("status", "stopped")
hours_now = compute_running_hours(row_data)
age = get_pump_age(row_data.get("install_date"))

c_st1, c_st2, c_st3 = st.columns(3)
with c_st1:
    st.markdown(f"**Status Saat Ini:**")
    if status == "running":
        st.markdown('<span class="badge-running">🟢 RUNNING (BEROPERASI)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-stopped">⚪ STOPPED (STANDBY/MATI)</span>', unsafe_allow_html=True)

with c_st2:
    st.markdown(f"**Akumulasi Jam Kerja:**")
    st.markdown(f"⏱️ **{hours_now:,.1f} jam**")

with c_st3:
    st.markdown(f"**Umur Unit Pompa:**")
    st.markdown(f"📅 **{age or 'Belum diatur'}**")

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

tab_op, tab_age, tab_bearing, tab_maint = st.tabs([
    "⏱️ Pencatatan Jam Operasi",
    "📅 Umur Unit Equipment",
    "🔩 Umur Bearing (4 Posisi)",
    "⚠️ Overhaul & Reset"
])

with tab_op:
    col_run, col_stop = st.columns(2)
    with col_run:
        st.markdown("#### ▶️ Mulai Operasi (Start)")
        st.caption("Ubah status menjadi **Running** dan mulai akumulasi jam kerja.")
        
        if st.button("⚡ Start Sekarang (Waktu Saat Ini)", key="btn_quick_start", width="stretch", disabled=(status == "running")):
            start_pump_runtime(sel_eq, sel_unit, datetime.now())
            st.cache_data.clear()
            st.success("Operasi berhasil dimulai.")
            st.rerun()
            
        with st.expander("Opsi Tanggal & Jam Manual (Start)"):
            s_date = st.date_input("Tanggal Mulai", value=date.today(), key="kp_s_date")
            s_time = st.time_input("Jam Mulai", value=dtime(0, 0), key="kp_s_time")
            if st.button("💾 Simpan Manual Start", key="btn_man_start", width="stretch", disabled=(status == "running")):
                start_dt = datetime.combine(s_date, s_time)
                start_pump_runtime(sel_eq, sel_unit, start_dt)
                st.cache_data.clear()
                st.success(f"Status running dicatat sejak: {start_dt.strftime('%d %b %Y %H:%M')}")
                st.rerun()

    with col_stop:
        st.markdown("#### ⏹️ Hentikan Operasi (Stop)")
        st.caption("Ubah status menjadi **Stopped** dan simpan durasi berjalan ke total jam.")
        
        if st.button("⚡ Stop Sekarang (Waktu Saat Ini)", key="btn_quick_stop", width="stretch", disabled=(status == "stopped")):
            stop_pump_runtime(
                sel_eq, sel_unit, datetime.now(), status,
                float(row_data.get("accumulated_hours", 0) or 0),
                row_data.get("status_changed_at")
            )
            st.cache_data.clear()
            st.success("Operasi berhasil dihentikan.")
            st.rerun()
            
        with st.expander("Opsi Tanggal & Jam Manual (Stop)"):
            e_date = st.date_input("Tanggal Berhenti", value=date.today(), key="kp_e_date")
            e_time = st.time_input("Jam Berhenti", value=dtime(0, 0), key="kp_e_time")
            if st.button("💾 Simpan Manual Stop", key="btn_man_stop", width="stretch", disabled=(status == "stopped")):
                stop_dt = datetime.combine(e_date, e_time)
                stop_pump_runtime(
                    sel_eq, sel_unit, stop_dt, status,
                    float(row_data.get("accumulated_hours", 0) or 0),
                    row_data.get("status_changed_at")
                )
                st.cache_data.clear()
                st.success(f"Status stopped dicatat pada: {stop_dt.strftime('%d %b %Y %H:%M')}")
                st.rerun()

with tab_age:
    st.markdown("#### 📅 Tanggal Instalasi Equipment")
    st.caption("Digunakan sebagai dasar kalkulasi umur peralatan secara menyeluruh.")
    existing_inst = _safe_date(row_data.get("install_date"))
    
    col_dt, col_act = st.columns([2, 1])
    with col_dt:
        new_inst_date = st.date_input(
            "Tanggal Instalasi Unit Fisik",
            value=existing_inst or date.today(),
            key="kp_eq_inst_date"
        )
    with col_act:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 Perbarui Tanggal Instalasi", key="kp_save_inst_date", width="stretch"):
            update_pump_install_date(sel_eq, sel_unit, new_inst_date)
            st.cache_data.clear()
            st.success("Tanggal instalasi berhasil disimpan.")
            st.rerun()

with tab_bearing:
    st.markdown("#### 🔩 Penggantian & Umur Bearing per Posisi")
    st.caption("Pencatatan tanggal perakitan bearing yang terpisah dari umur equipment induk.")
    
    b_cols = st.columns(4)
    for bi, posisi in enumerate(BEARING_POSISI):
        b_match = df_bearing_all[
            (df_bearing_all["equipment"] == sel_eq) & 
            (df_bearing_all["unit"] == sel_unit) & 
            (df_bearing_all["posisi"] == posisi)
        ] if not df_bearing_all.empty else pd.DataFrame()
        
        b_existing_date = _safe_date(
            b_match.iloc[0].get("install_date") if not b_match.empty else None
        )
        b_age = get_pump_age(b_existing_date) if b_existing_date else None
        
        with b_cols[bi]:
            st.markdown(f"**{posisi}**")
            st.caption(f"Umur: **{b_age or '–'}**")
            b_val = st.date_input(
                "Tgl Pasang",
                value=b_existing_date or date.today(),
                key=f"b_input_{sel_eq}_{sel_unit}_{bi}",
                label_visibility="collapsed"
            )
            if st.button(f"💾 Simpan", key=f"b_btn_{sel_eq}_{sel_unit}_{bi}", width="stretch"):
                update_bearing_install(sel_eq, sel_unit, posisi, b_val)
                st.cache_data.clear()
                st.success(f"Tersimpan ({posisi})")
                st.rerun()

with tab_maint:
    st.markdown("#### ⚠️ Reset Running Hours / Overhaul Unit")
    st.caption("Gunakan bagian ini hanya jika peralatan fisik telah diganti baru atau selesai overhaul total.")
    
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.error("Reset Jam Operasi")
        confirm_reset_h = st.checkbox("Konfirmasi: Kembalikan Running Hours ke 0.0 Jam", key="chk_res_h")
        if st.button("🔄 Eksekusi Reset Jam Operasi", key="btn_exec_rh", width="stretch", disabled=not confirm_reset_h):
            reset_pump_runtime(sel_eq, sel_unit)
            st.cache_data.clear()
            st.success("Running hours berhasil direset ke 0.")
            st.rerun()
            
    with r_col2:
        st.error("Reset Tanggal Instalasi")
        confirm_reset_a = st.checkbox("Konfirmasi: Setel Tanggal Instalasi ke Hari Ini", key="chk_res_a")
        if st.button("🔄 Eksekusi Reset Umur Pompa", key="btn_exec_ra", width="stretch", disabled=not confirm_reset_a):
            reset_pump_install_date(sel_eq, sel_unit)
            st.cache_data.clear()
            st.success("Tanggal instalasi berhasil direset ke hari ini.")
            st.rerun()
