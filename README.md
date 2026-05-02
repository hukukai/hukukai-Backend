# HukukAI Backend

Django REST API — Türk hukuku için geliştirilmiş **retrieval-first, source-grounded RAG (Retrieval Augmented Generation)** sistemi.

HukukAI’nin temel amacı, kullanıcı sorusunu önce kaynak kontrollü biçimde çözmek, ilgili mevzuat / karar / belge kaynaklarını bulmak ve LLM’i yalnızca son aşamada, bulunan kaynaklara dayalı cevap üretimi için kullanmaktır.

Sistem özellikle Türk hukuku için:

- kanun
- madde
- madde aralığı
- “ve devamı” ifadesi
- bağlamsal madde atfı
- fıkra atfı
- bent atfı
- özel madde tipleri
- yönetmelik maddeleri
- madde içi referanslar
- karar / içtihat niyeti
- belge / ihtarname / dilekçe taslak niyeti

tespit ederek öncelikle **doğrudan mevzuat retrieval** yapar.

LLM, kaynak bulunmadan hukuki değerlendirme üretmek için kullanılmaz. Gemini kotası dolsa veya cevap üretimi başarısız olsa bile sistem **retrieval-only fallback** ile çalışmaya devam eder.

---

## Temel Tasarım İlkesi

HukukAI bir genel amaçlı chatbot değildir.

Sistem şu ilkeye göre tasarlanır:

```text
Önce kaynak bul.
Kaynak yoksa hukuki cevap üretme.
Karar yoksa içtihat uydurma.
Belge istenirse güvenli şablon üret.
LLM cevabı kaynak doğrulamasından geçmezse kullanıcıya gösterme.
````

Bu nedenle sistemde dört ana güvenlik katmanı vardır:

1. **Retrieval-first mimari**
2. **Production safety gate**
3. **Answer validator**
4. **Source-strict fallback / safe document template**

---

## Teknoloji Stack

* **Backend:** Django + Django REST Framework
* **Vector DB:** Supabase PostgreSQL + pgvector
* **LLM Provider:** Google Gemini API
* **Embedding Model:** `gemini-embedding-001`
* **Default Chat Model:** `gemini-2.5-flash-lite`
* **Streaming:** SSE (Server-Sent Events)
* **Test:** pytest + pytest-django

---

## Model Ayrımı

Sistemde iki farklı Gemini modeli kullanılır:

| Amaç                      | Model                   | Açıklama                                        |
| ------------------------- | ----------------------- | ----------------------------------------------- |
| Embedding / vector search | `gemini-embedding-001`  | Mevzuat ve sorgu metinlerini vektöre çevirir    |
| Chat / cevap üretimi      | `gemini-2.5-flash-lite` | Bulunan kaynaklara göre kullanıcı cevabı üretir |

Embedding modeli ile chat modeli farklıdır.

Embedding modeli değiştirilirse mevcut vektörlerin yeniden üretilmesi gerekebilir. Bu nedenle production ortamında embedding modeli dikkatle değiştirilmelidir.

---

## Kurulum

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## `requirements.txt`

Projede kullanılan temel paketler:

```txt
Django==6.0.3
djangorestframework
django-cors-headers
python-dotenv
supabase
google-genai
pytest
pytest-django==4.12.0
```

---

## `.env` Dosyası

```env
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

GEMINI_CHAT_MODEL=gemini-2.5-flash-lite
```

Opsiyonel:

```env
GEMINI_EMBED_MODEL=gemini-embedding-001
GEMINI_EMBED_DIM=1536
```

> Not: Mevcut kodda embedding modeli production tutarlılığı için `gemini-embedding-001` olarak korunur.

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

| Method | URL               | Açıklama                                              |
| ------ | ----------------- | ----------------------------------------------------- |
| POST   | `/api/chat/`      | Mevzuat retrieval + karar intent + LLM/fallback cevap |
| POST   | `/api/karar-ara/` | Karar / mevzuat arama endpointi                       |
| POST   | `/api/editor/`    | Belge / editör destek endpointi                       |

---

## `/api/chat/` Request Formatı

`/api/chat/` endpoint’i JSON içinde **`question`** alanını bekler.

Doğru kullanım:

```json
{
  "question": "TBK 49",
  "history": []
}
```

Yanlış kullanım:

```json
{
  "message": "TBK 49"
}
```

```json
{
  "soru": "TBK 49"
}
```

Bu alanlar endpoint tarafından chat sorusu olarak okunmaz.

---

## `/api/chat/` Response Formatı

Chat endpoint’i **SSE stream** döner.

Örnek response:

```text
data: {"type": "sources", "mevzuat": [...], "kararlar": [...], "all_sources": [...]}

data: {"type": "text", "content": "..."}

data: {"type": "done"}
```

Response content type:

```text
text/event-stream; charset=utf-8
```

SSE eventleri UTF-8 olarak encode edilir.

---

## PowerShell Test Örneği

```powershell
$body = @{
  question = "TBK 49"
} | ConvertTo-Json -Compress

Invoke-WebRequest `
  -UseBasicParsing `
  -Uri "http://127.0.0.1:8000/api/chat/" `
  -Method POST `
  -ContentType "application/json; charset=utf-8" `
  -Body $body |
  Select-Object -ExpandProperty Content
```

---

## API Input Limitleri

Production safety için request inputları backend seviyesinde sınırlandırılır.

| Alan                |          Limit |
| ------------------- | -------------: |
| `question`          |  5000 karakter |
| `query`             |  1000 karakter |
| `history`           |   son 20 mesaj |
| `history[].content` |  4000 karakter |
| `doc_content`       | 20000 karakter |

Geçersiz inputlarda API `400` döner.

Örnek:

```json
{
  "error": "Soru boş olamaz."
}
```

```json
{
  "error": "Soru en fazla 5000 karakter olabilir."
}
```

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

Madde içindeki fıkraları ve bentleri ayrıştırmak için kullanılır.

```json
{
  "fikralar": {
    "1": "...",
    "2": "...",
    "3": "..."
  }
}
```

Bazı maddelerde fıkralar dict formatında bentleri de içerebilir:

```json
{
  "fikralar": {
    "1": {
      "text": "...",
      "bentler": {
        "a": "...",
        "b": "..."
      }
    }
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

## Structured Content / Fıkra Parsing

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

### Fıkra Extraction Status

| Status           | Açıklama                          |
| ---------------- | --------------------------------- |
| `matched`        | İstenen fıkra bulundu             |
| `partial_match`  | İstenen fıkra/bent kısmen bulundu |
| `not_structured` | Veri yeterince ayrışmadı          |
| `not_requested`  | Soru fıkra istemiyor              |

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

çözüm:

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

Sistem yalnızca normal `madde` değil, aşağıdaki özel tipleri de parse edip direct lookup ile getirebilir.

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

## Yönetmelik Retrieval

Sistem bazı yönetmelik aliaslarını da çözebilir.

Örnekler:

```text
Mesafeli Sözleşmeler Yönetmeliği 5
Mesafeli Sözleşmeler Yön. 5
Elektronik Tebligat Yönetmeliği 10
Ticaret Sicili Yönetmeliği 1
```

Yönetmelik kaynakları `source_type = "yonetmelik"` olarak normalize edilir.

---

## RAG Pipeline

```text
User Question
↓
normalize_user_legal_query
↓
resolve_contextual_article_question
↓
parse_explicit_article_refs
↓
parse_intra_article_refs
↓
direct article lookup
↓
direct yönetmelik lookup
↓
semantic / keyword fallback
↓
previous article expansion
↓
reference graph expansion
↓
merge + ranking
↓
production safety gate
↓
safe document template check
↓
context build
↓
LLM answer
↓
answer validator
↓
source-strict fallback / safe document template
```

---

## Retrieval Source Türleri

| Source                     | Açıklama                                 |
| -------------------------- | ---------------------------------------- |
| `direct_article_lookup`    | Doğrudan kanun + madde                   |
| `direct_yonetmelik_lookup` | Doğrudan yönetmelik + madde              |
| `keyword`                  | Keyword search sonucu                    |
| `semantic`                 | Semantic search sonucu                   |
| `previous_article_ref`     | Önceki madde genişletmesi                |
| `reference_graph`          | Madde referans ağı üzerinden gelen sonuç |

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

## Production Safety Gate

HukukAI’de LLM her durumda çağrılmaz.

### Kaynak yoksa

Eğer mevzuat ve karar kaynağı bulunamazsa sistem LLM çağırmadan güvenli cevap döner:

```text
Bu konuda veritabanımda yeterli kaynak bulunamadı.
Kaynak bulunmadığı için hukuki değerlendirme yapamam.
```

### Karar / içtihat sorusu varsa ama karar yoksa

Kullanıcı Yargıtay, Danıştay, emsal karar veya içtihat sorarsa ve karar kaynağı bulunamazsa sistem LLM çağırmadan cevap döner:

```text
Bu konuda veritabanımda ilgili karar/içtihat kaynağı bulunamadı.
Karar kaynağı bulunmadığı için Yargıtay, Danıştay veya emsal karar değerlendirmesi yapamam.
```

Bu katman, karar kaynağı yokken içtihat uydurma riskini engeller.

---

## Answer Validator

LLM cevabı kullanıcıya gösterilmeden önce temel kaynak güvenlik doğrulamasından geçirilir.

Validator şunları kontrol eder:

* cevap boş mu
* kaynak var mı
* karar kaynağı yokken Yargıtay / Danıştay / AYM / emsal karar ifadeleri kullanılmış mı
* cevapta izinli kaynak atfı var mı
* cevapta kullanılan mevzuat atfı retrieved kaynaklarla uyumlu mu
* kaynak metninde bulunmayan bazı riskli teknik terimler eklenmiş mi

Desteklenen kaynak atıf formatları:

```text
Türk Borçlar Kanunu Madde 49
Türk Borçlar Kanunu Md. 49
Türk Borçlar Kanunu Md.49
TBK m. 49
TBK 49
6098 sayılı Kanun Madde 49
```

Kaynakta açıkça geçmiyorsa ilk aşamada reddedilen riskli terim grupları:

```text
illiyet bağı / nedensellik
faiz
zamanaşımı
hak düşürücü süre
arabuluculuk
görevli mahkeme
yetkili mahkeme
```

Validator başarısız olursa LLM cevabı kullanıcıya gösterilmez.

---

## Source-Strict Fallback

LLM cevabı validator’dan geçmezse sistem kullanıcıya doğrudan LLM çıktısını göstermez.

Örneğin retrieved kaynak yalnızca `Türk Borçlar Kanunu Madde 49` ise ve LLM cevapta kaynak metninde açıkça bulunmayan `illiyet bağı`, `faiz`, `zamanaşımı`, `arabuluculuk` gibi teknik unsurlar üretirse cevap reddedilir.

Bu durumda sistem “servis yoğun” mesajı yerine kaynak metnine dayalı deterministic kısa cevap döner:

```text
Kısa Cevap

Türk Borçlar Kanunu Madde 49 metnine göre:
[retrieved kaynak metni]

Dayandığı Kaynaklar:
- Türk Borçlar Kanunu Madde 49

Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.
```

Bu katman, sistemin kaynak dışına çıkan LLM cevaplarını güvenli biçimde ikame etmesini sağlar.

---

## Standart Hukuki Uyarı

Her kullanıcı cevabının sonunda backend tarafından şu uyarı garanti edilir:

```text
Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.
```

Bu uyarı yalnızca prompt’a bırakılmaz; backend `ensure_standard_disclaimer` katmanı ile otomatik ekler.

---

## Belge / İhtarname Modu

Sistem belge, dilekçe, ihtarname, sözleşme maddesi veya benzeri metin taleplerini tespit eder.

Örnek belge talepleri:

```text
TBK 49 dayalı 5 cümlelik kısa ihtarname hazırla
ihtarname örneği ver
dilekçe taslağı hazırla
sözleşme maddesi yaz
```

Basit / şablon belge isteklerinde sistem LLM’e bırakmadan **deterministic safe document template** döndürür.

Amaç:

* Apilex benzeri sade belge formatı
* kaynak dışı usul/sonuç eklenmesini önlemek
* kısa belge isteklerinde kullanıcı sınırına uymak
* üretimin LLM davranışına bağlı kalmaması

### Örnek Güvenli İhtarname Formatı

```text
İHTARNAME

İHTAR EDEN:
[Ad / Unvan]
[Adres]

MUHATAP:
[Ad / Unvan]
[Adres]

KONU:
Hukuka aykırı fiil nedeniyle doğan zararın giderilmesi talebidir.

AÇIKLAMALAR:
Tarafınızca gerçekleştirilen [olayın kısa açıklaması] nedeniyle [zarar gören kişi/şirket] zarara uğramıştır. Türk Borçlar Kanunu Madde 49 uyarınca, kusurlu ve hukuka aykırı bir fiille başkasına zarar veren kişi bu zararı gidermekle yükümlüdür. Bu nedenle [zarar tutarı / zarar kalemi] tutarındaki zararın işbu ihtarnamenin tebliğinden itibaren [süre] içinde giderilmesini talep ederiz.

SONUÇ VE İHTAR:
Belirtilen süre içinde zararın giderilmemesi halinde, yasal haklarımızı kullanacağımızı ihtaren bildiririz.

İHTAR EDEN / VEKİLİ
[Ad / Unvan]
[İmza]

Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.
```

Kaynakta yoksa belgeye şu tür bilgiler eklenmez:

```text
faiz
arabuluculuk
ihtiyati haciz
görevli mahkeme
yetkili mahkeme
dava şartı
vekalet ücreti
zamanaşımı
```

---

## LLM Quota / Generation Fallback

Gemini kotası dolduğunda veya LLM cevap üretimi başarısız olduğunda sistem çökmez.

Fallback cevap mantığı:

```text
Yanıt oluşturma servisi şu anda yoğun görünüyor.
Ama ilgili kaynakları senin için buldum:
```

Ardından bulunan mevzuat / karar kaynakları gösterilir.

Belge isteği varsa ve LLM cevabı validator’dan geçemezse, sistem düz kaynak fallback yerine güvenli belge şablonu döndürebilir.

LLM cevabı validator’dan geçemezse ama kaynak varsa, sistem “servis yoğun” demek yerine source-strict fallback döndürür.

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

### `pytest.ini`

Projede pytest-django için `pytest.ini` kullanılmalıdır:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings
python_files = tests.py test_*.py *_tests.py
```

---

### Retrieval Regression Suite

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
* yönetmelik lookup
* fıkra / bent extraction
* ranking / coverage

Çalıştırma:

```bash
pytest tests/test_retrieval.py -q
```

---

### Answer Safety Tests

Dosya:

```text
tests/test_answer_safety.py
```

Bu testler şunları korur:

* belge isteği detection
* safe ihtarname template
* source-strict fallback
* standart hukuki uyarının otomatik eklenmesi
* kaynak dışı terimlerin engellenmesi
* kısa TBK atıf formatlarının kabulü
* karar yokken içtihat / Yargıtay yorumu reddi
* kaynak atfı yoksa cevabın reddi

Çalıştırma:

```bash
pytest tests/test_answer_safety.py -q
```

---

### API Contract Tests

Dosya:

```text
tests/test_api_contract.py
```

Bu testler backend API sözleşmesini korur:

* `/api/chat/` yalnızca `question` alanını kabul eder
* `message` veya `soru` alanları chat sorusu olarak kabul edilmez
* boş `question` 400 döner
* 5000 karakterden uzun `question` 400 döner
* `history` liste değilse 400 döner
* `history` en fazla son 20 mesajla sınırlandırılır
* her history mesajı en fazla 4000 karaktere kırpılır
* `/api/chat/` SSE response döner
* `/api/karar-ara/` boş ve uzun query değerlerini reddeder
* `/api/editor/` boş soru ve 20000 karakterden uzun belge içeriğini reddeder

Çalıştırma:

```bash
pytest tests/test_api_contract.py -q
```

---

### Tüm Aktif Testler

```bash
pytest tests/test_api_contract.py tests/test_answer_safety.py tests/test_retrieval.py -q
```

---

## Güncel Sistem Durumu

Son aktif test sonuçları:

```text
tests/test_api_contract.py
10 passed

tests/test_answer_safety.py
12 passed

tests/test_retrieval.py
97 passed

combined
119 passed
```

Uyarılar:

```text
DeprecationWarning: google.genai / supabase package warnings
```

Bu warningler test başarısızlığı değildir; kullanılan paketlerden gelen deprecation uyarılarıdır.

---

## Benchmark

Retrieval benchmark komutu:

```bash
python tests/run_retrieval_benchmark.py
```

Önceki güncel benchmark sonucu:

```text
Total cases: 96
Resolved accuracy: 20/20
Intent accuracy: 1/1
Top-1 accuracy: 94/94
Top-docs coverage: 94/94
```

Bu sonuç retrieval çekirdeğinin regression açısından güçlü biçimde korunduğunu gösterir.

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

Ayrıca bazı yönetmelik kaynakları da desteklenir.

---

## Bilinen Sınırlamalar

1. Bazı maddeler hâlâ tek blok metindir.
   Bu nedenle fıkra ayrıştırma her kanunda aynı kalitede olmayabilir.

2. Bent parsing desteklenmeye başlamıştır ancak tüm kanunlarda aynı doğrulukta değildir.
   `structured_content` kalitesi belgeye göre değişebilir.

3. Karar retrieval henüz mevzuat retrieval kadar güçlü değildir.
   Sistem şu aşamada esas olarak mevzuat retrieval tarafında güçlüdür.

4. Belge üretimi için şu an ihtarname odaklı güvenli template vardır.
   Dilekçe, sözleşme, protokol, KVKK metni gibi belge türleri için ayrı deterministic template motoru geliştirilmelidir.

5. API production güvenliği ayrıca güçlendirilmelidir.
   Auth, rate limit, request size limit, CORS kısıtları ve audit logging production öncesi tamamlanmalıdır.

6. Answer validator bilinçli olarak dar bir riskli terim listesiyle başlar.
   Aşırı agresif yapılırsa doğru cevapları da kesebilir. Bu nedenle yeni terimler testle eklenmelidir.

---

## Sonraki Yol Haritası

### Retrieval

* `structured_content` v2
* bent parser iyileştirmesi
* kanunlar arası graph genişletme
* yönetmelik coverage artırımı
* ranking refactor

### Karar / İçtihat

* karar metadata normalize
* mahkeme / daire / esas / karar / tarih alanları
* karar paragraf chunking
* mevzuat maddesiyle karar eşleştirme
* “en güncel karar” sorguları için tarih bazlı ranking
* karar bulunamadığında güvenli cevap standardı

### Belge Modu

* ihtarname template motoru genişletme
* dava dilekçesi template
* cevap dilekçesi template
* sözleşme maddesi template
* KVKK aydınlatma metni template
* editöre aktar / indir çıktısı
* belge türü bazlı validator

### Production Hardening

* auth / user bazlı erişim
* API rate limit
* query logging
* answer audit
* source usage audit
* error monitoring
* CORS production ayarı
* deployment checklist

---

## Not

`backfill_structured_content.py` ve `extract_mevzuat_references.py` asıl mevzuat metnini değiştirmek için değil, yardımcı veri üretmek için vardır:

* `icerik` = asıl resmi madde metni
* `structured_content` = fıkra / bent ayrıştırma sonucu
* `mevzuat_references` = madde referans ağı

Asıl otorite her zaman `icerik` alanıdır.

---

## Hukuki Uyarı

HukukAI tarafından üretilen cevaplar genel hukuki bilgi niteliğindedir.
Sistem kaynak kontrollü çalışacak şekilde tasarlanmış olsa da, üretilen içerikler bağlayıcı hukuki görüş veya avukatlık hizmeti yerine geçmez. Somut dosya bakımından uzman bir avukattan görüş alınmalıdır.

