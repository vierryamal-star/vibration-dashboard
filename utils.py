import pandas as pd
from datetime import datetime

# ── Threshold baru ────────────────────────────────────────────────────────────
# A (Accepted)   : < 1.4
# B (Pre Warning): 1.4 - 2.8
# C (Warning)    : 2.8 - 4.5
# D (Danger)     : > 4.5
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

ZONE_BG = {
    "ZONE A": "rgba(59,130,246,.13)",
    "ZONE B": "rgba(34,197,94,.13)",
    "ZONE C": "rgba(217,119,6,.14)",
    "ZONE D": "rgba(220,38,38,.14)",
    "N/A":    "rgba(107,114,128,.1)",
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

# Alias pendek untuk kompatibilitas — diimport di app.py & 1_Analisis.py
ZC = ZONE_COLOR
ZB = ZONE_BG

# ── Threshold suhu (°C) — 3 tier: Normal / Warning / Danger ──────────────────
# Dicocokkan lewat nama TITIK UKUR (bukan jenis equipment) — berlaku sama baik
# equipment-nya Pump maupun Fan (mis. Bearing DE Motor Fan == Bearing DE Motor Pompa).
#
# KONVENSI KHUSUS MOTOR (dikonfirmasi user): titik "DE MOTOR" & "NDE MOTOR" dipakai
# ulang dari titik vibrasi yang SAMA, tapi untuk baris suhu (direction="T") artinya beda:
#   - DE MOTOR  -> suhu BEARING  (74/95°C)
#   - NDE MOTOR -> suhu WINDING  (99/140°C)   <-- BUKAN bearing, meski nama titiknya "MOTOR"
# Pompa/Fan (DE & NDE) tetap bearing biasa, karena tidak ada winding di situ.
THRESHOLD_TEMP = {
    "TURBIN":            {"normal": 80, "danger": 119},
    "WINDING":           {"normal": 99, "danger": 140},
    "BEARING DE MOTOR":  {"normal": 74, "danger": 95},
    "BEARING DE DRIVEN":  {"normal": 74, "danger": 95},  # Bearing DE Pompa/Fan
    "BEARING NDE DRIVEN": {"normal": 74, "danger": 95},  # Bearing NDE Pompa/Fan
}

def get_temp_threshold(equipment: str, titik: str):
    """Pilih threshold suhu berdasarkan nama titik ukur (Turbin/Winding/Bearing DE Motor/Driven)."""
    eq, t = str(equipment).upper(), str(titik).upper()
    if "TURBIN" in eq and "WINDING" not in t:
        return THRESHOLD_TEMP["TURBIN"]
    if "WINDING" in t:
        return THRESHOLD_TEMP["WINDING"]
    if "MOTOR" in t:
        # NDE Motor -> winding (bukan bearing), DE Motor -> bearing. Konvensi khusus motor.
        return THRESHOLD_TEMP["WINDING"] if "NDE" in t else THRESHOLD_TEMP["BEARING DE MOTOR"]
    if any(k in t for k in ["POMPA", "PUMP", "FAN"]):
        return THRESHOLD_TEMP["BEARING NDE DRIVEN" if "NDE" in t else "BEARING DE DRIVEN"]
    return THRESHOLD_TEMP["BEARING DE DRIVEN"]  # fallback

def get_zone_temp(value, thr):
    """Return (zone_key, icon, label) — 3 tier, reuse warna ZONE A(biru)/C(kuning)/D(merah)."""
    if pd.isna(value):
        return "N/A", "⬜", "N/A"
    if value <= thr["normal"]:
        return "ZONE A", "🔵", "Normal"
    elif value < thr["danger"]:
        return "ZONE C", "🟡", "Warning"
    else:
        return "ZONE D", "🔴", "Danger"

def get_supabase(service_role=False):
    import streamlit as st
    from supabase import create_client
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"] if service_role else st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def get_threshold(equipment: str):
    name = equipment.upper()
    if "TURBINE" in name:
        return THRESHOLD["Turbine"]
    return THRESHOLD["Pump/Fan"]

def get_turbine_unit(equipment: str) -> str:
    name = equipment.upper()
    if "TURBINE" in name or "TURBIN" in name:
        if "01" in name or "1" in name:
            return "TBK #1"
        elif "02" in name or "2" in name:
            return "TBK #2"
    return None

def get_zone(value, thr):
    """Return (zone_key, icon, label)"""
    if pd.isna(value):
        return "N/A", "⬜", "N/A"
    if value < thr["A"]:
        return "ZONE A", "🔵", "Accepted"
    elif value <= thr["B"]:
        return "ZONE B", "🟢", "Pre Warning"
    elif value <= thr["C"]:
        return "ZONE C", "🟡", "Warning"
    else:
        return "ZONE D", "🔴", "Danger"

def init_db():
    pass

import streamlit as st

@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    try:
        sb = get_supabase()

        all_rows = []
        batch_size = 1000
        start = 0

        while True:

            res = (
                sb.table("vibration")
                .select("*")
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
    import streamlit as st
    try:
        df = pd.read_excel(file, sheet_name="Vibration_Data")
    except Exception as e:
        st.error(f"Gagal baca file {getattr(file, 'name', 'unknown')}: {e}")
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
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
        st.error(f"Kolom tidak ditemukan: {missing}")
        return pd.DataFrame()
    df["date"]  = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return df[list(required)].dropna(subset=["equipment", "unit", "titik", "direction"])

def load_filtered(df_hist, units, equips, directions):
    if df_hist.empty:
        return pd.DataFrame()
    df = df_hist.copy()
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[df["unit"].isin(units) & df["equipment"].isin(equips) & df["direction"].isin(directions)].copy()

def add_zone_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hitung zone per baris. Baris vibrasi (direction H/V/A) pakai THRESHOLD (mm/s, 4 tier).
    Baris suhu (direction == 'T') pakai THRESHOLD_TEMP (°C, 3 tier) — dicocokkan lewat titik ukur,
    BUKAN via thr_type equipment, karena skala & satuannya beda total dari vibrasi.
    """
    df = df.copy()
    df["thr_type"] = df["equipment"].apply(lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan")

    def _zone_row(r):
        if r["direction"] == "T":
            thr = get_temp_threshold(r["equipment"], r["titik"])
            return get_zone_temp(r["value"], thr)
        return get_zone(r["value"], THRESHOLD[r["thr_type"]])

    z = df.apply(_zone_row, axis=1)
    df["zone"], df["zone_icon"], df["zone_label"] = zip(*z)
    return df

EDITOR_PASSWORD = "pltu2026"

def check_role():
    import streamlit as st
    if "role" not in st.session_state:
        st.session_state["role"] = "viewer"
    return st.session_state["role"]

def render_login_sidebar():
    import streamlit as st
    role = check_role()
    st.sidebar.divider()
    if role == "editor":
        st.sidebar.success("🔓 Mode: **Editor**")
        if st.sidebar.button("🔒 Logout", key="sb_logout"):
            st.session_state["role"] = "viewer"
            st.rerun()
    else:
        st.sidebar.info("👁️ Mode: **Viewer**")
        with st.sidebar.expander("🔑 Login Editor"):
            pwd = st.text_input("Password", type="password", key="sb_pwd_input")
            if st.button("Login", key="sb_login_btn"):
                if pwd == EDITOR_PASSWORD:
                    st.session_state["role"] = "editor"
                    st.rerun()
                else:
                    st.error("Password salah.")

def require_editor():
    import streamlit as st
    if check_role() != "editor":
        st.warning("🔒 Fitur ini hanya tersedia untuk Editor.")
        return False
    return True

# ── Running Hours Pompa (live) ────────────────────────────────────────────────
# Tabel Supabase: pump_runtime
#   equipment (text), unit (text), status (text: 'running'/'stopped'),
#   status_changed_at (timestamptz), accumulated_hours (float8)
# Unique constraint: (equipment, unit)

def get_pump_runtime() -> pd.DataFrame:
    """Baca status running/stopped semua pompa dari Supabase."""
    import streamlit as st
    cols = ["equipment", "unit", "status", "status_changed_at", "accumulated_hours"]
    try:
        sb = get_supabase()
        res = sb.table("pump_runtime").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Gagal load running hours: {e}")
        return pd.DataFrame(columns=cols)

def init_pump_runtime(equipment: str, unit: str):
    """Pastikan baris pump_runtime ada untuk equipment ini; kalau belum, buat baru (status stopped)."""
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

def toggle_pump_runtime(equipment: str, unit: str, current_status: str,
                         current_accum: float, current_changed_at) -> None:
    """Toggle status running <-> stopped. Saat pindah dari running ke stopped,
    akumulasikan jam yang sudah berjalan sejak status_changed_at terakhir."""
    import streamlit as st
    try:
        sb = get_supabase(service_role=True)
        now = datetime.now()
        if current_status == "running":
            try:
                changed = pd.to_datetime(current_changed_at)
                if changed.tzinfo is not None:
                    changed = changed.tz_localize(None)
                delta_hours = max((now - changed).total_seconds() / 3600, 0)
            except Exception:
                delta_hours = 0
            new_accum = float(current_accum or 0) + delta_hours
            new_status = "stopped"
        else:
            new_accum = float(current_accum or 0)
            new_status = "running"
        sb.table("pump_runtime").update({
            "status": new_status,
            "status_changed_at": now.isoformat(),
            "accumulated_hours": new_accum,
        }).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal update status pompa: {e}")

def compute_running_hours(row: dict) -> float:
    """Hitung total running hours SAAT INI (live) — akumulasi + waktu berjalan
    sejak status_changed_at kalau status masih 'running'. Dipanggil ulang tiap
    rerun/autorefresh sehingga angkanya terlihat bertambah otomatis."""
    accum = float(row.get("accumulated_hours", 0) or 0)
    if row.get("status") == "running":
        try:
            changed = pd.to_datetime(row["status_changed_at"])
            if changed.tzinfo is not None:
                changed = changed.tz_localize(None)
            delta = (pd.Timestamp.now() - changed).total_seconds() / 3600
            return accum + max(delta, 0)
        except Exception:
            return accum
    return accum
