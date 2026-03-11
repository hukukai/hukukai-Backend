# validate_mevzuat.py

import os
import re
import json
from typing import List, Dict

PARSED_DIR = "parsed_mevzuat"
REPORT_PATH = os.path.join(PARSED_DIR, "_validation_report.txt")


def load_json_files() -> List[str]:
    if not os.path.exists(PARSED_DIR):
        return []
    return sorted(
        [
            os.path.join(PARSED_DIR, f)
            for f in os.listdir(PARSED_DIR)
            if f.endswith(".json")
        ]
    )


def detect_suspicious(item: Dict) -> List[str]:
    reasons = []
    text = item.get("icerik", "")

    if len(text) < 80:
        reasons.append("çok kısa")

    if re.search(r"\bMadde\s+\d+\s*\(Mülga", text, flags=re.IGNORECASE):
        reasons.append("başlık bozukluğu olası")

    if re.search(r"\bEk\s+Madde\b", text, flags=re.IGNORECASE) and item["madde_tipi"] == "madde":
        reasons.append("ek madde sızıntısı")

    if re.search(r"\bGeçici\s+Madde\b", text, flags=re.IGNORECASE) and item["madde_tipi"] == "madde":
        reasons.append("geçici madde sızıntısı")

    if re.search(r"ibaresi .*? değiştirilmiştir", text, flags=re.IGNORECASE):
        reasons.append("değişiklik dipnotu sızıntısı")

    if re.search(r"madde metninden çıkarılmıştır", text, flags=re.IGNORECASE):
        reasons.append("dipnot sızıntısı")

    if re.search(r"yürürlükten kaldırılmıştır", text, flags=re.IGNORECASE):
        reasons.append("dipnot sızıntısı")

    if re.search(r"Anayasa Mahkemesinin .*? Kararı ile", text, flags=re.IGNORECASE):
        reasons.append("karar dipnotu sızıntısı")

    return reasons


def validate_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return f"\n=== {os.path.basename(path)} ===\nBoş dosya.\n"

    kanun_adi = data[0].get("kanun_adi", "?")
    kanun_no = data[0].get("kanun_no", "?")

    ana = [m for m in data if m["madde_tipi"] == "madde"]
    ek = [m for m in data if m["madde_tipi"] == "ek"]
    gecici = [m for m in data if m["madde_tipi"] == "gecici"]

    report = []
    report.append(f"\n=== {kanun_no} - {kanun_adi} ===")
    report.append(f"Toplam kayıt: {len(data)}")
    report.append(f"Ana madde: {len(ana)}")
    report.append(f"Ek madde: {len(ek)}")
    report.append(f"Geçici madde: {len(gecici)}")

    # Duplicate kontrol
    seen = set()
    dupes = []
    for item in data:
        key = (item["madde_tipi"], item["madde_no"])
        if key in seen:
            dupes.append(key)
        seen.add(key)

    if dupes:
        report.append(f"Duplicate kayıtlar: {dupes}")
    else:
        report.append("Duplicate kayıt: yok")

    # Sıra kontrol
    def sorted_nos(items: List[Dict]) -> List[int]:
        nums = []
        for x in items:
            try:
                nums.append(int(x["madde_no"]))
            except Exception:
                pass
        return sorted(nums)

    ana_nolar = sorted_nos(ana)
    if ana_nolar:
        expected_min = min(ana_nolar)
        expected_max = max(ana_nolar)
        expected = set(range(expected_min, expected_max + 1))
        missing = sorted(expected - set(ana_nolar))
        report.append(f"Eksik ana madde no: {missing if missing else 'yok'}")
    else:
        report.append("Ana madde yok")

    # Şüpheli kayıtlar
    suspicious = []
    for item in data:
        reasons = detect_suspicious(item)
        if reasons:
            suspicious.append((item["madde_tipi"], item["madde_no"], reasons, item["icerik"][:220]))

    if suspicious:
        report.append("\nŞüpheli kayıtlar:")
        for tip, no, reasons, preview in suspicious[:40]:
            report.append(f"- {tip} {no} | {', '.join(reasons)}")
            report.append(f"  {preview}")
    else:
        report.append("\nŞüpheli kayıt: yok")

    return "\n".join(report) + "\n"


def main():
    files = load_json_files()
    if not files:
        print("parsed_mevzuat altında JSON bulunamadı.")
        return

    full_report = []
    for path in files:
        full_report.append(validate_file(path))

    text = "\n".join(full_report)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print(text)
    print(f"\nRapor kaydedildi: {REPORT_PATH}")


if __name__ == "__main__":
    main()