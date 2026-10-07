import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import pytz
import requests
import os

# ==============================================================================
# 1. KONFIGURASI SUPABASE & API EKSTERNAL
# ==============================================================================
EXTERNAL_VERCEL_API = "https://bearing-monitoring.vercel.app/api/equipment"
BEARING_POSISI = ["DE Motor", "NDE Motor", "DE Pump", "NDE Pump"]

def get_supabase_client():
    """Menginisialisasi koneksi Supabase Client dengan fallback aman."""
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"[Supabase Client Init Error]: {e}")
    return None

# ==============================================================================
# 2. WAKTU & TANGGAL (WIB)
# ==============================================================================
def now_wib() -> datetime:
    """Mengembalikan datetime saat ini dalam zona waktu WIB (UTC+7)."""
    tz = pytz.timezone("Asia/Jakarta")
    return datetime.now(tz)

def parse_iso_datetime(dt_str):
    """Parsing string timestamp ISO menjadi datetime objek dengan aman."""
    if not dt_str:
        return None
    try:
        cleaned = str(dt_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        tz = pytz.timezone("Asia/Jakarta")
        return dt.astimezone(tz)
    except Exception:
        return None

# ==============================================================================
# 3. AUTENTIKASI & ROLE PENGGUNA
# ==============================================================================
def check_role() -> str:
    """
    Memeriksa role pengguna yang sedang login.
    Mengembalikan 'editor' atau 'viewer'. Default: 'viewer'.
    """
    if "user_role" in st.session_state:
        return str(st.session_state["user_role"]).lower()
    if "role" in st.session_state:
        return str(st.session_state["role"]).lower()
    return "viewer"

def set_role(role: str):
    """Menyetel role pengguna di session state."""
    st.session_state["user_role"] = role.lower()

# ==============================================================================
# 4. RUNNING HOURS & RUNTIME LOGIC (LOCAL / SUPABASE)
# ==============================================================================
def compute_running_hours(row_dict: dict) -> float:
    """
    Menghitung running hours efektif.
    Jika status 'running', tambahkan selisih waktu dari start_time ke akumulasi.
    """
    base_hours = float(row_dict.get("accumulated_hours") or row_dict.get("total_hours") or 0.0)
    status = str(row_dict.get("status", "")).lower()
    started_at_str = row_dict.get("last_started_at") or row_dict.get("session_started_at")

    if status == "running" and started_at_str:
        started_dt = parse_iso_datetime(started_at_str)
        if started_dt:
            curr_wib = now_wib()
            delta_sec = (curr_wib - started_dt).total_seconds()
            if delta_sec > 0:
                return base_hours + (delta_sec / 3600.0)
    return base_hours

def get_pump_runtime() -> pd.DataFrame:
    """Mengambil status jam operasi lokal/database."""
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("pump_runtime").select("*").execute()
            if res.data:
                return pd.DataFrame(res.data)
        except Exception as e:
            print(f"[Supabase pump_runtime Error]: {e}")
    
    # Fallback jika Supabase belum dikonfigurasi
    if "pump_runtime_data" in st.session_state:
        return pd.DataFrame(st.session_state["pump_runtime_data"])
    return pd.DataFrame()

# ==============================================================================
# 5. PEMANTAUAN UMUR BEARING
# ==============================================================================
def get_pump_age(install_date_val) -> str:
    """Menghitung selisih hari/bulan/tahun sejak tanggal instalasi bearing."""
    if not install_date_val or pd.isna(install_date_val):
        return None
    try:
        if isinstance(install_date_val, str):
            inst_d = datetime.strptime(install_date_val[:10], "%Y-%m-%d").date()
        elif isinstance(install_date_val, datetime):
            inst_d = install_date_val.date()
        elif isinstance(install_date_val, date):
            inst_d = install_date_val
        else:
            return None

        today = now_wib().date()
        diff_days = (today - inst_d).days

        if diff_days < 0:
            return "0 Hari"
        elif diff_days < 30:
            return f"{diff_days} Hari"
        elif diff_days < 365:
            bln = diff_days // 30
            sisa_hari = diff_days % 30
            return f"{bln} Bln {sisa_hari} Hr"
        else:
            thn = diff_days // 365
            sisa_bln = (diff_days % 365) // 30
            return f"{thn} Thn {sisa_bln} Bln"
    except Exception:
        return None

def get_bearing_install() -> pd.DataFrame:
    """Mengambil catatan tanggal pasang bearing."""
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("bearing_install").select("*").execute()
            if res.data:
                return pd.DataFrame(res.data)
        except Exception as e:
            print(f"[Supabase get_bearing_install Error]: {e}")

    if "bearing_install_data" in st.session_state:
        return pd.DataFrame(st.session_state["bearing_install_data"])
    return pd.DataFrame()

def update_bearing_install(equipment: str, unit: str, posisi: str, new_date):
    """
    Memperbarui atau mereset tanggal pasang bearing.
    Jika new_date None, tanggal akan dikosongkan (tidak berakumulasi).
    """
    sb = get_supabase_client()
    val_date_str = str(new_date) if new_date is not None else None

    # Simpan ke Supabase jika aktif
    if sb:
        try:
            payload = {
                "equipment": equipment,
                "unit": unit,
                "posisi": posisi,
                "install_date": val_date_str,
                "updated_at": now_wib().isoformat()
            }
            sb.table("bearing_install").upsert(payload, on_conflict="equipment,unit,posisi").execute()
        except Exception as e:
            print(f"[Supabase update_bearing_install Error]: {e}")

    # Fallback ke session state lokal
    if "bearing_install_data" not in st.session_state:
        st.session_state["bearing_install_data"] = []

    existing = [r for r in st.session_state["bearing_install_data"] 
                if not (r.get("equipment") == equipment and r.get("unit") == unit and r.get("posisi") == posisi)]
    
    if val_date_str:
        existing.append({
            "equipment": equipment,
            "unit": unit,
            "posisi": posisi,
            "install_date": val_date_str
        })
    st.session_state["bearing_install_data"] = existing

# ==============================================================================
# 6. SINKRONISASI API VERCEL (BEARING MONITORING)
# ==============================================================================
def map_vercel_area_to_unit(area_str: str) -> str:
    """Memetakan area Vercel ke format penamaan unit standar PLTU TBK."""
    if not area_str:
        return "TBK COM"
    a = str(area_str).upper()
    if "TURBIN 2" in a or "BOILER 2" in a or "UNIT 2" in a:
        return "TBK #2"
    elif "TURBIN" in a or "BOILER" in a or "UNIT 1" in a:
        return "TBK #1"
    elif "UNLOADING" in a or "LOADING" in a:
        return "TBK CAH"
    elif "COMMON" in a:
        return "TBK COM"
    return f"TBK {area_str}"

@st.cache_data(ttl=60)
def fetch_vercel_running_data():
    """Mengambil list peralatan live dari API Vercel dengan timeout dan cache 60 detik."""
    try:
        res = requests.get(EXTERNAL_VERCEL_API, timeout=8)
        if res.status_code == 200:
            data = res.json()
            return data.get("equipment", [])
    except Exception as e:
        print(f"[Vercel Fetch Error]: {e}")
    return []

def get_synced_running_hours_df() -> pd.DataFrame:
    """Mengolah JSON Vercel menjadi DataFrame running hours & bearing yang siap pakai."""
    raw_list = fetch_vercel_running_data()
    if not raw_list:
        return pd.DataFrame()

    rows = []
    for item in raw_list:
        rt = item.get("runtime", {})
        total_h = float(rt.get("total_hours") or 0.0)
        sess_h = float(rt.get("current_session_hours") or 0.0)
        eff_total = total_h + sess_h if str(item.get("status", "")).upper() == "RUNNING" else total_h

        bearings = item.get("bearings", [])
        brg_dict = {}
        for b in bearings:
            pos = b.get("position")
            brg_dict[pos] = {
                "hours": float(b.get("hours") or 0.0),
                "install_date": b.get("installation_date"),
                "limit_hours": b.get("limit_hours"),
                "remaining_hours": b.get("remaining_hours"),
                "usage_percent": b.get("usage_percent", 0),
                "status": b.get("status", "NORMAL")
            }

        rows.append({
            "id": item.get("id"),
            "code": item.get("code", ""),
            "equipment": item.get("name", ""),
            "area": item.get("area", ""),
            "unit": map_vercel_area_to_unit(item.get("area", "")),
            "status": str(item.get("status", "STOPPED")).lower(),
            "total_hours": eff_total,
            "session_hours": sess_h,
            "session_started_at": rt.get("session_started_at"),
            "equipment_type": item.get("equipment_type", ""),
            "bearings": brg_dict,
            "bearing_status": item.get("bearing_status", "NORMAL")
        })

    return pd.DataFrame(rows)

# ==============================================================================
# 7. LOAD HISTORY & EQUIPMENT REPOSITORY
# ==============================================================================
def load_history() -> pd.DataFrame:
    """Mengambil history pengukuran vibrasi / daftar equipment terdaftar."""
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("vibration_history").select("equipment, unit").execute()
            if res.data:
                return pd.DataFrame(res.data)
        except Exception:
            pass

    # Jika tabel histori belum di-load, fallback dari data sinkronisasi Vercel
    df_sync = get_synced_running_hours_df()
    if not df_sync.empty:
        return df_sync[["equipment", "unit"]].drop_duplicates()

    return pd.DataFrame(columns=["equipment", "unit"])

# ==============================================================================
# 8. GLOBAL UI & LAYOUT COMPONENTS
# ==============================================================================
GLOBAL_UI_CSS = """
<style>
/* Main typography and card stylings */
h1, h2, h3, h4, h5, h6 { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 800; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    padding: 8px 16px;
    border-radius: 8px 8px 0 0;
    font-weight: 600;
}
</style>
"""

def render_page_header(title: str):
    """Menampilkan header judul halaman standar."""
    st.markdown(f"### {title}")

def render_app_sidebar():
    """Menampilkan sidebar navigasi dan informasi hak akses."""
    with st.sidebar:
        st.markdown("#### ⚡ PLTU TBK MONITORING")
        st.caption("PLTU Tanjung Balai Karimun (2 x 7 MW)")
        st.markdown("---")
        
        # Status Akun
        curr_role = check_role()
        role_label = "🟢 Editor (Akses Penuh)" if curr_role == "editor" else "⚪ Viewer (Hanya Lihat)"
        st.markdown(f"**Hak Akses:** `{role_label}`")

        # Tombol Login Sederhana
        if curr_role != "editor":
            with st.expander("🔑 Login Editor"):
                pwd = st.text_input("Password Editor", type="password", key="sb_login_pwd")
                if st.button("Masuk", key="sb_btn_login", use_container_width=True):
                    # Validasi password (sesuaikan password jika diperlukan)
                    if pwd == "editor123" or pwd == st.secrets.get("EDITOR_PASSWORD", "admin123"):
                        set_role("editor")
                        st.success("Login Editor berhasil!")
                        st.rerun()
                    else:
                        st.error("Password salah.")
        else:
            if st.button("Keluar (Logout)", key="sb_btn_logout", use_container_width=True):
                set_role("viewer")
                st.rerun()

        st.markdown("---")
        st.caption("Pusat Pengawasan Vibrasi, Rotor Balancing & Umur Bearing Mesin.")
