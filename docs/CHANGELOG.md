Tamamdır. En kullanışlı olanı bence **`docs/CHANGELOG.md`**.
Hem teknik gelişimi takip edersin, hem de yeni chat açınca ya da projeyi birine gösterince “ne zaman ne eklenmiş” net görünür.

Aşağıdaki metni yeni bir dosyaya koy:

## Dosya

`docs/CHANGELOG.md`

````md
# HukukAI Changelog

Bu dosya, retrieval çekirdeği, veri yükleme akışı ve test altyapısındaki önemli değişiklikleri kronolojik olarak özetler.

---

## [Unreleased]

### Eklendi
- Retrieval regression suite genişletildi.
- Aşağıdaki retrieval senaryoları active test setine alındı:
  - single article
  - range (`ila`)
  - `ve devamı`
  - contextual range
  - previous / next article
  - ek madde
  - geçici madde
  - ek geçici madde
  - mükerrer madde

### Eklendi
- `rag.py` içinde özel madde tipi parsing desteği:
  - `Ek Madde`
  - `Geçici Madde`
  - `Ek Geçici Madde`
  - `Mükerrer Madde`

### Eklendi
- `Mükerrer Madde` iç temsil standardı:
  - `Mükerrer Madde 35` → `35/A`
  - `Mükerrer Madde 27` → `27/A`

### Eklendi
- Genişletilmiş `LAW_ALIASES` desteği:
  - `İİK`
  - `CMK`
  - `İYUK`
  - `TKHK`
  - `Arabuluculuk Kanunu`
  - `Tebligat Kanunu`
  - `Avukatlık Kanunu`
  - diğer tam kanun adları

### Eklendi
- Bağlamsal çözüm testleri:
  - `bu Kanunun X ila Y`
  - `önceki madde`
  - `sonraki madde`

### Eklendi
- `backfill_structured_content.py` sonrası `structured_content` kullanımının retrieval akışında aktif hale gelmesi

### Eklendi
- `extract_mevzuat_references.py` normalizasyon ve alias kapsamı `rag.py` ile daha uyumlu hale getirildi

### Güncellendi
- Veri yükleme akışı netleştirildi:
  - `txt_to_json_mevzuat.py`
  - `validate_mevzuat_json.py`
  - `upload_mevzuat_json.py`
  - `backfill_structured_content.py`
  - `extract_mevzuat_references.py`

### Güncellendi
- README, eski upload akışından çıkarılıp güncel retrieval-first mimariye göre yeniden yazıldı

### Güncellendi
- Teknik özet dosyası, mevcut kanun coverage ve parser kapsamına göre yeniden düzenlendi

### Doğrulandı
- Active regression suite:
  - `40 passed`
- Benchmark:
  - `Top-1 accuracy: 37/37`
  - `Top-docs coverage: 37/37`

---

## [Önceki Durum]

### Mevcut Olanlar
- temel madde parsing
- single article retrieval
- sınırlı alias desteği
- sınırlı benchmark seti
- TBK / HMK / TCK ağırlıklı test coverage

### Eksik Olanlar
- İİK / CMK / İYUK / TKHK / Avukatlık / Tebligat doğal dil desteği
- özel madde tipleri
- geniş regression suite
- extractor tarafında geniş alias kapsaması

---

## Notlar

### Regression kuralı
`rag.py` veya retrieval davranışını etkileyen herhangi bir değişiklikten sonra mutlaka:

```bash
pytest tests/test_retrieval.py -q
python tests/run_retrieval_benchmark.py
````

çalıştırılmalıdır.

### Upload sonrası kural

Yeni kanun eklendiğinde süreç şu sırayla tamamlanmalıdır:

```text
RAW TXT
→ txt_to_json
→ validate
→ upload
→ backfill
→ extract
→ smoke test
→ active regression case ekleme
```