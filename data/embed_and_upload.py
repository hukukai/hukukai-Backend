from google import genai
from google.genai import types
from supabase import create_client
import requests, time, re, os, fitz
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

KANUNLAR = [
    ("4857",  "İş Kanunu"),
    ("6098",  "Türk Borçlar Kanunu"),
    ("4721",  "Türk Medeni Kanunu"),
    ("6502",  "Tüketicinin Korunması Hakkında Kanun"),
    ("2709",  "Türkiye Cumhuriyeti Anayasası"),
    ("5237",  "Türk Ceza Kanunu"),
    ("6102",  "Türk Ticaret Kanunu"),
    ("2577",  "İdari Yargılama Usulü Kanunu"),
]

def zaten_yuklu_mu(kanun_no: str, madde_no: str) -> bool:
    """Bu madde zaten Supabase'de var mı kontrol et."""
    res = supabase.table('mevzuat').select('id').eq('kanun_no', kanun_no).eq('madde_no', madde_no).execute()
    return len(res.data) > 0

def kac_madde_yuklu(kanun_no: str) -> int:
    """Bu kanundan kaç madde yüklenmiş."""
    res = supabase.table('mevzuat').select('id', count='exact').eq('kanun_no', kanun_no).execute()
    return res.count or 0

def fetch_pdf_text(kanun_no: str) -> str:
    url = f"https://www.mevzuat.gov.tr/MevzuatMetin/1.5.{kanun_no}.pdf"
    print(f"  PDF indiriliyor...")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code != 200:
        print(f"  ❌ HTTP {r.status_code}")
        return ""
    tmp_path = f"tmp_{kanun_no}.pdf"
    with open(tmp_path, 'wb') as f:
        f.write(r.content)
    doc = fitz.open(tmp_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    os.remove(tmp_path)
    print(f"  {len(full_text)} karakter metin çıkarıldı")
    return full_text

def parse_maddeler(text: str, kanun_adi: str, kanun_no: str) -> list:
    pattern = r'(?:MADDE|Madde)\s+(\d+)\s*[–\-—]?\s*'
    parcalar = re.split(pattern, text)
    maddeler = []
    for i in range(1, len(parcalar), 2):
        madde_no = parcalar[i].strip()
        icerik = parcalar[i+1].strip()[:1500] if i+1 < len(parcalar) else ""
        icerik = re.sub(r'\n+', ' ', icerik).strip()
        icerik = re.sub(r'\s+', ' ', icerik)
        if len(icerik) > 80:
            maddeler.append({
                "kanun_no":  kanun_no,
                "kanun_adi": kanun_adi,
                "madde_no":  madde_no,
                "icerik":    f"{kanun_adi} Madde {madde_no}: {icerik}"
            })
    return maddeler

def embed_text(text: str) -> list:
    result = client.models.embed_content(
        model='gemini-embedding-001',
        contents=text[:2000],
        config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT')
    )
    return result.embeddings[0].values

def upload_madde(madde: dict):
    embedding = embed_text(madde['icerik'])
    supabase.table('mevzuat').insert({
        'kanun_no':  madde['kanun_no'],
        'kanun_adi': madde['kanun_adi'],
        'madde_no':  madde['madde_no'],
        'icerik':    madde['icerik'],
        'embedding': embedding
    }).execute()

def main():
    toplam_yeni = 0
    toplam_atlandi = 0

    for kanun_no, kanun_adi in KANUNLAR:
        print(f"\n📖 {kanun_adi} işleniyor...")

        # Kaç madde zaten yüklenmiş?
        mevcut = kac_madde_yuklu(kanun_no)
        if mevcut > 0:
            print(f"  ⚡ Bu kanundan {mevcut} madde zaten yüklü")

        text = fetch_pdf_text(kanun_no)
        if not text:
            continue

        maddeler = parse_maddeler(text, kanun_adi, kanun_no)
        print(f"  {len(maddeler)} madde bulundu, kontrol ediliyor...")

        for madde in maddeler:
            # Zaten yüklüyse atla
            if zaten_yuklu_mu(madde['kanun_no'], madde['madde_no']):
                toplam_atlandi += 1
                continue

            try:
                upload_madde(madde)
                print(f"  ✅ Md.{madde['madde_no']} yüklendi")
                toplam_yeni += 1
                time.sleep(0.5)
            except Exception as e:
                err_str = str(e)
                if '429' in err_str:
                    print(f"  ⏸️  Rate limit! 60 saniye bekleniyor...")
                    time.sleep(60)
                    # Bir kez daha dene
                    try:
                        upload_madde(madde)
                        print(f"  ✅ Md.{madde['madde_no']} yüklendi (retry)")
                        toplam_yeni += 1
                    except Exception as e2:
                        print(f"  ❌ Md.{madde['madde_no']} atlandı: {e2}")
                else:
                    print(f"  ❌ Md.{madde['madde_no']} hata: {e}")

        time.sleep(2)

    print(f"\n🎉 Tamamlandı!")
    print(f"   Yeni yüklenen: {toplam_yeni} madde")
    print(f"   Atlanan (zaten vardı): {toplam_atlandi} madde")

if __name__ == '__main__':
    main()