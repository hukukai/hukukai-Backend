````md
# HukukAI Backend

Django REST API — Türk hukuku için geliştirilmiş **retrieval-first RAG (Retrieval Augmented Generation)** sistemi.

Sistem, kullanıcı sorusundan:

- kanun
- madde
- madde aralığı
- devamı ifadesi
- bağlamsal madde atfı
- fıkra atfı
- özel madde tipleri
- madde referansları

tespit ederek öncelikle **doğrudan mevzuat retrieval** yapar.

LLM yalnızca son aşamada cevap üretimi için kullanılır. Gemini kotası dolsa bile sistem retrieval-only fallback ile çalışmaya devam eder.

---

## Teknoloji Stack

- **Backend:** Django + Django REST
- **Vector DB:** Supabase PostgreSQL + pgvector
- **LLM:** Google Gemini
- **Embedding:** `gemini-embedding-001`
- **Chat Model:** `gemini-2.0-flash`
- **Streaming:** SSE (Server-Sent Events)

---

## Kurulum

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
````

---

## .env Dosyası

```env
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## Çalıştırma

```bash
python manage.py runserver
```

Server:

```text
http://127.0.0.1:8000
```

---

## Endpointler

| Method | URL             | Açıklama                               |
| ------ | --------------- | -------------------------------------- |
| POST   | /api/chat/      | mevzuat retrieval + LLM/fallback cevap |
| POST   | /api/karar-ara/ | karar arama endpointi                  |

---

## Veri Modeli

### `mevzuat` tablosu

Alanlar:

```text
id
kanun_no
kanun_adi
madde_no
madde_tipi
icerik
embedding
structured_content
```

### `structured_content` formatı

Madde içindeki fıkraları ayrıştırmak için kullanılır.

```json
{
  "fikralar": {
    "1": "...",
    "2": "...",
    "3": "..."
  }
}
```

Bu sayede örneğin:

```text
TBK 2 birinci fıkra
```

sorgusunda yalnızca ilgili fıkra döndürülebilir.

---

## Veri Yükleme Akışı

Yeni kanun eklerken doğru sıra:

```bash
cd data\mevzuat
python txt_to_json_mevzuat.py KLASOR_ADI
python validate_mevzuat_json.py KLASOR_ADI
python upload_mevzuat_json.py KLASOR_ADI
python backfill_structured_content.py
python extract_mevzuat_references.py
```

### Açıklama

#### 1. `txt_to_json_mevzuat.py`

RAW TXT mevzuat metnini JSON’a çevirir.

#### 2. `validate_mevzuat_json.py`

JSON içindeki madde numarası / madde tipi yapısını doğrular.

#### 3. `upload_mevzuat_json.py`

* mevzuatı `mevzuat` tablosuna yükler
* chunk üretir
* embedding oluşturur
* chunk tablosunu doldurur

#### 4. `backfill_structured_content.py`

`icerik` alanından okuyup `structured_content` alanını doldurur.

#### 5. `extract_mevzuat_references.py`

Madde içindeki açık referansları çıkarıp `mevzuat_references` tablosuna yazar.

> Not: `backfill_structured_content.py` ve `extract_mevzuat_references.py` **upload’dan sonra** çalıştırılmalıdır.

---

## Structured Content (Fıkra Parsing)

Sistem yalnızca açık fıkra numaralarını değil, bağlamsal fıkra referanslarını da çözebilir.

Desteklenen örnekler:

```text
birinci fıkra
ikinci fıkra
üçüncü fıkra
bu fıkra
önceki fıkra
yukarıdaki fıkra
```

### Fıkra extraction status

| Status         | Açıklama                           |
| -------------- | ---------------------------------- |
| matched        | istenen fıkra bulundu              |
| partial_match  | çoğul fıkraların bir kısmı bulundu |
| not_structured | veri yeterince ayrışmadı           |
| not_requested  | soru fıkra istemiyor               |

---

## Retrieval Özellikleri

### 1. Açık madde parsing

Desteklenen örnekler:

```text
TBK 49
TCK 109
CMK 100
İİK 82
HMK 114
İYUK 1
TKHK 1
Avukatlık Kanunu 1
Tebligat Kanunu 10
```

### 2. Çoklu madde parsing

```text
TBK 18, 19 ve 20
HMK 114, 115, 116
```

### 3. Madde aralığı parsing

```text
TBK 18-21
TBK 18 ila 21
CMK 100 ila 102
İİK 82 ila 84
```

### 4. “Ve devamı” parsing

```text
TBK 18 ve devamı
CMK 100 ve devamı
İYUK 1 ve devamı
Avukatlık Kanunu 1 ve devamı
```

### 5. Bağlamsal madde çözümü

```text
User: TBK 49
User: bu Kanunun 48 ila 52
```

çözümü:

```text
6098 sayılı Kanun madde 48-52
```

Ayrıca:

```text
önceki madde
sonraki madde
bu madde
```

gibi bağlamsal ifadeler de desteklenir.

---

## Özel Madde Tipleri

Sistem artık yalnızca normal `madde` değil, aşağıdaki özel tipleri de parse edip direct lookup ile getirebilir:

### Ek Madde

```text
Avukatlık Kanunu Ek Madde 1
İİK Ek Madde 1
İYUK Ek Madde 1
Tebligat Kanunu Ek Madde 1
```

### Geçici Madde

```text
Avukatlık Kanunu Geçici Madde 1
İİK Geçici Madde 1
İYUK Geçici Madde 1
Avukatlık Kanunu Geçici Madde 10
```

### Ek Geçici Madde

```text
Avukatlık Kanunu Ek Geçici Madde 1
```

### Mükerrer Madde

```text
Avukatlık Kanunu Mükerrer Madde 35
Avukatlık Kanunu Mükerrer Madde 27
```

İç temsilde mükerrer maddeler şu şekilde tutulur:

```text
35/A
27/A
```

---

## RAG Pipeline

```text
User Question
↓
resolve_contextual_article_question
↓
parse_explicit_article_refs
↓
parse_intra_article_refs
↓
direct article lookup
↓
semantic / keyword fallback
↓
previous article expansion
↓
reference graph expansion
↓
merge + ranking
↓
context build
↓
LLM answer or fallback
```

---

## Retrieval Source Türleri

| Source                | Açıklama                                 |
| --------------------- | ---------------------------------------- |
| direct_article_lookup | doğrudan kanun + madde                   |
| keyword               | keyword search sonucu                    |
| semantic              | semantic search sonucu                   |
| previous_article_ref  | önceki madde genişletmesi                |
| reference_graph       | madde referans ağı üzerinden gelen sonuç |

---

## Mevzuat Referans Graph

Madde içindeki açık referanslar çıkarılır ve `mevzuat_references` tablosunda tutulur.

Örnek:

```text
İş Kanunu 17
↓
18, 19, 20, 21
```

Script:

```bash
python extract_mevzuat_references.py
```

---

## LLM Quota Fallback

Gemini kotası dolduğunda sistem çökmez.

Fallback cevap mantığı:

```text
Otomatik cevap üretimi şu anda kullanılamıyor.
Ancak bulunan ilgili kaynaklar aşağıdadır:
```

Ardından bulunan mevzuat maddeleri gösterilir.

---

## Debug Retrieval

LLM kullanmadan retrieval test edilebilir.

```python
from chat.rag import debug_retrieve_mevzuat

print(debug_retrieve_mevzuat("İİK 82"))
print(debug_retrieve_mevzuat("CMK 100"))
print(debug_retrieve_mevzuat("TKHK 1"))
print(debug_retrieve_mevzuat("Avukatlık Kanunu Mükerrer Madde 35"))
print(debug_retrieve_mevzuat("TBK 2 birinci fıkra"))
```

---

## Test Altyapısı

### Active regression suite

Dosya:

```text
tests/retrieval_test_cases.json
```

Bu dosya active retrieval regression setidir.

Kapsadığı başlıca senaryolar:

* single article
* range
* devamı
* contextual range
* previous / next article
* ek madde
* geçici madde
* ek geçici madde
* mükerrer madde

### Test komutları

```bash
pytest tests/test_retrieval.py -q
python tests/run_retrieval_benchmark.py
```

---

## Güncel Sistem Durumu

Active regression sonuçları:

* `40 passed`
* benchmark `Top-1 accuracy: 37/37`
* benchmark `Top-docs coverage: 37/37`

Bu, retrieval çekirdeğinin regression açısından güçlü biçimde korunduğunu gösterir.

---

## Yüklü Kanunlar

Şu anda aktif kullanımda olan başlıca kanunlar:

* 1136 — Avukatlık Kanunu
* 2004 — İcra ve İflas Kanunu
* 2577 — İdari Yargılama Usulü Kanunu
* 4721 — Türk Medeni Kanunu
* 4857 — İş Kanunu
* 5237 — Türk Ceza Kanunu
* 5271 — Ceza Muhakemesi Kanunu
* 6098 — Türk Borçlar Kanunu
* 6100 — Hukuk Muhakemeleri Kanunu
* 6325 — Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu
* 6502 — Tüketicinin Korunması Hakkında Kanun
* 7036 — İş Mahkemeleri Kanunu
* 7201 — Tebligat Kanunu

---

## Bilinen Sınırlamalar

1. Bazı maddeler hâlâ tek blok metindir
   Bu nedenle fıkra ayrıştırma her kanunda aynı kalitede olmayabilir.

2. Bent parsing henüz yok

```text
a)
b)
c)
```

gibi yapılar henüz ayrı retrieval birimi değildir.

3. Karar retrieval ana güçlü katman değildir
   Sistem şu aşamada esas olarak mevzuat retrieval tarafında güçlüdür.

---

## Sonraki Yol Haritası

* bent parser
* `structured_content` v2
* karar retrieval / karar ranking iyileştirmesi
* kanunlar arası graph genişletme
* `rag.py` cleanup / refactor

---

## Not

`backfill_structured_content.py` ve `extract_mevzuat_references.py` asıl mevzuat metnini değiştirmek için değil, yardımcı veri üretmek için vardır:

* `icerik` = asıl resmi madde metni
* `structured_content` = fıkra ayrıştırma sonucu
* `mevzuat_references` = madde referans ağı

Asıl otorite her zaman `icerik` alanıdır.

