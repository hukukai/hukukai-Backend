import json, random

with open("aym_kararlar_v4.json", encoding="utf-8") as f:
    data = json.load(f)

# 1. Temel istatistik
eksik = [k for k in data if not k.get("metin")]
kisa = [k for k in data if 0 < k.get("metin_uzunluk", 0) < 1000]
print(f"Toplam: {len(data)}")
print(f"Metinli: {len(data) - len(eksik)}")
print(f"Metinsiz: {len(eksik)}")
print(f"Çok kısa (<1000 kar): {len(kisa)}")

# 2. URL duplikasyon
urls = [k["url"] for k in data]
print(f"Duplikat URL: {len(urls) - len(set(urls))}")

# 3. Zorunlu alanlar
for alan in ["baslik", "basvuru_no", "karar_tarihi"]:
    eksik_alan = [k for k in data if not k.get(alan)]
    print(f"'{alan}' eksik: {len(eksik_alan)}")

# 4. Metin kalite kontrolü — 5 random karar
print("\n--- 5 RANDOM KARAR METİN BAŞLANGIÇLARI ---")
for k in random.sample(data, 5):
    metin = k.get("metin", "")
    print(f"\n{k['basvuru_no']} | {k['baslik'][:50]}")
    print(f"  Uzunluk: {k.get('metin_uzunluk', 0):,} kar")
    print(f"  Başlangıç: {metin[:150]!r}")

# 5. Eksikleri kaydet
if eksik:
    with open("eksik_kararlar.json", "w", encoding="utf-8") as f:
        json.dump(eksik, f, ensure_ascii=False, indent=2)
    print(f"\nexsik_kararlar.json kaydedildi ({len(eksik)} adet)")