import re
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
YONETMELIK_DIR = BASE_DIR

# 1, 12, 123/A gibi numaraları destekle
MADDE_NO_PATTERN = r"(\d+(?:/[A-Z])?)"

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
EK_GECICI_RE = re.compile(
    rf"^\s*ek\s+geçici\s+madde\s+{MADDE_NO_PATTERN}(?:\s*[-–—]\s*|\s+)(.*)$",
    re.IGNORECASE,
)

# Yönetmeliklerde mükerrer çok nadir ama güvenli olsun
MUKERRER_RE = re.compile(
    r"^\s*mükerrer\s+madde\s+(\d+)(?:\s*[-–—]\s*|\s+)(.*)$",
    re.IGNORECASE,
)
MUKERRER_EK_RE = re.compile(
    r"^\s*mükerrer\s+ek\s+madde\s+(\d+)(?:\s*[-–—]\s*|\s+)(.*)$",
    re.IGNORECASE,
)


def normalize(line: str) -> str:
    if line is None:
        return ""

    # BOM / görünmez karakter / NBSP temizliği
    line = line.replace("\ufeff", "")
    line = line.replace("\u200b", "")
    line = line.replace("\xa0", " ")

    # tireleri normalize et
    line = line.replace("‐", "-")
    line = line.replace("-", "-")
    line = line.replace("‒", "-")
    line = line.replace("–", "–")
    line = line.replace("—", "—")

    # fazla boşlukları toparla
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def load_meta(folder: Path) -> dict:
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"meta.json bulunamadı: {meta_path}")

    with open(meta_path, "r", encoding="utf-8-sig") as f:
        meta = json.load(f)

    required = ["bagli_kanun_no", "yonetmelik_adi", "source_type"]
    for key in required:
        if not meta.get(key):
            raise ValueError(f"meta.json içinde eksik alan: {key}")

    return meta


def parse_txt(path: Path, meta: dict) -> list[dict]:
    # utf-8-sig ile aç: dosya başındaki BOM ilk maddeyi bozmasın
    lines = path.read_text(encoding="utf-8-sig").splitlines()

    maddeler = []
    current_type = None
    current_no = None
    buffer = []

    bagli_kanun_no = str(meta["bagli_kanun_no"])
    yonetmelik_adi = str(meta["yonetmelik_adi"])
    source_type = str(meta["source_type"])

    def flush():
        nonlocal current_type, current_no, buffer

        if current_type is None or current_no is None:
            return

        text = " ".join(buffer).strip()
        text = normalize(text)

        if not text:
            current_type = None
            current_no = None
            buffer = []
            return

        prefix = {
            "madde": f"{yonetmelik_adi} Madde {current_no}: ",
            "ek": f"{yonetmelik_adi} Ek Madde {current_no}: ",
            "gecici": f"{yonetmelik_adi} Geçici Madde {current_no}: ",
            "ek_gecici": f"{yonetmelik_adi} Ek Geçici Madde {current_no}: ",
            "mukerrer_madde": f"{yonetmelik_adi} Mükerrer Madde {current_no}: ",
            "mukerrer_ek": f"{yonetmelik_adi} Mükerrer Ek Madde {current_no}: ",
        }[current_type]

        maddeler.append(
            {
                "bagli_kanun_no": bagli_kanun_no,
                "yonetmelik_adi": yonetmelik_adi,
                "madde_no": str(current_no),
                "madde_tipi": current_type,
                "icerik": prefix + text,
                "structured_content": None,
                "source_type": source_type,
            }
        )

        current_type = None
        current_no = None
        buffer = []

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

        m = EK_GECICI_RE.match(line)
        if m:
            flush()
            current_type = "ek_gecici"
            current_no = m.group(1)
            first_part = normalize(m.group(2))
            buffer = [first_part] if first_part else []
            continue

        m = MUKERRER_RE.match(line)
        if m:
            flush()
            current_type = "mukerrer_madde"
            current_no = m.group(1)
            first_part = normalize(m.group(2))
            buffer = [first_part] if first_part else []
            continue

        m = MUKERRER_EK_RE.match(line)
        if m:
            flush()
            current_type = "mukerrer_ek"
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
        print("Kullanım: python txt_to_json_yonetmelik.py 6698_verbis_ym")
        return

    klasor = sys.argv[1]
    folder = YONETMELIK_DIR / klasor

    if not folder.exists():
        raise FileNotFoundError(f"Klasör bulunamadı: {folder}")

    meta = load_meta(folder)

    txt_files = list(folder.glob("*_raw.txt"))
    if not txt_files:
        raise FileNotFoundError(
            f"Raw txt bulunamadı. Beklenen örnek ad: {folder / '6698_verbis_raw.txt'}"
        )

    txt_file = txt_files[0]
    maddeler = parse_txt(txt_file, meta)

    # preview çıktısı
    bagli_kanun_no = str(meta["bagli_kanun_no"])
    out_path = folder / f"{bagli_kanun_no}_yonetmelik_preview.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(maddeler, f, ensure_ascii=False, indent=2)

    print("TXT dosyası:", txt_file)
    print("Toplam madde:", len(maddeler))
    print("JSON yazıldı:", out_path)


if __name__ == "__main__":
    main()