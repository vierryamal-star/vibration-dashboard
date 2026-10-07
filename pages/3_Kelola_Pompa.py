import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import render_page_header, render_app_sidebar, GLOBAL_UI_CSS

try:
    st.set_page_config(
        page_title="Jam Operasi Mesin — PLTU TBK",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

st.markdown("""
<style>
[data-testid="stSidebarNav"]{ display:none; }
section[data-testid="stSidebar"]>div:first-child{ padding-top:1rem; }

/* Status Badges */
.badge-running { background: rgba(34,197,94,.15); color: #16a34a; border: 1px solid #16a34a50; padding: 4px 10px; border-radius: 99px; font-weight: 800; font-size: 11px; display: inline-block; }
.badge-stopped { background: rgba(107,114,128,.15); color: #6b7280; border: 1px solid #6b728050; padding: 4px 10px; border-radius: 99px; font-weight: 800; font-size: 11px; display: inline-block; }

/* KPI Grid */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.kpi-card {
    border-radius: 12px;
    padding: 14px 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color));
}
.kpi-card .v { font-size: 24px; font-weight: 800; line-height: 1.2; margin-top: 4px; }
.kpi-card .l { font-size: 11px; font-weight: 700; opacity: .65; text-transform: uppercase; letter-spacing: .05em; }

/* Machine Card */
.machine-card {
    border-radius: 12px;
    padding: 16px;
    border: 1px solid color-mix(in srgb, var(--text-color) 14%, transparent);
    background: color-mix(in srgb, var(--secondary-background-color) 45%, var(--background-color));
    margin-bottom: 12px;
}
.machine-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.machine-title {
    font-size: 16px;
    font-weight: 800;
    color: #2563eb;
}
.bearing-chip-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 10px;
}
.bearing-chip {
    background: rgba(37,99,235,0.06);
    border: 1px solid rgba(37,99,235,0.2);
    border-radius: 8px;
    padding: 8px;
    font-size: 11px;
}
.bearing-chip .bp { font-weight: 800; color: #2563eb; margin-bottom: 2px; }
.bearing-chip .bh { font-weight: 700; font-size: 13px; }

@media (max-width: 992px) {
    .kpi-container { grid-template-columns: repeat(2, 1fr); }
    .bearing-chip-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
""", unsafe_allow_html=True)
st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("⏱️ Jam Operasi & Status Mesin (Live Sync)")
st.caption("Data terhubung langsung secara real-time dari sistem bearing-monitoring.vercel.app.")

# ── Logika Internal Fetch & Mapping API Vercel ──────────────────────────────
EXTERNAL_VERCEL_API = "https://bearing-monitoring.vercel.app/api/equipment"

def map_area(area_str: str) -> str:
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
def fetch_data_from_vercel():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    try:
        res = requests.get(EXTERNAL_VERCEL_API, headers=headers, timeout=10)
        if res.status_code == 200:
            payload = res.json()
            items = payload.get("equipment", []) if isinstance(payload, dict) else payload
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
                    "unit": map_area(eq.get("area", "")),
                    "status": str(eq.get("status", "STOPPED")).lower(),
                    "total_hours": eff_total,
                    "session_hours": sess_h,
                    "session_started_at": rt.get("session_started_at"),
                    "equipment_type": eq.get("equipment_type", ""),
                    "bearings": brg_dict,
                    "bearing_status": eq.get("bearing_status", "NORMAL")
                })
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"[Vercel Fetch Error]: {e}")
    return pd.DataFrame()

# ── Eksekusi Sinkronisasi ───────────────────────────────────────────────────
df_sync = fetch_data_from_vercel()

# ── Banner Atas & Tombol Akses Langsung ─────────────────────────────────────
top_c1, top_c2 = st.columns([3, 1.2])
with top_c1:
    st.info("💡 **Akses Portal:** Gunakan tombol di samping jika ingin melakukan rotasi, start/stop mesin, atau pergantian bearing.")
with top_c2:
    st.link_button("🚀 Buka Portal Vercel (Tab Baru)", "https://bearing-monitoring.vercel.app/", type="primary", use_container_width=True)

if df_sync.empty:
    st.warning("⏳ Sedang menghubungkan ke server Vercel atau belum ada data yang diterima.")
    if st.button("🔄 Coba Hubungkan Kembali", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ── Kontrol Filter ──────────────────────────────────────────────────────────
c_ref, c_u, c_st = st.columns([1, 1.5, 1.5])
with c_ref:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.success("Data diperbarui!")
        st.rerun()

with c_u:
    available_units = ["Semua Unit"] + sorted(list(df_sync["unit"].unique()))
    sel_u = st.selectbox("🏭 Filter Bagian Unit:", available_units)

with c_st:
    sel_status = st.selectbox("⚡ Status Mesin:", ["Semua Status", "Hanya Running (🟢)", "Hanya Stopped (⚪)"])

# Terapkan Filter
df_filtered = df_sync.copy()
if sel_u != "Semua Unit":
    df_filtered = df_filtered[df_filtered["unit"] == sel_u]
if sel_status == "Hanya Running (🟢)":
    df_filtered = df_filtered[df_filtered["status"] == "running"]
elif sel_status == "Hanya Stopped (⚪)":
    df_filtered = df_filtered[df_filtered["status"] == "stopped"]

# ── KPI Metrics Cards ───────────────────────────────────────────────────────
total_eq = len(df_filtered)
total_run = len(df_filtered[df_filtered["status"] == "running"])
total_stop = len(df_filtered[df_filtered["status"] == "stopped"])
sum_hours = df_filtered["total_hours"].sum()

st.markdown(f"""
<div class="kpi-container">
  <div class="kpi-card">
    <div class="l">Total Peralatan</div>
    <div class="v">{total_eq}</div>
  </div>
  <div class="kpi-card">
    <div class="l">Mesin Operasi (Running)</div>
    <div class="v" style="color:#16a34a;">🟢 {total_run}</div>
  </div>
  <div class="kpi-card">
    <div class="l">Mesin Standby (Stopped)</div>
    <div class="v" style="color:#6b7280;">⚪ {total_stop}</div>
  </div>
  <div class="kpi-card">
    <div class="l">Total Running Hours</div>
    <div class="v" style="color:#d97706;">⏱️ {sum_hours:,.1f} <span style="font-size:13px;opacity:.7;">jam</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs Tampilan ───────────────────────────────────────────────────────────
tab_cards, tab_table = st.tabs([
    "📋 Ringkasan Kartu & Posisi Bearing",
    "📊 Tabel Rekapitulasi Lengkap",
])

with tab_cards:
    if df_filtered.empty:
        st.info("Tidak ada equipment yang cocok dengan kriteria filter.")
    else:
        for _, row in df_filtered.iterrows():
            is_run = row["status"] == "running"
            badge = '<span class="badge-running">🟢 RUNNING</span>' if is_run else '<span class="badge-stopped">⚪ STOPPED</span>'
            code_label = f"<span style='font-size:12px;opacity:.7;'>[{row['code']}]</span>" if row["code"] else ""
            
            st.markdown(f"""
            <div class="machine-card">
              <div class="machine-header">
                <div>
                  <span class="machine-title">{row['equipment']}</span> {code_label}
                  <div style="font-size:11.5px;opacity:.75;margin-top:2px;">📍 Lokasi / Area: <b>{row['area']}</b> ({row['unit']})</div>
                </div>
                <div style="text-align:right;">
                  {badge}
                  <div style="font-size:17px;font-weight:800;color:#d97706;margin-top:4px;">⏱️ {row['total_hours']:,.1f} jam</div>
                </div>
              </div>
            """, unsafe_allow_html=True)

            brgs = row.get("bearings", {})
            if brgs:
                pos_order = ["MD", "MN", "PD", "PN", "DE", "NDE"]
                sorted_keys = [k for k in pos_order if k in brgs] + [k for k in brgs if k not in pos_order]
                
                chips_html = '<div class="bearing-chip-grid">'
                for pk in sorted_keys:
                    b_data = brgs[pk]
                    h_val = b_data.get("hours", 0.0)
                    rem_val = b_data.get("remaining_hours")
                    rem_str = f"Sisa: {rem_val:,.0f} jam" if rem_val is not None else "Limit: –"
                    chips_html += f"""
                    <div class="bearing-chip">
                      <div class="bp">📍 Posisi {pk}</div>
                      <div class="bh">{h_val:,.1f} jam</div>
                      <div style="opacity:.7;font-size:10px;">{rem_str}</div>
                    </div>
                    """
                chips_html += '</div>'
                st.markdown(chips_html, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

with tab_table:
    df_table = df_filtered[["code", "equipment", "unit", "area", "status", "total_hours", "bearing_status"]].copy()
    df_table.columns = ["Kode", "Nama Equipment", "Unit", "Area", "Status", "Running Hours (jam)", "Kondisi Bearing"]
    df_table["Status"] = df_table["Status"].str.upper()
    
    st.dataframe(df_table, use_container_width=True, hide_index=True)
    
    csv_bytes = df_table.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data CSV",
        data=csv_bytes,
        file_name=f"running_hours_tbk_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )
