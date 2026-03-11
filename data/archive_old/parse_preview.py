
import requests
import re
import os
import json
import fitz


KANUN_PDF_VERSIYON = {
    "213": "1.4",
}

KANUNLAR = [
    ("4857", "İş Kanunu"),
]

# İstersen buraya lokal PDF yolu verebilirsin
LOCAL_PDF_MAP = {
    # "4857": r"C:\PROJELERvol2\2-active\HukukAI\hukukai-backend\data\1.5.4857.pdf",
}

ARTICLE_HEADER_RE = re.compile(
    r'^(?P<kind>Ek\s+Madde|Geçici\s+Madde|Madde)\s+(?P<num>\d+)\s*(?:[-–—]\s*)?(?P<rest>.*)$',
    re.IGNORECASE,
)

APPENDIX_START_RE = re.compile(
    r"^4857 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN",
    re.IGNORECASE,
)


def get_pdf_path(kanun_no: str) -> str:
    local_path = LOCAL_PDF_MAP.get(kanun_no)
    if local_path and os.path.exists(local_path):
        print(f"Lokal PDF kullanılıyor: {local_path}")
        return local_path

    versiyon = KANUN_PDF_VERSIYON.get(kanun_no, "1.5")
    url = f"https://www.mevzuat.gov.tr/MevzuatMetin/{versiyon}.{kanun_no}.pdf"
    print(f"PDF indiriliyor: {url}")

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"PDF indirilemedi. HTTP {r.status_code}")

    tmp_path = f"tmp_{kanun_no}.pdf"
    with open(tmp_path, "wb") as f:
        f.write(r.content)
    return tmp_path


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("­", "")  # soft hyphen
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def remove_inline_footnote_numbers(text: str) -> str:
    # "dayanarak;1" -> "dayanarak;"
    # "sayılır.23" -> "sayılır."
    text = re.sub(r"(?<=[^\W\d_])(\d{1,4})(?=\s|$)", "", text)
    text = re.sub(r"(?<=[\.;,\)])(\d{1,4})(?=\s|$)", "", text)
    text = re.sub(r"(?<=\])(\d{1,4})(?=\s|$)", "", text)
    return text


def clean_article_text(text: str) -> str:
    text = normalize_text(text)

    # satır sonu birleşmeleri
    text = re.sub(r"\n+", "\n", text)

    # dipnot başlangıcı gibi görünen satırları at
    kept_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if re.match(r"^\d+\s+\d{1,2}/\d{1,2}/\d{4}\b", line):
            continue

        if APPENDIX_START_RE.match(line):
            break

        kept_lines.append(line)

    text = "\n".join(kept_lines)
    text = remove_inline_footnote_numbers(text)

    # artık tek satıra indir
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_blocks(pdf_path: str) -> list[str]:
    doc = fitz.open(pdf_path)
    blocks = []

    for page in doc:
        page_dict = page.get_text("dict")

        for block in page_dict["blocks"]:
            if block["type"] != 0:
                continue

            x0, y0, x1, y1 = block["bbox"]
            if y0 < 60:
                continue

            line_texts = []
            first_line = None

            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]).strip()
                if text:
                    if first_line is None:
                        first_line = text
                    line_texts.append(text)

            if not line_texts:
                continue

            # alt dipnot bloklarını at
            if first_line and re.match(r"^\d+\s+", first_line) and y0 > 560:
                continue

            block_text = normalize_text(" ".join(line_texts))
            if block_text:
                blocks.append(block_text)

    doc.close()
    return blocks


def preprocess_stream(blocks: list[str]) -> str:
    texts = []

    for block in blocks:
        if APPENDIX_START_RE.match(block):
            break
        texts.append(block)

    text = "\n".join(texts)
    text = normalize_text(text)

    # Cümle bitiminden sonra gelen madde başlıklarından önce newline aç
    text = re.sub(
        r"([.!?])\s+([A-ZÇĞİÖŞÜ][^.\n]{1,120}?)\s+(?=(?:Ek\s+Madde|Geçici\s+Madde)\s+\d+\s*(?:[-–—]\s*)?)",
        r"\1\n\2\n",
        text,
    )
    text = re.sub(
        r"([.!?])\s+([A-ZÇĞİÖŞÜ][^.\n]{1,120}?)\s+(?=(?<!Ek\s)(?<!Geçici\s)Madde\s+\d+\s*(?:[-–—]\s*)?)",
        r"\1\n\2\n",
        text,
    )

    # Başlıkların önüne newline koy
    text = re.sub(
        r"(?<!\n)(?=\b(?:Ek\s+Madde|Geçici\s+Madde)\s+\d+\s*(?:[-–—]\s*)?)",
        "\n",
        text,
    )
    text = re.sub(
        r"(?<!Ek )(?<!Geçici )(?<!\n)(?=\bMadde\s+\d+\s*(?:[-–—]\s*)?)",
        "\n",
        text,
    )

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    header_re = ARTICLE_HEADER_RE

    def is_probable_title_line(line: str) -> bool:
        if header_re.match(line):
            return False
        if len(line) > 120:
            return False
        if line.endswith((".", ";", ":")):
            return False
        if line.startswith("("):
            return False
        if sum(ch.isdigit() for ch in line) > 6:
            return False

        words = line.split()
        if not (1 <= len(words) <= 12):
            return False

        return True

    cleaned_lines = []
    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else ""

        # "Yürürlük" gibi tek başına duran başlıklar
        if is_probable_title_line(line) and header_re.match(next_line):
            continue

        cleaned_lines.append(line)

    # ilk gerçek maddeden önceki her şeyi at
    for i, line in enumerate(cleaned_lines):
        if header_re.match(line):
            cleaned_lines = cleaned_lines[i:]
            break

    return "\n".join(cleaned_lines)


def parse_maddeler_from_pdf(pdf_path: str, kanun_adi: str, kanun_no: str) -> list[dict]:
    blocks = extract_blocks(pdf_path)
    print(f"{len(blocks)} blok çıkarıldı")

    stream = preprocess_stream(blocks)

    header_re = re.compile(
        r'^(?P<kind>Ek\s+Madde|Geçici\s+Madde|Madde)\s+(?P<num>\d+)\s*(?:[-–—]\s*)?(?P<rest>.*)$',
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(header_re.finditer(stream))

    maddeler = []

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(stream)

        full_chunk = stream[start:end].strip()
        lines = [x.strip() for x in full_chunk.splitlines() if x.strip()]
        if not lines:
            continue

        first_line = lines[0]
        m = ARTICLE_HEADER_RE.match(first_line)
        if not m:
            continue

        raw_kind = m.group("kind").lower().replace("\n", " ")
        madde_no = m.group("num").strip()
        first_rest = m.group("rest").strip()

        if raw_kind.startswith("ek"):
            madde_tipi = "ek"
            prefix = f"{kanun_adi} Ek Madde {madde_no}: "
        elif raw_kind.startswith("geçici"):
            madde_tipi = "gecici"
            prefix = f"{kanun_adi} Geçici Madde {madde_no}: "
        else:
            madde_tipi = "madde"
            prefix = f"{kanun_adi} Madde {madde_no}: "

        body_parts = [first_rest] if first_rest else []
        body_parts.extend(lines[1:])

        body = clean_article_text("\n".join(body_parts))
        if not body:
            continue

        maddeler.append({
            "kanun_no": kanun_no,
            "kanun_adi": kanun_adi,
            "madde_no": str(madde_no),
            "madde_tipi": madde_tipi,
            "icerik": prefix + body,
        })

    # duplicate temizliği
    uniq = {}
    for item in maddeler:
        key = (item["madde_tipi"], item["madde_no"])
        if key not in uniq or len(item["icerik"]) > len(uniq[key]["icerik"]):
            uniq[key] = item

    result = list(uniq.values())

    def sort_key(x):
        order = {"madde": 0, "ek": 1, "gecici": 2}
        return (order.get(x["madde_tipi"], 9), int(x["madde_no"]))

    result.sort(key=sort_key)
    return result


def save_preview_files(kanun_no: str, maddeler: list[dict]) -> None:
    json_path = f"preview_{kanun_no}.json"
    txt_path = f"preview_{kanun_no}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(maddeler, f, ensure_ascii=False, indent=2)

    ana = [m for m in maddeler if m["madde_tipi"] == "madde"]
    ek = [m for m in maddeler if m["madde_tipi"] == "ek"]
    gecici = [m for m in maddeler if m["madde_tipi"] == "gecici"]

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Toplam kayıt: {len(maddeler)}\n")
        f.write(f"Ana madde: {len(ana)}\n")
        f.write(f"Ek madde: {len(ek)}\n")
        f.write(f"Geçici madde: {len(gecici)}\n\n")

        f.write("İLK 10 KAYIT\n")
        f.write("=" * 80 + "\n")
        for m in maddeler[:10]:
            f.write(f"{m['madde_tipi']} {m['madde_no']} | {m['icerik'][:700]}\n\n")

        f.write("\nSON 10 KAYIT\n")
        f.write("=" * 80 + "\n")
        for m in maddeler[-10:]:
            f.write(f"{m['madde_tipi']} {m['madde_no']} | {m['icerik'][:700]}\n\n")

    print(f"Kaydedildi: {json_path}")
    print(f"Kaydedildi: {txt_path}")


def debug_maddeler(maddeler: list[dict]) -> None:
    ana = [m for m in maddeler if m["madde_tipi"] == "madde"]
    ek = [m for m in maddeler if m["madde_tipi"] == "ek"]
    gecici = [m for m in maddeler if m["madde_tipi"] == "gecici"]

    ana_nolar = sorted(int(m["madde_no"]) for m in ana)
    expected = set(range(1, 123))
    mevcut = set(ana_nolar)
    missing = sorted(expected - mevcut)

    print("\nİlk 20 ana madde no:")
    print(ana_nolar[:20])

    print("\nSon 20 ana madde no:")
    print(ana_nolar[-20:])

    print("\nEksik ana madde numaraları:")
    print(missing)

    print("\nŞüpheli kısa kayıtlar (<120 karakter):")
    for m in maddeler:
        if len(m["icerik"]) < 120:
            print(f"{m['madde_tipi']} {m['madde_no']} -> {m['icerik']}")

    print("\n110-122 arası ana maddeler:")
    for m in ana:
        no = int(m["madde_no"])
        if 110 <= no <= 122:
            print(f"{m['madde_no']} -> {m['icerik'][:250]}")


def main():
    for kanun_no, kanun_adi in KANUNLAR:
        print(f"\n{kanun_adi} parse ediliyor...")
        pdf_path = get_pdf_path(kanun_no)
        temp_download = pdf_path.startswith("tmp_") and pdf_path.endswith(".pdf")

        try:
            maddeler = parse_maddeler_from_pdf(pdf_path, kanun_adi, kanun_no)
        finally:
            if temp_download and os.path.exists(pdf_path):
                os.remove(pdf_path)

        ana = [m for m in maddeler if m["madde_tipi"] == "madde"]
        ek = [m for m in maddeler if m["madde_tipi"] == "ek"]
        gecici = [m for m in maddeler if m["madde_tipi"] == "gecici"]

        print(f"Toplam kayıt: {len(maddeler)}")
        print(f"Ana madde: {len(ana)}")
        print(f"Ek madde: {len(ek)}")
        print(f"Geçici madde: {len(gecici)}")

        print("\nİlk 5 kayıt:")
        for m in maddeler[:5]:
            print(m["madde_tipi"], m["madde_no"], "->", m["icerik"][:180])

        print("\nSon 8 kayıt:")
        for m in maddeler[-8:]:
            print(m["madde_tipi"], m["madde_no"], "->", m["icerik"][:220])

        debug_maddeler(maddeler)
        save_preview_files(kanun_no, maddeler)


if __name__ == "__main__":
    main()
