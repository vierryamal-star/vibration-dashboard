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

/* Portal Hub Card Fallback */
.hub-fallback-box {
    border-radius: 14px;
    padding: 24px;
    background: color-mix(in srgb, var(--secondary-background-color) 60%, var(--background-color));
    border: 1px solid color-mix(in srgb, var(--text-color) 15%, transparent);
    text-align: center;
    margin: 16px 0;
}
.cred-chip-box {
    display: inline-flex;
    gap: 16px;
    background: rgba(37,99,235,0.08);
    border: 1px solid rgba(37,99,235,0.25);
    border-radius: 8px;
    padding: 8px 16px;
    margin: 14px 0;
    font-size: 13px;
}
.cred-mono {
    font-family: monospace;
    font-weight: 800;
    color: #2563eb;
}

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

# ── Logika Fetch Data Mandiri Tanpa Bergantung pada utils.py ────────────────
EXTERNAL_VERCEL_API = "https://bearing-monitoring.vercel.app/api/equipment"

def map_area(area_str: str) -> str:
    if not area_str:
        return "TBK COM"
    a = str(area_str).upper()
    if "TURBIN 2" in a or "BOILER 2" in a or "UNIT 2" in a:
        return "TBK #2"
    elif "TURBIN" in a or
