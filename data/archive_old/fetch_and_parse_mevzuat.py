# fetch_and_parse_mevzuat.py

import os
import re
import json
import requests
import fitz
from typing import List, Dict, Optional

from sources import KANUNLAR, KANUN_PDF_VERSIYON, LOCAL_PDF_MAP


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

OUTPUT_DIR = "parsed_mevzuat"
PDF_CACHE_DIR = "pdf_cache"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PDF_CACHE_DIR, exist_ok=True)


MADDE_RE = re.compile(r"^(?:MADDE|Madde)\s+(\d+)\s*[-–—]\s*(.*)$", re.IGNORECASE)
EK_MADDE_RE = re.compile(r"^(?:EK|Ek)\s+MADDE\s+(\d+)\s*[-–—]\s*(.*)$", re.IGNORECASE)
GECICI_MADDE_RE = re.compile(r"^(?:GEÇİCİ|Geçici)\s+MADDE\s+(\d+)\s*[-–—]\s*(.*)$", re.IGNORECASE)

BOLUM_RE = re.compile(
    r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|ONBİRİNCİ|ONİKİNCİ)\s+BÖLÜM$",
    re.IGNORECASE,
)

KISIM_RE = re.compile(
    r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|ONBİRİNCİ|ONİKİNCİ)\s+KISIM$",
    re.IGNORECASE,
)

AYIRICI_BASLIK_RE = re.compile(
    r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|ONBİRİNCİ|ONİKİNCİ)\s+AYIRIM$",
    re.IGNORECASE,
)

KANUN_EK_LISTE_RE = re.compile(
    r"^.+ SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN",
    re.IGNORECASE,
)

DIPNOT_LINE_RE = re.compile(r"^\d+\s")
ALL_CAPS_LINE_RE = re.compile(r"^[A-ZÇĞİÖŞÜ0-9\s\.\-–—()/:,;]+$")

# Sayfa altı dipnot / değişiklik cümleleri için güçlü filtreler
CHANGE_GARBAGE_PATTERNS = [
    r"ibaresi .*? şeklinde değiştirilmiştir",
    r"ibaresinden sonra gelmek üzere .*? eklenmiştir",
    r"madde metninden çıkarılmıştır",
    r"madde metninden çıkartılmıştır",
    r"yürürlükten kaldırılmıştır",
    r"iptal edilmiştir",
    r"mülga",
    r"verilmiş yetkiye",
    r"cumhurbaşkanlığı kararnamesine",
    r"anayasa mahkemesinin .*? kararı ile",
]

CHANGE_GARBAGE_RE_LIST = [re.compile(p, re.IGNORECASE) for p in CHANGE_GARBAGE_PATTERNS]


def normalize_line(line: str) -> str:
    line = line.replace("\xa0", " ")
    line = line.replace("\u200b", "")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_probable_change_garbage(line: str) -> bool:
    s = normalize_line(line)
    if not s:
        return False

    for cre in CHANGE_GARBAGE_RE_LIST:
        if cre.search(s):
            return True

    # Çok kısa dipnot / tarih satırları
    if DIPNOT_LINE_RE.match(s) and len(s) < 120:
        return True

    if re.match(r"^\d+\s+\d{1,2}/\d{1,2}/\d{4}", s):
        return True

    if re.match(r"^\(?[A-ZÇĞİÖŞÜ]\)?$", s):
        return True

    return False


def is_structural_heading(line: str) -> bool:
    s = normalize_line(line)
    if not s:
        return False

    if BOLUM_RE.match(s) or KISIM_RE.match(s) or AYIRICI_BASLIK_RE.match(s):
        return True

    if KANUN_EK_LISTE_RE.match(s):
        return True

    # Genel bölüm başlıkları
    if ALL_CAPS_LINE_RE.match(s) and len(s.split()) <= 8:
        if not MADDE_RE.match(s) and not EK_MADDE_RE.match(s) and not GECICI_MADDE_RE.match(s):
            return True

    return False


def get_pdf_url(kanun_no: str) -> str:
    versiyon = KANUN_PDF_VERSIYON.get(kanun_no, "1.5")
    return f"https://www.mevzuat.gov.tr/MevzuatMetin/{versiyon}.{kanun_no}.pdf"


def get_pdf_path(kanun_no: str) -> str:
    local_path = LOCAL_PDF_MAP.get(kanun_no)
    if local_path and os.path.exists(local_path):
        print(f"  Lokal PDF kullanılıyor: {local_path}")
        return local_path

    pdf_path = os.path.join(PDF_CACHE_DIR, f"{kanun_no}.pdf")
    if os.path.exists(pdf_path):
        print(f"  Cache PDF kullanılıyor: {pdf_path}")
        return pdf_path

    url = get_pdf_url(kanun_no)
    print(f"  PDF indiriliyor: {url}")

    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"PDF indirilemedi. HTTP {r.status_code} - {url}")

    with open(pdf_path, "wb") as f:
        f.write(r.content)

    return pdf_path


def should_keep_block(x0, y0, x1, y1, text, page_width, page_height) -> bool:
    text = normalize_line(text)
    if not text:
        return False

    # Header / footer kaba temizleme
    if y0 < 40 or y1 > page_height - 40:
        return False

    block_width = x1 - x0
    if block_width < page_width * 0.28:
        return False

    if len(text) < 2:
        return False

    return True


def fetch_pdf_lines(kanun_no: str) -> List[str]:
    pdf_path = get_pdf_path(kanun_no)
    doc = fitz.open(pdf_path)
    lines: List[str] = []

    for page in doc:
        page_width = page.rect.width
        page_height = page.rect.height

        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

        for block in blocks:
            x0, y0, x1, y1, text, *_ = block

            if not should_keep_block(x0, y0, x1, y1, text, page_width, page_height):
                continue

            for raw_line in text.splitlines():
                line = normalize_line(raw_line)
                if line:
                    lines.append(line)

    doc.close()
    print(f"  {len(lines)} satır çıkarıldı")
    return lines


def clean_article_text(text: str) -> str:
    text = normalize_text(text)

    end_markers = [
        "KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN",
    ]
    for marker in end_markers:
        idx = text.upper().find(marker)
        if idx != -1:
            text = text[:idx].strip()

    # " Geçici " / " Ek " / " Madde " sonradan yapıştıysa onları düzeltmek için kaba temizlik
    text = re.sub(r"\s+", " ", text).strip()
    return text


def flush_current_article(
    maddeler: List[Dict],
    kanun_no: str,
    kanun_adi: str,
    current_type: Optional[str],
    current_no: Optional[str],
    current_lines: List[str],
) -> None:
    if current_type is None or current_no is None:
        return

    text = " ".join(current_lines).strip()
    text = clean_article_text(text)

    if not text:
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


def parse_maddeler_from_lines(lines: List[str], kanun_adi: str, kanun_no: str) -> List[Dict]:
    maddeler: List[Dict] = []

    current_type: Optional[str] = None
    current_no: Optional[str] = None
    current_lines: List[str] = []

    i = 0
    while i < len(lines):
        line = normalize_line(lines[i])
        next_line = normalize_line(lines[i + 1]) if i + 1 < len(lines) else ""

        if not line:
            i += 1
            continue

        if KANUN_EK_LISTE_RE.match(line):
            flush_current_article(maddeler, kanun_no, kanun_adi, current_type, current_no, current_lines)
            break

        # Önce madde başlangıçlarını yakala
        m = GECICI_MADDE_RE.match(line)
        if m:
            flush_current_article(maddeler, kanun_no, kanun_adi, current_type, current_no, current_lines)
            current_type = "gecici"
            current_no = m.group(1)
            current_lines = [m.group(2).strip()] if m.group(2).strip() else []
            i += 1
            continue

        m = EK_MADDE_RE.match(line)
        if m:
            flush_current_article(maddeler, kanun_no, kanun_adi, current_type, current_no, current_lines)
            current_type = "ek"
            current_no = m.group(1)
            current_lines = [m.group(2).strip()] if m.group(2).strip() else []
            i += 1
            continue

        m = MADDE_RE.match(line)
        if m:
            flush_current_article(maddeler, kanun_no, kanun_adi, current_type, current_no, current_lines)
            current_type = "madde"
            current_no = m.group(1)
            current_lines = [m.group(2).strip()] if m.group(2).strip() else []
            i += 1
            continue

        # Yapısal başlıklar
        if is_structural_heading(line):
            i += 1
            continue

        # Hemen sonraki satır yeni maddeyse bu satır başlık gürültüsüdür
        if MADDE_RE.match(next_line) or EK_MADDE_RE.match(next_line) or GECICI_MADDE_RE.match(next_line):
            i += 1
            continue

        # Dipnot / değişiklik gürültüsü
        if is_probable_change_garbage(line):
            i += 1
            continue

        # Tamamen büyük harf kısa satırlar
        if ALL_CAPS_LINE_RE.match(line) and len(line.split()) <= 6:
            i += 1
            continue

        if current_type is not None:
            current_lines.append(line)

        i += 1

    flush_current_article(maddeler, kanun_no, kanun_adi, current_type, current_no, current_lines)

    # Aynı madde geldiyse en uzunu tut
    uniq = {}
    for m in maddeler:
        key = (m["madde_tipi"], m["madde_no"])
        if key not in uniq or len(m["icerik"]) > len(uniq[key]["icerik"]):
            uniq[key] = m

    result = list(uniq.values())

    def sort_key(x):
        order = {"madde": 0, "ek": 1, "gecici": 2}
        try:
            no = int(x["madde_no"])
        except Exception:
            no = 999999
        return (order.get(x["madde_tipi"], 9), no)

    result.sort(key=sort_key)
    return result


def post_clean_articles(maddeler: List[Dict]) -> List[Dict]:
    cleaned = []

    for item in maddeler:
        text = item["icerik"]

        # Bir sonraki madde başlığı yanlış yapıştıysa kırp
        cut_patterns = [
            r"\s+Ek\s+Madde\s+\d+\s*[:\-–—]",
            r"\s+Geçici\s+Madde\s+\d+\s*[:\-–—]",
            r"\s+Madde\s+\d+\s*[:\-–—]",
        ]
        for pat in cut_patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m and m.start() > 30:
                text = text[:m.start()].strip()
                break

        text = normalize_text(text)
        item["icerik"] = text
        cleaned.append(item)

    return cleaned


def save_outputs(kanun_no: str, kanun_adi: str, maddeler: List[Dict]) -> None:
    json_path = os.path.join(OUTPUT_DIR, f"{kanun_no}.json")
    txt_path = os.path.join(OUTPUT_DIR, f"{kanun_no}.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(maddeler, f, ensure_ascii=False, indent=2)

    ana = [m for m in maddeler if m["madde_tipi"] == "madde"]
    ek = [m for m in maddeler if m["madde_tipi"] == "ek"]
    gecici = [m for m in maddeler if m["madde_tipi"] == "gecici"]

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Kanun: {kanun_adi}\n")
        f.write(f"Kanun No: {kanun_no}\n")
        f.write(f"Toplam kayıt: {len(maddeler)}\n")
        f.write(f"Ana madde: {len(ana)}\n")
        f.write(f"Ek madde: {len(ek)}\n")
        f.write(f"Geçici madde: {len(gecici)}\n\n")

        f.write("İLK 10 KAYIT\n")
        f.write("=" * 100 + "\n")
        for m in maddeler[:10]:
            f.write(f"{m['madde_tipi']} {m['madde_no']} | {m['icerik'][:800]}\n\n")

        f.write("\nSON 10 KAYIT\n")
        f.write("=" * 100 + "\n")
        for m in maddeler[-10:]:
            f.write(f"{m['madde_tipi']} {m['madde_no']} | {m['icerik'][:800]}\n\n")

    print(f"  Kaydedildi: {json_path}")
    print(f"  Kaydedildi: {txt_path}")


def print_summary(kanun_adi: str, maddeler: List[Dict]) -> None:
    ana = [m for m in maddeler if m["madde_tipi"] == "madde"]
    ek = [m for m in maddeler if m["madde_tipi"] == "ek"]
    gecici = [m for m in maddeler if m["madde_tipi"] == "gecici"]

    print(f"  Toplam kayıt: {len(maddeler)}")
    print(f"  Ana madde: {len(ana)}")
    print(f"  Ek madde: {len(ek)}")
    print(f"  Geçici madde: {len(gecici)}")

    if maddeler:
        print("  İlk 3 kayıt:")
        for m in maddeler[:3]:
            print(f"    {m['madde_tipi']} {m['madde_no']} -> {m['icerik'][:180]}")

        print("  Son 3 kayıt:")
        for m in maddeler[-3:]:
            print(f"    {m['madde_tipi']} {m['madde_no']} -> {m['icerik'][:180]}")


def main():
    for item in KANUNLAR:
        kanun_no = item["kanun_no"]
        kanun_adi = item["kanun_adi"]

        try:
            print(f"\n{kanun_adi} ({kanun_no}) parse ediliyor...")
            lines = fetch_pdf_lines(kanun_no)
            maddeler = parse_maddeler_from_lines(lines, kanun_adi, kanun_no)
            maddeler = post_clean_articles(maddeler)
            print_summary(kanun_adi, maddeler)
            save_outputs(kanun_no, kanun_adi, maddeler)

        except Exception as e:
            print(f"  HATA [{kanun_no} - {kanun_adi}]: {e}")


if __name__ == "__main__":
    main()