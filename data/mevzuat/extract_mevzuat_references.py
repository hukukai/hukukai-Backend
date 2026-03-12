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


LAW_ALIASES = {
    "tbk": "6098",
    "türk borçlar kanunu": "6098",
    "borçlar kanunu": "6098",
    "tck": "5237",
    "türk ceza kanunu": "5237",
    "hmk": "6100",
    "hukuk muhakemeleri kanunu": "6100",
    "cmk": "5271",
    "ceza muhakemesi kanunu": "5271",
    "iş kanunu": "4857",
    "4857 sayılı kanun": "4857",
    "6098 sayılı kanun": "6098",
    "6100 sayılı kanun": "6100",
    "5237 sayılı kanun": "5237",
    "5271 sayılı kanun": "5271",
}


def normalize_law_ref(text: str):
    text_l = (text or "").strip().casefold()
    return LAW_ALIASES.get(text_l)


def extract_explicit_article_refs(text: str, source_kanun_no: str):
    text = canon_text(text)
    refs = []

    def add_ref(target_kanun_no, target_madde_no, raw_match, ref_type="explicit_article"):
        if not target_kanun_no or not target_madde_no:
            return
        refs.append({
            "source_kanun_no": source_kanun_no,
            "source_madde_tipi": "madde",
            "target_kanun_no": str(target_kanun_no),
            "target_madde_tipi": "madde",
            "target_madde_no": str(target_madde_no).upper().replace(" ", ""),
            "ref_type": ref_type,
            "raw_match": raw_match,
        })

    # -------------------------------------------------
    # 1) HMK m. 114 / TBK 49 / TCK 109 / CMK 100
    # -------------------------------------------------
    short_alias_pattern = re.finditer(
        r"\b(TBK|TCK|HMK|CMK)\s*(?:m\.|md\.|madde)?\s*(\d+(?:/[A-Z])?)\b",
        text,
        flags=re.IGNORECASE
    )
    for m in short_alias_pattern:
        law_alias = m.group(1)
        madde_no = m.group(2)
        add_ref(normalize_law_ref(law_alias), madde_no, m.group(0), "explicit_cross_law")

    # -------------------------------------------------
    # 2) 6100 sayılı Kanunun 114 üncü maddesi
    # -------------------------------------------------
    numbered_law_pattern = re.finditer(
        r"\b(\d{4})\s+sayılı\s+Kanun(?:un|unun|nun|nın|na|nda|daki)?\s+(\d+(?:/[A-Z])?)\s*(?:inci|nci|uncu|üncü)\s*madd",
        text,
        flags=re.IGNORECASE
    )
    for m in numbered_law_pattern:
        law_no = m.group(1)
        madde_no = m.group(2)
        add_ref(law_no, madde_no, m.group(0), "explicit_cross_law")

    # -------------------------------------------------
    # 3) Türk Borçlar Kanununun 49 uncu maddesi
    # -------------------------------------------------
    named_law_pattern = re.finditer(
        r"\b(Türk Borçlar Kanunu|Borçlar Kanunu|Türk Ceza Kanunu|Hukuk Muhakemeleri Kanunu|Ceza Muhakemesi Kanunu|İş Kanunu)\b"
        r"(?:nun|nın|nunun|nunun|un|ün|na|ne|nda|nde|daki|deki)?\s+"
        r"(\d+(?:/[A-Z])?)\s*(?:inci|nci|uncu|üncü)\s*madd",
        text,
        flags=re.IGNORECASE
    )
    for m in named_law_pattern:
        law_name = m.group(1)
        madde_no = m.group(2)
        add_ref(normalize_law_ref(law_name), madde_no, m.group(0), "explicit_cross_law")

    # -------------------------------------------------
    # 4) Bu Kanunun 18 inci maddesi
    # -------------------------------------------------
    same_law_pattern = re.finditer(
        r"\bbu\s+Kanun(?:un|unun|nun|nın|na|nda|daki)?\s+(\d+(?:/[A-Z])?)\s*(?:inci|nci|uncu|üncü)\s*madd",
        text,
        flags=re.IGNORECASE
    )
    for m in same_law_pattern:
        madde_no = m.group(1)
        add_ref(source_kanun_no, madde_no, m.group(0), "explicit_same_law")

    # -------------------------------------------------
    # 5) Çoklu atıf: 18, 19, 20 ve 21 inci maddeleri
    # -------------------------------------------------
    multi_pattern = re.finditer(
        r"((?:\d+(?:/[A-Z])?\s*,\s*)+(?:\d+(?:/[A-Z])?\s*ve\s*)?\d+(?:/[A-Z])?)\s*(?:inci|nci|uncu|üncü)\s*madd",
        text,
        flags=re.IGNORECASE
    )

    for match in multi_pattern:
        raw_match = match.group(0)
        numbers_part = match.group(1)
        numbers = re.findall(r"\d+(?:/[A-Z])?", numbers_part, flags=re.IGNORECASE)

        for num in numbers:
            add_ref(source_kanun_no, num, raw_match, "explicit_article")

    # -------------------------------------------------
    # 6) Tekil atıf: 32 nci madde
    # -------------------------------------------------
    single_pattern = re.finditer(
        r"\b(\d+(?:/[A-Z])?)\s*(?:inci|nci|uncu|üncü)\s*madd(?:e|esi|enin|elerine|eleri)?\b",
        text,
        flags=re.IGNORECASE
    )

    for match in single_pattern:
        raw_match = match.group(0)
        num = match.group(1)
        add_ref(source_kanun_no, num, raw_match, "explicit_article")

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