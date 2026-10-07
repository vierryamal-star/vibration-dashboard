import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS

try:
    st.set_page_config(
        page_title="Datasheet Pompa — PLTU TBK",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

st.markdown(
    "<style>[data-testid='stSidebarNav'] { display: none !important; } section[data-testid='stSidebar'] > div:first-child { padding-top: 1rem; }</style>",
    unsafe_allow_html=True,
)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("📋 Datasheet Pompa & Peralatan Utama PLTU TBK")
st.caption("Data spesifikasi teknis peralatan langsung dari file datasheet PLTU Tanjung Balai Karimun.")

# ── Cari Lokasi File Excel ──────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)

excel_candidates = [
    os.path.join(root_dir, "Datasheet Pompa PLTU TBK (1).xlsx"),
    os.path.join(current_dir, "Datasheet Pompa PLTU TBK (1).xlsx"),
    os.path.join(root_dir, "Datasheet Pompa PLTU TBK.xlsx"),
]

target_file = None
for path in excel_candidates:
    if os.path.exists(path):
        target_file = path
        break

if not target_file:
    # Cari file .xlsx apa saja di root
    for f in os.listdir(root_dir):
        if f.endswith(".xlsx") and "Datasheet" in f:
            target_file = os.path.join(root_dir, f)
            break

# ── Ekstraksi Sheet Excel Secara Dinamis ─────────────────────────────────────
@st.cache_data(ttl=300)
def load_excel_datasheet(file_path):
    if not file_path or not os.path.exists(file_path):
        return {}
    xls = pd.ExcelFile(file_path)
    all_sheets = {}
    for sheet in xls.sheet_names:
        # Kecualikan sheet Duplex Filter dan Sheet2
        s_clean = sheet.strip()
        if s_clean in ["Duplex Filter", "Sheet2"] or "duplex" in s_clean.lower():
            continue
        df = pd.read_excel(xls, sheet_name=sheet)
        all_sheets[s_clean] = df
    return all_sheets

if not target_file:
    st.error("⚠️ File Excel `Datasheet Pompa PLTU TBK (1).xlsx` tidak ditemukan di repositori GitHub.")
    st.info("Pastikan file Excel telah di-upload ke folder utama project Anda.")
    st.stop()

sheets_dict = load_excel_datasheet(target_file)
sheet_names = list(sheets_dict.keys())

# ── Kontrol Dropdown & Pencarian ─────────────────────────────────────────────
c_select, c_search = st.columns([1.5, 2])

with c_select:
    list_pilihan = ["Semua Sheet"] + sheet_names
    selected_sheet = st.selectbox("📑 Pilih Sheet Peralatan:", list_pilihan)

with c_search:
    keyword = st.text_input("🔍 Cari Teks / Spesifikasi / Part Number:", placeholder="Contoh: 6305, Head, Torishima, Teco...")

# ── Tampilan Data ───────────────────────────────────────────────────────────
sheets_to_display = sheet_names if selected_sheet == "Semua Sheet" else [selected_sheet]

found_any = False
for s_name in sheets_to_display:
    df_raw = sheets_dict[s_name].copy()
    
    # Bersihkan baris dan kolom kosong
    df_clean = df_raw.dropna(how="all").dropna(axis=1, how="all").fillna("")
    
    # Filter kata kunci
    if keyword.strip():
        kw = keyword.strip().lower()
        match_mask = df_clean.astype(str).apply(lambda col: col.str.lower().str.contains(kw)).any(axis=1)
        df_show = df_clean[match_mask]
        if df_show.empty:
            continue
    else:
        df_show = df_clean

    found_any = True
    with st.expander(f"📄 Sheet: **{s_name}**", expanded=(selected_sheet != "Semua Sheet")):
        st.dataframe(df_show, use_container_width=True, hide_index=True)

if not found_any:
    st.info("Tidak ada data atau sheet yang cocok dengan kata kunci pencarian.")
