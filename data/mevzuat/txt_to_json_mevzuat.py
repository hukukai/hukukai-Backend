import re
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MEVZUAT_DIR = BASE_DIR

KANUN_ADLARI = {
    "4857": "İş Kanunu",
    "5237": "Türk Ceza Kanunu",
    "6098": "Türk Borçlar Kanunu",
    "6100": "Hukuk Muhakemeleri Kanunu",
}

# 1, 12, 123/A, 183/A, 305/A gibi madde numaralarını destekler
MADDE_NO_PATTERN = r"(\d+(?:/[A-Z])?)"

# Satır başındaki BOM / görünmez karakterleri tolere etmek için ^ öncesine opsiyonel boşluk ekledik
MADDE_RE = re.compile(
    rf"^\s*madde\s+{MADDE_NO_PATTERN}(?:\s*[-–—]\s*|\s+)(.*)$",
    re.IGNORECASE,
)
EK_RE = re.compile(
    rf"^\s*ek\s+madde\s+{MADDE_NO_PATTERN}(?:\s*[-–—]\s*|\s+)(.*)$",
    re.IGNORECASE,
)
GECICI_RE = re.compile(
    rf"^\s*geçici\s+madde\s+{MADDE_NO_PATTERN}(?:\s*[-–—]\s*|\s+)(.*)$",
    re.IGNORECASE,
)


def normalize(line: str) -> str:
    if line is None:
        return ""
    line = line.replace("\ufeff", "")  # BOM temizle
    line = line.replace("\xa0", " ")
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def parse_txt(path: Path, kanun_no: str, kanun_adi: str):
    # utf-8-sig ile açarak dosya başındaki BOM yüzünden ilk madde kaçmasını önlüyoruz
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    maddeler = []

    current_type = None
    current_no = None
    buffer = []

    def flush():
        nonlocal buffer, current_no, current_type

        if current_no is None or current_type is None:
            return

        text = " ".join(buffer).strip()
        text = normalize(text)

        if not text:
            buffer = []
            current_no = None
            current_type = None
            return

        prefix = {
            "madde": f"{kanun_adi} Madde {current_no}: ",
            "ek": f"{kanun_adi} Ek Madde {current_no}: ",
            "gecici": f"{kanun_adi} Geçici Madde {current_no}: ",
        }[current_type]

        maddeler.append(
            {
                "kanun_no": kanun_no,
                "kanun_adi": kanun_adi,
                "madde_no": str(current_no),
                "madde_tipi": current_type,
                "icerik": prefix + text,
            }
        )

        buffer = []
        current_no = None
        current_type = None

    for raw in lines:
        line = normalize(raw)

        if not line:
            continue

        m = MADDE_RE.match(line)
        if m:
            flush()
            current_type = "madde"
            current_no = m.group(1)
            first_part = normalize(m.group(2))
            buffer = [first_part] if first_part else []
            continue

        m = EK_RE.match(line)
        if m:
            flush()
            current_type = "ek"
            current_no = m.group(1)
            first_part = normalize(m.group(2))
            buffer = [first_part] if first_part else []
            continue

        m = GECICI_RE.match(line)
        if m:
            flush()
            current_type = "gecici"
            current_no = m.group(1)
            first_part = normalize(m.group(2))
            buffer = [first_part] if first_part else []
            continue

        if current_no is not None:
            buffer.append(line)

    flush()
    return maddeler


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python txt_to_json_mevzuat.py 4857_is_kanunu")
        return

    klasor = sys.argv[1]
    folder = MEVZUAT_DIR / klasor

    if not folder.exists():
        raise FileNotFoundError(f"Klasör bulunamadı: {folder}")

    txt_files = list(folder.glob("*_raw.txt"))
    if not txt_files:
        raise FileNotFoundError(
            f"Raw txt bulunamadı. Beklenen örnek ad: {folder / '4857_raw.txt'}"
        )

    txt_file = txt_files[0]

    kanun_no = klasor.split("_")[0]
    kanun_adi = KANUN_ADLARI.get(kanun_no, " ".join(klasor.split("_")[1:]))

    maddeler = parse_txt(txt_file, kanun_no, kanun_adi)

    out_path = folder / f"{kanun_no}_preview.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(maddeler, f, ensure_ascii=False, indent=2)

    print("TXT dosyası:", txt_file)
    print("Toplam madde:", len(maddeler))
    print("JSON yazıldı:", out_path)


if __name__ == "__main__":
    main()