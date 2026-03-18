import json
import sys
from pathlib import Path
from collections import Counter


BASE_DIR = Path(__file__).resolve().parent
VALID_TYPES = {"madde", "ek", "gecici", "ek_gecici", "mukerrer_madde", "mukerrer_ek"}


def sort_key(record):
    madde_tipi_order = {
        "madde": 0,
        "ek": 1,
        "gecici": 2,
        "ek_gecici": 3,
        "mukerrer_madde": 4,
        "mukerrer_ek": 5,
    }

    no = str(record.get("madde_no", ""))
    if "/" in no:
        base, suffix = no.split("/", 1)
        try:
            base_num = int(base)
        except ValueError:
            base_num = 10**9
        return (madde_tipi_order.get(record.get("madde_tipi"), 99), base_num, suffix)

    try:
        no_num = int(no)
    except ValueError:
        no_num = 10**9

    return (madde_tipi_order.get(record.get("madde_tipi"), 99), no_num, "")


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python validate_yonetmelik_json.py 6698_verbis_ym")
        return

    klasor = sys.argv[1]
    folder = BASE_DIR / klasor

    if not folder.exists():
        raise FileNotFoundError(f"Klasör bulunamadı: {folder}")

    json_files = list(folder.glob("*_yonetmelik_preview.json"))
    if not json_files:
        raise FileNotFoundError(f"Preview JSON bulunamadı: {folder}")

    json_path = json_files[0]

    with open(json_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    print(f"Dosya: {json_path.name}")
    print(f"Toplam kayıt: {len(data)}")

    if not isinstance(data, list):
        print("HATA: JSON liste formatında değil.")
        return

    type_counter = Counter()
    duplicates = []
    missing_fields = []
    invalid_types = []
    invalid_source_type = []
    empty_content = []
    inconsistent_bagli_kanun = []
    inconsistent_title = []

    seen = set()

    first_bagli_kanun = None
    first_title = None

    for i, row in enumerate(data, start=1):
        key = (
            str(row.get("bagli_kanun_no")),
            str(row.get("yonetmelik_adi")),
            str(row.get("madde_tipi")),
            str(row.get("madde_no")),
        )

        if key in seen:
            duplicates.append((i, key))
        else:
            seen.add(key)

        required_fields = [
            "bagli_kanun_no",
            "yonetmelik_adi",
            "madde_no",
            "madde_tipi",
            "icerik",
            "source_type",
        ]
        missing = [field for field in required_fields if not row.get(field)]
        if missing:
            missing_fields.append((i, missing))

        madde_tipi = row.get("madde_tipi")
        type_counter[madde_tipi] += 1

        if madde_tipi not in VALID_TYPES:
            invalid_types.append((i, madde_tipi))

        if row.get("source_type") != "yonetmelik":
            invalid_source_type.append((i, row.get("source_type")))

        icerik = str(row.get("icerik", "")).strip()
        if not icerik:
            empty_content.append(i)

        if first_bagli_kanun is None:
            first_bagli_kanun = str(row.get("bagli_kanun_no", ""))
        elif str(row.get("bagli_kanun_no", "")) != first_bagli_kanun:
            inconsistent_bagli_kanun.append((i, row.get("bagli_kanun_no")))

        if first_title is None:
            first_title = str(row.get("yonetmelik_adi", ""))
        elif str(row.get("yonetmelik_adi", "")) != first_title:
            inconsistent_title.append((i, row.get("yonetmelik_adi")))

    print("Tip dağılımı:", dict(type_counter))

    print("\n=== DUPLICATE KAYITLAR ===")
    if duplicates:
        for item in duplicates[:20]:
            print(item)
    else:
        print("Yok")

    print("\n=== EKSİK ALANLAR ===")
    if missing_fields:
        for item in missing_fields[:20]:
            print(item)
    else:
        print("Yok")

    print("\n=== GEÇERSİZ madde_tipi ===")
    if invalid_types:
        for item in invalid_types[:20]:
            print(item)
    else:
        print("Yok")

    print("\n=== GEÇERSİZ source_type ===")
    if invalid_source_type:
        for item in invalid_source_type[:20]:
            print(item)
    else:
        print("Yok")

    print("\n=== BOŞ icerik ===")
    if empty_content:
        print(empty_content[:20])
    else:
        print("Yok")

    print("\n=== TUTARSIZ bagli_kanun_no ===")
    if inconsistent_bagli_kanun:
        for item in inconsistent_bagli_kanun[:20]:
            print(item)
    else:
        print("Yok")

    print("\n=== TUTARSIZ yonetmelik_adi ===")
    if inconsistent_title:
        for item in inconsistent_title[:20]:
            print(item)
    else:
        print("Yok")

    print("\n=== MADDE SIRASI ÖNİZLEME ===")
    ordered = sorted(data, key=sort_key)
    preview = [
        (row.get("madde_tipi"), row.get("madde_no"))
        for row in ordered[:20]
    ]
    print(preview)


if __name__ == "__main__":
    main()