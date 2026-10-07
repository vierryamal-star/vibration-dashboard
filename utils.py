import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import pytz
import requests
import os

# ==============================================================================
# 1. KONFIGURASI API & SUPABASE
# ==============================================================================
EXTERNAL_VERCEL_API = "https://bearing-monitoring.vercel.app/api/equipment"
BEARING_POSISI = ["DE Motor", "NDE Motor", "DE Pump", "NDE Pump"]

def get_supabase_client():
    """Menginisialisasi Supabase Client jika kredensial tersedia."""
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"[Supabase Init Warning]: {e}")
    return None

# ==============================================================================
# 2. WAKTU & TANGGAL (WIB)
# ==============================================================================
def now_wib() -> datetime:
    """Mengembalikan waktu saat ini dalam zona WIB (Asia/Jakarta)."""
    tz = pytz.timezone("Asia/Jakarta")
    return datetime.now(tz)

def parse_iso_datetime(dt_str):
    """Parsing string ISO timestamp menjadi objek datetime WIB."""
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
# 3. AUTENTIKASI & ROLE
# ==============================================================================
def check_role() -> str:
    """Mengembalikan role akun ('editor' atau 'viewer')."""
    if "user_role" in st.session_state:
        return str(st.session_state["user_role"]).lower()
    return "viewer"

def set_role(role: str):
    """Mengatur role akun ke session state."""
    st.session_state["user_role"] = role.lower()

# ==============================================================================
# 4. SINKRONISASI API VERCEL (RUNNING HOURS & BEARINGS)
# ==============================================================================
def map_vercel_area_to_unit(area_str: str) -> str:
    """Memetakan field area Vercel ke unit standar PLTU TBK."""
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
    """Mengambil payload data mesin & bearing dari REST API Vercel."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    try:
        res = requests.get(EXTERNAL_VERCEL_API, headers=headers, timeout=10)
        if res.status_code == 200:
            payload = res.json()
            if isinstance(payload, dict):
                return payload.get("equipment", [])
            elif isinstance(payload, list):
                return payload
    except Exception as e:
        print(f"[Vercel Fetch Error]: {e}")
    return []

def get_synced_running_hours_df() -> pd.DataFrame:
    """Mengubah payload JSON Vercel menjadi DataFrame yang siap divisualisasikan."""
    items = fetch_vercel_running_data()
    if not items:
        return pd.DataFrame()

    rows = []
    for eq in items:
        rt = eq.get("runtime", {})
        total_h = float(rt.get("total_hours") or 0.0)
        sess_h = float(rt.get("current_session_hours") or 0.0)
        eff_total = total_h + sess_h if str(eq.get("status", "")).upper() == "RUNNING" else total_h

        bearings = eq.get("bearings", [])
        brg_dict = {}
        for b in bearings:
            pos = b.get("position")
            brg_dict[pos] = {
                "code": b.get("bearing_code", ""),
                "hours": float(b.get("hours") or 0.0),
                "install_date": b.get("installation_date"),
                "limit_hours": b.get("limit_hours"),
                "remaining_hours": b.get("remaining_hours"),
                "usage_percent": b.get("usage_percent", 0),
                "status": b.get("status", "NORMAL")
            }

        rows.append({
            "id": eq.get("id"),
            "code": eq.get("code", ""),
            "equipment": eq.get("name", ""),
            "area": eq.get("area", ""),
            "unit": map_vercel_area_to_unit(eq.get("area", "")),
            "status": str(eq.get("status", "STOPPED")).lower(),
            "total_hours": eff_total,
            "session_hours": sess_h,
            "session_started_at": rt.get("session_started_at"),
            "equipment_type": eq.get("equipment_type", ""),
            "bearings": brg_dict,
            "bearing_status": eq.get("bearing_status", "NORMAL")
        })

    return pd.DataFrame(rows)

# ==============================================================================
# 5. PEMANTAUAN UMUR BEARING & LOCAL RUNTIME
# ==============================================================================
def compute_running_hours(row_dict: dict) -> float:
    base_hours = float(row_dict.get("accumulated_hours") or row_dict.get("total_hours") or 0.0)
    status = str(row_dict.get("status", "")).lower()
    started_at_str = row_dict.get("last_started_at") or row_dict.get("session_started_at")
    if status == "running" and started_at_str:
        started_dt = parse_iso_datetime(started_at_str)
        if started_dt:
            delta_sec = (now_wib() - started_dt).total_seconds()
            if delta_sec > 0:
                return base_hours + (delta_sec / 3600.0)
    return base_hours

def get_pump_age(install_date_val) -> str:
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

        diff_days = (now_wib().date() - inst_d).days
        if diff_days < 0:
            return "0 Hari"
        elif diff_days < 30:
            return f"{diff_days} Hari"
        elif diff_days < 365:
            return f"{diff_days // 30} Bln {diff_days % 30} Hr"
        else:
            return f"{diff_days // 365} Thn {(diff_days % 365) // 30} Bln"
    except Exception:
        return None

def get_pump_runtime() -> pd.DataFrame:
    df_sync = get_synced_running_hours_df()
    if not df_sync.empty:
        return df_sync
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("pump_runtime").select("*").execute()
            if res.data:
                return pd.DataFrame(res.data)
        except Exception:
            pass
    return pd.DataFrame()

def get_bearing_install() -> pd.DataFrame:
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("bearing_install").select("*").execute()
            if res.data:
                return pd.DataFrame(res.data)
        except Exception:
            pass
    return pd.DataFrame()

def update_bearing_install(equipment: str, unit: str, posisi: str, new_date):
    sb = get_supabase_client()
    val_date_str = str(new_date) if new_date is not None else None
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
        except Exception:
            pass

def load_history() -> pd.DataFrame:
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("vibration_history").select("equipment, unit").execute()
            if res.data:
                return pd.DataFrame(res.data)
        except Exception:
            pass
    df_sync = get_synced_running_hours_df()
    if not df_sync.empty:
        return df_sync[["equipment", "unit"]].drop_duplicates()
    return pd.DataFrame(columns=["equipment", "unit"])

# ==============================================================================
# 6. GLOBAL UI & LAYOUT COMPONENTS
# ==============================================================================
GLOBAL_UI_CSS = """
<style>
h1, h2, h3, h4, h5, h6 { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 800; }
</style>
"""

def render_page_header(title: str):
    st.markdown(f"### {title}")

def render_app_sidebar():
    with st.sidebar:
        st.markdown("#### ⚡ PLTU TBK MONITORING")
        st.caption("PLTU Tanjung Balai Karimun (2 x 7 MW)")
        st.markdown("---")
        curr_role = check_role()
        role_label = "🟢 Editor" if curr_role == "editor" else "⚪ Viewer"
        st.markdown(f"**Hak Akses:** `{role_label}`")
        if curr_role != "editor":
            with st.expander("🔑 Login Editor"):
                pwd = st.text_input("Password", type="password", key="sb_pwd")
                if st.button("Masuk", key="sb_btn_login", use_container_width=True):
                    if pwd in ["editor123", "admin123"]:
                        set_role("editor")
                        st.success("Login Editor berhasil!")
                        st.rerun()
                    else:
                        st.error("Password salah.")
        else:
            if st.button("Keluar", key="sb_btn_logout", use_container_width=True):
                set_role("viewer")
                st.rerun()
        st.markdown("---")
        st.caption("Sistem Pemantauan Vibrasi & Jam Operasi Mesin.")
