import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS

try:
    st.set_page_config(
        page_title="Datasheet Pompa & Peralatan — PLTU TBK",
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
render_page_header("📋 Datasheet Pompa & Peralatan Utama PLTU TBK")
st.caption("Pusat data teknis peralatan mekanik, pompa, motor penggerak, nomor bearing, dan dokumen drawing sistem PLTU Tanjung Balai Karimun.")

# ── Data Master dari Ekstraksi File Excel ────────────────────────────────────
EQUIPMENT_DATASHEET = [
    {
        "no": 1,
        "equipment": "Close Cooling Water Pump (CCWP)",
        "tag": "AP-1105 C/D",
        "category": "Pompa Air & Pendingin",
        "unit": "Turbin / Common",
        "pump_merek": "TORISHIMA PUMP",
        "pump_type": "CPEN 25 - 200",
        "pump_head": "43.8 m",
        "pump_capacity": "6 m³/h (2 x 100%)",
        "pump_speed": "2900 RPM",
        "pump_driver": "3 kW",
        "pump_brg_front": "6305 DDU C3",
        "pump_brg_rear": "6305 DDU C3",
        "motor_merek": "Teco Elec. & Mach. PTE. LTD",
        "motor_code_frame": "AEEBKB 020004 YU (Frame 100 L)",
        "motor_power": "3 kW (4 HP)",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "6.06 A",
        "motor_speed": "2854 RPM",
        "motor_brg_front": "6206 ZZ",
        "motor_brg_rear": "6305 ZZ",
        "system": "Close Cooling Water System",
        "drawing_no": "1802-00-M-10-PG-001-02",
    },
    {
        "no": 2,
        "equipment": "Cooling Booster Pump",
        "tag": "AP-1110 C/D",
        "category": "Pompa Air & Pendingin",
        "unit": "Turbin / Common",
        "pump_merek": "TORISHIMA PUMP",
        "pump_type": "ETA - N 125 x 100 - 315",
        "pump_head": "33.9 m",
        "pump_capacity": "154 m³/h (2 x 100%)",
        "pump_speed": "1460 RPM",
        "pump_driver": "22 kW",
        "pump_brg_front": "6309 DDU C3",
        "pump_brg_rear": "6309 DDU C3",
        "motor_merek": "Teco Elec. & Mach. PTE. LTD",
        "motor_code_frame": "AEEBKB.040030 FBB (Frame 180 L.C)",
        "motor_power": "22 kW (30 HP)",
        "motor_volt": "380 - 415 V (50 Hz)",
        "motor_current": "40.8 A",
        "motor_speed": "1460 RPM",
        "motor_brg_front": "6611 ZZ",
        "motor_brg_rear": "6310 ZZ",
        "system": "Sea Water Cooling Supply System",
        "drawing_no": "1802-00-M-10-P-001-01",
    },
    {
        "no": 3,
        "equipment": "Boiler Feed Water Pump (BFP)",
        "tag": "BFP Multi Stage",
        "category": "Pompa Boiler",
        "unit": "Boiler",
        "pump_merek": "Shenyang Pump Manufactory",
        "pump_type": "Multi Stage DGJ 45 - 80 x 7",
        "pump_head": "560 m",
        "pump_capacity": "45 m³/h (3 x 100%)",
        "pump_speed": "2986 RPM",
        "pump_driver": "125 kW (Berat 1250 kg)",
        "pump_brg_front": "N 6319 C3",
        "pump_brg_rear": "N 6319 C3",
        "motor_merek": "Shandong Huali Electric Motor Group",
        "motor_code_frame": "Y3-315 L1 - B3",
        "motor_power": "160 kW (214.5 HP)",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "282.1 A (PF: 0.91, Eff: 94%)",
        "motor_speed": "2986 RPM",
        "motor_brg_front": "N 6319 C3",
        "motor_brg_rear": "N 6319 C3",
        "system": "Boiler Feed Water System",
        "drawing_no": "1802-00-M-09-LB-002-01 / 003-01",
    },
    {
        "no": 4,
        "equipment": "Water Jet Pump",
        "tag": "AP / 1114 A/B",
        "category": "Pompa Air & Pendingin",
        "unit": "Turbin / Kondensat",
        "pump_merek": "Shenyang Pump Manufactory",
        "pump_type": "IS100 - 65 - 200",
        "pump_head": "47 m",
        "pump_capacity": "120 m³/h (Desain 105 m³/h)",
        "pump_speed": "2900 RPM",
        "pump_driver": "19.7 kW (Berat 320 kg)",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "Shandong Huali Electric Motor Group",
        "motor_code_frame": "Frame Y2 - 180M - 2",
        "motor_power": "22 kW (29.5 HP)",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "41.0 A (PF: 0.9)",
        "motor_speed": "2940 RPM",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Vacuum Jet / Condensate Extraction System",
        "drawing_no": "1802-00-M-10-LB-003-02",
    },
    {
        "no": 5,
        "equipment": "AC Auxiliary Oil Pump",
        "tag": "CHY 18 - 1 (AC)",
        "category": "Pompa Pelumas / Oil",
        "unit": "Turbin Lube Oil",
        "pump_merek": "Botoushi Yunhe Estate of Pump Co.",
        "pump_type": "Gear Pump (Positive Displacement)",
        "pump_head": "5 m (NPSH) / Tekanan 0.353 MPa",
        "pump_capacity": "350 L/min (20.5 m³/h)",
        "pump_speed": "960 RPM",
        "pump_driver": "3.8 kW (Shaft ø70 mm)",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "Jiangsu Electric Motor Co., Ltd",
        "motor_code_frame": "Y2 - 132 M2 - 6T",
        "motor_power": "5.5 kW",
        "motor_volt": "400 V (50 Hz)",
        "motor_current": "11.6 A",
        "motor_speed": "960 RPM",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Oil Cooling System of Steam Turbine",
        "drawing_no": "1802-00-M-10-P-002-01 (Unit 1) / 002-02 (Unit 2)",
    },
    {
        "no": 6,
        "equipment": "DC Auxiliary Oil Pump",
        "tag": "CHY 18 - 1 (DC)",
        "category": "Pompa Pelumas / Oil",
        "unit": "Turbin Lube Oil",
        "pump_merek": "Botoushi Yunhe Estate of Pump Co.",
        "pump_type": "Gear Pump (Positive Displacement)",
        "pump_head": "5 m (NPSH) / Tekanan 0.353 MPa",
        "pump_capacity": "350 L/min (20.5 m³/h)",
        "pump_speed": "960 RPM",
        "pump_driver": "3.8 kW (Shaft ø70 mm)",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "Xi'an Simo Motors, Inc",
        "motor_code_frame": "Z2 - 61 (Direct Current / DC)",
        "motor_power": "5.5 kW",
        "motor_volt": "220 V (DC)",
        "motor_current": "30.3 A",
        "motor_speed": "1000 RPM",
        "motor_brg_front": "6309 / CMZ1",
        "motor_brg_rear": "6309 / CMZ1",
        "system": "Emergency Oil Supply System Steam Turbine",
        "drawing_no": "1802-00-M-10-P-002-01 / 002-02",
    },
    {
        "no": 7,
        "equipment": "Circulating Water Pump (CWP)",
        "tag": "AP / 1103 A/B",
        "category": "Pompa Air & Pendingin",
        "unit": "Cooling Tower / Turbin",
        "pump_merek": "Torishima Guna Indonesia",
        "pump_type": "CDM 450 LN",
        "pump_head": "16.2 m (Diff: 1.62 kg/cm²G)",
        "pump_capacity": "1375 m³/h (2 Unit 2 x 50%)",
        "pump_speed": "890 RPM",
        "pump_driver": "90 kW",
        "pump_brg_front": "6315 C3",
        "pump_brg_rear": "6315 C3",
        "motor_merek": "TECO, 3 Phase Induction Motor",
        "motor_code_frame": "Frame 315 SC",
        "motor_power": "90 kW (125 HP)",
        "motor_volt": "380 - 415 V (50 Hz)",
        "motor_current": "170 A",
        "motor_speed": "975 RPM",
        "motor_brg_front": "6315",
        "motor_brg_rear": "NU 320 C3",
        "system": "Sea Water Cooling Supply System",
        "drawing_no": "1802-00-10-P-001-01 / 001-02",
    },
    {
        "no": 8,
        "equipment": "Condensate Feed Water Pump",
        "tag": "AP - 1101 A/B/C/D",
        "category": "Pompa Boiler & Kondensat",
        "unit": "Turbin / Kondensat",
        "pump_merek": "Shenyang Pump Manufactory",
        "pump_type": "4 N6 (Horizontal Pump)",
        "pump_head": "59.5 m (NPSH 1.75 m)",
        "pump_capacity": "50 m³/h (13.9 L/s)",
        "pump_speed": "2950 RPM",
        "pump_driver": "14.1 kW (Impeller 225 mm)",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "Shandong Huali Electric Motor Group",
        "motor_code_frame": "Frame Y2-180M - 2",
        "motor_power": "22 kW (29.5 HP)",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "41.0 A (PF: 0.90, Eff: 90.5%)",
        "motor_speed": "2940 RPM",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Steam Supply & Condensate System",
        "drawing_no": "1802-00-M-10-LB-003-05",
    },
    {
        "no": 9,
        "equipment": "Demin Water Transfer Pump",
        "tag": "Demin Pump",
        "category": "Water Treatment (WTP)",
        "unit": "Demin Plant",
        "pump_merek": "TORISHIMA PUMP",
        "pump_type": "CPEN 25 - 160",
        "pump_head": "35 m",
        "pump_capacity": "4 m³/h (2 x 100%)",
        "pump_speed": "2900 RPM",
        "pump_driver": "2.2 kW",
        "pump_brg_front": "6305 DDU C3",
        "pump_brg_rear": "6305 DDU C3",
        "motor_merek": "Teco Elec. & Mach. PTE. LTD",
        "motor_code_frame": "3 Phase Induction (Frame 90 L)",
        "motor_power": "2.2 kW (3 HP)",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "4.5 A",
        "motor_speed": "2870 RPM",
        "motor_brg_front": "6205 ZZ",
        "motor_brg_rear": "6205 ZZ",
        "system": "Demineralized Water Supply System",
        "drawing_no": "-",
    },
    {
        "no": 10,
        "equipment": "Reverse Osmosis Transfer Pump",
        "tag": "RO Pump #1 & #2",
        "category": "Water Treatment (WTP)",
        "unit": "RO Plant",
        "pump_merek": "TORISHIMA PUMP",
        "pump_type": "FTA - N 65 x 50 - 200",
        "pump_head": "40 m",
        "pump_capacity": "27.5 m³/h (2 x 100%)",
        "pump_speed": "2900 RPM",
        "pump_driver": "7.5 kW",
        "pump_brg_front": "6305 DDU C3",
        "pump_brg_rear": "6305 DDU C3",
        "motor_merek": "Teco Elec. & Mach. PTE. LTD",
        "motor_code_frame": "AEEBKBO20010FMB (Frame F 132 S)",
        "motor_power": "7.5 kW (10 HP)",
        "motor_volt": "380 - 415 V (50 Hz)",
        "motor_current": "13.8 A",
        "motor_speed": "2880 RPM",
        "motor_brg_front": "6308 ZZ",
        "motor_brg_rear": "6308 ZZ",
        "system": "Reverse Osmosis Pre-Treatment System",
        "drawing_no": "Seal: CN25 (22-MG1/25-S1) Viton/SS316",
    },
    {
        "no": 11,
        "equipment": "Make Up Transfer Pump Cooling Tower",
        "tag": "Make Up CT",
        "category": "Water Treatment (WTP)",
        "unit": "Cooling Tower",
        "pump_merek": "TORISHIMA PUMP",
        "pump_type": "FTA - N 150 x 125 - 315",
        "pump_head": "30 m",
        "pump_capacity": "220 m³/h (2 x 100%)",
        "pump_speed": "1450 RPM",
        "pump_driver": "30 kW",
        "pump_brg_front": "6311 DDU C3",
        "pump_brg_rear": "6311 DDU C3",
        "motor_merek": "Teco Elec. & Mach. PTE. LTD",
        "motor_code_frame": "AEEBKBD40040 FMB (Frame 200 LC)",
        "motor_power": "30 kW (40 HP)",
        "motor_volt": "380 - 415 V (50 Hz)",
        "motor_current": "53.8 A",
        "motor_speed": "1470 RPM",
        "motor_brg_front": "6312 ZZ",
        "motor_brg_rear": "6312 ZZ",
        "system": "Cooling Tower Make Up Water Supply",
        "drawing_no": "-",
    },
    {
        "no": 12,
        "equipment": "Vacuum Pump BOP",
        "tag": "Vacum BOP",
        "category": "Pompa Aux BOP",
        "unit": "BOP / Turbin",
        "pump_merek": "KENFLO",
        "pump_type": "2BF1 101 - 0HD2",
        "pump_head": "30 m (Suction: 33-1013 hpa)",
        "pump_capacity": "0.7 - 2.8 m³/h (1 x 100%)",
        "pump_speed": "1450 RPM",
        "pump_driver": "5.5 kW (Berat 64 kg)",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "Teco Elec. & Mach. PTE. LTD",
        "motor_code_frame": "AEEBKBO47R50FMB (Frame F 132 S)",
        "motor_power": "5.5 kW (7.5 HP)",
        "motor_volt": "380 - 415 V (50 Hz)",
        "motor_current": "11.4 A",
        "motor_speed": "1445 RPM",
        "motor_brg_front": "6306 ZZ",
        "motor_brg_rear": "6308 ZZ",
        "system": "BOP Vacuum & Priming System",
        "drawing_no": "-",
    },
    {
        "no": 13,
        "equipment": "Sea Water Intake Pump (SWIP)",
        "tag": "SWIP A/B",
        "category": "Pompa Air Laut / Intake",
        "unit": "Intake Canal",
        "pump_merek": "TORISHIMA PUMP",
        "pump_type": "ETA - N 200 x 150 - 400",
        "pump_head": "19.52 m",
        "pump_capacity": "247.5 m³/h (2 x 100%)",
        "pump_speed": "970 RPM",
        "pump_driver": "22 kW",
        "pump_brg_front": "6313 DDU C3",
        "pump_brg_rear": "6313 DDU C3",
        "motor_merek": "MOTOR SWIP",
        "motor_code_frame": "3 - W21 - 200L - 06",
        "motor_power": "22 kW (30 HP)",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "43.1 A",
        "motor_speed": "970 RPM",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Sea Water Intake Supply System",
        "drawing_no": "-",
    },
    {
        "no": 14,
        "equipment": "Cooling Tower (CT)",
        "tag": "Cooling Tower Cell",
        "category": "Peralatan Pendingin",
        "unit": "Cooling Tower",
        "pump_merek": "-",
        "pump_type": "Mechanical Induced Draft Counter Flow",
        "pump_head": "Suhu Air: 39°C (Inlet) / 31°C (Outlet)",
        "pump_capacity": "Total 5500 m³/h (2750 m³/h per Cell)",
        "pump_speed": "-",
        "pump_driver": "Total Fan Power 249.9 kW @ 2 Cell",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "3-Phase Induction Motor (IP 55 TEFC)",
        "motor_code_frame": "Frame 3155 / M",
        "motor_power": "145 kW",
        "motor_volt": "380 V (50 Hz)",
        "motor_current": "271 A (Insulation Class F)",
        "motor_speed": "1485 RPM",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Circulating Water Cooling Tower System",
        "drawing_no": "Drift Loss: 1.13% | Evap: 0.001%",
    },
    {
        "no": 15,
        "equipment": "Generator Cooler",
        "tag": "Generator Cooler Heat Exchanger",
        "category": "Heat Exchanger & Filter",
        "unit": "Generator",
        "pump_merek": "Shandong Machinery I&E Group",
        "pump_type": "Surface Cooler (Pendingin Air Laut)",
        "pump_head": "Inlet Tekanan: 0.2 MPa | Test: 0.6 MPa",
        "pump_capacity": "Kapasitas Transfer Panas: 90 kW",
        "pump_speed": "Kecepatan Udara: 3.35 m³/s | Air: 25 m³/s",
        "pump_driver": "Material: Tube B10, Frame SUS 304L",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "-",
        "motor_code_frame": "Parallel Connected 2 Water Circuits",
        "motor_power": "Heat Transfer 90 kW",
        "motor_volt": "-",
        "motor_current": "-",
        "motor_speed": "-",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Generator Air & Stator Cooling System",
        "drawing_no": "Water Press Drop: 5187 Pa | Air: 300 Pa",
    },
    {
        "no": 16,
        "equipment": "Duplex Filter (Oil Strainer)",
        "tag": "Duplex Oil Filter",
        "category": "Heat Exchanger & Filter",
        "unit": "Lube Oil System",
        "pump_merek": "BCB Filtration Technology Co., LTD",
        "pump_type": "Duplex Strainer / Oil Filter",
        "pump_head": "Tekanan Kerja: 1.6 MPa",
        "pump_capacity": "Aliran: 360 m³/min",
        "pump_driver": "Ukuran: 60 μm (Microfiber 160x400/80 mm)",
        "pump_speed": "-",
        "pump_brg_front": "-",
        "pump_brg_rear": "-",
        "motor_merek": "-",
        "motor_code_frame": "Serial No: 242504 (Brand: BCB)",
        "motor_power": "-",
        "motor_volt": "-",
        "motor_current": "-",
        "motor_speed": "-",
        "motor_brg_front": "-",
        "motor_brg_rear": "-",
        "system": "Steam Turbine Lube Oil Filtration",
        "drawing_no": "-",
    },
]

df_all = pd.DataFrame(EQUIPMENT_DATASHEET)

# ── Kontrol Filter & Kotak Pencarian ─────────────────────────────────────────
col1, col2, col3 = st.columns([1.5, 1.5, 2])

with col1:
    list_cat = ["Semua Kategori"] + sorted(list(df_all["category"].unique()))
    sel_cat = st.selectbox("📂 Kategori Peralatan:", list_cat)

with col2:
    list_unit = ["Semua Unit"] + sorted(list(df_all["unit"].unique()))
    sel_unit = st.selectbox("🏭 Lokasi / Area:", list_unit)

with col3:
    search_q = st.text_input("🔍 Cari (Nama Pompa, No Bearing, Tipe):", placeholder="Contoh: 6305, BFP, Torishima, TECO...")

df_filt = df_all.copy()
if sel_cat != "Semua Kategori":
    df_filt = df_filt[df_filt["category"] == sel_cat]
if sel_unit != "Semua Unit":
    df_filt = df_filt[df_filt["unit"] == sel_unit]

if search_q.strip():
    q = search_q.strip().lower()
    df_filt = df_filt[
        df_filt["equipment"].str.lower().str.contains(q)
        | df_filt["tag"].str.lower().str.contains(q)
        | df_filt["pump_type"].str.lower().str.contains(q)
        | df_filt["pump_merek"].str.lower().str.contains(q)
        | df_filt["pump_brg_front"].str.lower().str.contains(q)
        | df_filt["pump_brg_rear"].str.lower().str.contains(q)
        | df_filt["motor_brg_front"].str.lower().str.contains(q)
        | df_filt["motor_brg_rear"].str.lower().str.contains(q)
    ]

# ── Tabs Tampilan ───────────────────────────────────────────────────────────
tab_cards, tab_table = st.tabs([
    "📇 Kartu Spesifikasi Lengkap",
    "📊 Tabel Rekapitulasi & Export",
])

with tab_cards:
    if df_filt.empty:
        st.info("Tidak ada data peralatan yang cocok dengan filter atau kata kunci pencarian.")
    else:
        for _, row in df_filt.iterrows():
            with st.container(border=True):
                # Header Equipment
                c_title, c_badge = st.columns([3.5, 1.5])
                with c_title:
                    st.subheader(f"#{row['no']} {row['equipment']}")
                    st.caption(f"🏷️ Tag/KKS: **{row['tag']}** | 📍 Area: **{row['unit']}** | 📂 **{row['category']}**")
                with c_badge:
                    st.metric("Daya Motor", row["motor_power"], delta=row["pump_speed"], delta_color="off")

                st.divider()

                # Spesifikasi Pompa & Motor
                col_p, col_m = st.columns(2)
                with col_p:
                    st.markdown("#### ⚙️ Spesifikasi Pompa / Unit")
                    st.write(f"• **Merek:** {row['pump_merek']}")
                    st.write(f"• **Type & Size:** {row['pump_type']}")
                    st.write(f"• **Total Head:** {row['pump_head']}")
                    st.write(f"• **Kapasitas Aliran:** {row['pump_capacity']}")
                    st.write(f"• **Putaran (Speed):** {row['pump_speed']}")
                    st.write(f"• **Driver Output:** {row['pump_driver']}")

                    st.markdown("**Nomor Bearing Pompa:**")
                    col_bp1, col_bp2 = st.columns(2)
                    col_bp1.info(f"**Front (DE):**\n`{row['pump_brg_front']}`")
                    col_bp2.info(f"**Rear (NDE):**\n`{row['pump_brg_rear']}`")

                with col_m:
                    st.markdown("#### ⚡ Spesifikasi Motor Penggerak")
                    st.write(f"• **Merek Motor:** {row['motor_merek']}")
                    st.write(f"• **Type / Frame:** {row['motor_code_frame']}")
                    st.write(f"• **Daya Motor:** {row['motor_power']}")
                    st.write(f"• **Tegangan & Frekuensi:** {row['motor_volt']}")
                    st.write(f"• **Arus Listrik (Current):** {row['motor_current']}")
                    st.write(f"• **Kecepatan Motor:** {row['motor_speed']}")

                    st.markdown("**Nomor Bearing Motor:**")
                    col_bm1, col_bm2 = st.columns(2)
                    col_bm1.success(f"**Front (DE):**\n`{row['motor_brg_front']}`")
                    col_bm2.success(f"**Rear (NDE):**\n`{row['motor_brg_rear']}`")

                if row["system"] != "-" or row["drawing_no"] != "-":
                    st.caption(f"🔗 **Sistem Terhubung:** {row['system']} | 📑 **Drawing / Ref:** {row['drawing_no']}")

with tab_table:
    cols_display = [
        "no", "equipment", "tag", "unit", "pump_merek", "pump_type", "pump_head", "pump_capacity",
        "pump_brg_front", "pump_brg_rear", "motor_power", "motor_volt", "motor_brg_front", "motor_brg_rear"
    ]
    df_table_view = df_filt[cols_display].copy()
    df_table_view.columns = [
        "No", "Nama Peralatan", "Tag/KKS", "Unit/Area", "Merek Pompa", "Type Pompa", "Head", "Kapasitas",
        "Bearing DE Pompa", "Bearing NDE Pompa", "Power Motor", "Voltage", "Bearing DE Motor", "Bearing NDE Motor"
    ]
    
    st.dataframe(df_table_view, use_container_width=True, hide_index=True)
    
    csv_bytes = df_table_view.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Datasheet Lengkap (CSV)",
        data=csv_bytes,
        file_name="datasheet_pompa_pltu_tbk.csv",
        mime="text/csv",
    )
