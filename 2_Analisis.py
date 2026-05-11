import streamlit as st

st.set_page_config(page_title="Analisis — PLTU TBK", layout="wide")

st.title("📈 Halaman 2 — Analisis")
st.info("Halaman Analisis (Trend + Prediksi) sedang dalam pembuatan...")

with st.sidebar:
    st.page_link("app.py", label="📊 Monitor", icon="1️⃣")
    st.page_link("pages/2_Analisis.py", label="📈 Analisis", icon="2️⃣")
    st.page_link("pages/3_Data_Kelola.py", label="🗄️ Data & Kelola", icon="3️⃣")
