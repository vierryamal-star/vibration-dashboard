import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS, get_supabase_client, load_history

try:
    st.set_page_config(
        page_title="Datasheet Peralatan — PLTU TBK",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# Sembunyikan navigasi bawaan Streamlit agar sidebar menu tidak dobel
st.markdown("""
<style>
[data-testid="stSidebarNav"] {
    display: none !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("📋 Datasheet & Spesifikasi Peralatan")
st.caption("Pusat informasi teknis, nomor part bearing, pelumasan, dan spesifikasi mesin PLTU TBK.")

# ── 1. Ambil Data dari Database Supabase ────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_datasheet_records():
    sb = get_supabase_client()
    if sb:
        # Coba kueri beberapa nama tabel umum yang sering digunakan
        for candidate_table in ["datasheet", "datasheet_peralatan", "equipment_datasheet", "equipment_spec"]:
            try:
                res = sb.table(candidate_table).select("*").execute()
                if res.data and len(res.data) > 0:
                    return pd.DataFrame(res.data)
            except Exception:
                continue

    # Fallback: Buat kerangka dari equipment terdaftar di history
    try:
        df_h = load_history()
        if not df_h.empty and "equipment" in df_h.columns:
            base = df_h[["equipment", "unit"]].drop_duplicates().copy()
            base["tag"] = base["equipment"].astype(str).str.replace(" ", "-")
            base["motor_power"] = "-"
            base["rpm"] = "-"
            base["bearing_de_motor"] = "-"
            base["bearing_nde_motor"] = "-"
            base["bearing_de_pump"] = "-"
            base["bearing_nde_pump"] = "-"
            base["lube_type"] = "-"
            return base
    except Exception:
        pass

    # Fallback Master Default Unit PLTU TBK
    default_records = [
        {"unit": "TBK #1", "equipment": "Booster Pump A", "tag": "BP-A", "motor_power": "90 kW", "rpm": "2950 RPM", "bearing_de_motor": "6314 C3", "bearing_nde_motor": "6314 C3", "bearing_de_pump": "7312 B", "bearing_nde_pump": "7312 B", "lube_type": "Shell Gadus S2"},
        {"unit": "TBK #1", "equipment": "Booster Pump B", "tag": "BP-B", "motor_power": "90 kW", "rpm": "2950 RPM", "bearing_de_motor": "6314 C3", "bearing_nde_motor": "6314 C3", "bearing_de_pump": "7312 B", "bearing_nde_pump": "7312 B", "lube_type": "Shell Gadus S2"},
        {"unit": "TBK #1", "equipment": "Condensate Pump A", "tag": "CP-A", "motor_power": "37 kW", "rpm": "1480 RPM", "bearing_de_motor": "6312 C3", "bearing_nde_motor": "6312 C3", "bearing_de_pump": "7310 B", "bearing_nde_pump": "6310 C3", "lube_type": "Shell Gadus S2"},
        {"unit": "TBK #1", "equipment": "Condensate Pump B", "tag": "CP-B", "motor_power": "37 kW", "rpm": "1480 RPM", "bearing_de_motor": "6312 C3", "bearing_nde_motor": "6312 C3", "bearing_de_pump": "7310 B", "bearing_nde_pump": "6310 C3", "lube_type": "Shell Gadus S2"},
        {"unit": "TBK #1", "equipment": "Circulating Water Pump A", "tag": "CWP-A", "motor_power": "160 kW", "rpm": "980 RPM", "bearing_de_motor": "6319 C3", "bearing_nde_motor": "NU 319 C3", "bearing_de_pump": "29420", "bearing_nde_pump": "Bushing", "lube_type": "ISO VG 68"},
        {"unit": "TBK #1", "equipment": "Circulating Water Pump B", "tag": "CWP-B", "motor_power": "160 kW", "rpm": "980 RPM", "bearing_de_motor": "6319 C3", "bearing_nde_motor": "NU 319 C3", "bearing_de_pump": "29420", "bearing_nde_pump": "Bushing", "lube_type": "ISO VG 68"},
        {"unit": "TBK #1", "equipment": "Induced Draft Fan", "tag": "ID-FAN", "motor_power": "185 kW", "rpm": "980 RPM", "bearing_de_motor": "6319 C3", "bearing_nde_motor": "NU 319 C3", "bearing_de_pump": "22222 EK", "bearing_nde_pump": "22222 EK", "lube_type": "ISO VG 68"},
        {"unit": "TBK #1", "equipment": "Forced Draft Fan", "tag": "FD-FAN", "motor_power": "90 kW", "rpm": "1480 RPM", "bearing_de_motor": "6314 C3", "bearing_nde_motor": "6314 C3", "bearing_de_pump": "22216 EK", "bearing_nde_pump": "22216 EK", "lube_type": "Shell Gadus S3"},
        {"unit": "TBK #1", "equipment": "Secondary Air Fan", "tag": "SA-FAN", "motor_power": "75 kW", "rpm": "2950 RPM", "bearing_de_motor": "6313 C3", "bearing_nde_motor": "6313 C3", "bearing_de_pump": "22214 EK", "bearing_nde_pump": "22214 EK", "lube_type": "Shell Gadus S3"},
        {"unit": "TBK COM", "equipment": "Sea Water Intake A", "tag": "SWI-A", "motor_power": "75 kW", "rpm": "1480 RPM", "bearing_de_motor": "6314 C3", "bearing_nde_motor": "6314 C3", "bearing_de_pump": "7312 B", "bearing_nde_pump": "Thrust", "lube_type": "Shell Gadus S2"},
        {"unit": "TBK COM", "equipment": "Sea Water Intake B", "tag": "SWI-B", "motor_power": "75 kW", "rpm": "1480 RPM", "bearing_de_motor": "6314 C3", "bearing_nde_motor": "6314 C3", "bearing_de_pump": "7312 B", "bearing_nde_pump": "Thrust", "lube_type": "Shell Gadus S2"}
    ]
    return pd.DataFrame(default_records)

df_raw = fetch_datasheet_records()

# Pastikan field-field utama tersedia agar UI tidak KeyError
standard_cols = ["unit", "equipment", "tag", "motor_power", "rpm", "bearing_de_motor", "bearing_nde_motor", "bearing_de_pump", "bearing_nde_pump", "lube_type"]
for c in standard_cols:
    if c not in df_raw.columns:
        df_raw[c] = "-"

# ── 2. Filter & Pencarian ──────────────────────────────────────────────────
c_flt1, c_flt2 = st.columns
