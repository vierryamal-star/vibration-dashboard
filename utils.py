import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "vibration_history.db"

THRESHOLD = {
    "Turbine": {"A": 3.8, "B": 7.5, "C": 11.8},
    "Pump/Fan": {"A": 1.4, "B": 2.8, "C": 4.5},
}

ZONE_COLOR = {
    "ZONE A": "#22c55e",
    "ZONE B": "#eab308",
    "ZONE C": "#f97316",
    "ZONE D": "#ef4444",
    "N/A":    "#94a3b8",
}

def get_threshold(equipment: str):
    name = equipment.upper()
    if "TURBINE" in name:
        return THRESHOLD["Turbine"]
    return THRESHOLD["Pump/Fan"]

def get_turbine_unit(equipment: str) -> str:
    """Kembalikan unit berdasarkan nama turbine (Turbine 01 → TBK #1, Turbine 02 → TBK #2)."""
    name = equipment.upper()
    if "TURBINE" in name or "TURBIN" in name:
        if "01" in name or "1" in name:
            return "TBK #1"
        elif "02" in name or "2" in name:
            return "TBK #2"
    return None

def get_zone(value, thr):
    if pd.isna(value):
        return "N/A", "⬜"
    if value <= thr["A"]:
        return "ZONE A", "🟢"
    elif value <= thr["B"]:
        return "ZONE B", "🟡"
    elif value <= thr["C"]:
        return "ZONE C", "🟠"
    else:
        return "ZONE D", "🔴"

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS vibration (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment   TEXT,
            unit        TEXT,
            titik       TEXT,
            direction   TEXT,
            date        TEXT,
            value       REAL,
            uploaded_at TEXT
        )
    """)
    con.commit()
    con.close()

def save_to_db(df: pd.DataFrame):
    con = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    rows = df.copy()
    rows["uploaded_at"] = now
    try:
        existing = pd.read_sql(
            "SELECT equipment, unit, titik, direction, date FROM vibration", con
        )
        existing["_key"] = (
            existing["equipment"].astype(str) + "|" +
            existing["unit"].astype(str) + "|" +
            existing["titik"].astype(str) + "|" +
            existing["direction"].astype(str) + "|" +
            pd.to_datetime(existing["date"], errors="coerce").dt.date.astype(str)
        )
        rows["_key"] = (
            rows["equipment"].astype(str) + "|" +
            rows["unit"].astype(str) + "|" +
            rows["titik"].astype(str) + "|" +
            rows["direction"].astype(str) + "|" +
            pd.to_datetime(rows["date"], errors="coerce").dt.date.astype(str)
        )
        rows_new = rows[~rows["_key"].isin(existing["_key"])].drop(columns=["_key"])
    except Exception:
        rows_new = rows.copy()
    saved = len(rows_new)
    if not rows_new.empty:
        rows_new.to_sql("vibration", con, if_exists="append", index=False)
    con.close()
    return saved

def load_history() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM vibration ORDER BY date DESC", con)
    except Exception:
        df = pd.DataFrame()
    con.close()
    return df

def parse_excel(file) -> pd.DataFrame:
    import streamlit as st
    df = pd.read_excel(file, sheet_name="Vibration_Data")
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
    df["date"]  = pd.to_datetime(df["date"],  errors="coerce")
    df["value"] = pd.to_numeric(df["value"],  errors="coerce")
    return df[list(required)].dropna(subset=["equipment", "unit", "titik", "direction"])

def load_filtered(df_hist: pd.DataFrame, units, equips, directions) -> pd.DataFrame:
    if df_hist.empty:
        return pd.DataFrame()
    df = df_hist.copy()
    df["date"]  = pd.to_datetime(df["date"],  errors="coerce")
    df["value"] = pd.to_numeric(df["value"],  errors="coerce")
    return df[
        df["unit"].isin(units) &
        df["equipment"].isin(equips) &
        df["direction"].isin(directions)
    ].copy()

def add_zone_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["thr_type"] = df["equipment"].apply(
        lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan"
    )
    df["zone"] = df.apply(
        lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[0], axis=1
    )
    df["zone_icon"] = df.apply(
        lambda r: get_zone(r["value"], THRESHOLD[r["thr_type"]])[1], axis=1
    )
    return df

# ── Sistem autentikasi role ────────────────────────────────────────────────────
EDITOR_PASSWORD = "pltu2026"   # Ganti sesuai kebutuhan

def check_role():
    """
    Kembalikan role sesi saat ini: 'viewer' atau 'editor'.
    Disimpan di st.session_state['role'].
    """
    import streamlit as st
    if "role" not in st.session_state:
        st.session_state["role"] = "viewer"
    return st.session_state["role"]

def render_login_sidebar():
    """
    Tampilkan widget login/logout di sidebar.
    Viewer bisa lihat semua data, Editor bisa upload/hapus/edit.
    """
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
    """
    Blokir aksi jika bukan editor. Kembalikan True jika editor, False jika viewer.
    """
    import streamlit as st
    if check_role() != "editor":
        st.warning("🔒 Fitur ini hanya tersedia untuk **Editor**. Silakan login terlebih dahulu.")
        return False
    return True
