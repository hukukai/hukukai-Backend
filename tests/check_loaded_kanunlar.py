from dotenv import load_dotenv
from supabase import create_client
import os
from collections import Counter

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_all_mevzuat_rows(page_size=1000):
    all_rows = []
    start = 0

    while True:
        end = start + page_size - 1
        res = (
            supabase.table("mevzuat")
            .select("kanun_no, kanun_adi, madde_no", count="exact")
            .range(start, end)
            .execute()
        )

        rows = res.data or []
        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        start += page_size

    return all_rows

rows = fetch_all_mevzuat_rows()

if not rows:
    print("mevzuat tablosunda hiç kayıt yok.")
    raise SystemExit

counter = Counter()
kanun_adlari = {}

for row in rows:
    kanun_no = str(row.get("kanun_no") or "").strip()
    kanun_adi = str(row.get("kanun_adi") or "").strip()

    if not kanun_no:
        continue

    counter[kanun_no] += 1
    if kanun_no not in kanun_adlari and kanun_adi:
        kanun_adlari[kanun_no] = kanun_adi

print("\nYüklü kanunlar:\n")
for kanun_no, count in sorted(counter.items(), key=lambda x: x[0]):
    print(f"- {kanun_no} | {kanun_adlari.get(kanun_no, 'Kanun adı yok')} | kayıt sayısı: {count}")

print(f"\nToplam kayıt sayısı: {sum(counter.values())}")
print(f"Toplam farklı kanun sayısı: {len(counter)}")