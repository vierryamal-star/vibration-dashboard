"""
Rotor Balance — Single-Plane Balancing Calculator
---------------------------------------------------
Drop this file into your Streamlit multi-page app's `pages/` folder
(e.g. rename to `pages/8_Rotor_Balance.py`) and it will show up as a
page in your existing app's sidebar navigation automatically.

If you want to run it standalone to test first:
    streamlit run Rotor_Balance.py

Method: classic single-plane (4-step) vector balancing.
  1. Run rotor, record original vibration: amplitude + phase   -> O
  2. Stop, attach a trial weight at a known angle               -> T
  3. Run again, record new vibration: amplitude + phase         -> O+T
  4. Vector math gives the correction weight and where to place it.

No external services, no data storage — pure calculation page.
"""

import numpy as np
import streamlit as st
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Page config — wrapped in try/except because a multi-page app usually already
# calls st.set_page_config() once in its main entry file. Calling it twice
# raises an error, so we swallow that here.
# ---------------------------------------------------------------------------
try:
    st.set_page_config(page_title="Rotor Balance", page_icon="⚙️", layout="wide")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Core balancing math
# ---------------------------------------------------------------------------
def to_complex(amp: float, phase_deg: float) -> complex:
    return amp * np.exp(1j * np.radians(phase_deg))


def balance_single_plane(
    o_amp: float,
    o_phase: float,
    t_weight: float,
    t_angle: float,
    ot_amp: float,
    ot_phase: float,
):
    """
    Single-plane (static) balancing via the 4-step vector method.

    o_amp, o_phase   : original vibration amplitude & phase (no trial weight)
    t_weight, t_angle: trial weight mass & the angle it was placed at
    ot_amp, ot_phase : vibration amplitude & phase WITH the trial weight fitted

    Returns dict with effect vector, sensitivity, correction weight & angle.
    """
    O = to_complex(o_amp, o_phase)
    OT = to_complex(ot_amp, ot_phase)
    effect = OT - O  # vibration change caused purely by the trial weight

    effect_amp = float(np.abs(effect))
    effect_phase = float(np.degrees(np.angle(effect)) % 360)

    if effect_amp == 0 or t_weight == 0:
        return None

    sensitivity = effect_amp / t_weight  # vibration units per gram of weight

    correction_weight = o_amp / sensitivity

    # Angle to rotate the trial weight by, so its effect cancels the original vibration
    angle_shift = (np.degrees(np.angle(O)) - np.degrees(np.angle(effect))) % 360
    correction_angle = (t_angle + angle_shift) % 360

    return {
        "O": O,
        "OT": OT,
        "effect": effect,
        "effect_amp": effect_amp,
        "effect_phase": effect_phase,
        "sensitivity": sensitivity,
        "correction_weight": correction_weight,
        "correction_angle": correction_angle,
    }


def polar_plot(o_amp, o_phase, t_angle, ot_amp, ot_phase, corr_weight, corr_angle, unit_label):
    max_r = max(o_amp, ot_amp, 1e-6) * 1.25

    fig = go.Figure()

    # O (original) vector — line from center + marker
    fig.add_trace(go.Scatterpolar(
        r=[0, o_amp], theta=[o_phase, o_phase], mode="lines+markers",
        line=dict(color="#c0392b", width=2), marker=dict(size=[0, 10]),
        name="O (original)",
    ))

    # O+T (trial run) vector
    fig.add_trace(go.Scatterpolar(
        r=[0, ot_amp], theta=[ot_phase, ot_phase], mode="lines+markers",
        line=dict(color="#2980b9", width=2), marker=dict(size=[0, 10]),
        name="O+T (trial run)",
    ))

    # Correction angle — drawn at a fixed reference radius since it's a different
    # unit (grams) to the vibration vectors, so its own magnitude isn't to scale
    fig.add_trace(go.Scatterpolar(
        r=[0, max_r * 0.9], theta=[corr_angle, corr_angle], mode="lines+markers",
        line=dict(color="#27ae60", width=2, dash="dash"),
        marker=dict(size=[0, 12], symbol="triangle-up"),
        name="Correction angle",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, max_r], showticklabels=True),
            angularaxis=dict(direction="counterclockwise", rotation=0),
        ),
        title=f"Vibration vectors ({unit_label})",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=50, b=60, l=40, r=40),
        height=480,
    )
    return fig


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("⚙️ Rotor Balance — Single-Plane Calculator")
st.caption(
    "Four-step vector method for single-plane (static) field balancing. "
    "Enter your original run and trial-weight run readings below."
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1 · Original run (no trial weight)")
    o_amp = st.number_input("Original vibration amplitude", min_value=0.0, value=4.0, step=0.1, key="o_amp")
    o_phase = st.number_input("Original vibration phase (°)", min_value=0.0, max_value=360.0, value=60.0, step=1.0, key="o_phase")
    unit_label = st.selectbox("Amplitude unit", ["mm/s", "mils", "µm", "g"], index=0)

with col2:
    st.subheader("2 · Trial run (with trial weight fitted)")
    t_weight = st.number_input("Trial weight mass (g)", min_value=0.0, value=10.0, step=0.5, key="t_weight")
    t_angle = st.number_input("Trial weight placement angle (°)", min_value=0.0, max_value=360.0, value=0.0, step=1.0, key="t_angle")
    ot_amp = st.number_input("Trial-run vibration amplitude", min_value=0.0, value=5.6, step=0.1, key="ot_amp")
    ot_phase = st.number_input("Trial-run vibration phase (°)", min_value=0.0, max_value=360.0, value=127.0, step=1.0, key="ot_phase")

st.info(
    "Phase angle convention: measure from the same fixed reference mark on the shaft "
    "each time (e.g. keyphasor / reflective tape), in the same direction, for all three readings.",
    icon="ℹ️",
)

if st.button("Calculate correction", type="primary", use_container_width=True):
    result = balance_single_plane(o_amp, o_phase, t_weight, t_angle, ot_amp, ot_phase)

    if result is None:
        st.error("Trial weight effect came out as zero — check that the trial-run reading actually differs from the original run.")
    else:
        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Correction weight", f"{result['correction_weight']:.2f} g")
        r2.metric("Correction angle", f"{result['correction_angle']:.1f}°")
        r3.metric("Sensitivity", f"{result['sensitivity']:.3f} {unit_label}/g")

        st.caption(
            f"Effect vector of the trial weight: {result['effect_amp']:.2f} {unit_label} "
            f"@ {result['effect_phase']:.1f}°"
        )

        fig = polar_plot(o_amp, o_phase, t_angle, ot_amp, ot_phase,
                          result["correction_weight"], result["correction_angle"], unit_label)
        st.plotly_chart(fig, use_container_width=True)

        st.success(
            f"Place **{result['correction_weight']:.2f} g** at **{result['correction_angle']:.1f}°** "
            "from your reference mark (same direction you measured phase in), replacing the trial weight.",
            icon="✅",
        )

        with st.expander("How this was calculated"):
            st.markdown(
                "- Original and trial-run vibration readings are converted to vectors "
                "(amplitude ∠ phase).\n"
                "- The **effect vector** is the trial-run vector minus the original vector — "
                "this isolates the vibration change caused purely by the trial weight.\n"
                "- **Sensitivity** = effect amplitude ÷ trial weight mass.\n"
                "- **Correction weight** = original amplitude ÷ sensitivity.\n"
                "- **Correction angle** = trial weight angle, rotated by the angular difference "
                "between the original vector and the effect vector."
            )
else:
    st.caption("Fill in the readings above and press **Calculate correction**.")
