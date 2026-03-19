from dotenv import load_dotenv
from supabase import create_client
import os
import json
from collections import defaultdict

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

KANUNLAR = [
    "1136", "2004", "2576", "2577", "4721", "4733", "4857", "5237", "5271",
    "6098", "6100", "6102", "6183", "6325", "6502", "6698", "7036", "7201"
]


def classify_structured_content(sc):
    if not sc or not isinstance(sc, dict):
        return "missing"

    fikralar = sc.get("fikralar")
    if not isinstance(fikralar, dict) or not fikralar:
        return "missing"

    fikra_keys = list(fikralar.keys())
    bent_count = 0

    for _, value in fikralar.items():
        if isinstance(value, dict):
            bentler = value.get("bentler") or {}
            if isinstance(bentler, dict):
                bent_count += len(bentler)

    if len(fikra_keys) == 1 and bent_count == 0:
        return "single_fikra_only"

    if len(fikra_keys) == 1 and bent_count > 0:
        return "single_fikra_with_bents"

    if len(fikra_keys) > 1 and bent_count == 0:
        return "multi_fikra"

    if len(fikra_keys) > 1 and bent_count > 0:
        return "multi_fikra_with_bents"

    return "other"


def main():
    overall = []
    sample_rows = defaultdict(list)

    for kanun_no in KANUNLAR:
        print(f"\n=== {kanun_no} ===")

        res = (
            supabase.table("mevzuat")
            .select("kanun_no, kanun_adi, madde_no, madde_tipi, structured_content")
            .eq("kanun_no", kanun_no)
            .execute()
        )

        rows = res.data or []
        total = len(rows)

        counts = defaultdict(int)

        for row in rows:
            cls = classify_structured_content(row.get("structured_content"))
            counts[cls] += 1

            if len(sample_rows[(kanun_no, cls)]) < 3:
                sample_rows[(kanun_no, cls)].append({
                    "madde_no": row.get("madde_no"),
                    "madde_tipi": row.get("madde_tipi"),
                })

        summary = {
            "kanun_no": kanun_no,
            "total": total,
            "missing": counts["missing"],
            "single_fikra_only": counts["single_fikra_only"],
            "single_fikra_with_bents": counts["single_fikra_with_bents"],
            "multi_fikra": counts["multi_fikra"],
            "multi_fikra_with_bents": counts["multi_fikra_with_bents"],
        }
        overall.append(summary)

        print(json.dumps(summary, ensure_ascii=False, indent=2))

        for cls in [
            "missing",
            "single_fikra_only",
            "single_fikra_with_bents",
            "multi_fikra",
            "multi_fikra_with_bents",
        ]:
            samples = sample_rows.get((kanun_no, cls), [])
            if samples:
                print(f"  {cls} örnekleri: {samples}")

    print("\n\n=== TOPLU ÖZET ===")
    print(json.dumps(overall, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()