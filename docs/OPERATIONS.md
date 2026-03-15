Tamam — şimdi de **operasyon rehberi**ni hazırlayalım.
Bunu `docs/OPERATIONS.md` olarak koyman en temiz yol olur.

Aşağıdaki metni yeni bir dosyaya yapıştır:

## Dosya

`docs/OPERATIONS.md`

````md
# HukukAI Operations Guide

Bu doküman, projeye yeni mevzuat eklerken ve retrieval sistemini güvenli şekilde güncellerken izlenecek standart operasyon akışını tanımlar.

---

## 1. Amaç

Yeni bir kanunu sisteme eklerken hedef:

- resmi metni temizlemek
- JSON’a çevirmek
- doğrulamak
- Supabase’e yüklemek
- `structured_content` üretmek
- `mevzuat_references` üretmek
- retrieval regression setine eklemek

Bu akış tamamlanmadan kanun “production-ready” kabul edilmez.

---

## 2. Altın Kural

Asıl mevzuat metni:

```text
mevzuat.icerik
````

alanında tutulur ve otorite odur.

Aşağıdaki yapılar **yardımcı veri** üretir:

* `structured_content`
* `mevzuat_references`

Bunlar retrieval kalitesini artırmak içindir.
Asıl metnin yerine geçmez.

---

## 3. Yeni Kanun Ekleme Akışı

## Adım 1 — RAW TXT hazırla

Kaynak: resmi mevzuat PDF / resmi metin

Hedef:

* madde bazlı temiz TXT
* bölüm başlıkları, dipnotlar, meta bilgiler temizlenmiş olmalı
* yalnızca:

  * Madde
  * Ek Madde
  * Geçici Madde
  * Ek Geçici Madde
  * Mükerrer Madde

satırları ve içerikleri kalmalı

### Kritik not

Mükerrer maddeler iç temsilde `/A` standardına gider:

* `Mükerrer Madde 35` → `35/A`

---

## Adım 2 — TXT → JSON

```bash
cd data\mevzuat
python txt_to_json_mevzuat.py KLASOR_ADI
```

Örnek:

```bash
python txt_to_json_mevzuat.py 1136_avukatlik_kanunu
```

Bu adım:

* madde başlıklarını parse eder
* `madde_tipi`
* `madde_no`
* `icerik`

alanlarını JSON formatında üretir

---

## Adım 3 — JSON doğrulama

```bash
python validate_mevzuat_json.py KLASOR_ADI
```

Örnek:

```bash
python validate_mevzuat_json.py 1136_avukatlik_kanunu
```

Kontrol edilenler:

* beklenen madde listesi
* eksik / fazla madde
* madde tipi tutarlılığı

Validation geçmeden upload yapılmamalıdır.

---

## Adım 4 — Supabase upload

```bash
python upload_mevzuat_json.py KLASOR_ADI
```

Örnek:

```bash
python upload_mevzuat_json.py 1136_avukatlik_kanunu
```

Bu script:

* `mevzuat` tablosuna upsert yapar
* chunk üretir
* embedding üretir
* ilgili chunk kayıtlarını yazar

### Not

Bu adım Gemini embedding kotasına bağlıdır.

---

## Adım 5 — Structured content backfill

Upload tamamlandıktan sonra:

```bash
python backfill_structured_content.py
```

Kanun no sorunca ilgili kanun numarası girilir.

Örnek:

```text
1136
```

Bu script:

* `mevzuat.icerik` alanını okur
* fıkraları ayrıştırır
* sonucu `mevzuat.structured_content` alanına yazar

### Önemli

Bu script asıl metni değiştirmez.

---

## Adım 6 — Reference extraction

Upload ve backfill sonrasında:

```bash
python extract_mevzuat_references.py
```

Kanun no sorunca ilgili kanun numarası girilir.

Örnek:

```text
1136
```

Bu script:

* o kanuna ait maddeleri tarar
* açık madde atıflarını çıkarır
* `mevzuat_references` tablosuna yazar

Script önce ilgili kanunun eski reference kayıtlarını siler, sonra yeniden üretir.

---

## 4. Doğru Çalışma Sırası

Her yeni kanun için standart sıra:

```text
RAW TXT
→ txt_to_json_mevzuat.py
→ validate_mevzuat_json.py
→ upload_mevzuat_json.py
→ backfill_structured_content.py
→ extract_mevzuat_references.py
→ retrieval smoke test
→ regression case ekleme
```

---

## 5. Smoke Test

Yeni kanun yüklendikten sonra Python shell’de mutlaka hızlı test yapılmalıdır.

```
from chat.rag import debug_retrieve_mevzuat

debug_retrieve_mevzuat("KANUN 1")
debug_retrieve_mevzuat("KANUN 1 ila 3")
debug_retrieve_mevzuat("KANUN 1 ve devamı")
```


Örnek:

```
debug_retrieve_mevzuat("Avukatlık Kanunu 1")
debug_retrieve_mevzuat("Avukatlık Kanunu 1 ila 3")
debug_retrieve_mevzuat("Avukatlık Kanunu 1 ve devamı")
debug_retrieve_mevzuat("Avukatlık Kanunu Ek Madde 1")
debug_retrieve_mevzuat("Avukatlık Kanunu Geçici Madde 1")
debug_retrieve_mevzuat("Avukatlık Kanunu Mükerrer Madde 35")
```

Beklenti:

* `direct_article_lookup`
* doğru `kanun_no`
* doğru `madde_tipi`
* doğru `madde_no`

---

## 6. Regression Test Süreci

Yeni kanun sisteme gerçekten girdiyse:

* pending’de tutulmaz
* active suite’e alınır

### Active suite

```text
tests/retrieval_test_cases.json
```

### Test komutları

```bash
pytest tests/test_retrieval.py -q
python tests/run_retrieval_benchmark.py
```

### Pending suite

Sadece DB’de olmayan veya henüz desteklenmeyen case’ler için kullanılmalıdır.

```text
tests/retrieval_test_cases_pending.json
```

---

## 7. Active Suite’e Eklenecek Minimum Case Seti

Yeni kanun için en az şu testler eklenmelidir:

### Zorunlu minimum

* single article
* range
* devamı

### Varsa

* contextual range
* previous / next article
* ek madde
* geçici madde
* ek geçici madde
* mükerrer madde

---

## 8. Özel Madde Tipleri İçin İç Temsil

### Normal Madde

```text
madde_tipi = "madde"
madde_no   = "49"
```

### Ek Madde

```text
madde_tipi = "ek"
madde_no   = "1"
```

### Geçici Madde

```text
madde_tipi = "gecici"
madde_no   = "1"
```

### Ek Geçici Madde

```text
madde_tipi = "ek_gecici"
madde_no   = "1"
```

### Mükerrer Madde

```text
madde_tipi = "madde"
madde_no   = "35/A"
```

---

## 9. Backfill ve Extract Ne Zaman Tekrar Çalıştırılır?

Aşağıdaki durumlarda tekrar çalıştır:

* RAW/TXT değiştiyse
* JSON değiştiyse
* upload yeniden yapıldıysa
* parser mantığı güncellendiyse
* extractor mantığı güncellendiyse

### Genel kural

* yalnızca retrieval testleri eklediyse tekrar çalıştırma gerekmez
* metin/veri değiştiyse tekrar çalıştır

---

## 10. Sık Yapılan Hatalar

### Hata 1

Yanlış klasörde script çalıştırmak

Yanlış:

```bash
python extract_mevzuat_references.py
```

Doğru:

```bash
cd data\mevzuat
python extract_mevzuat_references.py
```

### Hata 2

Upload’dan önce backfill/extract çalıştırmak

Yanlış sıra:

```text
txt_to_json
→ backfill
→ extract
→ upload
```

Doğru sıra:

```text
txt_to_json
→ validate
→ upload
→ backfill
→ extract
```

### Hata 3

Pending case’i active’e taşımayı unutmak

Kanun DB’deyse test artık pending’de kalmamalı.

---

## 11. Production Readiness Checklist

Bir kanun ancak aşağıdaki koşullardan sonra “hazır” kabul edilir:

* [ ] RAW TXT temiz
* [ ] JSON validation geçti
* [ ] Upload tamamlandı
* [ ] Structured content üretildi
* [ ] Reference extraction tamamlandı
* [ ] Smoke test geçti
* [ ] Active regression suite’e eklendi
* [ ] `pytest` geçti
* [ ] benchmark sonucu doğru

---

## 12. Retrieval Çekirdeği İçin Freeze Kuralı

`rag.py` değiştirildikten sonra mutlaka:

```bash
pytest tests/test_retrieval.py -q
python tests/run_retrieval_benchmark.py
```

çalıştırılmalıdır.

Regression bozuluyorsa değişiklik kabul edilmez.

---

## 13. Gelecek Geliştirmeler

Planlanan sonraki iyileştirmeler:

* bent parsing
* `structured_content` v2
* karar retrieval / karar ranking
* kanunlar arası graph iyileştirmesi
* `rag.py` cleanup / refactor
