import hmac
import time
import json
from datetime import datetime, date, timezone, timedelta
import numpy as np
import pandas as pd
import streamlit as st

WIB = timezone(timedelta(hours=7))

def now_wib() -> datetime:
    return datetime.now(WIB).replace(tzinfo=None)

def today_wib() -> date:
    return datetime.now(WIB).date()

def _to_wib_naive(value) -> pd.Timestamp:
    ts = pd.to_datetime(value)
    if pd.isna(ts):
        raise ValueError("Nilai waktu tidak valid")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Jakarta").tz_localize(None)
    return ts

# Ambang Batas Default (ISO 10816)
DEFAULT_THRESHOLD = {
    "Turbine": {"A": 1.4, "B": 2.8, "C": 4.5},
    "Pump/Fan": {"A": 1.4, "B": 2.8, "C": 4.5},
}
THRESHOLD = DEFAULT_THRESHOLD

ZONE_COLOR = {
    "ZONE A": "#2563eb", "ZONE B": "#16a34a",
    "ZONE C": "#d97706", "ZONE D": "#dc2626", "N/A": "#6b7280",
}
ZONE_BG = {
    "ZONE A": "rgba(37,99,235,.12)", "ZONE B": "rgba(22,163,74,.12)",
    "ZONE C": "rgba(217,119,6,.14)", "ZONE D": "rgba(220,38,38,.14)",
    "N/A": "rgba(107,114,128,.1)",
}
ZONE_LABEL = {
    "ZONE A": "Accepted", "ZONE B": "Pre Warning",
    "ZONE C": "Warning", "ZONE D": "Danger", "N/A": "N/A",
}
ZONE_ICON = {
    "ZONE A": "🔵", "ZONE B": "🟢", "ZONE C": "🟡", "ZONE D": "🔴", "N/A": "⬜",
}
ZC = ZONE_COLOR
ZB = ZONE_BG

UI = {
    "radius_card": "12px", "radius_pill": "8px", "radius_badge": "99px",
    "pad_card": "14px", "font_xs": "10px", "font_sm": "11px",
    "font_base": "12px", "font_md": "13px", "font_lg": "15px", "font_xl": "24px",
    "accent_gradient": "linear-gradient(180deg, #2563eb, #0891b2)",
}

def render_page_header(title: str) -> None:
    st.markdown(f"""
<div style="margin-bottom:8px">
  <div style="font-size:24px;font-weight:800;line-height:1.2;color:var(--text-color);">{title}</div>
</div>""", unsafe_allow_html=True)

def render_section_header(title: str) -> None:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        f'<div style="width:4px;height:20px;border-radius:2px;'
        f'background:{UI["accent_gradient"]};flex-shrink:0"></div>'
        f'<span style="font-size:15px;font-weight:700;color:var(--text-color);">{title}</span></div>',
        unsafe_allow_html=True)

GLOBAL_UI_CSS = """
<style>
* { font-variant-numeric: tabular-nums; }
div[data-testid="stExpander"] {
    border-radius: 12px !important;
    border: 1px solid color-mix(in srgb, var(--text-color) 12%, transparent) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.03) !important;
}
.card-danger-glow-static {
    border-color: rgba(220, 38, 38, 0.45) !important;
    box-shadow: 0 0 12px rgba(220, 38, 38, 0.18) !important;
    background: color-mix(in srgb, rgba(220, 38, 38, 0.05) 50%, var(--secondary-background-color)) !important;
}
@media (max-width: 992px) {
    .pill-grid { grid-template-columns: repeat(2, 1fr) !important; }
}
</style>
"""

# PERBAIKAN: Ambang Batas Suhu (°C) yang benar
THRESHOLD_TEMP = {
    "TURBIN":             {"normal": 80, "danger": 119},
    "WINDING":            {"normal": 99, "danger": 140},
    "BEARING DE MOTOR":   {"normal": 74, "danger": 95},
    "BEARING NDE MOTOR":  {"normal": 74, "danger": 95},
    "BEARING DE DRIVEN":  {"normal": 74, "danger": 95},
    "BEARING NDE DRIVEN": {"normal": 74, "danger": 95},
}

def get_temp_threshold(equipment: str, titik: str):
    eq, t = str(equipment).upper(), str(titik).upper()
    if "TURBIN" in eq and "WINDING" not in t:
        return THRESHOLD_TEMP["TURBIN"]
    if "WINDING" in t or "GULUNGAN" in t:
        return THRESHOLD_TEMP["WINDING"]
    if "MOTOR" in t:
        return THRESHOLD_TEMP["BEARING NDE MOTOR" if "NDE" in t else "BEARING DE MOTOR"]
    if any(k in t for k in ["POMPA", "PUMP", "FAN"]):
        return THRESHOLD_TEMP["BEARING NDE DRIVEN" if "NDE" in t else "BEARING DE DRIVEN"]
    return THRESHOLD_TEMP["BEARING DE DRIVEN"]

def get_zone_temp(value, thr):
    if pd.isna(value):
        return "N/A", "⬜", "N/A"
    if value <= thr["normal"]:
        return "ZONE A", "🔵", "Normal"
    elif value < thr["danger"]:
        return "ZONE C", "🟡", "Warning"
    else:
        return "ZONE D", "🔴", "Danger"

@st.cache_resource(show_spinner=False)
def _supabase_client(url: str, key: str):
    from supabase import create_client
    return create_client(url, key)

def get_supabase(service_role=False):
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"] if service_role else st.secrets["SUPABASE_KEY"]
    return _supabase_client(url, key)

def _paged_select(sb, table: str, cols: str, order_cols=("date", "id"),
                  desc: bool = False, query_mod=None, batch: int = 1000) -> list:
    def _run(order_list):
        rows, start = [], 0
        while True:
            q = sb.table(table).select(cols)
            if query_mod is not None:
                q = query_mod(q)
            for c in order_list:
                q = q.order(c, desc=desc)
            data = q.range(start, start + batch - 1).execute().data or []
            rows.extend(data)
            if len(data) < batch:
                return rows
            start += batch
    try:
        return _run(order_cols)
    except Exception:
        if len(order_cols) > 1:
            return _run(order_cols[:1])
        raise

# PERBAIKAN: Persistensi Ambang Batas ke Supabase
@st.cache_data(ttl=120)
def load_db_thresholds():
    try:
        sb = get_supabase()
        res = sb.table("app_settings").select("value").eq("key", "threshold_iso").limit(1).execute()
        if res.data:
            return res.data[0]["value"]
    except Exception:
        pass
    return DEFAULT_THRESHOLD

def save_db_thresholds(thr_dict: dict) -> tuple[bool, str]:
    if not _assert_editor():
        return False, "Hanya Editor yang berhak memperbarui threshold."
    try:
        sb = get_supabase(service_role=True)
        sb.table("app_settings").upsert({
            "key": "threshold_iso",
            "value": thr_dict,
            "updated_at": datetime.now(WIB).isoformat()
        }).execute()
        load_db_thresholds.clear()
        return True, "Ambang batas berhasil disimpan permanen ke database."
    except Exception as e:
        return False, f"Gagal menyimpan ke database: {e}"

def get_threshold(equipment: str):
    name = str(equipment).upper()
    key = "Turbine" if "TURBINE" in name else "Pump/Fan"
    cfg = load_db_thresholds()
    return cfg.get(key, DEFAULT_THRESHOLD[key])

def get_zone(value, thr):
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

def add_zone_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["thr_type"] = df["equipment"].map(
        lambda x: "Turbine" if "turbine" in str(x).lower() else "Pump/Fan"
    )
    if df.empty:
        for c in ("zone", "zone_icon", "zone_label"):
            df[c] = pd.Series(dtype=object)
        return df

    vals = pd.to_numeric(df["value"], errors="coerce").to_numpy(dtype=float)
    temp_mask = df["direction"].eq("T").to_numpy()
    zone = np.full(len(df), "N/A", dtype=object)

    if (~temp_mask).any():
        eqs = df["equipment"].astype(str)
        thr_by_eq = {e: get_threshold(e) for e in eqs.unique()}
        a = eqs.map({e: t["A"] for e, t in thr_by_eq.items()}).to_numpy(dtype=float)
        b = eqs.map({e: t["B"] for e, t in thr_by_eq.items()}).to_numpy(dtype=float)
        c = eqs.map({e: t["C"] for e, t in thr_by_eq.items()}).to_numpy(dtype=float)
        vz = np.select(
            [np.isnan(vals) | np.isnan(a), vals < a, vals <= b, vals <= c],
            ["N/A", "ZONE A", "ZONE B", "ZONE C"],
            default="ZONE D",
        )
        zone[~temp_mask] = vz[~temp_mask]

    if temp_mask.any():
        sub = df.loc[temp_mask, ["equipment", "titik"]]
        cache, normal, danger = {}, [], []
        for key in zip(sub["equipment"], sub["titik"]):
            if key not in cache:
                cache[key] = get_temp_threshold(*key)
            normal.append(cache[key]["normal"])
            danger.append(cache[key]["danger"])
        tv = vals[temp_mask]
        normal = np.asarray(normal, dtype=float)
        danger = np.asarray(danger, dtype=float)
        tz = np.select(
            [np.isnan(tv), tv <= normal, tv < danger],
            ["N/A", "ZONE A", "ZONE C"],
            default="ZONE D",
        )
        zone[temp_mask] = tz

    df["zone"] = zone
    df["zone_icon"] = df["zone"].map(ZONE_ICON)
    label = df["zone"].map(ZONE_LABEL)
    is_temp_normal = pd.Series(temp_mask, index=df.index) & df["zone"].eq("ZONE A")
    df["zone_label"] = label.where(~is_temp_normal, "Normal")
    return df

@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    try:
        sb = get_supabase()
        rows = _paged_select(
            sb, "vibration", "equipment,unit,titik,direction,date,value",
            order_cols=("date", "id"), desc=True,
        )
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["date", "value"])
        return df
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame()

_KEY_COLS = ["equipment", "unit", "titik", "direction"]

def save_to_db_detailed(df: pd.DataFrame) -> tuple[int, str | None]:
    if not _assert_editor():
        return 0, "Hanya Editor yang dapat menyimpan data."
    if df is None or df.empty:
        return 0, None

    inserted = 0
    try:
        sb = get_supabase(service_role=True)
        now = datetime.now(WIB).isoformat()

        work = df.copy()
        for c in _KEY_COLS:
            work[c] = work[c].astype(str).str.strip()
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        work["value"] = pd.to_numeric(work["value"], errors="coerce")
        work = work.dropna(subset=["date", "value"])
        if work.empty:
            return 0, None
        work["_key"] = work[_KEY_COLS + ["date"]].agg("|".join, axis=1)
        work = work.drop_duplicates("_key")

        d_min, d_max = work["date"].min(), work["date"].max()
        existing_rows = _paged_select(
            sb, "vibration", "equipment,unit,titik,direction,date",
            order_cols=("date", "id"),
            query_mod=lambda q: q.gte("date", d_min).lte("date", d_max),
        )
        existing_keys = {
            "|".join([str(r["equipment"]).strip(), str(r["unit"]).strip(),
                      str(r["titik"]).strip(), str(r["direction"]).strip(),
                      str(r["date"])[:10]])
            for r in existing_rows
        }

        new_rows = work[~work["_key"].isin(existing_keys)]
        if new_rows.empty:
            return 0, None

        records = new_rows[_KEY_COLS + ["date", "value"]].to_dict("records")
        for rec in records:
            rec["value"] = float(rec["value"])
            rec["uploaded_at"] = now

        step = 500
        for i in range(0, len(records), step):
            batch = records[i:i + step]
            sb.table("vibration").insert(batch).execute()
            inserted += len(batch)
        return inserted, None
    except Exception as e:
        return inserted, str(e)

# PERBAIKAN: Fungsi delete yang mengembalikan jumlah baris aktual dan error
def delete_by_dates_detailed(dates: list) -> tuple[int, str | None]:
    if not _assert_editor():
        return 0, "Aksi ditolak: hanya Editor yang dapat menghapus data."
    if not dates:
        return 0, None
    try:
        sb = get_supabase(service_role=True)
        total = 0
        for d in dates:
            res = sb.table("vibration").delete().eq("date", str(d)).execute()
            if res.data:
                total += len(res.data)
        return total, None
    except Exception as e:
        return 0, str(e)

def delete_all_detailed() -> tuple[int, str | None]:
    if not _assert_editor():
        return 0, "Aksi ditolak: hanya Editor yang dapat menghapus data."
    try:
        sb = get_supabase(service_role=True)
        res = sb.table("vibration").delete().neq("equipment", "__UNDEFINED__").execute()
        count = len(res.data) if res.data else 0
        return count, None
    except Exception as e:
        return 0, str(e)

# PERBAIKAN: Fallback parsing Excel jika sheet 'Vibration_Data' tidak ditemukan
def parse_excel(file) -> pd.DataFrame:
    df = None
    try:
        df = pd.read_excel(file, sheet_name="Vibration_Data")
    except Exception:
        try:
            df = pd.read_excel(file, sheet_name=0)
        except Exception as e:
            st.error(f"Gagal membaca file {getattr(file, 'name', 'Excel')}: {e}")
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
        st.error(f"Kolom wajib tidak ditemukan: {missing}")
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return df[list(required)].dropna(subset=["equipment", "unit", "titik", "direction"])

_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_LOCK_SECONDS = 60

def check_role():
    if "role" not in st.session_state:
        st.session_state["role"] = "viewer"
    return st.session_state["role"]

def _verify_editor_password(pwd: str) -> bool:
    try:
        expected = str(st.secrets["EDITOR_PASSWORD"])
    except Exception:
        return False
    if not expected:
        return False
    return hmac.compare_digest(pwd.encode("utf-8"), expected.encode("utf-8"))

def _try_login(pwd: str):
    now = time.time()
    lock_until = st.session_state.get("_login_lock_until", 0)
    if lock_until > now:
        return f"Terlalu banyak percobaan. Coba lagi dalam {int(lock_until - now) + 1} detik."
    try:
        st.secrets["EDITOR_PASSWORD"]
    except Exception:
        return "EDITOR_PASSWORD belum diatur di secrets. Hubungi admin dashboard."

    if _verify_editor_password(pwd):
        st.session_state["role"] = "editor"
        st.session_state["_login_fails"] = 0
        return None

    fails = st.session_state.get("_login_fails", 0) + 1
    if fails >= _MAX_LOGIN_ATTEMPTS:
        st.session_state["_login_lock_until"] = now + _LOGIN_LOCK_SECONDS
        fails = 0
    st.session_state["_login_fails"] = fails
    return "Password salah."

def require_editor():
    if check_role() != "editor":
        st.warning("🔒 Fitur ini hanya tersedia untuk Editor.")
        return False
    return True

def _assert_editor() -> bool:
    if check_role() != "editor":
        st.error("🔒 Aksi ini hanya dapat dilakukan oleh Editor.")
        return False
    return True

@st.cache_data(ttl=60, show_spinner=False)
def _alarm_summary():
    df_h = load_history()
    if df_h.empty:
        return 0, 0
    df_lat = (
        df_h[df_h["direction"] != "T"]
        .sort_values("date")
        .groupby(["unit", "equipment", "titik", "direction"], as_index=False)
        .last()
    )
    df_lat = add_zone_cols(df_lat)
    return int((df_lat["zone"] == "ZONE D").sum()), int((df_lat["zone"] == "ZONE C").sum())

def render_app_sidebar():
    with st.sidebar:
        try:
            st.image("assets/logo_pln_ip.png", width=190)
        except Exception:
            pass
        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 14px;">
            <div style="font-size: 24px; font-weight: 900; line-height: 1.1; color: var(--text-color); letter-spacing: -0.02em;">
                ⚡ PLTU TBK
            </div>
            <div style="font-size: 13px; opacity: .8; font-weight: 600; margin-top: 3px; color: color-mix(in srgb, var(--text-color) 80%, transparent);">
                Vibration & Asset Monitoring
            </div>
            <div style="margin-top: 8px;">
                <span style="font-size: 11px; font-weight: 700; background: rgba(22, 163, 74, 0.14); color: #16a34a; border: 1px solid rgba(22, 163, 74, 0.35); padding: 3px 10px; border-radius: 99px;">
                    ● Database Connected
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()
        st.caption("**NAVIGASI UTAMA**")
        st.page_link("app.py",                  label="📊 Monitor Vibrasi")
        st.page_link("pages/1_Analisis.py",     label="📈 Analisis Tren")
        st.page_link("pages/2_Data_Kelola.py",  label="🗄️ Data & Kelola")
        st.page_link("pages/3_Kelola_Pompa.py", label="🛠️ Kelola Jam Operasi")
        st.page_link("pages/4_Rotor_Balance.py", label="⚙️ Rotor Balance")
        st.divider()

        if st.button("🔄 Segarkan Data", key="sb_sync_btn", width="stretch"):
            st.cache_data.clear()
            st.rerun()

        n_d, n_c = _alarm_summary()
        df_rt = get_pump_runtime()
        n_run = int((df_rt["status"] == "running").sum()) if not df_rt.empty else 0

        st.markdown(f"""
        <div style="background: color-mix(in srgb, var(--secondary-background-color) 80%, transparent); border-radius: 10px; padding: 10px 12px; border: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent); margin: 12px 0;">
            <div style="font-size: 10px; font-weight: 700; opacity: .6; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px;">Ringkasan Alarm Global</div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: 700;">
                <span style="color: #dc2626;">🔴 {n_d} Danger</span>
                <span style="color: #d97706;">🟡 {n_c} Warning</span>
                <span style="color: #16a34a;">🟢 {n_run} Running</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        role = check_role()
        st.divider()
        if role == "editor":
            st.success("🔓 Mode: **Editor**")
            if st.button("🔒 Logout", key="sb_logout_main", width="stretch"):
                st.session_state["role"] = "viewer"
                st.rerun()
        else:
            st.info("👁️ Mode: **Viewer**")
            with st.expander("🔑 Login Editor"):
                pwd = st.text_input("Password", type="password", key="sb_pwd_input_main")
                if st.button("Login", key="sb_login_btn_main", width="stretch"):
                    err = _try_login(pwd)
                    if err:
                        st.error(err)
                    else:
                        st.rerun()

        st.markdown("""
        <div style="font-size: 10px; text-align: center; opacity: .45; margin-top: 20px;">
            ISO 10816 Standard Compliance<br>
            © 2026 PLTU TBK · v2.5
        </div>
        """, unsafe_allow_html=True)

# ── Running Hours & Bearing ──────────────────────────────────────────────────
PUMP_LOG_TABLE = "pump_runtime_log"
to_wib_naive = _to_wib_naive

def _num(x, default: float = 0.0) -> float:
    try:
        v = float(x)
        return default if np.isnan(v) else v
    except (TypeError, ValueError):
        return default

def _floor_min(value) -> pd.Timestamp:
    return _to_wib_naive(value).floor("min")

def fmt_wib(ts) -> str:
    return pd.Timestamp(ts).strftime("%d %b %Y %H:%M")

def _is_editor() -> bool:
    return check_role() == "editor"

@st.cache_data(ttl=15)
def get_pump_runtime() -> pd.DataFrame:
    cols = ["equipment", "unit", "status", "status_changed_at", "accumulated_hours", "install_date"]
    try:
        sb = get_supabase()
        res = sb.table("pump_runtime").select(
            "equipment,unit,status,status_changed_at,accumulated_hours,install_date"
        ).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Gagal memuat running hours: {e}")
        return pd.DataFrame(columns=cols)

@st.cache_data(ttl=15, show_spinner=False)
def get_pump_log(limit: int = 1000):
    cols = ["created_at", "equipment", "unit", "action", "event_time",
            "hours_before", "hours_after", "note", "actor"]
    try:
        sb = get_supabase(service_role=True)
        res = (
            sb.table(PUMP_LOG_TABLE).select(",".join(cols))
            .order("created_at", desc=True).limit(limit).execute()
        )
        return (pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)), None
    except Exception as e:
        return pd.DataFrame(columns=cols), str(e)

def clear_runtime_caches() -> None:
    get_pump_runtime.clear()
    get_bearing_install.clear()
    get_pump_log.clear()

def _fetch_pump_row(sb, equipment: str, unit: str):
    res = (
        sb.table("pump_runtime")
        .select("status,status_changed_at,accumulated_hours")
        .eq("equipment", equipment).eq("unit", unit)
        .limit(1).execute()
    )
    return res.data[0] if res.data else None

def _log_pump_event(sb, equipment, unit, action, event_time, hours_before, hours_after,
                    note: str = "", actor: str = "") -> str:
    try:
        sb.table(PUMP_LOG_TABLE).insert({
            "equipment": equipment, "unit": unit, "action": action,
            "event_time": pd.Timestamp(event_time).strftime("%Y-%m-%d %H:%M:%S"),
            "hours_before": round(float(hours_before), 4),
            "hours_after": round(float(hours_after), 4),
            "note": note or None, "actor": actor or None,
        }).execute()
        return ""
    except Exception:
        return " ⚠️ Catatan riwayat gagal ditulis."

def init_pump_runtime(equipment: str, unit: str):
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        res = sb.table("pump_runtime").select("id").eq("equipment", equipment).eq("unit", unit).execute()
        if not res.data:
            sb.table("pump_runtime").insert({
                "equipment": equipment, "unit": unit, "status": "stopped",
                "status_changed_at": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
                "accumulated_hours": 0.0,
            }).execute()
    except Exception as e:
        st.error(f"Gagal inisialisasi jam operasi: {e}")

def validate_start(row, start_ts):
    try:
        ts = _floor_min(start_ts)
    except Exception:
        return "Waktu start tidak valid."
    if ts > _floor_min(now_wib()):
        return f"Waktu start tidak boleh di masa depan (sekarang {fmt_wib(now_wib())} WIB)."
    if row:
        if row.get("status") == "running":
            return "Equipment sudah berstatus Running."
        if _num(row.get("accumulated_hours")) > 0:
            try:
                last = _floor_min(row.get("status_changed_at"))
            except Exception:
                last = None
            if last is not None and ts < last:
                return f"Waktu start tidak boleh sebelum waktu stop terakhir ({fmt_wib(last)} WIB)."
    return None

def validate_stop(row, stop_ts):
    if not row:
        return "Data running hours equipment tidak ditemukan."
    if row.get("status") != "running":
        return "Equipment tidak sedang Running."
    try:
        ts = _floor_min(stop_ts)
    except Exception:
        return "Waktu stop tidak valid."
    try:
        started = _floor_min(row.get("status_changed_at"))
    except Exception:
        return "Waktu start tercatat tidak valid."
    if ts < started:
        return f"Waktu stop tidak boleh sebelum start ({fmt_wib(started)} WIB)."
    if ts > _floor_min(now_wib()):
        return f"Waktu stop tidak boleh di masa depan."
    return None

def session_hours(row, stop_ts) -> float:
    started = _floor_min(row.get("status_changed_at"))
    return max((_floor_min(stop_ts) - started).total_seconds() / 3600.0, 0.0)

def compute_running_hours(row: dict) -> float:
    accum = _num(row.get("accumulated_hours"))
    if row.get("status") != "running":
        return accum
    try:
        changed = _to_wib_naive(row["status_changed_at"])
        delta_seconds = (now_wib() - changed).total_seconds()
        return accum + max(delta_seconds / 3600.0, 0.0)
    except Exception:
        return accum

def start_pump_runtime(equipment: str, unit: str, start_dt, actor: str = ""):
    if not _is_editor():
        return False, "Aksi ini hanya dapat dilakukan oleh Editor."
    try:
        sb = get_supabase(service_role=True)
        fresh = _fetch_pump_row(sb, equipment, unit)
        if not fresh:
            return False, "Data equipment belum ada."
        err = validate_start(fresh, start_dt)
        if err:
            return False, err
        ts = _floor_min(start_dt)
        q = sb.table("pump_runtime").update({
            "status": "running", "status_changed_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
        }).eq("equipment", equipment).eq("unit", unit)
        if fresh.get("status") is not None:
            q = q.eq("status", fresh["status"])
        if not q.execute().data:
            return False, "Status berubah saat diproses pengguna lain."
        accum = _num(fresh.get("accumulated_hours"))
        warn = _log_pump_event(sb, equipment, unit, "start", ts, accum, accum, actor=actor)
        return True, f"Running dicatat sejak {fmt_wib(ts)} WIB." + warn
    except Exception as e:
        return False, f"Gagal mencatat start: {e}"

def stop_pump_runtime(equipment: str, unit: str, stop_dt, actor: str = ""):
    if not _is_editor():
        return False, "Aksi ini hanya dapat dilakukan oleh Editor."
    try:
        sb = get_supabase(service_role=True)
        fresh = _fetch_pump_row(sb, equipment, unit)
        err = validate_stop(fresh, stop_dt)
        if err:
            return False, err
        ts = _floor_min(stop_dt)
        added = session_hours(fresh, ts)
        accum = _num(fresh.get("accumulated_hours"))
        new_accum = accum + added
        started = _floor_min(fresh.get("status_changed_at"))

        res = sb.table("pump_runtime").update({
            "status": "stopped",
            "status_changed_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "accumulated_hours": round(new_accum, 4),
        }).eq("equipment", equipment).eq("unit", unit).eq("status", "running").execute()
        if not res.data:
            return False, "Status berubah saat diproses."

        warn = _log_pump_event(
            sb, equipment, unit, "stop", ts, accum, new_accum,
            note=f"Sesi {fmt_wib(started)} → {fmt_wib(ts)} = {added:.2f} jam", actor=actor,
        )
        return True, f"Stop dicatat pada {fmt_wib(ts)} WIB (+{added:,.2f} jam)." + warn
    except Exception as e:
        return False, f"Gagal mencatat stop: {e}"

def edit_pump_hours(equipment: str, unit: str, *, new_total=None, delta=None, note: str = "", actor: str = ""):
    if not _is_editor():
        return False, "Hanya Editor yang berhak mengubah jam operasi."
    if (new_total is None) == (delta is None):
        return False, "Isi total baru atau selisih jam."
    note, actor = (note or "").strip(), (actor or "").strip()
    if not actor or not note:
        return False, "Nama petugas dan alasan wajib diisi."
    try:
        sb = get_supabase(service_role=True)
        fresh = _fetch_pump_row(sb, equipment, unit)
        if not fresh:
            return False, "Data equipment tidak ditemukan."
        accum = _num(fresh.get("accumulated_hours"))
        current_total = compute_running_hours(fresh)
        live_part = current_total - accum
        target = _num(new_total) if new_total is not None else current_total + _num(delta)
        if target < 0:
            return False, "Total tidak boleh negatif."
        new_accum = max(target - live_part, 0.0)

        q = sb.table("pump_runtime").update({"accumulated_hours": round(new_accum, 4)}).eq("equipment", equipment).eq("unit", unit)
        if fresh.get("status") is not None:
            q = q.eq("status", fresh["status"])
        if not q.execute().data:
            return False, "Status berubah saat diproses."

        warn = _log_pump_event(sb, equipment, unit, "edit_hours", now_wib(), current_total, target, note=note, actor=actor)
        return True, f"Running hours diubah: {current_total:,.1f} → {target:,.1f} jam." + warn
    except Exception as e:
        return False, f"Gagal mengubah jam: {e}"

def reset_pump_runtime(equipment: str, unit: str, note: str = "", actor: str = ""):
    if not _is_editor():
        return False, "Hanya Editor yang berhak me-reset jam."
    note, actor = (note or "").strip(), (actor or "").strip()
    if not actor or not note:
        return False, "Nama petugas dan alasan wajib diisi."
    try:
        sb = get_supabase(service_role=True)
        fresh = _fetch_pump_row(sb, equipment, unit)
        before = compute_running_hours(fresh) if fresh else 0.0
        ts = now_wib()
        res = sb.table("pump_runtime").update({
            "status": "stopped", "status_changed_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "accumulated_hours": 0.0,
        }).eq("equipment", equipment).eq("unit", unit).execute()
        if not res.data:
            return False, "Data running hours tidak ditemukan."
        warn = _log_pump_event(sb, equipment, unit, "reset_hours", ts, before, 0.0, note=note, actor=actor)
        return True, f"Running hours direset ke 0 (sebelumnya {before:,.1f} jam)." + warn
    except Exception as e:
        return False, f"Gagal reset: {e}"

def get_pump_age(install_date) -> str:
    if not install_date or pd.isna(install_date):
        return None
    try:
        d = pd.to_datetime(install_date)
        now = today_wib()
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

BEARING_POSISI = ["DE Motor", "NDE Motor", "DE Pompa/Fan", "NDE Pompa/Fan"]

@st.cache_data(ttl=15)
def get_bearing_install() -> pd.DataFrame:
    cols = ["equipment", "unit", "posisi", "install_date"]
    try:
        sb = get_supabase()
        res = sb.table("bearing_install").select("equipment,unit,posisi,install_date").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Gagal memuat umur bearing: {e}")
        return pd.DataFrame(columns=cols)

def update_bearing_install(equipment: str, unit: str, posisi: str, install_date) -> None:
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        existing = sb.table("bearing_install").select("id").eq("equipment", equipment).eq("unit", unit).eq("posisi", posisi).execute()
        if existing.data:
            sb.table("bearing_install").update({"install_date": str(install_date)}).eq("equipment", equipment).eq("unit", unit).eq("posisi", posisi).execute()
        else:
            sb.table("bearing_install").insert({
                "equipment": equipment, "unit": unit, "posisi": posisi, "install_date": str(install_date),
            }).execute()
    except Exception as e:
        st.error(f"Gagal menyimpan instalasi bearing: {e}")
