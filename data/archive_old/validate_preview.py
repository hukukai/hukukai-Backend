import json
import re
from collections import Counter

JSON_FILE = "preview_4857.json"

EXPECTED = {
    "madde": set(str(i) for i in range(1, 123)),
    "ek": set(str(i) for i in range(1, 4)),
    "gecici": set(str(i) for i in range(1, 13)),
}

BAD_PATTERNS = [
    r"\bBİRİNCİ BÖLÜM\b",
    r"\bİKİNCİ BÖLÜM\b",
    r"\bÜÇÜNCÜ BÖLÜM\b",
    r"\bDÖRDÜNCÜ BÖLÜM\b",
    r"\bBEŞİNCİ BÖLÜM\b",
    r"\bALTINCI BÖLÜM\b",
    r"\bYEDİNCİ BÖLÜM\b",
    r"\bSEKİZİNCİ BÖLÜM\b",
    r"\bDOKUZUNCU BÖLÜM\b",
    r"\bONUNCU BÖLÜM\b",
    r"\bGenel Hükümler\b",
    r"\bÜcret\b",
    r"\bİşin Düzenlenmesi\b",
    r"\bİş Sağlığı ve Güvenliği\b",
    r"\bİdari Ceza Hükümleri\b",
    r"\bÇeşitli, Geçici ve Son Hükümler\b",
    r"\bYürürlük\b",
    r"\bYürütme\b",
    r"\bMADDE\s+\d+\b",
    r"\bMadde\s+\d+\b",
    r"\bEk Madde\s+\d+\b",
    r"\bGeçici Madde\s+\d+\b",
]

SHORT_LIMIT = 120


def load_data(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise RuntimeError("JSON list formatında değil.")
    return data


def strip_prefix(text: str) -> str:
    text = re.sub(r"^İş Kanunu\s+Madde\s+\d+\s*:\s*", "", text)
    text = re.sub(r"^İş Kanunu\s+Ek Madde\s+\d+\s*:\s*", "", text)
    text = re.sub(r"^İş Kanunu\s+Geçici Madde\s+\d+\s*:\s*", "", text)
    return text.strip()


def expected_prefix(item: dict) -> str:
    tip = item["madde_tipi"]
    no = item["madde_no"]
    if tip == "madde":
        return f"İş Kanunu Madde {no}: "
    if tip == "ek":
        return f"İş Kanunu Ek Madde {no}: "
    if tip == "gecici":
        return f"İş Kanunu Geçici Madde {no}: "
    return ""


def main():
    data = load_data(JSON_FILE)

    print(f"Toplam kayıt: {len(data)}")

    tip_counter = Counter(item.get("madde_tipi", "?") for item in data)
    print("Tip dağılımı:", dict(tip_counter))
    print()

    # 1) duplicate kontrol
    seen = Counter((item.get("madde_tipi"), item.get("madde_no")) for item in data)
    duplicates = [k for k, v in seen.items() if v > 1]

    print("=== DUPLICATE KAYITLAR ===")
    if duplicates:
        for d in duplicates:
            print(d)
    else:
        print("Yok")
    print()

    # 2) eksik / fazla numara kontrolü
    mevcut = {"madde": set(), "ek": set(), "gecici": set()}
    for item in data:
        tip = item.get("madde_tipi")
        no = str(item.get("madde_no"))
        if tip in mevcut:
            mevcut[tip].add(no)

    print("=== EKSİK NUMARALAR ===")
    for tip in ["madde", "ek", "gecici"]:
        missing = sorted(EXPECTED[tip] - mevcut[tip], key=lambda x: int(x))
        print(f"{tip}: {missing if missing else 'Yok'}")
    print()

    print("=== BEKLENMEYEN / FAZLA NUMARALAR ===")
    for tip in ["madde", "ek", "gecici"]:
        extra = sorted(mevcut[tip] - EXPECTED[tip], key=lambda x: int(x))
        print(f"{tip}: {extra if extra else 'Yok'}")
    print()

    # 3) prefix kontrol
    print("=== PREFIX HATASI ===")
    prefix_errors = []
    for item in data:
        expected = expected_prefix(item)
        icerik = item.get("icerik", "")
        if expected and not icerik.startswith(expected):
            prefix_errors.append((item["madde_tipi"], item["madde_no"], icerik[:150]))

    if prefix_errors:
        for row in prefix_errors:
            print(row)
    else:
        print("Yok")
    print()

    # 4) şüpheli kısa kayıtlar
    print(f"=== ŞÜPHELİ KISA KAYITLAR (<{SHORT_LIMIT}) ===")
    short_items = []
    for item in data:
        body = strip_prefix(item.get("icerik", ""))
        if len(body) < SHORT_LIMIT:
            short_items.append((item["madde_tipi"], item["madde_no"], body[:200]))

    if short_items:
        for row in short_items:
            print(f"{row[0]} {row[1]} -> {row[2]}")
    else:
        print("Yok")
    print()

    # 5) başlık / bölüm / sonraki madde sızıntısı
    print("=== YAPI BOZAN METİN SIZINTILARI ===")
    leakage_found = False
    for item in data:
        body = strip_prefix(item.get("icerik", ""))

        matches = []
        for pat in BAD_PATTERNS:
            if re.search(pat, body):
                matches.append(pat)

        if matches:
            leakage_found = True
            print(f"{item['madde_tipi']} {item['madde_no']} -> {body[:250]}")
            print("  eşleşmeler:", matches[:5])

    if not leakage_found:
        print("Yok")
    print()

    # 6) tip-no sıralama kontrolü
    print("=== SIRALAMA KONTROLÜ ===")
    current_order = [(x["madde_tipi"], int(x["madde_no"])) for x in data]
    desired_order = sorted(
        current_order,
        key=lambda z: {"madde": 0, "ek": 1, "gecici": 2}.get(z[0], 9) * 1000 + z[1]
    )

    if current_order == desired_order:
        print("Sıralama doğru")
    else:
        print("Sıralama bozuk")
    print()

    # 7) genel kalite özeti
    print("=== KALİTE ÖZETİ ===")
    print(f"Duplicate sayısı: {len(duplicates)}")
    print(f"Kısa kayıt sayısı: {len(short_items)}")
    print(f"Prefix hatası: {len(prefix_errors)}")

    total_missing = 0
    for tip in ["madde", "ek", "gecici"]:
        total_missing += len(EXPECTED[tip] - mevcut[tip])
    print(f"Toplam eksik kayıt: {total_missing}")


if __name__ == "__main__":
    main()