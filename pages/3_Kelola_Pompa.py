import sys
import os
import streamlit as st
import pandas as pd

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

st.set_page_config(page_title="Kelola Jam Operasi - Condition Monitoring", layout="wide", page_icon="⚙️")

st.title("⚙️ Kelola Jam Operasi Pompa")

# 1. Cek hak akses / role
user_role = check_role() if callable(check_role) else "admin"

# 2. Filter / Konteks Unit dan Equipment
col_u, col_e = st.columns(2)
with col_u:
    selected_unit = st.selectbox("Pilih Unit:", ["Unit 1", "Unit 2", "Common"], index=0)
with col_e:
    selected_equipment = st.selectbox(
        "Pilih Kategori Equipment:", 
        ["Water Jet Pump", "Sea Water Pump", "Boiler Feed Pump", "Condensate Pump", "Cooling Water Pump"],
        index=0
    )

# 3. Inisialisasi runtime pompa dengan parameter equipment & unit
try:
    init_pump_runtime(equipment=selected_equipment, unit=selected_unit)
except Exception as e:
    st.error(f"Gagal inisialisasi runtime pompa: {e}")

# 4. Ambil data status pompa (handle jika get_pump_runtime butuh equipment/unit atau tidak)
try:
    runtime_data = get_pump_runtime(equipment=selected_equipment, unit=selected_unit)
except TypeError:
    try:
        runtime_data = get_pump_runtime(selected_equipment)
    except TypeError:
        runtime_data = get_pump_runtime()

# Evaluasi apakah data kosong (DataFrame vs List/Dict)
is_empty = False
if isinstance(runtime_data, pd.DataFrame):
    is_empty = runtime_data.empty
    df_pumps = runtime_data
else:
    is_empty = not runtime_data
    df_pumps = pd.DataFrame(runtime_data) if runtime_data else pd.DataFrame()

if is_empty:
    st.info(f"Belum ada data pompa untuk {selected_equipment} ({selected_unit}).")
    if st.button("🔄 Refresh Data"):
        clear_runtime_caches()
        st.rerun()
    st.stop()

# 5. Tampilkan Tabel Ringkasan
st.subheader(f"📊 Status Operasional: {selected_equipment} - {selected_unit}")
st.dataframe(df_pumps, use_container_width=True)

# 6. Panel Kontrol Operasional Pompa
st.markdown("---")
st.subheader("🎮 Kontrol Jam Operasi")

# Ekstraksi nama / id pompa dari dataframe
possible_cols = ["pump_name", "equipment_name", "nama_pompa", "pump_id", "tag_name", "id"]
found_col = next((c for c in possible_cols if c in df_pumps.columns), df_pumps.columns[0])
pump_names = df_pumps[found_col].dropna().unique().tolist()

col_select, col_action = st.columns([1, 2])

with col_select:
    selected_pump = st.selectbox("Pilih Pompa / Tag:", pump_names)

# Helper untuk memanggil fungsi kontrol secara dinamis sesuai signature parameter di utils
def call_control_fn(fn, pump, eq, un, *extra_args):
    try:
        return fn(pump, equipment=eq, unit=un, *extra_args)
    except TypeError:
        try:
            return fn(pump, *extra_args)
        except TypeError:
            return fn(pump, eq, *extra_args)

with col_action:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("▶️ Start Pompa", use_container_width=True):
            try:
                call_control_fn(start_pump_runtime, selected_pump, selected_equipment, selected_unit)
                clear_runtime_caches()
                st.success(f"{selected_pump} berhasil dinyalakan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal menyalakan pompa: {e}")

    with c2:
        if st.button("⏹️ Stop Pompa", use_container_width=True):
            try:
                call_control_fn(stop_pump_runtime, selected_pump, selected_equipment, selected_unit)
                clear_runtime_caches()
                st.warning(f"{selected_pump} berhasil dimatikan.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal mematikan pompa: {e}")

    with c3:
        if st.button("🔄 Refresh", use_container_width=True):
            clear_runtime_caches()
            st.rerun()

# 7. Panel Modifikasi Manual (Admin / Supervisor)
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
                    call_control_fn(edit_pump_hours, selected_pump, selected_equipment, selected_unit, new_hours)
                    clear_runtime_caches()
                    st.success(f"Jam kerja {selected_pump} diperbarui ke {new_hours} jam.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal mengubah jam kerja: {e}")

    with tab_reset:
        st.warning(f"Tindakan ini akan mengembalikan jam kerja {selected_pump} menjadi 0.")
        if st.button(f"⚠️ Reset {selected_pump} ke 0 Jam", type="secondary"):
            try:
                call_control_fn(reset_pump_runtime, selected_pump, selected_equipment, selected_unit)
                clear_runtime_caches()
                st.success(f"Jam kerja {selected_pump} berhasil di-reset.")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal reset jam kerja: {e}")
