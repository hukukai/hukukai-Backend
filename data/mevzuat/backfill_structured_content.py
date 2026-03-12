import os
import re
from typing import Any, Dict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def build_structured_content(article_text: str) -> dict:
    """
    Tam madde metninden structured_content üretir.
    Öncelik:
    1) (1) (2) (3) gibi açık fıkra numaraları
    2) boş satıra göre paragraf ayrımı
    3) tek parça fallback
    """
    text = (article_text or "").strip()

    if not text:
        return {"fikralar": {}}

    # 1) Açık numaralı fıkra ayrımı: (1) ... (2) ...
    parts = re.split(r"(\(\d+\))", text)

    if len(parts) >= 3:
        fikra_map = {}
        current_no = None

        for part in parts:
            part = (part or "").strip()

            if re.fullmatch(r"\(\d+\)", part):
                current_no = part.strip("()")
                fikra_map[current_no] = part
            else:
                if current_no:
                    if fikra_map[current_no]:
                        fikra_map[current_no] += " " + part
                    else:
                        fikra_map[current_no] = part

        fikra_map = {k: v.strip() for k, v in fikra_map.items() if v.strip()}
        if fikra_map:
            return {"fikralar": fikra_map}

    # 2) Paragraf bazlı ayırma
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if len(paragraphs) > 1:
        return {
            "fikralar": {
                str(i + 1): p for i, p in enumerate(paragraphs)
            }
        }

    # 3) Son fallback: tek parça
    return {
        "fikralar": {
            "1": text
        }
    }


def main():
    kanun_no = input("Kanun no gir (örn: 6098): ").strip()

    res = (
        supabase.table("mevzuat")
        .select("id, kanun_no, madde_no, madde_tipi, icerik")
        .eq("kanun_no", kanun_no)
        .execute()
    )

    rows = res.data or []
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