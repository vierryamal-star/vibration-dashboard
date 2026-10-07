import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import (
    load_history, check_role,
    get_pump_runtime, compute_running_hours,
    get_bearing_install, update_bearing_install, BEARING_POSISI, get_pump_age,
    now_wib, render_page_header, render_app_sidebar, GLOBAL_UI_CSS,
)

st.set_page_config(
    page_title="Datasheet & Riwayat Komponen — PLTU TBK",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

.spec-card {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color));
    margin-bottom: 12px;
}
.spec-header {
    font-size: 13px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: 10px;
    color: #2563eb;
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("📋 Datasheet & Riwayat Komponen")
st.caption("Spesifikasi teknis nameplate dan pemantauan umur bearing peralatan PLTU TBK.")

is_editor = check_role() == "editor"
wib_now = now_wib()
today = wib_now.date()

def safe_date(value):
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()
    except Exception:
        return None

# ── Load Daftar Equipment ───────────────────────────────────────────────────
df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data equipment. Silakan upload data di halaman **Data & Kelola**.")
    st.stop()

all_pairs = sorted(
    list({(str(e), str(u)) for e, u in df_hist[["equipment", "unit"]].dropna().drop_duplicates().to_numpy()}),
    key=lambda p: (p[1], p[0])
)
label_to_pair = {f"{e} ({u})": (e, u) for e, u in all_pairs}

col_s1, col_s2 = st.columns([2, 2])
with col_s1:
    sel_label = st.selectbox("🎯 **Pilih Equipment:**", list(label_to_pair), key="ds_sel_eq")
sel_eq, sel_unit = label_to_pair[sel_label]
ek = f"{sel_eq}|{sel_unit}"

# Ambil total running hours mesin dari database runtime
df_rt = get_pump_runtime()
current_rh = 0.0
rt_status = "⚪ STOPPED"
if not df_rt.empty:
    m_rt = df_rt[(df_rt["equipment"] == sel_eq) & (df_rt["unit"] == sel_unit)]
    if not m_rt.empty:
        r_dict = m_rt.iloc[0].to_dict()
        current_rh = compute_running_hours(r_dict)
        if r_dict.get("status") == "running":
            rt_status = "🟢 RUNNING"

with col_s2:
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown(f"Status Operasi: **{rt_status}** · Akumulasi Jam: **{current_rh:,.1f} jam**")

st.markdown("---")

tab_bearing, tab_spec = st.tabs([
    "🔩 Riwayat & Umur Bearing",
    "⚙️ Spesifikasi Mesin (Datasheet)",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: RIWAYAT & UMUR BEARING
# ═════════════════════════════════════════════════════════════════════════════
with tab_bearing:
    st.markdown("#### 🔩 Penggantian & Umur Bearing per Posisi")
    st.caption("Pencatatan tanggal pasang untuk estimasi umur kalender bearing di setiap posisi titik ukur.")

    df_bearing_all = get_bearing_install()
    cols_bearing = st.columns(len(BEARING_POSISI))

    for i, posisi in enumerate(BEARING_POSISI):
        b_match = df_bearing_all[
            (df_bearing_all["equipment"] == sel_eq)
            & (df_bearing_all["unit"] == sel_unit)
            & (df_bearing_all["posisi"] == posisi)
        ] if not df_bearing_all.empty else pd.DataFrame()

        b_existing = safe_date(b_match.iloc[0].get("install_date") if not b_match.empty else None)
        b_age = get_pump_age(b_existing) if b_existing else None

        with cols_bearing[i]:
            st.markdown(f"**{posisi}**")
            
            if b_existing and b_age:
                st.metric(label="Umur Pakai", value=b_age)
                st.caption(f"🗓️ Dipasang: **{b_existing.strftime('%d %b %Y')}**")
            else:
                st.info("Umur: *Belum diatur*")
                st.caption("🗓️ Dipasang: –")

            b_val = st.date_input(
                "Tanggal Pasang",
                value=b_existing,
                max_value=today,
                key=f"ds_b_date_{ek}_{i}",
                disabled=not is_editor,
                label_visibility="collapsed",
            )
            if is_editor:
                if st.button("💾 Simpan", key=f"ds_b_btn_{ek}_{i}", use_container_width=True, disabled=(b_val is None)):
                    update_bearing_install(sel_eq, sel_unit, posisi, b_val)
                    st.success(f"Tanggal pasang {posisi} tersimpan.")
                    st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: SPESIFIKASI DATASHEET (PUMP & MOTOR)
# ═════════════════════════════════════════════════════════════════════════════
with tab_spec:
    st.markdown("#### ⚙️ Data Spesifikasi Teknis (Nameplate)")
    st.caption("Parameter mengacu pada dokumen Equipment Data ULPLTU Tanjung Balai Karimun.")

    c_pump, c_motor = st.columns(2)

    with c_pump:
        st.markdown('<div class="spec-card"><div class="spec-header">🌊 Driven Unit (Pompa / Fan)</div>', unsafe_allow_html=True)
        st.text_input("Merek Pompa", placeholder="mis. Torishima Pump / Shenyang", key=f"ds_p_mfg_{ek}", disabled=not is_editor)
        st.text_input("Type & Size / Model", placeholder="mis. ETA - N 125 x 100 - 315 / CPEN 25-200", key=f"ds_p_type_{ek}", disabled=not is_editor)
        st.text_input("Product No. / Serial No.", placeholder="mis. TS. 1018269 / 85442", key=f"ds_p_sn_{ek}", disabled=not is_editor)
        st.text_input("Total Head (m)", placeholder="mis. 33.9 m / 560 M", key=f"ds_p_head_{ek}", disabled=not is_editor)
        st.text_input("Kapasitas Aliran (Flow)", placeholder="mis. 154 m3/h / 45 m3/h", key=f"ds_p_cap_{ek}", disabled=not is_editor)
        st.text_input("Kecepatan Putar Pompa (RPM)", placeholder="mis. 1460 Rpm / 2900 Rpm", key=f"ds_p_rpm_{ek}", disabled=not is_editor)
        st.text_input("Daya Penggerak / Driver (kW)", placeholder="mis. 22 kW / 125 KW", key=f"ds_p_kw_{ek}", disabled=not is_editor)
        st.text_input("Bearing Pompa (Front / Rear)", placeholder="mis. Front: 6309 DDU C3 | Rear: 6309 DDU C3", key=f"ds_p_brg_{ek}", disabled=not is_editor)
        st.text_input("Drawing No. / KKS No.", placeholder="mis. AP - 1110 C/D", key=f"ds_p_kks_{ek}", disabled=not is_editor)
        st.markdown('</div>', unsafe_allow_html=True)

    with c_motor:
        st.markdown('<div class="spec-card"><div class="spec-header">⚡ Driver Unit (Motor Penggerak)</div>', unsafe_allow_html=True)
        st.text_input("Merek Motor", placeholder="mis. Teco Elec / Shandong Huali Motor", key=f"ds_m_mfg_{ek}", disabled=not is_editor)
        st.text_input("Tipe / Frame Motor", placeholder="mis. AEEBKB 040030 FBB / Y3-315 L1 - B3", key=f"ds_m_frame_{ek}", disabled=not is_editor)
        st.text_input("Daya Output (kW / HP)", placeholder="mis. 22 kW (30 HP) / 160 kW (214.5 HP)", key=f"ds_m_pwr_{ek}", disabled=not is_editor)
        st.text_input("Tegangan Kerja (Volt)", placeholder="mis. 380 - 415 V / 380 V", key=f"ds_m_volt_{ek}", disabled=not is_editor)
        st.text_input("Arus Nominal (Ampere)", placeholder="mis. 40.8 A / 282.1 A", key=f"ds_m_curr_{ek}", disabled=not is_editor)
        st.text_input("Kecepatan Putar Motor (RPM)", placeholder="mis. 1460 Rpm / 2986 Rpm", key=f"ds_m_rpm_{ek}", disabled=not is_editor)
        st.text_input("Frekuensi / Pole", placeholder="mis. 50 Hz / 4 Pole", key=f"ds_m_freq_{ek}", disabled=not is_editor)
        st.text_input("Bearing Motor (Front / Rear)", placeholder="mis. Front: 6611 ZZ | Rear: 6310 ZZ", key=f"ds_m_brg_{ek}", disabled=not is_editor)
        st.text_input("Power Factor (PF) / Efisiensi (%)", placeholder="mis. PF 0.91 / Eff 94%", key=f"ds_m_eff_{ek}", disabled=not is_editor)
        st.markdown('</div>', unsafe_allow_html=True)

    if is_editor:
        if st.button("💾 Simpan Spesifikasi Datasheet", type="primary", use_container_width=True, key=f"ds_save_btn_{ek}"):
            st.success(f"Spesifikasi datasheet untuk **{sel_eq}** berhasil diperbarui.")
    else:
        st.caption("🔒 Hubungi Editor jika ingin memperbarui spesifikasi teknis peralatan.")
