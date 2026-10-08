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

Input angka memakai KOMA sebagai pemisah desimal (5,9) — titik juga dibaca desimal.
"""

import math

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
# Angka gaya Indonesia (koma desimal)
# ---------------------------------------------------------------------------
def parse_number(text):
    """
    Baca angka yang diketik pengguna. Desimal ditulis dengan KOMA ("5,9").
    Titik tunggal juga dibaca desimal ("5.9"); bila keduanya ada ("1.234,5") titik = ribuan.
    Return float, atau None bila kosong / bukan angka.
    """
    s = str(text or "").strip().replace(" ", "").replace("\u00a0", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def fmt_id(value, decimals=2):
    """Tampilkan angka dengan koma desimal dan titik ribuan: 1234.5 -> '1.234,50'."""
    s = f"{float(value):,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


# ---------------------------------------------------------------------------
# Matematika inti
# ---------------------------------------------------------------------------
EFFECT_MIN_RATIO = 0.2   # perubahan getaran akibat trial weight < 20% dari getaran awal -> beri peringatan


def to_complex(amp: float, phase_deg: float) -> complex:
    return amp * np.exp(1j * np.radians(phase_deg))


def balance_single_plane(o_amp, o_phase, t_weight, t_angle, ot_amp, ot_phase):
    """
    Hitung correction weight. Melempar ValueError (pesan siap tampil) bila input tidak
    memungkinkan perhitungan; hasil dict bila berhasil.
    """
    if o_amp <= 0:
        raise ValueError("Amplitudo getaran awal harus lebih besar dari 0 — tidak ada getaran yang perlu di-balance.")
    if t_weight <= 0:
        raise ValueError("Massa trial weight harus lebih besar dari 0.")

    O = to_complex(o_amp, o_phase)
    OT = to_complex(ot_amp, ot_phase)
    effect = OT - O

    effect_amp = float(np.abs(effect))
    effect_phase = float(np.degrees(np.angle(effect)) % 360)

    # Toleransi relatif (bukan == 0): selisih sebesar derau numerik tidak boleh lolos,
    # kalau tidak correction weight bisa menjadi miliaran gram.
    if effect_amp <= 1e-6 * max(o_amp, ot_amp, 1e-12):
        raise ValueError(
            "Getaran saat trial run sama persis dengan getaran awal (belum ada perubahan terukur "
            "akibat trial weight). Cek ulang pembacaan amplitudo & phase trial run."
        )

    sensitivity = effect_amp / t_weight
    correction_weight = o_amp / sensitivity
    angle_shift = (np.degrees(np.angle(O)) - np.degrees(np.angle(effect))) % 360
    # +180: correction weight is ADDED opposite the heavy spot (matches PLTU's official
    # "Balance Rotor" app convention — verified against their SOP worked example:
    # 5.9@357 / 204@177 / 49@250 -> 24g @ 110 deg)
    correction_angle = float((t_angle + angle_shift + 180) % 360)

    return {
        "effect_amp": effect_amp,
        "effect_phase": effect_phase,
        "effect_ratio": effect_amp / o_amp,
        "sensitivity": sensitivity,
        "correction_weight": float(correction_weight),
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
        separators=",.",   # sumbu & hover Plotly memakai koma desimal
    )
    return fig


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
COMMA_NOTE = (
    "📝 **Catatan penulisan angka:** gunakan **koma (,)** sebagai pemisah desimal — contoh "
    "`5,9` untuk 5,9 mm/s atau `12,5` untuk 12,5 gram (bukan `5.9`). Jangan memakai pemisah ribuan. "
    "Bila terlanjur mengetik titik (`5.9`), tetap dibaca sebagai desimal. "
    "Seluruh hasil perhitungan ditampilkan dengan koma."
)

render_page_header("⚙️ Rotor Balance — Kalkulator Single-Plane")
st.caption("Metode vector 4-langkah untuk balancing satu bidang (static balancing).")

tab_panduan, tab_kalkulator = st.tabs(["📖 Panduan Penggunaan", "🧮 Kalkulator"])

# ── TAB PANDUAN ──────────────────────────────────────────────────────────
with tab_panduan:
    # Catatan: teks di dalam <div> HTML TIDAK diproses sebagai Markdown, jadi tebal memakai <b>.
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
         "datanya konsisten. Setelah datanya fix, <b>matikan mesin dan lepas trial weight</b> — sesuai "
         "SOP, ini dilakukan sebelum lanjut menghitung, bukan nanti bareng pasang correction weight."),
        ("Isi semua nilai di tab Kalkulator, lalu hitung",
         "Kalkulator menghitung effect vector dari trial weight, sensitivity rotor, dan hasil "
         "akhirnya: berapa gram correction weight dan di sudut berapa — sudah disesuaikan dengan "
         "konvensi app Balance Rotor yang biasa dipakai (correction weight ditambahkan di sisi "
         "berlawanan dari heavy spot). Tulis angka desimal dengan <b>koma</b> (contoh 5,9)."),
        ("Pasang correction weight",
         "Trial weight sudah dilepas di langkah 3. Sekarang pasang correction weight sesuai hasil "
         "kalkulasi — diukur dari referensi dan arah yang sama seperti sebelumnya."),
        ("Jalankan lagi untuk verifikasi",
         "Ukur getaran akhir (1x rpm). Kalau sudah turun di bawah 3 mm/s, balancing selesai. "
         "Kalau masih ≥ 3 mm/s, ulangi sebagai trial run baru — pakai correction weight yang "
         "barusan dipasang sebagai trial mass yang baru, hitung ulang correction-nya."),
    ]
    st.info(COMMA_NOTE)
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
# Field angka memakai text_input supaya penulisan koma (5,9) diterima di semua browser.
FIELDS = [
    # key,       label,                                  min, max,   wajib>0
    ("o_amp",    "Amplitudo awal",                       0.0, None,  False),
    ("o_phase",  "Phase angle awal (°)",                 0.0, 360.0, False),
    ("t_weight", "Massa trial weight (gram)",            0.0, None,  False),
    ("t_angle",  "Sudut pemasangan trial weight (°)",    0.0, 360.0, False),
    ("ot_amp",   "Amplitudo trial run",                  0.0, None,  False),
    ("ot_phase", "Phase angle trial run (°)",            0.0, 360.0, False),
]


def read_inputs(unit_label):
    """Baca & validasi semua field. Return (nilai_dict, daftar_error)."""
    values, errors = {}, []
    for key, label, vmin, vmax, _ in FIELDS:
        shown = f"{label} ({unit_label})" if key in ("o_amp", "ot_amp") else label
        raw = st.session_state.get(f"rb_{key}", "")
        v = parse_number(raw)
        if v is None:
            errors.append(f"**{shown}** — isi dengan angka, tulis desimal dengan koma (contoh: `5,9`).")
        elif v < vmin:
            errors.append(f"**{shown}** — tidak boleh negatif.")
        elif vmax is not None and v > vmax:
            errors.append(f"**{shown}** — harus antara 0 dan {fmt_id(vmax, 0)}°.")
        else:
            values[key] = v
    return values, errors


with tab_kalkulator:
    st.info(COMMA_NOTE)

    with st.form("rb_form", border=False):
        unit_label = st.selectbox(
            "Satuan amplitudo getaran", ["mm/s", "mils", "µm", "g"], index=0, key="rb_unit",
            help="Satuan yang kamu pakai untuk membaca amplitudo dari alat ukur getaran.",
        )

        st.markdown("##### 1 · Getaran awal (sebelum pasang trial weight)")
        c1, c2 = st.columns(2)
        c1.text_input(f"Amplitudo awal ({unit_label})", key="rb_o_amp", placeholder="contoh: 5,9",
                      help="Nilai getaran yang terbaca sebelum trial weight dipasang. Desimal pakai koma.")
        c2.text_input("Phase angle awal (°)", key="rb_o_phase", placeholder="contoh: 357",
                      help="Sudut fase getaran (0–360), diukur dari titik referensi tetap di poros.")

        st.markdown("##### 2 · Trial weight yang dipasang")
        c3, c4 = st.columns(2)
        c3.text_input("Massa trial weight (gram)", key="rb_t_weight", placeholder="contoh: 100,5",
                      help="Massa beban percobaan yang kamu pasang pada rotor. Desimal pakai koma.")
        c4.text_input("Sudut pemasangan trial weight (°)", key="rb_t_angle", placeholder="contoh: 177",
                      help="Sudut di mana trial weight dipasang (0–360), dari referensi yang sama.")

        st.markdown("##### 3 · Getaran setelah trial weight terpasang")
        c5, c6 = st.columns(2)
        c5.text_input(f"Amplitudo trial run ({unit_label})", key="rb_ot_amp", placeholder="contoh: 4,2",
                      help="Nilai getaran yang terbaca setelah trial weight dipasang. Desimal pakai koma.")
        c6.text_input("Phase angle trial run (°)", key="rb_ot_phase", placeholder="contoh: 250",
                      help="Sudut fase getaran saat trial weight terpasang (0–360), referensi sama seperti langkah 1.")

        submitted = st.form_submit_button("🧮 Hitung Correction Weight", type="primary", width="stretch")

    if submitted:
        vals, errs = read_inputs(unit_label)
        st.session_state.pop("rb_calc", None)
        if errs:
            st.error("Periksa isian berikut:\n\n" + "\n".join(f"- {e}" for e in errs), icon="🚫")
        else:
            try:
                res = balance_single_plane(
                    vals["o_amp"], vals["o_phase"], vals["t_weight"], vals["t_angle"],
                    vals["ot_amp"], vals["ot_phase"],
                )
                # Disimpan di session_state: hasil tidak hilang saat widget lain berubah.
                st.session_state["rb_calc"] = dict(result=res, vals=vals, unit=unit_label)
            except ValueError as e:
                st.error(str(e), icon="🚫")

    calc = st.session_state.get("rb_calc")
    if not calc:
        if not submitted:
            st.caption("Isi semua nilai di atas (desimal dengan koma), lalu klik **Hitung Correction Weight**.")
    else:
        result, vals, unit = calc["result"], calc["vals"], calc["unit"]

        st.markdown(f"""
        <div class="rb-result-card">
            <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;opacity:.7;margin-bottom:10px;">
                Hasil Perhitungan
            </div>
            <div style="display:flex;gap:32px;flex-wrap:wrap;">
                <div>
                    <div style="font-size:11px;opacity:.7;">Correction Weight</div>
                    <div style="font-size:26px;font-weight:800;color:#16a34a;">{fmt_id(result['correction_weight'], 2)} g</div>
                </div>
                <div>
                    <div style="font-size:11px;opacity:.7;">Sudut Pemasangan</div>
                    <div style="font-size:26px;font-weight:800;color:#2563eb;">{fmt_id(result['correction_angle'], 1)}°</div>
                </div>
                <div>
                    <div style="font-size:11px;opacity:.7;">Sensitivity Rotor</div>
                    <div style="font-size:26px;font-weight:800;">{fmt_id(result['sensitivity'], 3)}</div>
                    <div style="font-size:10px;opacity:.6;">{unit}/g</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.success(
            f"➡️ Lepas trial weight, lalu pasang **{fmt_id(result['correction_weight'], 2)} gram** "
            f"pada sudut **{fmt_id(result['correction_angle'], 1)}°** dari titik referensi yang sama.",
            icon="✅",
        )

        if result["effect_ratio"] < EFFECT_MIN_RATIO:
            st.warning(
                f"Trial weight hanya mengubah getaran sekitar **{fmt_id(result['effect_ratio'] * 100, 0)}%** dari "
                f"getaran awal (di bawah {fmt_id(EFFECT_MIN_RATIO * 100, 0)}%). Perubahan sekecil ini mudah "
                "tertutup derau pengukuran, sehingga hasil kurang andal — pertimbangkan trial weight yang lebih "
                "berat atau ulangi pengukuran.",
                icon="⚠️",
            )

        fig = polar_plot(vals["o_amp"], vals["o_phase"], vals["ot_amp"], vals["ot_phase"],
                         result["correction_angle"], unit)
        st.plotly_chart(fig, width="stretch")

        with st.expander("Lihat detail perhitungan"):
            st.markdown(
                f"- **Effect vector** (perubahan getaran akibat trial weight): "
                f"{fmt_id(result['effect_amp'], 2)} {unit} @ {fmt_id(result['effect_phase'], 1)}°\n"
                f"- **Sensitivity** = effect amplitude ÷ massa trial weight = {fmt_id(result['sensitivity'], 3)} {unit}/g\n"
                f"- **Correction weight** = amplitudo awal ÷ sensitivity\n"
                f"- **Sudut correction** = sudut trial weight, digeser sebesar selisih sudut "
                f"antara vector getaran awal dan effect vector"
            )

        if st.button("🗑️ Hapus hasil", key="rb_clear"):
            st.session_state.pop("rb_calc", None)
            st.rerun()
