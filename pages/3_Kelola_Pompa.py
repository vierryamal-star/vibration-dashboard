import sys
import os
import streamlit as st
import pandas as pd
from datetime import datetime

# Tambahkan root folder ke sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import (
    load_history,
    check_role,
    get_pump_runtime,
    init_pump_runtime,
    clear_runtime_caches,
    start_pump_runtime,
    stop_pump_runtime,
    edit_pump_hours,
    reset_pump_runtime
)

st.set_page_config(page_title="Kelola Pompa - Condition Monitoring", layout="wide", page_icon="⚙️")

st.title("⚙️ Manajemen Running Hours & Status Pompa")

# 1. Cek hak akses / autentikasi peran
user_role = check_role() if callable(check_role) else "admin"

# 2. Inisialisasi data runtime jika belum ada
try:
    init_pump_runtime()
except Exception as e:
    st.error(f"Gagal inisialisasi runtime pompa: {e}")

# 3. Ambil data status pompa
runtime_data = get_pump_runtime()

if not runtime_data:
    st.info("Belum ada data pompa terdaftar di database.")
    if st.button("🔄 Refresh Data"):
        clear_runtime_caches()
        st.rerun()
    st.stop()

# 4. Tampilkan Tabel Ringkasan
st.subheader("📊 Status Operasional Saat Ini")

df_pumps = pd.DataFrame(runtime_data)
st.dataframe(df_pumps, use_container_width=True)

# 5. Panel Kontrol Operasional Pompa
st.markdown("---")
st.subheader("🎮 Kontrol Pompa")

col_select, col_action = st.columns([1, 2])

pump_names = [p.get("pump_name", p.get("pump_id", f"Pompa #{i+1}")) for i, p in enumerate(runtime_data)]

with col_select:
    selected_pump = st.selectbox("Pilih Pompa:", pump_names)

with col_action:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("▶️ Start Pompa", use_container_width=True):
            try:
                start_pump_runtime(selected_pump)
                clear_runtime_caches()
                st.success(f"{selected_pump} berhasil dinyalakan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyalakan pompa: {e}")

    with c2:
        if st.button("⏹️ Stop Pompa", use_container_width=True):
            try:
                stop_pump_runtime(selected_pump)
                clear_runtime_caches()
                st.warning(f"{selected_pump} berhasil dimatikan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal mematikan pompa: {e}")

    with c3:
        if st.button("🔄 Refresh", use_container_width=True):
            clear_runtime_caches()
            st.rerun()

# 6. Panel Modifikasi Manual (Khusus Administrator)
if user_role in ["admin", "supervisor"]:
    st.markdown("---")
    st.subheader("🛠️ Pengaturan Manual Running Hours (Admin)")

    tab_edit, tab_reset = st.tabs(["Edit Jam Kerja", "Reset Jam Kerja"])

    with tab_edit:
        with st.form("form_edit_hours"):
            new_hours = st.number_input("Jam Kerja Baru (Hours):", min_value=0.0, step=0.5, format="%.2f")
            submit_edit = st.form_submit_button("Simpan Perubahan")
            if submit_edit:
                try:
                    edit_pump_hours(selected_pump, new_hours)
                    clear_runtime_caches()
                    st.success(f"Jam kerja {selected_pump} diperbarui ke {new_hours} jam.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal mengubah jam kerja: {e}")

    with tab_reset:
        st.warning(f"Tindakan ini akan mengembalikan jam kerja {selected_pump} menjadi 0.")
        if st.button(f"⚠️ Reset {selected_pump} ke 0 Jam", type="secondary"):
            try:
                reset_pump_runtime(selected_pump)
                clear_runtime_caches()
                st.success(f"Jam kerja {selected_pump} berhasil di-reset.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal reset jam kerja: {e}")
