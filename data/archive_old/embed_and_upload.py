from google import genai
from google.genai import types
from supabase import create_client
import requests
import time
import re
import os
import fitz
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EMBED_DIM = 1536

KANUN_PDF_VERSIYON = {
    "213": "1.4",
}

KANUNLAR = [
    ("4857", "İş Kanunu"),
    # ("6098", "Türk Borçlar Kanunu"),
    # ("4721", "Türk Medeni Kanunu"),
    # ("6100", "Hukuk Muhakemeleri Kanunu"),
    # ("2004", "İcra ve İflas Kanunu"),
]


def download_pdf(kanun_no: str) -> str:
    versiyon = KANUN_PDF_VERSIYON.get(kanun_no, "1.5")
    url = f"https://www.mevzuat.gov.tr/MevzuatMetin/{versiyon}.{kanun_no}.pdf"
    print(f"  PDF indiriliyor: {url}")

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"PDF indirilemedi. HTTP {r.status_code}")

    tmp_path = f"tmp_{kanun_no}.pdf"
    with open(tmp_path, "wb") as f:
        f.write(r.content)

    return tmp_path


def normalize_line(line: str) -> str:
    line = line.replace("\xa0", " ")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def should_keep_block(x0, y0, x1, y1, text, page_width, page_height) -> bool:
    """
    Ana metin dışındaki gürültüyü filtrele:
    - çok üst / çok alt header-footer
    - aşırı dar bloklar
    - boş bloklar
    """
    text = normalize_line(text)
    if not text:
        return False

    # header / footer
    if y0 < 45 or y1 > page_height - 45:
        return False

    block_width = x1 - x0

    # Çok dar bloklar çoğu zaman sayfa no, dipnot, kenar notu
    if block_width < page_width * 0.35:
        return False

    # Çok kısa ve anlamsız blokları at
    if len(text) < 3:
        return False

    return True


def fetch_pdf_lines(kanun_no: str) -> list[str]:
    tmp_path = download_pdf(kanun_no)
    doc = fitz.open(tmp_path)

    lines = []

    for page in doc:
        page_width = page.rect.width
        page_height = page.rect.height

        blocks = page.get_text("blocks")
        # block tuple: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

        for block in blocks:
            x0, y0, x1, y1, text, *_ = block

            if not should_keep_block(x0, y0, x1, y1, text, page_width, page_height):
                continue

            for raw_line in text.splitlines():
                line = normalize_line(raw_line)
                if not line:
                    continue
                lines.append(line)

    doc.close()
    os.remove(tmp_path)

    print(f"  {len(lines)} satır çıkarıldı")
    return lines


def clean_article_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Sondaki açık cetvel / tablo kirlerini kes
    end_markers = [
        "4857 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN",
        "KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN",
    ]
    for marker in end_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx].strip()

    return text


def parse_maddeler_from_lines(lines: list[str], kanun_adi: str, kanun_no: str) -> list[dict]:
    madde_header = re.compile(r"^(?:MADDE|Madde)\s+(\d+)\s*[-–—]\s*(.*)$")
    end_marker = re.compile(r"KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN", re.I)

    maddeler = []
    current_no = None
    current_lines = []

    def flush_current():
        nonlocal current_no, current_lines, maddeler

        if current_no is None:
            return

        icerik_raw = clean_article_text(" ".join(current_lines))

        if len(icerik_raw) < 80:
            current_no = None
            current_lines = []
            return

        full_text = f"{kanun_adi} Madde {current_no}: {icerik_raw}"
        maddeler.append({
            "kanun_no": kanun_no,
            "kanun_adi": kanun_adi,
            "madde_no": str(current_no),
            "icerik": full_text,
        })

        current_no = None
        current_lines = []

    for line in lines:
        if end_marker.search(line):
            flush_current()
            break

        m = madde_header.match(line)
        if m:
            # yeni madde başladı
            flush_current()
            current_no = int(m.group(1))
            first_part = m.group(2).strip()
            current_lines = [first_part] if first_part else []
            continue

        if current_no is not None:
            # Sayfa numarası / çıplak tarih / tablo satırı benzeri kirleri at
            if re.fullmatch(r"\d+", line):
                continue
            if re.search(r"\bE\.\s*:\s*\d{4}/\d+\b", line) and re.search(r"\bK\.\s*:\s*\d{4}/\d+\b", line):
                continue
            current_lines.append(line)

    flush_current()

    # duplicate madde no olursa en uzun olanı koru
    uniq = {}
    for m in maddeler:
        no = m["madde_no"]
        if no not in uniq or len(m["icerik"]) > len(uniq[no]["icerik"]):
            uniq[no] = m

    result = list(uniq.values())
    result.sort(key=lambda x: int(x["madde_no"]))
    return result


def validate_parser_output(maddeler: list[dict]) -> None:
    if not maddeler:
        raise RuntimeError("Parser hiç madde çıkaramadı.")

    first_no = int(maddeler[0]["madde_no"])
    last_no = int(maddeler[-1]["madde_no"])

    if first_no != 1:
        raise RuntimeError(f"Parser hatalı: ilk madde {first_no}")

    if len(maddeler) < 100:
        raise RuntimeError(f"Parser hatalı: sadece {len(maddeler)} madde bulundu.")

    first_text = maddeler[0]["icerik"]
    if "Bu Kanunun amacı" not in first_text:
        raise RuntimeError("Parser hatalı: Madde 1 beklenen metinle başlamıyor.")

    if last_no < 110:
        raise RuntimeError(f"Parser hatalı: son madde numarası şüpheli ({last_no}).")

    print(f"  ✅ Parser doğrulandı. İlk madde: {first_no}, son madde: {last_no}, toplam: {len(maddeler)}")


def split_text(text: str, chunk_size=1000, overlap=200) -> list[str]:
    chunks = []
    text = text.strip()
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def embed_text(text: str) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text[:2000],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_DIM,
        ),
    )
    return result.embeddings[0].values


def main_kayit_var_mi(kanun_no: str, madde_no: str):
    res = (
        supabase.table("mevzuat")
        .select("id, kanun_no, madde_no")
        .eq("kanun_no", kanun_no)
        .eq("madde_no", madde_no)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]
    return None


def delete_existing_chunks(mevzuat_id: int):
    supabase.table("mevzuat_chunks").delete().eq("mevzuat_id", mevzuat_id).execute()


def upsert_madde(madde: dict) -> int:
    mevcut = main_kayit_var_mi(madde["kanun_no"], madde["madde_no"])

    if mevcut:
        mevzuat_id = mevcut["id"]
        supabase.table("mevzuat").update({
            "kanun_adi": madde["kanun_adi"],
            "icerik": madde["icerik"],
        }).eq("id", mevzuat_id).execute()
        return mevzuat_id

    insert_res = supabase.table("mevzuat").insert({
        "kanun_no": madde["kanun_no"],
        "kanun_adi": madde["kanun_adi"],
        "madde_no": madde["madde_no"],
        "icerik": madde["icerik"],
    }).execute()

    return insert_res.data[0]["id"]


def process_madde(madde: dict) -> int:
    # Önce embeddingleri al; başarılı olmadan DB'ye yazma
    chunks = split_text(madde["icerik"], chunk_size=1000, overlap=200)

    chunk_rows = []
    for idx, chunk_text in enumerate(chunks):
        embedding = embed_text(chunk_text)
        chunk_rows.append({
            "kanun_no": madde["kanun_no"],
            "kanun_adi": madde["kanun_adi"],
            "madde_no": madde["madde_no"],
            "chunk_index": idx,
            "chunk_text": chunk_text,
            "embedding": embedding,
        })
        time.sleep(0.4)

    mevzuat_id = upsert_madde(madde)
    delete_existing_chunks(mevzuat_id)

    for row in chunk_rows:
        row["mevzuat_id"] = mevzuat_id
        supabase.table("mevzuat_chunks").insert(row).execute()

    return len(chunk_rows)


def main():
    toplam_madde = 0
    toplam_chunk = 0
    gunluk_limit_doldu = False

    for kanun_no, kanun_adi in KANUNLAR:
        if gunluk_limit_doldu:
            break

        print(f"\n📖 {kanun_adi} işleniyor...")

        try:
            lines = fetch_pdf_lines(kanun_no)
            maddeler = parse_maddeler_from_lines(lines, kanun_adi, kanun_no)
            validate_parser_output(maddeler)
        except Exception as e:
            print(f"  ⛔ Parse/doğrulama hatası: {e}")
            continue

        for madde in maddeler:
            if gunluk_limit_doldu:
                break

            try:
                chunk_sayisi = process_madde(madde)
                toplam_madde += 1
                toplam_chunk += chunk_sayisi
                print(f"  ✅ Md.{madde['madde_no']} yüklendi ({chunk_sayisi} chunk)")
                time.sleep(0.5)

            except Exception as e:
                err_str = str(e)

                if "429" in err_str:
                    if "PerDay" in err_str or "per_day" in err_str.lower():
                        print("\n🛑 GÜNLÜK LİMİT DOLDU!")
                        print("   Yarın tekrar çalıştırın.")
                        print(f"   Bu oturumda {toplam_madde} madde ve {toplam_chunk} chunk yüklendi.")
                        gunluk_limit_doldu = True
                        break
                    else:
                        print("  ⏸️ Dakikalık limit! 65 saniye bekleniyor...")
                        time.sleep(65)

                        try:
                            chunk_sayisi = process_madde(madde)
                            toplam_madde += 1
                            toplam_chunk += chunk_sayisi
                            print(f"  ✅ Md.{madde['madde_no']} yüklendi (retry, {chunk_sayisi} chunk)")
                        except Exception as e2:
                            if "PerDay" in str(e2) or "per_day" in str(e2).lower():
                                print("\n🛑 GÜNLÜK LİMİT DOLDU!")
                                print("   Yarın tekrar çalıştırın.")
                                gunluk_limit_doldu = True
                                break

                            print(f"  ❌ Md.{madde['madde_no']} atlandı: {e2}")
                else:
                    print(f"  ❌ Md.{madde['madde_no']} hata: {e}")

        time.sleep(2)

    print("\n🎉 Oturum tamamlandı!")
    print(f"   Yüklenen madde : {toplam_madde}")
    print(f"   Yüklenen chunk : {toplam_chunk}")

    if gunluk_limit_doldu:
        print("   ⏰ Daha sonra aynı komutla devam edebilirsiniz.")


if __name__ == "__main__":
    lines = fetch_pdf_lines("4857")
    maddeler = parse_maddeler_from_lines(lines, "İş Kanunu", "4857")
    validate_parser_output(maddeler)

    print("\nİlk 3 madde:")
    for m in maddeler[:3]:
        print(m["madde_no"], "->", m["icerik"][:180])

    print("\nSon 3 madde:")
    for m in maddeler[-3:]:
        print(m["madde_no"], "->", m["icerik"][:180])