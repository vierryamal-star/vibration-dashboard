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

try:
    st.set_page_config(
        page_title="Datasheet & Riwayat Komponen — PLTU TBK",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

/* Status Badges */
.badge-running { background: rgba(34,197,94,.15); color: #16a34a; border: 1px solid #16a34a50; padding: 4px 12px; border-radius: 99px; font-weight: 800; font-size: 11px; display: inline-block; }
.badge-stopped { background: rgba(107,114,128,.15); color: #6b7280; border: 1px solid #6b728050; padding: 4px 12px; border-radius: 99px; font-weight: 800; font-size: 11px; display: inline-block; }

/* Top Equipment KPI Summary */
.eq-summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.eq-summary-card {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color));
}
.eq-summary-card .v { font-size: 20px; font-weight: 800; line-height: 1.2; margin-top: 3px; }
.eq-summary-card .l { font-size: 11px; font-weight: 700; opacity: .65; text-transform: uppercase; letter-spacing: .05em; }

/* Bearing Card UI */
.bearing-card {
    border-radius: 14px;
    padding: 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 50%, var(--background-color));
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.bearing-title {
    font-size: 13.5px;
    font-weight: 800;
    color: #2563eb;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.bearing-age-box {
    background: rgba(37,99,235,0.08);
    border-radius: 8px;
    padding: 10px 12px;
    margin: 8px 0;
    border-left: 3px solid #2563eb;
}
.bearing-age-val { font-size: 16px; font-weight: 800; }
.bearing-age-lbl { font-size: 10.5px; opacity: .7; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }

/* Datasheet Section Boxes */
.spec-box {
    border-radius: 14px;
    padding: 18px 20px;
    border: 1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 45%, var(--background-color));
    margin-bottom: 16px;
}
.spec-box-title {
    font-size: 14px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent);
    display: flex;
    align-items: center;
    gap: 8px;
}

@media (max-width: 992px) {
    .eq-summary-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("📋 Datasheet & Riwayat Komponen")
st.caption("Pusat informasi spesifikasi teknis nameplate, umur bearing, dan integrasi jam jalan.")

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

# ── Load Equipment & Filtering Unit ─────────────────────────────────────────
df_hist = load_history()
if df_hist.empty:
    st.info("📂 Belum ada data equipment terdaftar. Silakan upload data di menu **Data & Kelola**.")
    st.stop()

# Ambil pasangan equipment & unit
all_pairs_raw = sorted(
    list({(str(e), str(u)) for e, u in df_hist[["equipment", "unit"]].dropna().drop_duplicates().to_numpy()}),
    key=lambda p: (p[1], p[0])
)

# Filter Unit & Equipment Berjenjang
col_u, col_eq = st.columns([1.5, 2.5])

with col_u:
    unit_list = sorted(list({u for _, u in all_pairs_raw}))
    sel_unit_filter = st.selectbox(
        "🏭 **Filter Bagian Unit:**",
        ["Semua Unit"] + unit_list,
        key="ds_unit_filter"
    )

# Filter daftar equipment berdasarkan unit terpilih
if sel_unit_filter == "Semua Unit":
    filtered_pairs = all_pairs_raw
else:
    filtered_pairs = [p for p in all_pairs_raw if p[1] == sel_unit_filter]

if not filtered_pairs:
    st.warning("Tidak ada equipment yang terdaftar pada unit ini.")
    st.stop()

label_to_pair = {f"{e} ({u})": (e, u) for e, u in filtered_pairs}

with col_eq:
    sel_label = st.selectbox(
        "🎯 **Pilih Equipment:**",
        list(label_to_pair),
        key="ds_sel_eq"
    )

sel_eq, sel_unit = label_to_pair[sel_label]
ek = f"{sel_eq}|{sel_unit}"

# Ambil data jam operasi real-time
df_rt = get_pump_runtime()
current_rh = 0.0
rt_status = "stopped"
if not df_rt.empty:
    m_rt = df_rt[(df_rt["equipment"] == sel_eq) & (df_rt["unit"] == sel_unit)]
    if not m_rt.empty:
        r_dict = m_rt.iloc[0].to_dict()
        current_rh = compute_running_hours(r_dict)
        rt_status = r_dict.get("status") or "stopped"

# ── Header KPI Cards ────────────────────────────────────────────────────────
badge_html = '<span class="badge-running">🟢 RUNNING</span>' if rt_status == "running" else '<span class="badge-stopped">⚪ STOPPED</span>'
st.markdown(f"""
<div class="eq-summary-grid">
  <div class="eq-summary-card">
    <div class="l">Peralatan Terpilih</div>
    <div class="v" style="font-size:17px;color:#2563eb;">{sel_eq}</div>
  </div>
  <div class="eq-summary-card">
    <div class="l">Bagian Unit / Lokasi</div>
    <div class="v" style="font-size:17px;">{sel_unit}</div>
  </div>
  <div class="eq-summary-card">
    <div class="l">Status Operasional</div>
    <div style="margin-top:6px;">{badge_html}</div>
  </div>
  <div class="eq-summary-card">
    <div class="l">Total Running Hours</div>
    <div class="v" style="color:#d97706;">⏱️ {current_rh:,.1f} <span style="font-size:12px;opacity:.7;">jam</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs Utama ──────────────────────────────────────────────────────────────
tab_bearing, tab_spec = st.tabs([
    "🔩 Status & Umur Bearing",
    "⚙️ Spesifikasi Teknis (Nameplate)",
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: STATUS & UMUR BEARING
# ═════════════════════════════════════════════════════════════════════════════
with tab_bearing:
    st.markdown("##### 🔩 Riwayat Pemasangan & Pemantauan Bearing")
    st.caption("Umur kalender dihitung otomatis sejak tanggal instalasi fisik terakhir.")

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
            st.markdown(f"""
            <div class="bearing-card">
              <div>
                <div class="bearing-title">📍 {posisi}</div>
                <div class="bearing-age-box">
                  <div class="bearing-age-lbl">Umur Kalender</div>
                  <div class="bearing-age-val">{b_age if b_age else 'Belum Diatur'}</div>
                </div>
                <div style="font-size:11.5px;opacity:.7;margin-bottom:8px;">
                  🗓️ Pasang: <b>{b_existing.strftime('%d %b %Y') if b_existing else '–'}</b>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if is_editor:
                with st.expander("Kelola / Ganti Bearing"):
                    b_val = st.date_input(
                        "Tanggal Pasang Baru",
                        value=b_existing or today,
                        max_value=today,
                        key=f"ds_b_date_{ek}_{i}",
                        label_visibility="collapsed",
                    )
                    
                    c_save, c_reset = st.columns(2)
                    with c_save:
                        if st.button("💾 Simpan", key=f"ds_b_btn_{ek}_{i}", use_container_width=True):
                            update_bearing_install(sel_eq, sel_unit, posisi, b_val)
                            st.success(f"{posisi} tersimpan.")
                            st.rerun()

                    with c_reset:
                        if st.button("🔄 Ganti Hari Ini", key=f"ds_b_rst_{ek}_{i}", use_container_width=True, help="Set tanggal pasang ke hari ini (umur otomatis kembali ke 0 hari)"):
                            update_bearing_install(sel_eq, sel_unit, posisi, today)
                            st.success(f"Bearing {posisi} direset ke hari ini.")
                            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: SPESIFIKASI DATASHEET (PUMP & MOTOR)
# ═════════════════════════════════════════════════════════════════════════════
with tab_spec:
    st.markdown("##### ⚙️ Parameter Desain Mesin & Nameplate")
    st.caption("Referensi data mengacu pada dokumen Equipment Data ULPLTU Tanjung Balai Karimun.")

    c_pump, c_motor = st.columns(2)

    with c_pump:
        st.markdown("""
        <div class="spec-box">
          <div class="spec-box-title" style="color:#0284c7;">🌊 Driven Equipment (Pompa / Driven Unit)</div>
        """, unsafe_allow_html=True)
        
        p1, p2 = st.columns(2)
        with p1:
            st.text_input("Merek Pompa", placeholder="mis. Torishima Pump / Shenyang", key=f"ds_p_mfg_{ek}", disabled=not is_editor)
            st.text_input("Product No. / Serial", placeholder="mis. TS. 1018269 / 85442", key=f"ds_p_sn_{ek}", disabled=not is_editor)
            st.text_input("Kapasitas (Flow Rate)", placeholder="mis. 154 m³/h / 45 m³/h", key=f"ds_p_cap_{ek}", disabled=not is_editor)
            st.text_input("Daya Driver (kW)", placeholder="mis. 22 kW / 125 kW", key=f"ds_p_kw_{ek}", disabled=not is_editor)
        with p2:
            st.text_input("Tipe & Ukuran (Model)", placeholder="mis. ETA - N 125 x 100 - 315", key=f"ds_p_type_{ek}", disabled=not is_editor)
            st.text_input("Total Head (m)", placeholder="mis. 33.9 m / 560 M", key=f"ds_p_head_{ek}", disabled=not is_editor)
            st.text_input("Kecepatan Putar (RPM)", placeholder="mis. 1460 RPM / 2900 RPM", key=f"ds_p_rpm_{ek}", disabled=not is_editor)
            st.text_input("KKS / Drawing No.", placeholder="mis. AP - 1110 C/D", key=f"ds_p_kks_{ek}", disabled=not is_editor)

        st.text_input("Tipe Bearing Pompa (Front / Rear)", placeholder="mis. Front: 6309 DDU C3 | Rear: 6309 DDU C3", key=f"ds_p_brg_{ek}", disabled=not is_editor)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_motor:
        st.markdown("""
        <div class="spec-box">
          <div class="spec-box-title" style="color:#d97706;">⚡ Driver Equipment (Motor Penggerak)</div>
        """, unsafe_allow_html=True)

        m1, m2 = st.columns(2)
        with m1:
            st.text_input("Merek Motor", placeholder="mis. Teco Elec / Shandong Huali", key=f"ds_m_mfg_{ek}", disabled=not is_editor)
            st.text_input("Daya Output (kW / HP)", placeholder="mis. 22 kW (30 HP) / 160 kW", key=f"ds_m_pwr_{ek}", disabled=not is_editor)
            st.text_input("Arus Nominal (Ampere)", placeholder="mis. 40.8 A / 282.1 A", key=f"ds_m_curr_{ek}", disabled=not is_editor)
            st.text_input("Frekuensi / Pole", placeholder="mis. 50 Hz / 4 Pole", key=f"ds_m_freq_{ek}", disabled=not is_editor)
        with m2:
            st.text_input("Tipe / Frame Motor", placeholder="mis. AEEBKB 040030 FBB / 315L", key=f"ds_m_frame_{ek}", disabled=not is_editor)
            st.text_input("Tegangan Kerja (Volt)", placeholder="mis. 380 - 415 V / 6.6 kV", key=f"ds_m_volt_{ek}", disabled=not is_editor)
            st.text_input("Kecepatan Motor (RPM)", placeholder="mis. 1460 RPM / 2986 RPM", key=f"ds_m_rpm_{ek}", disabled=not is_editor)
            st.text_input("Power Factor (PF) / Eff", placeholder="mis. PF 0.91 / Eff 94%", key=f"ds_m_eff_{ek}", disabled=not is_editor)

        st.text_input("Tipe Bearing Motor (Front / Rear)", placeholder="mis. Front: 6611 ZZ | Rear: 6310 ZZ", key=f"ds_m_brg_{ek}", disabled=not is_editor)
        st.markdown("</div>", unsafe_allow_html=True)

    if is_editor:
        if st.button("💾 Simpan Spesifikasi Datasheet", type="primary", use_container_width=True, key=f"ds_save_btn_{ek}"):
            st.success(f"Spesifikasi datasheet untuk **{sel_eq}** berhasil diperbarui.")
    else:
        st.info("🔒 Mode Viewer: Hanya akun dengan role **Editor** yang dapat memperbarui spesifikasi teknis.")
