from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MADDE_TIPLERI = ["ek", "gecici", "ek_gecici"]

for madde_tipi in MADDE_TIPLERI:
    print(f"\n=== {madde_tipi.upper()} ===")
    res = (
        supabase.table("mevzuat")
        .select("kanun_no, kanun_adi, madde_no, madde_tipi")
        .eq("madde_tipi", madde_tipi)
        .order("kanun_no")
        .order("madde_no")
        .limit(50)
        .execute()
    )

    rows = res.data or []
    if not rows:
        print("Kayıt yok.")
        continue

    for row in rows:
        print(
            f"- {row.get('kanun_no')} | "
            f"{row.get('kanun_adi')} | "
            f"{row.get('madde_tipi')} | "
            f"{row.get('madde_no')}"
        )

print("\n=== MUKERRER ADAYLARI (/A) ===")
res = (
    supabase.table("mevzuat")
    .select("kanun_no, kanun_adi, madde_no, madde_tipi")
    .like("madde_no", "%/A")
    .order("kanun_no")
    .order("madde_no")
    .limit(50)
    .execute()
)

rows = res.data or []
if not rows:
    print("Kayıt yok.")
else:
    for row in rows:
        print(
            f"- {row.get('kanun_no')} | "
            f"{row.get('kanun_adi')} | "
            f"{row.get('madde_tipi')} | "
            f"{row.get('madde_no')}"
        )