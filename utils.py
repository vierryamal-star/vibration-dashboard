import pandas as pd
from datetime import datetime, date
import streamlit as st

# ── Threshold ISO 10816 ────────────────────────────────────────────────────────
THRESHOLD = {
    "Turbine": {"A": 1.4, "B": 2.8, "C": 4.5},
    "Pump/Fan": {"A": 1.4, "B": 2.8, "C": 4.5},
}

ZONE_COLOR = {
    "ZONE A": "#3b82f6",
    "ZONE B": "#22c55e",
    "ZONE C": "#d97706",
    "ZONE D": "#dc2626",
    "N/A":    "#6b7280",
}

# Opacity dinaikkan dari 0.13 menjadi 0.22 - 0.25 agar warna zona tegas dan jelas
ZONE_BG = {
    "ZONE A": "rgba(59,130,246,.22)",
    "ZONE B": "rgba(34,197,94,.22)",
    "ZONE C": "rgba(217,119,6,.24)",
    "ZONE D": "rgba(220,38,38,.24)",
    "N/A":    "rgba(107,114,128,.15)",
}

ZONE_LABEL = {
    "ZONE A": "Accepted",
    "ZONE B": "Pre Warning",
    "ZONE C": "Warning",
    "ZONE D": "Danger",
    "N/A":    "N/A",
}

ZONE_ICON = {
    "ZONE A": "🔵",
    "ZONE B": "🟢",
    "ZONE C": "🟡",
    "ZONE D": "🔴",
    "N/A":    "⬜",
}

ZC = ZONE_COLOR
ZB = ZONE_BG

THRESHOLD_TEMP = {
    "TURBIN":            {"normal": 80, "danger": 119},
    "WINDING":           {"normal": 99, "danger": 140},
    "BEARING DE MOTOR":  {"normal": 74, "danger": 95},
    "BEARING DE DRIVEN":  {"normal": 74, "danger": 95},
    "BEARING NDE DRIVEN": {"normal": 74, "danger": 95},
}

def get_temp_threshold(equipment: str, titik: str):
    eq, t = str(equipment).upper(), str(titik).upper()
    if "TURBIN" in eq and "WINDING" not in t:
        return THRESHOLD_TEMP["TURBIN"]
    if "WINDING" in t:
        return THRESHOLD_TEMP["WINDING"]
    if "MOTOR" in t:
        return THRESHOLD_TEMP["WINDING"] if "NDE" in t else THRESHOLD_TEMP["BEARING DE MOTOR"]
    if any(k in t for k in ["POMPA", "PUMP", "FAN"]):
        return THRESHOLD_TEMP["BEARING NDE DRIVEN" if "NDE" in t else "BEARING DE DRIVEN"]
    return THRESHOLD_TEMP["BEARING DE DRIVEN"]

def get_zone_temp(value, thr):
    if pd.isna(value) or value is None:
        return "N/A", "⬜", "N/A"
    try:
        val = float(value)
    except (ValueError, TypeError):
        return "N/A", "⬜", "N/A"
    if val <= thr["normal"]:
        return "ZONE A", "🔵", "Normal"
    elif val < thr["danger"]:
        return "ZONE C", "🟡", "Warning"
    else:
        return "ZONE D", "🔴", "Danger"

def get_supabase(service_role=False):
    from supabase import create_client
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_KEY"] if service_role else st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Gagal koneksi Supabase. Pastikan secrets terkonfigurasi: {e}")
        st.stop()

def get_threshold(equipment: str):
    name = str(equipment).upper()
    if "TURBINE" in name or "TURBIN" in name:
        return THRESHOLD["Turbine"]
    return THRESHOLD["Pump/Fan"]

def get_zone(value, thr):
    if pd.isna(value) or value is None:
        return "N/A", "⬜", "N/A"
    try:
        val = float(value)
    except (ValueError, TypeError):
        return "N/A", "⬜", "N/A"
    if val < thr["A"]:
        return "ZONE A", "🔵", "Accepted"
    elif val <= thr["B"]:
        return "ZONE B", "🟢", "Pre Warning"
    elif val <= thr["C"]:
        return "ZONE C", "🟡", "Warning"
    else:
        return "ZONE D", "🔴", "Danger"

@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    try:
        sb = get_supabase()
        all_rows = []
        batch_size = 5000
        start = 0
        _cols = "equipment,unit,titik,direction,date,value"

        while True:
            res = (
                sb.table("vibration")
                .select(_cols)
                .order("date", desc=True)
                .range(start, start + batch_size - 1)
                .execute()
            )
            rows = res.data if res.data else []
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < batch_size:
                break
            start += batch_size

        return pd.DataFrame(all_rows)
    except Exception as e:
        st.error(f"Gagal load data: {e}")
        return pd.DataFrame()

def save_to_db(df: pd.DataFrame) -> int:
    try:
        sb = get_supabase(service_role=True)
        now = datetime.now().isoformat()
        res = sb.table("vibration").select("equipment,unit,titik,direction,date").execute()
        existing_keys = set()
        if res.data:
            for row in res.data:
                key = f"{row['equipment']}|{row['unit']}|{row['titik']}|{row['direction']}|{str(row['date'])[:10]}"
                existing_keys.add(key)
        rows_to_insert = []
        for _, r in df.iterrows():
            date_str = str(r["date"])[:10] if pd.notna(r["date"]) else ""
            key = f"{r['equipment']}|{r['unit']}|{r['titik']}|{r['direction']}|{date_str}"
            if key not in existing_keys:
                rows_to_insert.append({
                    "equipment":   str(r["equipment"]),
                    "unit":        str(r["unit"]),
                    "titik":       str(r["titik"]),
                    "direction":   str(r["direction"]),
                    "date":        date_str,
                    "value":       float(r["value"]) if pd.notna(r["value"]) else None,
                    "uploaded_at": now,
                })
        if rows_to_insert:
            batch_size = 500
            for i in range(0, len(rows_to_insert), batch_size):
                sb.table("vibration").insert(rows_to_insert[i:i+batch_size]).execute()
        return len(rows_to_insert)
    except Exception as e:
        st.error(f"Gagal simpan data: {e}")
        return 0

def delete_by_dates(dates: list) -> int:
    try:
        sb = get_supabase(service_role=True)
        total = 0
        for d in dates:
            res = sb.table("vibration").delete().eq("date", d).execute()
            if res.data:
                total += len(res.data)
        return total
    except Exception as e:
        st.error(f"Gagal hapus data: {e}")
        return 0

def delete_all() -> int:
    try:
        sb = get_supabase(service_role=True)
        res = sb.table("vibration").delete().neq("equipment", "").execute()
        return len(res.data) if res.data else 0
    except Exception as e:
        st.error(f"Gagal hapus semua data: {e}")
        return 0

def parse_excel(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file, sheet_name="Vibration_Data")
    except Exception:
        try:
            df = pd.read_excel(file)
        except Exception as e:
            st.error(f"Gagal baca file {getattr(file, 'name', 'unknown')}: {e}")
            return pd.DataFrame()
            
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "equipment" in cl:    col_map[c] = "equipment"
        elif "unit" in cl:       col_map[c] = "unit"
        elif "titik" in cl:      col_map[c] = "titik"
        elif "direction" in cl:  col_map[c] = "direction"
        elif "date" in cl:       col_map[c] = "date"
        elif "value" in cl:      col_map[c] = "value"
    df = df.rename(columns=col_map)
    required = {"equipment", "unit", "titik", "direction", "date", "value"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Kolom wajib tidak ditemukan: {missing}")
        return pd.DataFrame()
        
    df["date"]  = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "value", "equipment", "unit", "titik", "direction"])
    return df[list(required)]

def add_zone_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["thr_type"] = df["equipment"].apply(lambda x: "Turbine" if "turbine" in str(x).lower() or "turbin" in str(x).lower() else "Pump/Fan")

    def _zone_row(r):
        if r["direction"] == "T":
            thr = get_temp_threshold(r["equipment"], r["titik"])
            return get_zone_temp(r["value"], thr)
        return get_zone(r["value"], THRESHOLD[r["thr_type"]])

    z = df.apply(_zone_row, axis=1)
    df["zone"], df["zone_icon"], df["zone_label"] = zip(*z)
    return df

def get_editor_password():
    return st.secrets.get("EDITOR_PASSWORD", "pltu2026")

def check_role():
    if "role" not in st.session_state:
        st.session_state["role"] = "viewer"
    return st.session_state["role"]

def render_login_sidebar():
    role = check_role()
    st.sidebar.divider()
    if role == "editor":
        st.sidebar.success("🔓 Mode: **Editor**")
        if st.sidebar.button("🔒 Logout", key="sb_logout", use_container_width=True):
            st.session_state["role"] = "viewer"
            st.rerun()
    else:
        st.sidebar.info("👁️ Mode: **Viewer**")
        with st.sidebar.expander("🔑 Login Editor"):
            pwd = st.text_input("Password", type="password", key="sb_pwd_input")
            if st.button("Login", key="sb_login_btn", use_container_width=True):
                if pwd == get_editor_password():
                    st.session_state["role"] = "editor"
                    st.rerun()
                else:
                    st.error("Password salah.")

def require_editor():
    if check_role() != "editor":
        st.warning("🔒 Fitur ini hanya tersedia untuk Editor.")
        return False
    return True

# ── Running Hours Pompa ───────────────────────────────────────────────────────
@st.cache_data(ttl=15)
def get_pump_runtime() -> pd.DataFrame:
    cols = ["equipment", "unit", "status", "status_changed_at", "accumulated_hours", "install_date"]
    try:
        sb = get_supabase()
        res = sb.table("pump_runtime").select(",".join(cols)).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Gagal load running hours: {e}")
        return pd.DataFrame(columns=cols)

def init_pump_runtime(equipment: str, unit: str):
    sb = get_supabase(service_role=True)
    res = sb.table("pump_runtime").select("id").eq("equipment", equipment).eq("unit", unit).execute()
    if not res.data:
        sb.table("pump_runtime").insert({
            "equipment": equipment,
            "unit": unit,
            "status": "stopped",
            "status_changed_at": datetime.now().isoformat(),
            "accumulated_hours": 0.0,
        }).execute()

def _to_naive_dt(dt_input):
    if dt_input is None or pd.isna(dt_input):
        return None
    dt = pd.to_datetime(dt_input)
    if dt.tzinfo is not None:
        dt = dt.tz_localize(None)
    return dt

def compute_running_hours(row: dict) -> float:
    accum = float(row.get("accumulated_hours", 0) or 0)
    if row.get("status") == "running":
        try:
            changed = _to_naive_dt(row.get("status_changed_at"))
            if changed:
                now_dt = datetime.now()
                delta = (now_dt - changed.to_pydatetime()).total_seconds() / 3600
                return accum + max(delta, 0.0)
        except Exception:
            return accum
    return accum

def start_pump_runtime(equipment: str, unit: str, start_dt) -> None:
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update({
            "status": "running",
            "status_changed_at": pd.Timestamp(start_dt).isoformat(),
        }).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal catat waktu mulai: {e}")

def stop_pump_runtime(equipment: str, unit: str, stop_dt, current_status: str,
                       current_accum: float, current_changed_at) -> None:
    try:
        sb = get_supabase(service_role=True)
        stop_ts = _to_naive_dt(stop_dt)
        if current_status == "running":
            try:
                changed = _to_naive_dt(current_changed_at)
                delta_hours = max((stop_ts - changed).total_seconds() / 3600, 0.0) if changed else 0.0
            except Exception:
                delta_hours = 0.0
            new_accum = float(current_accum or 0) + delta_hours
        else:
            new_accum = float(current_accum or 0)
        sb.table("pump_runtime").update({
            "status": "stopped",
            "status_changed_at": stop_ts.isoformat(),
            "accumulated_hours": new_accum,
        }).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal catat waktu berhenti: {e}")

def reset_pump_runtime(equipment: str, unit: str) -> None:
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update({
            "status": "stopped",
            "status_changed_at": datetime.now().isoformat(),
            "accumulated_hours": 0.0,
        }).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal reset running hours: {e}")

def reset_pump_install_date(equipment: str, unit: str) -> None:
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update(
            {"install_date": datetime.now().date().isoformat()}
        ).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal reset umur pompa: {e}")

def get_pump_age(install_date) -> str:
    if not install_date or pd.isna(install_date):
        return None
    try:
        d = pd.to_datetime(install_date)
        now = datetime.now()
        months = (now.year - d.year) * 12 + (now.month - d.month)
        if now.day < d.day:
            months -= 1
        months = max(months, 0)
        years, rem_months = divmod(months, 12)
        parts = []
        if years: parts.append(f"{years} th")
        parts.append(f"{rem_months} bln")
        return " ".join(parts)
    except Exception:
        return None

def update_pump_install_date(equipment: str, unit: str, install_date) -> None:
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update(
            {"install_date": str(install_date)}
        ).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal simpan tanggal instalasi: {e}")

BEARING_POSISI = ["DE Motor", "NDE Motor", "DE Pompa/Fan", "NDE Pompa/Fan"]

def get_bearing_install() -> pd.DataFrame:
    cols = ["equipment", "unit", "posisi", "install_date"]
    try:
        sb = get_supabase()
        res = sb.table("bearing_install").select(",".join(cols)).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Gagal load umur bearing: {e}")
        return pd.DataFrame(columns=cols)

def update_bearing_install(equipment: str, unit: str, posisi: str, install_date) -> None:
    try:
        sb = get_supabase(service_role=True)
        existing = (
            sb.table("bearing_install").select("id")
            .eq("equipment", equipment).eq("unit", unit).eq("posisi", posisi)
            .execute()
        )
        if existing.data:
            sb.table("bearing_install").update(
                {"install_date": str(install_date)}
            ).eq("equipment", equipment).eq("unit", unit).eq("posisi", posisi).execute()
        else:
            sb.table("bearing_install").insert({
                "equipment": equipment, "unit": unit, "posisi": posisi,
                "install_date": str(install_date),
            }).execute()
    except Exception as e:
        st.error(f"Gagal simpan tanggal instalasi bearing: {e}")
