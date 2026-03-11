import os
import re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def canon_text(text: str) -> str:
    return (text or "").strip()


def extract_explicit_article_refs(text: str, source_kanun_no: str):
    """
    Metin içindeki açık madde atıflarını çıkarır.
    İlk sürümde şunları yakalar:
    - 18 inci madde
    - 32 nci madde
    - 18, 19, 20 ve 21 inci maddeleri
    - bu Kanunun 18 inci maddesi
    """
    text = canon_text(text)
    refs = []

    # 1) Çoklu atıf: "18, 19, 20 ve 21 inci maddeleri"
    multi_pattern = re.finditer(
        r"((?:\d+\s*,\s*)+(?:\d+\s*ve\s*)?\d+)\s*(?:inci|nci|uncu|üncü)\s*madd",
        text,
        flags=re.IGNORECASE
    )

    for match in multi_pattern:
        raw_match = match.group(0)
        numbers_part = match.group(1)
        numbers = re.findall(r"\d+", numbers_part)

        for num in numbers:
            refs.append({
                "source_kanun_no": source_kanun_no,
                "source_madde_tipi": "madde",
                "target_kanun_no": source_kanun_no,
                "target_madde_tipi": "madde",
                "target_madde_no": num,
                "ref_type": "explicit_article",
                "raw_match": raw_match,
            })

    # 2) Tekil atıf: "32 nci madde", "18 inci maddesi"
    single_pattern = re.finditer(
        r"\b(\d+)\s*(?:inci|nci|uncu|üncü)\s*madd(?:e|esi|enin|elerine|eleri)?\b",
        text,
        flags=re.IGNORECASE
    )

    for match in single_pattern:
        raw_match = match.group(0)
        num = match.group(1)

        refs.append({
            "source_kanun_no": source_kanun_no,
            "source_madde_tipi": "madde",
            "target_kanun_no": source_kanun_no,
            "target_madde_tipi": "madde",
            "target_madde_no": num,
            "ref_type": "explicit_article",
            "raw_match": raw_match,
        })

    # duplicate temizle
    deduped = []
    seen = set()

    for r in refs:
        key = (
            r["source_kanun_no"],
            r["target_kanun_no"],
            r["target_madde_tipi"],
            r["target_madde_no"],
            r["ref_type"],
            r["raw_match"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return deduped


def main():
    kanun_no = input("Kanun no gir (örn: 4857): ").strip()

    # Önce eski kayıtları sil
    supabase.table("mevzuat_references").delete().eq("source_kanun_no", kanun_no).execute()

    res = (
        supabase.table("mevzuat")
        .select("kanun_no, madde_no, madde_tipi, icerik")
        .eq("kanun_no", kanun_no)
        .eq("madde_tipi", "madde")
        .execute()
    )

    rows = res.data or []
    print(f"{kanun_no} için taranacak madde sayısı: {len(rows)}")

    all_refs = []

    for row in rows:
        text = row.get("icerik", "")
        source_madde_no = row.get("madde_no")

        refs = extract_explicit_article_refs(text, kanun_no)

        for ref in refs:
            ref["source_madde_no"] = source_madde_no

        all_refs.extend(refs)

    print(f"Bulunan toplam referans: {len(all_refs)}")

    if all_refs:
        chunk_size = 500
        for i in range(0, len(all_refs), chunk_size):
            chunk = all_refs[i:i + chunk_size]
            supabase.table("mevzuat_references").insert(chunk).execute()
            print(f"Inserted: {min(i + chunk_size, len(all_refs))}/{len(all_refs)}")

    print("Tamamlandı.")


if __name__ == "__main__":
    main()