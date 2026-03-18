import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

BASE_DIR = Path(__file__).resolve().parent
MEVZUAT_DIR = BASE_DIR

EXPECTED_MAP = {
    # 4857 İş Kanunu
    "4857": {
        "madde": [str(i) for i in range(1, 123)],
        "ek": ["1", "2", "3"],
        "gecici": [str(i) for i in range(1, 13)],
    },

    # 5237 Türk Ceza Kanunu
    "5237": {
        "madde": (
                [str(i) for i in range(1, 124)]
                + ["123/A"]
                + [str(i) for i in range(124, 218)]
                + ["217/A"]
                + [str(i) for i in range(218, 245)]
                + ["245/A"]
                + [str(i) for i in range(246, 346)]
        ),
        "ek": [],
        "gecici": ["1"],
    },

    # 6098 Türk Borçlar Kanunu
    "6098": {
        "madde": [str(i) for i in range(1, 650)],
        "ek": [],
        "gecici": ["1", "2"],
    },

    # 6100 Hukuk Muhakemeleri Kanunu
    "6100": {
        "madde": (
                [str(i) for i in range(1, 184)]
                + ["183/A"]
                + [str(i) for i in range(184, 306)]
                + ["305/A"]
                + [str(i) for i in range(306, 453)]
        ),
        "ek": ["1"],
        "gecici": ["1", "2", "3", "4"],
    },

    # 4721 Türk Medeni Kanunu
    "4721": {
        "madde": [str(i) for i in range(1, 1031)],
        "ek": [],
        "gecici": ["1"],
    },

    # 7036 İMK
    "7036": {
        "madde": [str(i) for i in range(1, 40)],
        "gecici": ["1"],
        "ek": []
    },

    # 6325 huak
    "6325": {
        "madde": [
            "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
            "11", "12", "13", "14", "15", "16", "17", "17/A", "17/B",
            "18", "18/A", "18/B", "19", "20", "21", "22", "23", "24",
            "25", "26", "27", "28", "29", "30", "31", "32", "33", "34",
            "35", "36", "37", "38"
        ],
        "ek": [],
        "gecici": ["1", "2", "3"],
    },

    # 2577 iyuk
    "2577": {
        "madde": (
                [str(i) for i in range(1, 21)]
                + ["20/A", "20/B", "20/C"]
                + [str(i) for i in range(21, 66)]
        ),
        "ek": ["1", "2", "3"],
        "gecici": [str(i) for i in range(1, 12)],
    },

    # 7201 Tebligat Kanunu
    "7201": {
        "madde": (
                [str(i) for i in range(1, 7)]
                + ["7", "7/a"]
                + [str(i) for i in range(8, 25)]
                + ["25", "25/a"]
                + ["26", "26/A"]
                + [str(i) for i in range(27, 65)]
        ),
        "ek": ["1", "2"],
        "gecici": ["1", "2"],
    },

    # 6502 tüketici hakları
    "6502": {
        "madde": (
                [str(i) for i in range(1, 48)]
                + ["47/A"]
                + [str(i) for i in range(48, 58)]
                + ["57/A"]
                + [str(i) for i in range(58, 74)]
                + ["73/A"]
                + [str(i) for i in range(74, 78)]
                + ["77/A"]
                + [str(i) for i in range(78, 89)]
        ),
        "ek": [],
        "gecici": ["1", "2", "3"],
    },
    # 1136 Avukatlık Kanunu
    "1136": {
        "madde": (
                [str(i) for i in range(1, 28)]
                + ["27/A"]
                + [str(i) for i in range(28, 36)]
                + ["35/A"]
                + [str(i) for i in range(36, 202)]
        ),
        "ek": ["1", "2", "3", "4"],
        "gecici": [str(i) for i in range(1, 26)],
        "ek_gecici": ["1"],
    },
    # 6183 AATUHK
    "6183": {
        "madde": (
                [str(i) for i in range(1, 23)]
                + ["22/A"]
                + [str(i) for i in range(23, 36)]
                + ["36", "36/A"]
                + [str(i) for i in range(37, 49)]
                + ["48/A"]
                + [str(i) for i in range(49, 75)]
                + ["74/A"]
                + [str(i) for i in range(75, 98)]
                + ["97/A"]
                + [str(i) for i in range(98, 119)]
        ),
        "mukerrer_madde": ["35"],
        "ek": ["1"],
        "gecici": [str(i) for i in range(1, 10)],
    },
    # 2576 BİM / İdare / Vergi Mahkemeleri Kuruluş Kanunu
    "2576": {
        "madde": [
            "1", "2", "3",
            "3/A", "3/B", "3/C", "3/D", "3/E", "3/F", "3/G", "3/H", "3/I",
            "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17"
        ],
        "ek": ["1"],
        "gecici": [str(i) for i in range(1, 22)],
    },

    # 6102 Türk Ticaret Kanunu
    "6102": {
        "madde": (
                [str(i) for i in range(1, 6)]
                + ["5/A"]
                + [str(i) for i in range(6, 1536)]
        ),
        "ek": [],
        "gecici": [str(i) for i in range(1, 16)],
    },

    # 4733 Tütün, Tütün Mamulleri ve Alkol Piyasasının Düzenlenmesine Dair Kanun
    "4733": {
        "madde": [
            "1", "2", "3", "4", "4/A", "4/B",
            "5", "6", "7", "8", "8/A", "8/B",
            "9", "10", "11", "12"
        ],
        "ek": ["1", "2", "3", "4"],
        "gecici": [str(i) for i in range(1, 10)],
    },

    #6698 KVKK
    "6698": {
        "madde": [str(i) for i in range(1, 34)],
        "gecici": ["1", "2", "3"]
    },
}

HEADING_PATTERNS = [
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
    r"\bONBİRİNCİ BÖLÜM\b",
    r"\bONİKİNCİ BÖLÜM\b",
    r"\bGenel Hükümler\b",
    r"\bİşin Düzenlenmesi\b",
    r"\bİş Sağlığı ve Güvenliği\b",
    r"\bÇalışma Hayatının Denetimi ve Teftişi\b",
    r"\bİdari Ceza Hükümleri\b",
    r"\bÇeşitli, Geçici ve Son Hükümler\b",
    r"\bVekâlet İlişkileri\b",
    r"\bVekâlet Sözleşmesi\b",
    r"\bKefalet Sözleşmesi\b",
    r"\bHizmet Sözleşmesi\b",
    r"\bKira Sözleşmesi\b",
    r"\bSatış Sözleşmesi\b",
]


def normalize_text(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def get_expected_numbers(kanun_no: str):
    return EXPECTED_MAP.get(kanun_no, {})


def madde_sort_key(value: str):
    """
    1, 2, 183/A, 217/A, 245/A gibi madde numaralarını sıralamak için.
    """
    value = str(value).strip().upper()
    m = re.fullmatch(r"(\d+)(?:\s*/\s*([A-Z]))?", value)
    if m:
        base = int(m.group(1))
        suffix = m.group(2) or ""
        return (base, suffix)
    return (10 ** 9, value)


def get_expected_prefix(kanun_adi: str, madde_tipi: str, madde_no: str) -> str | None:
    return {
        "madde": f"{kanun_adi} Madde {madde_no}: ",
        "mukerrer_madde": f"{kanun_adi} Mükerrer Madde {madde_no}: ",
        "ek": f"{kanun_adi} Ek Madde {madde_no}: ",
        "mukerrer_ek": f"{kanun_adi} Mükerrer Ek Madde {madde_no}: ",
        "gecici": f"{kanun_adi} Geçici Madde {madde_no}: ",
        "ek_gecici": f"{kanun_adi} Ek Geçici Madde {madde_no}: ",
    }.get(madde_tipi)


def looks_like_article_start(text: str) -> bool:
    if re.search(r"\bMadde\s+\d+\s*-\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bEk\s+Madde\s+\d+\s*-\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bGeçici\s+Madde\s+\d+\s*-\b", text, re.IGNORECASE):
        return True
    if re.search(r"\bEk\s+Geçici\s+Madde\s+\d+\s*-\b", text, re.IGNORECASE):
        return True
    return False


def detect_heading_leaks(content_only: str):
    matched = []

    text = (content_only or "").replace("\r\n", "\n").replace("\r", "\n")

    # 1) Güçlü patternler: bölüm başlıkları / çok spesifik başlıklar
    for pat in HEADING_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            matched.append(pat)

    # 2) Satır bazlı kısa heading kontrolü
    # Tek kelime heading’leri sadece tek başına satırsa yakala
    suspicious_heading_lines = {
        "amaç",
        "kapsam",
        "tanımlar",
        "istisnalar",
        "ücret",
        "yürürlük",
        "yürütme",
    }

    for line in text.split("\n"):
        line_norm = normalize_text(line).casefold()
        if not line_norm:
            continue

        if line_norm in suspicious_heading_lines:
            matched.append(f"LINE_HEADING::{line_norm}")

    # duplicate temizle
    deduped = []
    seen = set()
    for m in matched:
        if m in seen:
            continue
        seen.add(m)
        deduped.append(m)

    return deduped


def build_summary_status(
        duplicates,
        prefix_errors,
        short_records,
        leaks,
        total_missing,
        ordering_errors,
        embedded_article_markers,
):
    errors = 0
    warnings = 0

    errors += len(duplicates)
    errors += len(prefix_errors)
    errors += total_missing
    errors += len(ordering_errors)
    errors += len(embedded_article_markers)

    warnings += len(short_records)
    warnings += len(leaks)

    if errors == 0 and warnings == 0:
        return "PASS"

    if errors == 0 and warnings > 0:
        return "PASS_WITH_WARNINGS"

    return "FAIL"


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python validate_mevzuat_json.py 4857_is_kanunu")
        return

    klasor = sys.argv[1]
    folder = MEVZUAT_DIR / klasor

    if not folder.exists():
        print(f"Klasör bulunamadı: {folder}")
        return

    json_files = list(folder.glob("*_preview.json"))
    if not json_files:
        print("Preview JSON bulunamadı.")
        return

    json_file = json_files[0]

    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"JSON okunamadı: {e}")
        return

    if not isinstance(data, list):
        print("JSON liste formatında değil.")
        return

    if not data:
        print("JSON boş.")
        return

    print(f"Dosya: {json_file.name}")
    print(f"Toplam kayıt: {len(data)}")

    type_counter = Counter()
    duplicates = []
    seen = set()
    numbers_by_type = defaultdict(list)
    short_records = []
    prefix_errors = []
    leaks = []
    ordering_errors = []
    embedded_article_markers = []
    empty_content_records = []

    kanun_no = str(data[0].get("kanun_no", "")).strip() if data else ""
    kanun_adi = str(data[0].get("kanun_adi", "")).strip() if data else ""
    expected_map = get_expected_numbers(kanun_no)

    for row in data:
        row_kanun_no = str(row.get("kanun_no", "")).strip()
        row_kanun_adi = str(row.get("kanun_adi", "")).strip()
        madde_no = str(row.get("madde_no", "")).strip()
        madde_tipi = str(row.get("madde_tipi", "")).strip()
        icerik = normalize_text(str(row.get("icerik", "")))

        type_counter[madde_tipi] += 1

        key = (madde_tipi, madde_no)
        if key in seen:
            duplicates.append(key)
        seen.add(key)

        if madde_no:
            numbers_by_type[madde_tipi].append(madde_no)

        expected_prefix = get_expected_prefix(row_kanun_adi, madde_tipi, madde_no)

        if expected_prefix and not icerik.startswith(expected_prefix):
            prefix_errors.append((madde_tipi, madde_no, icerik[:180]))

        content_only = (
            icerik[len(expected_prefix):].strip()
            if expected_prefix and icerik.startswith(expected_prefix)
            else icerik
        )

        if not content_only:
            empty_content_records.append((madde_tipi, madde_no))

        if len(content_only) < 120:
            short_records.append((madde_tipi, madde_no, content_only[:180]))

        matched = detect_heading_leaks(content_only)
        if matched:
            leaks.append((madde_tipi, madde_no, content_only[:260], matched))

        if looks_like_article_start(content_only):
            embedded_article_markers.append((madde_tipi, madde_no, content_only[:220]))

        if row_kanun_no != kanun_no:
            print(
                f"UYARI: Karışık kanun_no bulundu -> beklenen {kanun_no}, satırda {row_kanun_no} "
                f"({madde_tipi} {madde_no})"
            )

        if row_kanun_adi != kanun_adi:
            print(
                f"UYARI: Karışık kanun_adi bulundu -> beklenen {kanun_adi}, satırda {row_kanun_adi} "
                f"({madde_tipi} {madde_no})"
            )

    print("Tip dağılımı:", dict(type_counter))

    print("\n=== DUPLICATE KAYITLAR ===")
    if duplicates:
        for d in duplicates:
            print(d)
    else:
        print("Yok")

    print("\n=== EKSİK NUMARALAR ===")
    total_missing = 0
    for t in ["madde", "mukerrer_madde", "ek", "mukerrer_ek", "gecici", "ek_gecici"]:
        expected = set(expected_map.get(t, []))
        mevcut = set(numbers_by_type.get(t, []))
        missing = sorted(expected - mevcut, key=madde_sort_key)
        total_missing += len(missing)

        if expected:
            print(f"{t}: {missing if missing else 'Yok'}")
        else:
            print(f"{t}: Beklenen map yok / kontrol dışı")

    print("\n=== BEKLENMEYEN / FAZLA NUMARALAR ===")
    for t in ["madde", "mukerrer_madde", "ek", "mukerrer_ek", "gecici", "ek_gecici"]:
        expected = set(expected_map.get(t, []))
        mevcut = set(numbers_by_type.get(t, []))

        if expected:
            extras = sorted(mevcut - expected, key=madde_sort_key)
            print(f"{t}: {extras if extras else 'Yok'}")
        else:
            extras = sorted(mevcut, key=madde_sort_key)
            print(f"{t}: expected_map tanımlı değil, mevcut -> {extras if extras else 'Yok'}")

    print("\n=== PREFIX HATASI ===")
    if prefix_errors:
        for tip, no, preview in prefix_errors:
            print(f"{tip} {no} -> {preview}")
    else:
        print("Yok")

    print("\n=== BOŞ / İÇERİKSİZ KAYITLAR ===")
    if empty_content_records:
        for tip, no in empty_content_records:
            print(f"{tip} {no}")
    else:
        print("Yok")

    print("\n=== ŞÜPHELİ KISA KAYITLAR (<120) ===")
    if short_records:
        for tip, no, preview in short_records:
            print(f"{tip} {no} -> {preview}")
    else:
        print("Yok")

    print("\n=== YAPI BOZAN METİN SIZINTILARI ===")
    if leaks:
        for tip, no, preview, matched in leaks:
            print(f"{tip} {no} -> {preview}")
            print("  eşleşmeler:", matched)
    else:
        print("Yok")

    print("\n=== MADDE İÇİNE GÖMÜLÜ MADDE BAŞLANGICI ŞÜPHESİ ===")
    if embedded_article_markers:
        for tip, no, preview in embedded_article_markers:
            print(f"{tip} {no} -> {preview}")
    else:
        print("Yok")

    print("\n=== SIRALAMA KONTROLÜ ===")
    for t in ["madde", "mukerrer_madde", "ek", "mukerrer_ek", "gecici", "ek_gecici"]:
        nums = numbers_by_type.get(t, [])
        if nums:
            sorted_nums = sorted(nums, key=madde_sort_key)
            if nums == sorted_nums:
                print(f"{t}: Sıralama doğru")
            else:
                ordering_errors.append((t, nums, sorted_nums))
                print(f"{t}: Sıralama bozuk")
                print("  mevcut :", nums)
                print("  olması :", sorted_nums)
        else:
            print(f"{t}: Kayıt yok")

    status = build_summary_status(
        duplicates=duplicates,
        prefix_errors=prefix_errors,
        short_records=short_records,
        leaks=leaks,
        total_missing=total_missing,
        ordering_errors=ordering_errors,
        embedded_article_markers=embedded_article_markers,
    )

    print("\n=== KALİTE ÖZETİ ===")
    print("Kanun no:", kanun_no)
    print("Kanun adı:", kanun_adi)
    print("Duplicate sayısı:", len(duplicates))
    print("Prefix hatası:", len(prefix_errors))
    print("Boş kayıt sayısı:", len(empty_content_records))
    print("Kısa kayıt sayısı:", len(short_records))
    print("Heading leak sayısı:", len(leaks))
    print("Madde içi yeni madde başlangıcı şüphesi:", len(embedded_article_markers))
    print("Toplam eksik kayıt:", total_missing)
    print("Sıralama hatası:", len(ordering_errors))
    print("SONUÇ:", status)


if __name__ == "__main__":
    main()
