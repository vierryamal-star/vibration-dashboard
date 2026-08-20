import pandas as pd
from datetime import datetime
import streamlit as st

# ── Threshold Vibrasi (ISO 10816) ──────────────────────────────────────────
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

ZC = ZONE_COLOR
ZB = ZONE_BG

# ── Design Tokens Terpusat ───────────────────────────────────────────────────
UI = {
    "radius_card":   "12px",
    "radius_pill":   "8px",
    "radius_badge":  "99px",
    "pad_card":      "14px",
    "font_xs":       "10px",
    "font_sm":       "11px",
    "font_base":     "12px",
    "font_md":       "13px",
    "font_lg":       "15px",
    "font_xl":       "24px",
    "shadow_card":   "0 2px 12px rgba(0,0,0,.08)",
    "shadow_danger": "0 2px 14px rgba(220,38,38,.25)",
    "accent_gradient": "linear-gradient(180deg, #2563eb, #0891b2)",
}

def render_page_header(title: str) -> None:
    """Render judul halaman bersih tanpa garis biru di bawahnya."""
    st.markdown(f"""
<div style="margin-bottom:8px">
  <div style="font-size:26px;font-weight:800;line-height:1.2">{title}</div>
</div>""", unsafe_allow_html=True)

def render_section_header(title: str) -> None:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        f'<div style="width:4px;height:20px;border-radius:2px;'
        f'background:{UI["accent_gradient"]};flex-shrink:0"></div>'
        f'<span style="font-size:15px;font-weight:700">{title}</span></div>',
        unsafe_allow_html=True)

GLOBAL_UI_CSS = """
<style>
div[data-testid="stExpander"] {
    border-radius: 12px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,.06);
}
</style>
"""

# ── Threshold Suhu (°C) ──────────────────────────────────────────────────────
THRESHOLD_TEMP = {
    "TURBIN":            {"normal": 80, "danger": 119},
    "WINDING":           {"normal": 99, "danger": 140},
    "BEARING DE MOTOR":  {"normal": 74, "danger": 95},
    "BEARING DE DRIVEN":  {"normal": 74, "danger": 95},
    "BEARING NDE DRIVEN": {"normal": 74, "danger": 95},
}

def get_temp_threshold(equipment: str, titik: str):
    eq, t = str(equipment).upper(), str(titik).upper()[cite: 4]
    if "TURBIN" in eq and "WINDING" not in t:[cite: 4]
        return THRESHOLD_TEMP["TURBIN"][cite: 4]
    if "WINDING" in t:[cite: 4]
        return THRESHOLD_TEMP["WINDING"][cite: 4]
    if "MOTOR" in t:[cite: 4]
        return THRESHOLD_TEMP["WINDING"] if "NDE" in t else THRESHOLD_TEMP["BEARING DE MOTOR"][cite: 4]
    if any(k in t for k in ["POMPA", "PUMP", "FAN"]):[cite: 4]
        return THRESHOLD_TEMP["BEARING NDE DRIVEN" if "NDE" in t else "BEARING DE DRIVEN"][cite: 4]
    return THRESHOLD_TEMP["BEARING DE DRIVEN"][cite: 4]

def get_zone_temp(value, thr):
    if pd.isna(value):[cite: 4]
        return "N/A", "⬜", "N/A"[cite: 4]
    if value <= thr["normal"]:[cite: 4]
        return "ZONE A", "🔵", "Normal"[cite: 4]
    elif value < thr["danger"]:[cite: 4]
        return "ZONE C", "🟡", "Warning"[cite: 4]
    else:
        return "ZONE D", "🔴", "Danger"[cite: 4]

def get_supabase(service_role=False):
    from supabase import create_client[cite: 4]
    url = st.secrets["SUPABASE_URL"][cite: 4]
    key = st.secrets["SUPABASE_SERVICE_KEY"] if service_role else st.secrets["SUPABASE_KEY"][cite: 4]
    return create_client(url, key)[cite: 4]

def get_threshold(equipment: str):
    name = equipment.upper()[cite: 4]
    key = "Turbine" if "TURBINE" in name else "Pump/Fan"[cite: 4]
    overrides = st.session_state.get("threshold_override")[cite: 4]
    if overrides and key in overrides:[cite: 4]
        return overrides[key][cite: 4]
    return THRESHOLD[key][cite: 4]

def get_zone(value, thr):
    if pd.isna(value):[cite: 4]
        return "N/A", "⬜", "N/A"[cite: 4]
    if value < thr["A"]:[cite: 4]
        return "ZONE A", "🔵", "Accepted"[cite: 4]
    elif value <= thr["B"]:[cite: 4]
        return "ZONE B", "🟢", "Pre Warning"[cite: 4]
    elif value <= thr["C"]:[cite: 4]
        return "ZONE C", "🟡", "Warning"[cite: 4]
    else:
        return "ZONE D", "🔴", "Danger"[cite: 4]

@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    try:
        sb = get_supabase()[cite: 4]
        all_rows = [][cite: 4]
        batch_size = 5000[cite: 4]
        start = 0[cite: 4]
        _cols = "equipment,unit,titik,direction,date,value"[cite: 4]

        while True:
            res = (
                sb.table("vibration")
                .select(_cols)
                .order("date", desc=True)
                .range(start, start + batch_size - 1)
                .execute()
            )[cite: 4]
            rows = res.data if res.data else [][cite: 4]
            if not rows:[cite: 4]
                break[cite: 4]
            all_rows.extend(rows)[cite: 4]
            if len(rows) < batch_size:[cite: 4]
                break[cite: 4]
            start += batch_size[cite: 4]

        return pd.DataFrame(all_rows)[cite: 4]
    except Exception as e:
        st.error(f"Gagal load data: {e}")[cite: 4]
        return pd.DataFrame()[cite: 4]

def save_to_db(df: pd.DataFrame) -> int:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        now = datetime.now().isoformat()[cite: 4]
        res = sb.table("vibration").select("equipment,unit,titik,direction,date").execute()[cite: 4]
        existing_keys = set()[cite: 4]
        if res.data:[cite: 4]
            for row in res.data:[cite: 4]
                key = f"{row['equipment']}|{row['unit']}|{row['titik']}|{row['direction']}|{str(row['date'])[:10]}"[cite: 4]
                existing_keys.add(key)[cite: 4]
        rows_to_insert = [][cite: 4]
        for _, r in df.iterrows():[cite: 4]
            date_str = str(r["date"])[:10] if pd.notna(r["date"]) else ""[cite: 4]
            key = f"{r['equipment']}|{r['unit']}|{r['titik']}|{r['direction']}|{date_str}"[cite: 4]
            if key not in existing_keys:[cite: 4]
                rows_to_insert.append({[cite: 4]
                    "equipment":   str(r["equipment"]),[cite: 4]
                    "unit":        str(r["unit"]),[cite: 4]
                    "titik":       str(r["titik"]),[cite: 4]
                    "direction":   str(r["direction"]),[cite: 4]
                    "date":        date_str,[cite: 4]
                    "value":       float(r["value"]) if pd.notna(r["value"]) else None,[cite: 4]
                    "uploaded_at": now,[cite: 4]
                })
        if rows_to_insert:[cite: 4]
            batch_size = 500[cite: 4]
            for i in range(0, len(rows_to_insert), batch_size):[cite: 4]
                sb.table("vibration").insert(rows_to_insert[i:i+batch_size]).execute()[cite: 4]
        return len(rows_to_insert)[cite: 4]
    except Exception as e:
        st.error(f"Gagal simpan data: {e}")[cite: 4]
        return 0[cite: 4]

def delete_by_dates(dates: list) -> int:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        total = 0[cite: 4]
        for d in dates:[cite: 4]
            res = sb.table("vibration").delete().eq("date", d).execute()[cite: 4]
            if res.data:[cite: 4]
                total += len(res.data)[cite: 4]
        return total[cite: 4]
    except Exception as e:
        st.error(f"Gagal hapus data: {e}")[cite: 4]
        return 0[cite: 4]

def delete_all() -> int:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        res = sb.table("vibration").delete().neq("equipment", "").execute()[cite: 4]
        return len(res.data) if res.data else 0[cite: 4]
    except Exception as e:
        st.error(f"Gagal hapus semua data: {e}")[cite: 4]
        return 0[cite: 4]

def parse_excel(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file, sheet_name="Vibration_Data")[cite: 4]
    except Exception as e:
        st.error(f"Gagal baca file {getattr(file, 'name', 'unknown')}: {e}")[cite: 4]
        return pd.DataFrame()[cite: 4]
    df.columns = [c.strip() for c in df.columns][cite: 4]
    col_map = {}[cite: 4]
    for c in df.columns:[cite: 4]
        cl = c.lower()[cite: 4]
        if "equipment" in cl:    col_map[c] = "equipment"[cite: 4]
        elif "unit" in cl:       col_map[c] = "unit"[cite: 4]
        elif "titik" in cl:      col_map[c] = "titik"[cite: 4]
        elif "direction" in cl:  col_map[c] = "direction"[cite: 4]
        elif "date" in cl:       col_map[c] = "date"[cite: 4]
        elif "value" in cl:      col_map[c] = "value"[cite: 4]
    df = df.rename(columns=col_map)[cite: 4]
    required = {"equipment", "unit", "titik", "direction", "date", "value"}[cite: 4]
    missing = required - set(df.columns)[cite: 4]
    if missing:[cite: 4]
        st.error(f"Kolom tidak ditemukan: {missing}")[cite: 4]
        return pd.DataFrame()[cite: 4]
    df["date"]  = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")[cite: 4]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")[cite: 4]
    df = df.dropna(subset=["value"])[cite: 4]
    return df[list(required)].dropna(subset=["equipment", "unit", "titik", "direction"])[cite: 4]

def add_zone_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()[cite: 4]
    df["thr_type"] = df["equipment"].apply(lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan")[cite: 4]

    def _zone_row(r):
        if r["direction"] == "T":[cite: 4]
            thr = get_temp_threshold(r["equipment"], r["titik"])[cite: 4]
            return get_zone_temp(r["value"], thr)[cite: 4]
        return get_zone(r["value"], THRESHOLD[r["thr_type"]])[cite: 4]

    z = df.apply(_zone_row, axis=1)[cite: 4]
    df["zone"], df["zone_icon"], df["zone_label"] = zip(*z)[cite: 4]
    return df[cite: 4]

EDITOR_PASSWORD = "pltu2026"[cite: 4]

def check_role():
    if "role" not in st.session_state:[cite: 4]
        st.session_state["role"] = "viewer"[cite: 4]
    return st.session_state["role"][cite: 4]

def render_login_sidebar():
    role = check_role()[cite: 4]
    st.sidebar.divider()[cite: 4]
    if role == "editor":[cite: 4]
        st.sidebar.success("🔓 Mode: **Editor**")[cite: 4]
        if st.sidebar.button("🔒 Logout", key="sb_logout"):[cite: 4]
            st.session_state["role"] = "viewer"[cite: 4]
            st.rerun()[cite: 4]
    else:
        st.sidebar.info("👁️ Mode: **Viewer**")[cite: 4]
        with st.sidebar.expander("🔑 Login Editor"):[cite: 4]
            pwd = st.text_input("Password", type="password", key="sb_pwd_input")[cite: 4]
            if st.button("Login", key="sb_login_btn"):[cite: 4]
                if pwd == EDITOR_PASSWORD:[cite: 4]
                    st.session_state["role"] = "editor"[cite: 4]
                    st.rerun()[cite: 4]
                else:
                    st.error("Password salah.")[cite: 4]

def require_editor():
    if check_role() != "editor":[cite: 4]
        st.warning("🔒 Fitur ini hanya tersedia untuk Editor.")[cite: 4]
        return False[cite: 4]
    return True[cite: 4]

# ── Running Hours Pompa ──────────────────────────────────────────────────────
@st.cache_data(ttl=15)
def get_pump_runtime() -> pd.DataFrame:
    cols = ["equipment", "unit", "status", "status_changed_at", "accumulated_hours"][cite: 4]
    try:
        sb = get_supabase()[cite: 4]
        res = sb.table("pump_runtime").select([cite: 4]
            "equipment,unit,status,status_changed_at,accumulated_hours,install_date"[cite: 4]
        ).execute()[cite: 4]
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)[cite: 4]
    except Exception as e:
        st.error(f"Gagal load running hours: {e}")[cite: 4]
        return pd.DataFrame(columns=cols)[cite: 4]

def init_pump_runtime(equipment: str, unit: str):
    sb = get_supabase(service_role=True)[cite: 4]
    res = sb.table("pump_runtime").select("id").eq("equipment", equipment).eq("unit", unit).execute()[cite: 4]
    if not res.data:[cite: 4]
        sb.table("pump_runtime").insert({[cite: 4]
            "equipment": equipment,[cite: 4]
            "unit": unit,[cite: 4]
            "status": "stopped",[cite: 4]
            "status_changed_at": datetime.now().isoformat(),[cite: 4]
            "accumulated_hours": 0.0,[cite: 4]
        }).execute()[cite: 4]

def start_pump_runtime(equipment: str, unit: str, start_dt) -> None:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        sb.table("pump_runtime").update({[cite: 4]
            "status": "running",[cite: 4]
            "status_changed_at": pd.Timestamp(start_dt).isoformat(),[cite: 4]
        }).eq("equipment", equipment).eq("unit", unit).execute()[cite: 4]
    except Exception as e:
        st.error(f"Gagal catat waktu mulai: {e}")[cite: 4]

def stop_pump_runtime(equipment: str, unit: str, stop_dt, current_status: str,
                       current_accum: float, current_changed_at) -> None:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        stop_ts = pd.Timestamp(stop_dt)[cite: 4]
        if current_status == "running":[cite: 4]
            try:
                changed = pd.to_datetime(current_changed_at)[cite: 4]
                if changed.tzinfo is not None:[cite: 4]
                    changed = changed.tz_localize(None)[cite: 4]
                delta_hours = max((stop_ts - changed).total_seconds() / 3600, 0)[cite: 4]
            except Exception:
                delta_hours = 0[cite: 4]
            new_accum = float(current_accum or 0) + delta_hours[cite: 4]
        else:
            new_accum = float(current_accum or 0)[cite: 4]
        sb.table("pump_runtime").update({[cite: 4]
            "status": "stopped",[cite: 4]
            "status_changed_at": stop_ts.isoformat(),[cite: 4]
            "accumulated_hours": new_accum,[cite: 4]
        }).eq("equipment", equipment).eq("unit", unit).execute()[cite: 4]
    except Exception as e:
        st.error(f"Gagal catat waktu berhenti: {e}")[cite: 4]

def reset_pump_runtime(equipment: str, unit: str) -> None:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        sb.table("pump_runtime").update({[cite: 4]
            "status": "stopped",[cite: 4]
            "status_changed_at": datetime.now().isoformat(),[cite: 4]
            "accumulated_hours": 0.0,[cite: 4]
        }).eq("equipment", equipment).eq("unit", unit).execute()[cite: 4]
    except Exception as e:
        st.error(f"Gagal reset running hours: {e}")[cite: 4]

def reset_pump_install_date(equipment: str, unit: str) -> None:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        sb.table("pump_runtime").update([cite: 4]
            {"install_date": datetime.now().date().isoformat()}[cite: 4]
        ).eq("equipment", equipment).eq("unit", unit).execute()[cite: 4]
    except Exception as e:
        st.error(f"Gagal reset umur pompa: {e}")[cite: 4]

def compute_running_hours(row: dict) -> float:
    accum = float(row.get("accumulated_hours", 0) or 0)[cite: 4]
    if row.get("status") == "running":[cite: 4]
        try:
            changed = pd.to_datetime(row["status_changed_at"])[cite: 4]
            if changed.tzinfo is not None:[cite: 4]
                changed = changed.tz_localize(None)[cite: 4]
            delta = (pd.Timestamp.now() - changed).total_seconds() / 3600[cite: 4]
            return accum + max(delta, 0)[cite: 4]
        except Exception:
            return accum[cite: 4]
    return accum[cite: 4]

def get_pump_age(install_date) -> str:
    if not install_date or pd.isna(install_date):[cite: 4]
        return None[cite: 4]
    try:
        d = pd.to_datetime(install_date)[cite: 4]
        now = pd.Timestamp.now()[cite: 4]
        months = (now.year - d.year) * 12 + (now.month - d.month)[cite: 4]
        if now.day < d.day:[cite: 4]
            months -= 1[cite: 4]
        months = max(months, 0)[cite: 4]
        years, rem_months = divmod(months, 12)[cite: 4]
        parts = [][cite: 4]
        if years:[cite: 4]
            parts.append(f"{years} th")[cite: 4]
        parts.append(f"{rem_months} bln")[cite: 4]
        return " ".join(parts)[cite: 4]
    except Exception:
        return None[cite: 4]

def update_pump_install_date(equipment: str, unit: str, install_date) -> None:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        sb.table("pump_runtime").update([cite: 4]
            {"install_date": str(install_date)}[cite: 4]
        ).eq("equipment", equipment).eq("unit", unit).execute()[cite: 4]
    except Exception as e:
        st.error(f"Gagal simpan tanggal instalasi: {e}")[cite: 4]

BEARING_POSISI = ["DE Motor", "NDE Motor", "DE Pompa/Fan", "NDE Pompa/Fan"][cite: 4]

@st.cache_data(ttl=15)
def get_bearing_install() -> pd.DataFrame:
    cols = ["equipment", "unit", "posisi", "install_date"][cite: 4]
    try:
        sb = get_supabase()[cite: 4]
        res = sb.table("bearing_install").select("equipment,unit,posisi,install_date").execute()[cite: 4]
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)[cite: 4]
    except Exception as e:
        st.error(f"Gagal load umur bearing: {e}")[cite: 4]
        return pd.DataFrame(columns=cols)[cite: 4]

def update_bearing_install(equipment: str, unit: str, posisi: str, install_date) -> None:
    try:
        sb = get_supabase(service_role=True)[cite: 4]
        existing = (
            sb.table("bearing_install").select("id")[cite: 4]
            .eq("equipment", equipment).eq("unit", unit).eq("posisi", posisi)[cite: 4]
            .execute()[cite: 4]
        )
        if existing.data:[cite: 4]
            sb.table("bearing_install").update([cite: 4]
                {"install_date": str(install_date)}[cite: 4]
            ).eq("equipment", equipment).eq("unit", unit).eq("posisi", posisi).execute()[cite: 4]
        else:
            sb.table("bearing_install").insert({[cite: 4]
                "equipment": equipment, "unit": unit, "posisi": posisi,[cite: 4]
                "install_date": str(install_date),[cite: 4]
            }).execute()[cite: 4]
    except Exception as e:
        st.error(f"Gagal simpan tanggal instalasi bearing: {e}")[cite: 4]
