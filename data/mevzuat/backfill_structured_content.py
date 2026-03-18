import os
import re
from typing import Any, Dict
from dotenv import load_dotenv
from supabase import create_client
from structured_content_utils import build_structured_content
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)




def main():
    kanun_no = input("Kanun no gir (örn: 6098): ").strip()

    batch_size = 500
    rows = []
    offset = 0

    while True:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, madde_no, madde_tipi, icerik")
            .eq("kanun_no", kanun_no)
            .range(offset, offset + batch_size - 1)
            .execute()
        )

        batch = res.data or []
        if not batch:
            break

        rows.extend(batch)

        if len(batch) < batch_size:
            break

        offset += batch_size

    print(f"{kanun_no} için bulunan kayıt sayısı: {len(rows)}")

    updated = 0

    for row in rows:
        structured_content = build_structured_content(row.get("icerik", ""))

        (
            supabase.table("mevzuat")
            .update({"structured_content": structured_content})
            .eq("id", row["id"])
            .execute()
        )

        updated += 1
        if updated % 50 == 0:
            print(f"Güncellendi: {updated}")

    print(f"Tamamlandı. Toplam güncellenen kayıt: {updated}")


if __name__ == "__main__":
    main()