"""
Rotor Balance — Kalkulator Single-Plane Balancing
---------------------------------------------------
File ini untuk folder `pages/` di repo dashboard kamu, sebagai
`pages/4_Rotor_Balance.py`.

Metode: single-plane (4-step) vector balancing method.
  1. Ukur getaran awal (tanpa trial weight)      -> O
  2. Pasang trial weight pada sudut tertentu     -> T
  3. Ukur ulang getaran (dengan trial weight)    -> O+T
  4. Hitung vector untuk dapat correction weight & sudut pemasangannya.

Tidak ada koneksi database — murni halaman kalkulasi.
"""

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from utils import render_app_sidebar, render_page_header, GLOBAL_UI_CSS

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
try:
    st.set_page_config(
        page_title="Rotor Balance — PLTU TBK",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# Sama seperti app.py: sembunyikan nav bawaan Streamlit, pakai sidebar custom
st.markdown(
    '<style>[data-testid="stSidebarNav"]{ display:none; }</style>',
    unsafe_allow_html=True,
)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

st.markdown("""
<style>
.rb-step-card {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 70%, var(--background-color));
    margin-bottom: 10px;
}
.rb-step-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; border-radius: 50%;
    background: #2563eb; color: white; font-size: 12px; font-weight: 800;
    margin-right: 8px; flex-shrink: 0;
}
.rb-step-title { font-weight: 700; font-size: 14px; }
.rb-step-desc { font-size: 12.5px; opacity: .8; margin-top: 4px; margin-left: 32px; }
.rb-result-card {
    border-radius: 14px;
    padding: 20px;
    background: linear-gradient(135deg, rgba(22,163,74,.10), rgba(37,99,235,.08));
    border: 1px solid rgba(22,163,74,.35);
    margin: 14px 0;
}
</style>
""", unsafe_allow_html=True)

render_app_sidebar()

# ---------------------------------------------------------------------------
# Matematika inti
# ---------------------------------------------------------------------------
def to_complex(amp: float, phase_deg: float) -> complex:
    return amp * np.exp(1j * np.radians(phase_deg))


def balance_single_plane(o_amp, o_phase, t_weight, t_angle, ot_amp, ot_phase):
    O = to_complex(o_amp, o_phase)
    OT = to_complex(ot_amp, ot_phase)
    effect = OT - O

    effect_amp = float(np.abs(effect))
    effect_phase = float(np.degrees(np.angle(effect)) % 360)

    if effect_amp == 0 or t_weight == 0:
        return None

    sensitivity = effect_amp / t_weight
    correction_weight = o_amp / sensitivity
    angle_shift = (np.degrees(np.angle(O)) - np.degrees(np.angle(effect))) % 360
    # +180: correction weight is ADDED opposite the heavy spot (matches PLTU's official
    # "Balance Rotor" app convention — verified against their SOP worked example:
    # 5.9@357 / 204@177 / 49@250 -> 24g @ 110 deg)
    correction_angle = (t_angle + angle_shift + 180) % 360

    return {
        "effect_amp": effect_amp,
        "effect_phase": effect_phase,
        "sensitivity": sensitivity,
        "correction_weight": correction_weight,
        "correction_angle": correction_angle,
    }


def polar_plot(o_amp, o_phase, ot_amp, ot_phase, corr_angle, unit_label):
    max_r = max(o_amp, ot_amp, 1e-6) * 1.25
    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=[0, o_amp], theta=[o_phase, o_phase], mode="lines+markers",
        line=dict(color="#c0392b", width=3), marker=dict(size=[0, 11]),
        name="O · Getaran awal",
    ))
    fig.add_trace(go.Scatterpolar(
        r=[0, ot_amp], theta=[ot_phase, ot_phase], mode="lines+markers",
        line=dict(color="#2980b9", width=3), marker=dict(size=[0, 11]),
        name="O+T · Dengan trial weight",
    ))
    fig.add_trace(go.Scatterpolar(
        r=[0, max_r * 0.9], theta=[corr_angle, corr_angle], mode="lines+markers",
        line=dict(color="#16a34a", width=3, dash="dash"),
        marker=dict(size=[0, 13], symbol="triangle-up"),
        name="Sudut correction weight",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, max_r], showticklabels=True, ticksuffix=f" {unit_label}"),
            angularaxis=dict(direction="counterclockwise", rotation=0, ticksuffix="°"),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
        margin=dict(t=30, b=70, l=40, r=40),
        height=440,
    )
    return fig


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
render_page_header("⚙️ Rotor Balance — Kalkulator Single-Plane")
st.caption("Metode vector 4-langkah untuk balancing satu bidang (static balancing).")

tab_panduan, tab_kalkulator = st.tabs(["📖 Panduan Penggunaan", "🧮 Kalkulator"])

# ── TAB PANDUAN ──────────────────────────────────────────────────────────
with tab_panduan:
    steps = [
        ("Ukur getaran awal (O)",
         "Jalankan rotor dalam kondisi normal. Catat amplitudo overall dan phase angle 1x rpm "
         "dari titik referensi tetap di poros (reflector + tachometer). Kalau nilai 1x-nya sudah "
         "≥ 3 mm/s, baru lanjut proses balancing — kalau belum, cek dulu penyebab getaran lain."),
        ("Matikan mesin, pasang trial weight",
         "Sesuai SOP PB.14.1.6.3.16.KRI: tentukan sudut trial weight dengan mengurangi fase "
         "initial run dengan 180° (titik lawan fase). Pasang trial weight seberat 100–200 gram "
         "di sudut tersebut."),
        ("Jalankan ulang, ukur getaran dengan trial weight (O+T)",
         "Nyalakan rotor lagi. Ukur amplitudo dan phase angle getaran yang baru, dari referensi "
         "yang persis sama seperti langkah 1. Ulangi pengukuran peak & phase 2–3× untuk memastikan "
         "datanya konsisten. Setelah datanya fix, **matikan mesin dan lepas trial weight** — sesuai "
         "SOP, ini dilakukan sebelum lanjut menghitung, bukan nanti bareng pasang correction weight."),
        ("Isi semua nilai di tab Kalkulator, lalu hitung",
         "Kalkulator menghitung effect vector dari trial weight, sensitivity rotor, dan hasil "
         "akhirnya: berapa gram correction weight dan di sudut berapa — sudah disesuaikan dengan "
         "konvensi app Balance Rotor yang biasa dipakai (correction weight ditambahkan di sisi "
         "berlawanan dari heavy spot)."),
        ("Pasang correction weight",
         "Trial weight sudah dilepas di langkah 3. Sekarang pasang correction weight sesuai hasil "
         "kalkulasi — diukur dari referensi dan arah yang sama seperti sebelumnya."),
        ("Jalankan lagi untuk verifikasi",
         "Ukur getaran akhir (1x rpm). Kalau sudah turun di bawah 3 mm/s, balancing selesai. "
         "Kalau masih ≥ 3 mm/s, ulangi sebagai trial run baru — pakai correction weight yang "
         "barusan dipasang sebagai trial mass yang baru, hitung ulang correction-nya."),
    ]
    for i, (title, desc) in enumerate(steps, start=1):
        st.markdown(f"""
        <div class="rb-step-card">
            <div><span class="rb-step-num">{i}</span><span class="rb-step-title">{title}</span></div>
            <div class="rb-step-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.caption("Mengikuti SOP PLN Indonesia Power — Instruksi Balancing Rotor (No. Dok: PB.14.1.6.3.16.KRI).")

    st.warning(
        "⚠️ **Penting:** ukur phase angle dari titik referensi dan arah yang **sama persis** "
        "di ketiga langkah pengukuran. Kalau referensinya berubah-ubah, sudut correction "
        "weight yang dihasilkan bisa salah arah.",
        icon="⚠️",
    )

# ── TAB KALKULATOR ───────────────────────────────────────────────────────
with tab_kalkulator:
    unit_label = st.selectbox(
        "Satuan amplitudo getaran", ["mm/s", "mils", "µm", "g"], index=0,
        help="Satuan yang kamu pakai untuk membaca amplitudo dari alat ukur getaran.",
    )

    st.markdown("##### 1 · Getaran awal (sebelum pasang trial weight)")
    c1, c2 = st.columns(2)
    o_amp = c1.number_input(
        f"Amplitudo awal ({unit_label})", min_value=0.0, value=0.0, step=0.1, key="o_amp",
        help="Nilai getaran yang terbaca sebelum trial weight dipasang.",
    )
    o_phase = c2.number_input(
        "Phase angle awal (°)", min_value=0.0, max_value=360.0, value=0.0, step=1.0, key="o_phase",
        help="Sudut fase getaran, diukur dari titik referensi tetap di poros.",
    )

    st.markdown("##### 2 · Trial weight yang dipasang")
    c3, c4 = st.columns(2)
    t_weight = c3.number_input(
        "Massa trial weight (gram)", min_value=0.0, value=0.0, step=0.5, key="t_weight",
        help="Massa beban percobaan yang kamu pasang pada rotor.",
    )
    t_angle = c4.number_input(
        "Sudut pemasangan trial weight (°)", min_value=0.0, max_value=360.0, value=0.0, step=1.0, key="t_angle",
        help="Sudut di mana trial weight dipasang, dari referensi yang sama.",
    )

    st.markdown("##### 3 · Getaran setelah trial weight terpasang")
    c5, c6 = st.columns(2)
    ot_amp = c5.number_input(
        f"Amplitudo trial run ({unit_label})", min_value=0.0, value=0.0, step=0.1, key="ot_amp",
        help="Nilai getaran yang terbaca setelah trial weight dipasang.",
    )
    ot_phase = c6.number_input(
        "Phase angle trial run (°)", min_value=0.0, max_value=360.0, value=0.0, step=1.0, key="ot_phase",
        help="Sudut fase getaran saat trial weight terpasang, referensi sama seperti langkah 1.",
    )

    st.button("🧮 Hitung Correction Weight", type="primary", use_container_width=True, key="calc_btn")

    if st.session_state.get("calc_btn"):
        result = balance_single_plane(o_amp, o_phase, t_weight, t_angle, ot_amp, ot_phase)

        if result is None:
            st.error(
                "Effect vector dari trial weight = 0 — cek lagi, kemungkinan nilai trial run "
                "sama persis dengan nilai getaran awal (belum ada perubahan terukur).",
                icon="🚫",
            )
        else:
            st.markdown(f"""
            <div class="rb-result-card">
                <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;opacity:.7;margin-bottom:10px;">
                    Hasil Perhitungan
                </div>
                <div style="display:flex;gap:32px;flex-wrap:wrap;">
                    <div>
                        <div style="font-size:11px;opacity:.7;">Correction Weight</div>
                        <div style="font-size:26px;font-weight:800;color:#16a34a;">{result['correction_weight']:.2f} g</div>
                    </div>
                    <div>
                        <div style="font-size:11px;opacity:.7;">Sudut Pemasangan</div>
                        <div style="font-size:26px;font-weight:800;color:#2563eb;">{result['correction_angle']:.1f}°</div>
                    </div>
                    <div>
                        <div style="font-size:11px;opacity:.7;">Sensitivity Rotor</div>
                        <div style="font-size:26px;font-weight:800;">{result['sensitivity']:.3f}</div>
                        <div style="font-size:10px;opacity:.6;">{unit_label}/g</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.success(
                f"➡️ Lepas trial weight, lalu pasang **{result['correction_weight']:.2f} gram** "
                f"pada sudut **{result['correction_angle']:.1f}°** dari titik referensi yang sama.",
                icon="✅",
            )

            fig = polar_plot(o_amp, o_phase, ot_amp, ot_phase, result["correction_angle"], unit_label)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Lihat detail perhitungan"):
                st.markdown(
                    f"- **Effect vector** (perubahan getaran akibat trial weight): "
                    f"{result['effect_amp']:.2f} {unit_label} @ {result['effect_phase']:.1f}°\n"
                    f"- **Sensitivity** = effect amplitude ÷ massa trial weight = {result['sensitivity']:.3f} {unit_label}/g\n"
                    f"- **Correction weight** = amplitudo awal ÷ sensitivity\n"
                    f"- **Sudut correction** = sudut trial weight, digeser sebesar selisih sudut "
                    f"antara vector getaran awal dan effect vector"
                )
    else:
        st.caption("Isi semua nilai di atas, lalu klik **Hitung Correction Weight**.")
