import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client

load_dotenv()

client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

JSON_PATH = "aym_kararlar_v4.json"

def embed_text(text):
    result = client.models.embed_content(
        model='gemini-embedding-001',
        contents=text[:2000],
        config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT')
    )
    return result.embeddings[0].values

def get_uploaded_basvuru_nolar():
    """Supabase'de zaten yüklü olan basvuru_no'ları çek."""
    uploaded = set()
    offset = 0
    while True:
        res = supabase.table('kararlar').select('basvuru_no').range(offset, offset + 999).execute()
        if not res.data:
            break
        for row in res.data:
            uploaded.add(row['basvuru_no'])
        if len(res.data) < 1000:
            break
        offset += 1000
    return uploaded

def main():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        kararlar = json.load(f)

    print(f"Toplam karar: {len(kararlar)}")

    print("Supabase'deki mevcut kayıtlar kontrol ediliyor...")
    uploaded = get_uploaded_basvuru_nolar()
    print(f"Zaten yüklenmiş: {len(uploaded)}")

    eksik = [k for k in kararlar if k.get('basvuru_no') and k['basvuru_no'] not in uploaded]
    print(f"Yüklenecek: {len(eksik)}\n")

    basarili = 0
    atlanan = 0

    for i, karar in enumerate(eksik):
        basvuru_no = karar.get('basvuru_no', '')
        metin = karar.get('metin', '')

        if not metin or len(metin) < 100:
            print(f"[{i+1}/{len(eksik)}] ATLA (metin yok): {basvuru_no}")
            atlanan += 1
            continue

        while True:
            try:
                embedding = embed_text(metin)
                row = {
                    'basvuru_no': basvuru_no,
                    'baslik': karar.get('baslik', ''),
                    'basvuru_konusu': karar.get('basvuru_konusu', ''),
                    'tur': karar.get('tur', ''),
                    'bolum': karar.get('bolum', ''),
                    'basvuru_tarihi': karar.get('basvuru_tarihi', ''),
                    'karar_tarihi': karar.get('karar_tarihi', ''),
                    'metin': metin,
                    'url': karar.get('url', ''),
                    'embedding': embedding,
                }
                supabase.table('kararlar').upsert(row, on_conflict='basvuru_no').execute()
                basarili += 1
                print(f"[{i+1}/{len(eksik)}] ✓ {basvuru_no} ({len(metin):,} kar)")
                break

            except Exception as e:
                if '429' in str(e) or 'quota' in str(e).lower():
                    print(f"  [!] 429 quota hatası — 60 saniye bekleniyor...")
                    time.sleep(60)
                else:
                    print(f"  [!] HATA {basvuru_no}: {e}")
                    atlanan += 1
                    break

        # Her 100 kayıtta ilerleme özeti
        if (i + 1) % 100 == 0:
            print(f"\n--- İlerleme: {i+1}/{len(eksik)} | Başarılı: {basarili} | Atlanan: {atlanan} ---\n")

    print(f"\n✓ Tamamlandı! Yüklenen: {basarili} | Atlanan: {atlanan}")

if __name__ == '__main__':
    main()