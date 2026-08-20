# utils.py

@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    """Mengambil seluruh data historis dari Supabase tanpa batas 1.000 baris."""
    try:
        sb = get_supabase()
        all_rows = []
        batch_size = 1000
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

        df = pd.DataFrame(all_rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["date", "value"])
        return df
    except Exception as e:
        st.error(f"Gagal load data: {e}")
        return pd.DataFrame()

def save_to_db(df: pd.DataFrame) -> int:
    """Menyimpan data Excel ke Supabase dalam batch tanpa batasan 1.000 baris."""
    try:
        sb = get_supabase(service_role=True)
        now = datetime.now().isoformat()
        
        # 1. Ambil SELURUH primary key yang sudah ada menggunakan paginasi
        existing_keys = set()
        start = 0
        batch_size = 1000
        
        while True:
            res = (
                sb.table("vibration")
                .select("equipment,unit,titik,direction,date")
                .range(start, start + batch_size - 1)
                .execute()
            )
            rows = res.data if res.data else []
            if not rows:
                break
            for row in rows:
                key = f"{str(row['equipment']).strip()}|{str(row['unit']).strip()}|{str(row['titik']).strip()}|{str(row['direction']).strip()}|{str(row['date'])[:10]}"
                existing_keys.add(key)
            if len(rows) < batch_size:
                break
            start += batch_size

        # 2. Filter hanya baris baru yang belum ada di database
        rows_to_insert = []
        for _, r in df.iterrows():
            date_str = str(r["date"])[:10] if pd.notna(r["date"]) else ""
            key = f"{str(r['equipment']).strip()}|{str(r['unit']).strip()}|{str(r['titik']).strip()}|{str(r['direction']).strip()}|{date_str}"
            
            if key not in existing_keys:
                rows_to_insert.append({
                    "equipment":   str(r["equipment"]).strip(),
                    "unit":        str(r["unit"]).strip(),
                    "titik":       str(r["titik"]).strip(),
                    "direction":   str(r["direction"]).strip(),
                    "date":        date_str,
                    "value":       float(r["value"]) if pd.notna(r["value"]) else None,
                    "uploaded_at": now,
                })
                existing_keys.add(key)  # Mencegah duplikasi internal di dalam file Excel yang sama

        # 3. Masukkan ke database secara bertahap (batch 500 baris)
        inserted_count = 0
        if rows_to_insert:
            insert_batch_size = 500
            for i in range(0, len(rows_to_insert), insert_batch_size):
                batch = rows_to_insert[i:i + insert_batch_size]
                sb.table("vibration").insert(batch).execute()
                inserted_count += len(batch)
                
        return inserted_count
    except Exception as e:
        st.error(f"Gagal simpan data: {e}")
        return 0
