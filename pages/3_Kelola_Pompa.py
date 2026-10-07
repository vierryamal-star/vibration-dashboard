import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import sys
import os

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

st.markdown(GLOBAL_UI_CSS, unsafe_allow_html=True)

render_app_sidebar()
render_page_header("⏱️ Jam Operasi & Status Mesin (Live Sync)")
st.caption("Data terhubung langsung secara real-time dari sistem bearing-monitoring.vercel.app.")

EXTERNAL_VERCEL_API = "https://bearing-monitoring.vercel.app/api/equipment"

def map_area(area_str):
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
def fetch_local_vercel_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://bearing-monitoring.vercel.app",
        "Referer": "https://bearing-monitoring.vercel.app/",
    }
    try:
        res = requests.get(EXTERNAL_VERCEL_API, headers=headers, timeout=8)
        if res.status_code == 200:
            payload = res.json()
            items = payload.get("equipment", []) if isinstance(payload, dict) else payload
            rows = []
            for eq in items:
                rt = eq.get("runtime", {})
                total_h = float(rt.get("total_hours") or 0.0)
                sess_h = float(rt.get("current_session_hours") or 0.0)
                is_running = str(eq.get("status", "")).upper() == "RUNNING"
                eff_total = total_h + sess_h if is_running else total_h

                bearings = eq.get("bearings", [])
                brg_dict = {}
                for b in bearings:
                    pos = b.get("position")
                    brg_dict[pos] = {
                        "hours": float(b.get("hours") or 0.0),
                        "remaining": b.get("remaining_hours"),
                        "status": b.get("status", "NORMAL"),
                    }

                rows.append({
                    "code": eq.get("code", ""),
                    "equipment": eq.get("name", ""),
                    "area": eq.get("area", ""),
                    "unit": map_area(eq.get("area", "")),
                    "status": "RUNNING" if is_running else "STOPPED",
                    "total_hours": eff_total,
                    "bearings": brg_dict,
                })
            return pd.DataFrame(rows)
    except Exception
