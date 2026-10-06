import hmac
import time
from datetime import datetime, date, timezone, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# ── Waktu WIB (satu sumber kebenaran) ────────────────────────────────────────
WIB = timezone(timedelta(hours=7))


def now_wib() -> datetime:
    """Waktu sekarang di WIB (GMT+7), tanpa tzinfo (naive)."""
    return datetime.now(WIB).replace(tzinfo=None)


def today_wib() -> date:
    return datetime.now(WIB).date()


def _to_wib_naive(value) -> pd.Timestamp:
    """Ubah nilai waktu apa pun menjadi Timestamp naive dalam WIB."""
    ts = pd.to_datetime(value)
    if pd.isna(ts):
        raise ValueError("Nilai waktu tidak valid")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Jakarta").tz_localize(None)
    return ts


# ── Threshold Vibrasi (ISO 10816) ──────────────────────────────────────────
THRESHOLD = {
    "Turbine": {"A": 1.4, "B": 2.8, "C": 4.5},
    "Pump/Fan": {"A": 1.4, "B": 2.8, "C": 4.5},
}

ZONE_COLOR = {
    "ZONE A": "#2563eb",
    "ZONE B": "#16a34a",
    "ZONE C": "#d97706",
    "ZONE D": "#dc2626",
    "N/A":    "#6b7280",
}

ZONE_BG = {
    "ZONE A": "rgba(37,99,235,.12)",
    "ZONE B": "rgba(22,163,74,.12)",
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

# ── Threshold Suhu (°C) ──────────────────────────────────────────────────────
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
        # TODO(verifikasi): titik "NDE Motor" saat ini memakai batas WINDING (99/140 °C).
        # Pastikan memang disengaja — bearing NDE motor biasanya memakai batas bearing.
        return THRESHOLD_TEMP["WINDING"] if "NDE" in t else THRESHOLD_TEMP["BEARING DE MOTOR"]
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

# ── Koneksi Supabase ─────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _supabase_client(url: str, key: str):
    """Client dibuat sekali per (url, key), bukan di setiap pemanggilan."""
    from supabase import create_client
    return create_client(url, key)

def get_supabase(service_role=False):
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"] if service_role else st.secrets["SUPABASE_KEY"]
    return _supabase_client(url, key)

def _paged_select(sb, table: str, cols: str, order_cols=("date", "id"),
                  desc: bool = False, query_mod=None, batch: int = 1000) -> list:
    """
    Ambil semua baris dengan pagination yang STABIL.

    Pagination dengan range() hanya aman kalau urutannya deterministik. Banyak baris
    punya tanggal yang sama, jadi diberi tie-breaker kedua (id). Kalau kolom tie-breaker
    tidak ada di tabel, otomatis fallback ke urutan kolom pertama saja.
    """
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

# ── Threshold & Zona ─────────────────────────────────────────────────────────
def get_threshold(equipment: str):
    name = str(equipment).upper()
    key = "Turbine" if "TURBINE" in name else "Pump/Fan"
    overrides = st.session_state.get("threshold_override")
    if overrides and key in overrides:
        return overrides[key]
    return THRESHOLD[key]

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
    """
    Tambahkan kolom thr_type, zone, zone_icon, zone_label.

    Memakai get_threshold() sehingga override threshold dari halaman Data & Kelola
    ikut berlaku (sebelumnya memakai THRESHOLD default sehingga KPI/sidebar bisa
    berbeda dengan kartu equipment). Versi ini juga vektorisasi, bukan apply per baris.
    """
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

    # Vibrasi
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

    # Suhu
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

# ── Data Vibrasi (Supabase) ──────────────────────────────────────────────────
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
        st.error(f"Gagal load data: {e}")
        return pd.DataFrame()

_KEY_COLS = ["equipment", "unit", "titik", "direction"]

def save_to_db_detailed(df: pd.DataFrame):
    """
    Simpan data baru ke tabel vibration, lewati duplikat.

    Return (jumlah_baris_tersimpan, pesan_error | None). Berbeda dengan save_to_db(),
    pemanggil bisa membedakan "semua duplikat" (0, None) dari "gagal" (0, "pesan").
    Kalau gagal di tengah jalan, jumlah yang sudah masuk tetap dilaporkan.
    """
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

        # Hanya unduh data existing pada rentang tanggal file ini (bukan seluruh tabel).
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

def save_to_db(df: pd.DataFrame) -> int:
    """Versi kompatibel: return jumlah baris tersimpan, error ditampilkan lewat st.error."""
    inserted, err = save_to_db_detailed(df)
    if err:
        st.error(f"Gagal simpan data: {err}")
    return inserted

def delete_by_dates(dates: list) -> int:
    if not _assert_editor():
        return 0
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
    if not _assert_editor():
        return 0
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

# ── Autentikasi Editor ───────────────────────────────────────────────────────
# Password TIDAK lagi ditulis di kode. Atur di .streamlit/secrets.toml (lokal)
# atau menu Secrets di Streamlit Cloud:
#     EDITOR_PASSWORD = "isi-password-baru"
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
    """Return None jika sukses, atau string pesan error."""
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
    """Guard di fungsi tulis: tombol yang disembunyikan di UI saja tidak cukup."""
    if check_role() != "editor":
        st.error("🔒 Aksi ini hanya dapat dilakukan oleh Editor.")
        return False
    return True

# ── Ringkasan alarm (di-cache, sadar override threshold) ─────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _alarm_summary(thr_sig: str):
    # NB: nama argumen tanpa awalan "_" supaya ikut menjadi cache key.
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

# ── Sidebar Terpusat & Modern ─────────────────────────────────────────────────
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

        # Ringkasan Global Alert
        n_d, n_c = _alarm_summary(repr(st.session_state.get("threshold_override")))
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
            © 2026 PLTU TBK · v2.4
        </div>
        """, unsafe_allow_html=True)

# ── Running Hours Pompa (Zona Waktu WIB Terpadu) ──────────────────────────────
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
        st.error(f"Gagal load running hours: {e}")
        return pd.DataFrame(columns=cols)

def _fetch_pump_row(sb, equipment: str, unit: str):
    """Baca baris terbaru langsung dari DB (bukan dari cache 15 detik)."""
    res = (
        sb.table("pump_runtime")
        .select("status,status_changed_at,accumulated_hours")
        .eq("equipment", equipment).eq("unit", unit)
        .limit(1).execute()
    )
    return res.data[0] if res.data else None

def init_pump_runtime(equipment: str, unit: str):
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        res = sb.table("pump_runtime").select("id").eq("equipment", equipment).eq("unit", unit).execute()
        if not res.data:
            sb.table("pump_runtime").insert({
                "equipment": equipment,
                "unit": unit,
                "status": "stopped",
                "status_changed_at": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
                "accumulated_hours": 0.0,
            }).execute()
    except Exception as e:
        st.error(f"Gagal inisialisasi data running hours: {e}")

def start_pump_runtime(equipment: str, unit: str, start_dt) -> None:
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        fresh = _fetch_pump_row(sb, equipment, unit)
        if fresh and fresh.get("status") == "running":
            st.warning(
                "Equipment sudah berstatus Running (mungkin diubah pengguna lain). "
                "Muat ulang halaman untuk melihat kondisi terbaru."
            )
            return
        start_ts = _to_wib_naive(start_dt)
        sb.table("pump_runtime").update({
            "status": "running",
            "status_changed_at": start_ts.strftime("%Y-%m-%d %H:%M:%S"),
        }).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal mencatat waktu mulai: {e}")

def stop_pump_runtime(equipment: str, unit: str, stop_dt, current_status: str = None,
                      current_accum: float = None, current_changed_at=None) -> None:
    """
    Hentikan operasi dan tambahkan durasi berjalan ke accumulated_hours.

    Status/akumulasi dibaca ULANG dari database tepat sebelum update, sehingga tidak
    memakai data cache halaman yang bisa basi (mencegah jam tertimpa kalau dua editor
    menekan tombol hampir bersamaan). Argumen current_* hanya dipakai sebagai cadangan
    kalau pembacaan ulang gagal; tetap ada agar pemanggil lama tidak perlu diubah.
    """
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        stop_ts = _to_wib_naive(stop_dt)

        fresh = _fetch_pump_row(sb, equipment, unit)
        if fresh:
            status = fresh.get("status")
            changed_at = fresh.get("status_changed_at")
            accum = float(fresh.get("accumulated_hours") or 0)
        else:
            status, changed_at, accum = current_status, current_changed_at, float(current_accum or 0)

        if status != "running":
            st.warning(
                "Equipment sudah berstatus Stopped (mungkin diubah pengguna lain). "
                "Tidak ada jam yang ditambahkan."
            )
            return

        try:
            started = _to_wib_naive(changed_at)
            delta_hours = (stop_ts - started).total_seconds() / 3600.0
            if delta_hours < 0:
                st.warning("Waktu berhenti lebih awal dari waktu mulai — jam operasi tidak ditambahkan.")
                delta_hours = 0.0
        except Exception:
            delta_hours = 0.0
        new_accum = accum + delta_hours

        q = sb.table("pump_runtime").update({
            "status": "stopped",
            "status_changed_at": stop_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "accumulated_hours": new_accum,
        }).eq("equipment", equipment).eq("unit", unit)
        if fresh:
            q = q.eq("status", "running")   # tidak menimpa kalau status keburu berubah
        res = q.execute()
        if fresh and not res.data:
            st.warning("Status berubah saat diproses pengguna lain. Muat ulang halaman lalu coba lagi.")
    except Exception as e:
        st.error(f"Gagal mencatat waktu berhenti: {e}")

def reset_pump_runtime(equipment: str, unit: str) -> None:
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update({
            "status": "stopped",
            "status_changed_at": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
            "accumulated_hours": 0.0,
        }).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal reset running hours: {e}")

def reset_pump_install_date(equipment: str, unit: str) -> None:
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update(
            {"install_date": today_wib().isoformat()}
        ).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal reset umur pompa: {e}")

def compute_running_hours(row: dict) -> float:
    """Menghitung total jam berjalan. Jam saat status STOPPED dijamin tidak ikut terhitung."""
    accum = float(row.get("accumulated_hours", 0) or 0)
    if row.get("status") != "running":
        return accum
    try:
        changed = _to_wib_naive(row["status_changed_at"])
        delta_seconds = (now_wib() - changed).total_seconds()
        return accum + max(delta_seconds / 3600.0, 0.0)
    except Exception:
        return accum

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
        if years:
            parts.append(f"{years} th")
        parts.append(f"{rem_months} bln")
        return " ".join(parts)
    except Exception:
        return None

def update_pump_install_date(equipment: str, unit: str, install_date) -> None:
    if not _assert_editor():
        return
    try:
        sb = get_supabase(service_role=True)
        sb.table("pump_runtime").update(
            {"install_date": str(install_date)}
        ).eq("equipment", equipment).eq("unit", unit).execute()
    except Exception as e:
        st.error(f"Gagal simpan tanggal instalasi: {e}")

BEARING_POSISI = ["DE Motor", "NDE Motor", "DE Pompa/Fan", "NDE Pompa/Fan"]

@st.cache_data(ttl=15)
def get_bearing_install() -> pd.DataFrame:
    cols = ["equipment", "unit", "posisi", "install_date"]
    try:
        sb = get_supabase()
        res = sb.table("bearing_install").select("equipment,unit,posisi,install_date").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=cols)
    except Exception as e:
        st.error(f"Gagal load umur bearing: {e}")
        return pd.DataFrame(columns=cols)

def update_bearing_install(equipment: str, unit: str, posisi: str, install_date) -> None:
    if not _assert_editor():
        return
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
