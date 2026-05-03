# HukukAI Backend

Django REST API — Türk hukuku için geliştirilmiş **retrieval-first, source-grounded RAG (Retrieval Augmented Generation)** sistemi.

HukukAI’nin temel amacı, kullanıcı sorusunu önce kaynak kontrollü biçimde çözmek, ilgili mevzuat / karar / belge kaynaklarını bulmak ve LLM’i yalnızca gerekli durumlarda, bulunan kaynaklara dayalı cevap üretimi için kullanmaktır.

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

LLM, kaynak bulunmadan hukuki değerlendirme üretmek için kullanılmaz. Gemini kotası dolsa veya cevap üretimi başarısız olsa bile sistem **deterministic RAG / retrieval-only fallback** ile çalışmaya devam eder.

---

## Temel Tasarım İlkesi

HukukAI bir genel amaçlı chatbot değildir.

Sistem şu ilkeye göre tasarlanır:

```text
Önce kaynak bul.
Kaynak yoksa hukuki cevap üretme.
Karar yoksa içtihat uydurma.
Mevzuat karar yerine gösterilmez.
Belge istenirse güvenli şablon üret.
LLM cevabı kaynak doğrulamasından geçmezse kullanıcıya gösterme.
```

Bu nedenle sistemde ana güvenlik katmanları vardır:

1. **Retrieval-first mimari**
2. **Deterministic RAG cevap yolları**
3. **Production safety gate**
4. **Answer validator**
5. **Source-strict fallback**
6. **Safe document template**
7. **Karar / içtihat hallucination guard**
8. **RAG mode logging**

---

## Teknoloji Stack

- **Backend:** Django + Django REST Framework
- **Vector DB:** Supabase PostgreSQL + pgvector
- **LLM Provider:** Google Gemini API
- **Embedding Model:** `gemini-embedding-001`
- **Stable Chat Model:** `gemini-2.5-flash`
- **Streaming:** SSE (Server-Sent Events)
- **Test:** pytest + pytest-django

---

## Model Ayrımı

Sistemde iki farklı Gemini modeli kullanılır:

| Amaç | Model | Açıklama |
|---|---|---|
| Embedding / vector search | `gemini-embedding-001` | Mevzuat ve sorgu metinlerini vektöre çevirir |
| Chat / cevap üretimi | `gemini-2.5-flash` | Bulunan kaynaklara göre kullanıcı cevabı üretir |

Embedding modeli ile chat modeli farklıdır.

Embedding modeli değiştirilirse mevcut vektörlerin yeniden üretilmesi gerekebilir. Bu nedenle production ortamında embedding modeli dikkatle değiştirilmelidir.

Chat modeli `.env` üzerinden ayarlanır:

```env
GEMINI_CHAT_MODEL=gemini-2.5-flash
```

---

## LLM Kullanım Stratejisi

HukukAI’de LLM her soruda çağrılmaz.

Aşağıdaki sorgu tipleri LLM’e gitmeden deterministic cevaplanır:

```text
TBK 49
TBK 49'u iki cümleyle açıkla
TBK 49 kısaca açıkla
TBK 49 metnini aynen ver
TBK 49 kaç fıkra?
TBK 49 birinci fıkra
TBK 49 içinde illiyet bağı geçiyor mu?
TBK 49 hakkında karar var mı?
karar ara
2022/585 kararını bul
TBK 49 dayalı ihtarname hazırla
```

LLM yalnızca gerçekten kaynaklara dayalı açıklama / sentez / analiz gerektiğinde kullanılır.

Bu stratejinin amacı:

- Gemini ücretsiz kota tüketimini azaltmak
- cevap süresini iyileştirmek
- halüsinasyon riskini düşürmek
- kaynak dışı hukuki yorum üretimini engellemek

---

## Kurulum

Backend kök dizininde:

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\activate
```

Paketleri yükle:

```bash
pip install -r requirements.txt
```

`.env.example` dosyasını `.env` olarak kopyala:

```powershell
copy .env.example .env
```

`.env` içindeki değerleri doldur.

Django kontrolü:

```bash
python manage.py check
```

Migration:

```bash
python manage.py migrate
```

Test:

```bash
pytest tests/test_api_contract.py tests/test_answer_safety.py tests/test_retrieval.py -q
```

Çalıştırma:

```bash
python manage.py runserver
```

Server:

```text
http://127.0.0.1:8000
```

---

## `requirements.txt`

Backend için temiz production/dev dependency listesi kullanılır.

Temel paketler:

```txt
Django==6.0.3
djangorestframework==3.16.1
django-cors-headers==4.9.0
djangorestframework_simplejwt==5.5.1

python-dotenv==1.2.2
dj-database-url==3.1.2

psycopg==3.3.4
psycopg-binary==3.3.4

supabase==2.28.0
google-genai==1.66.0

requests==2.32.5

pytest==9.0.2
pytest-django==4.12.0
```

Not: `pip freeze` çıktısı doğrudan kullanılmaz; venv içinde gereksiz paketler bulunabilir. `requirements.txt` bilinçli olarak sade tutulur.

---

## `.env` Dosyası

`.env.example` örnek dosyası:

```env
# Django
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS / CSRF
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://localhost:3000
CORS_ALLOW_CREDENTIALS=True
CORS_ALLOW_ALL_ORIGINS=False

# Google Gemini
GOOGLE_API_KEY=your-google-api-key

# Stable target chat model for HukukAI
# Free tier quota may be limited; deterministic RAG paths reduce model usage.
GEMINI_CHAT_MODEL=gemini-2.5-flash

# Supabase API client
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-supabase-key

# Django database
# Use Supabase PostgreSQL connection string.
# For IPv4-only environments, prefer Supabase Session Pooler.
DATABASE_URL=postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@aws-1-eu-west-1.pooler.supabase.com:5432/postgres

# Production / proxy security
# Local development should normally keep these disabled.
# Enable them in production behind HTTPS.
USE_X_FORWARDED_PROTO=False
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
```

Production’da `DEBUG=False`, güvenli `SECRET_KEY`, gerçek host ve HTTPS ayarları kullanılmalıdır.

---

## Database / Supabase

Backend Django default database olarak PostgreSQL kullanır.

Local ve production için Supabase PostgreSQL connection string kullanılabilir.

IPv4-only ortamlarda Supabase **Session Pooler** connection string tercih edilebilir:

```env
DATABASE_URL=postgresql://postgres.PROJECT_REF:YOUR_PASSWORD@aws-1-eu-west-1.pooler.supabase.com:5432/postgres
```

Supabase API client için ayrıca:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-supabase-key
```

kullanılır.

Bu iki yapı farklı amaçlara hizmet eder:

| Ayar | Kullanım |
|---|---|
| `DATABASE_URL` | Django ORM / migration / default database |
| `SUPABASE_URL` + `SUPABASE_KEY` | Supabase client ile tablo sorguları / retrieval |

---

## Endpointler

| Method | URL | Açıklama |
|---|---|---|
| POST | `/api/chat/` | Mevzuat retrieval + karar intent + deterministic/LLM/fallback cevap |
| POST | `/api/karar-ara/` | Karar odaklı güvenli arama endpointi |
| POST | `/api/editor/` | Belge / editör destek endpointi |

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

## `/api/karar-ara/` Request Formatı

```json
{
  "query": "TBK 49 hakkında karar var mı?"
}
```

Bu endpoint karar arama UI / listeleme ekranı için kullanılır.

Güvenlik davranışları:

| Sorgu | Davranış |
|---|---|
| `karar ara` | Boş sonuç + daha somut sorgu isteği |
| `Yargıtay karar ara` | Boş sonuç + daha somut sorgu isteği |
| `2022/585 kararını bul` | Sadece karar tablosu aranır, mevzuat dönmez |
| `TBK 49 hakkında karar var mı?` | Sadece karar tablosu aranır, mevzuat karara alternatif gösterilmez |

Örnek güvenli response:

```json
{
  "results": [],
  "mevzuat": [],
  "kararlar": [],
  "toplam": 0,
  "fallback": false,
  "karar_only": true,
  "message": "Karar/içtihat odaklı arama yapıldı. Bu endpointte mevzuat sonuçları karara alternatif olarak gösterilmez."
}
```

---

## PowerShell Test Örneği

Chat endpoint:

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

Karar arama endpoint:

```powershell
$body = @{
  query = "TBK 49 hakkında karar var mı?"
} | ConvertTo-Json -Compress

Invoke-WebRequest `
  -UseBasicParsing `
  -Uri "http://127.0.0.1:8000/api/karar-ara/" `
  -Method POST `
  -ContentType "application/json; charset=utf-8" `
  -Body $body |
  Select-Object -ExpandProperty Content
```

PowerShell’de Türkçe karakterler bozuk görünürse:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## API Input Limitleri

Production safety için request inputları backend seviyesinde sınırlandırılır.

| Alan | Limit |
|---|---:|
| `question` | 5000 karakter |
| `query` | 1000 karakter |
| `history` | son 20 mesaj |
| `history[].content` | 4000 karakter |
| `doc_content` | 20000 karakter |

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

### `mevzuat_chunks` tablosu

Mevzuat semantic retrieval için chunk ve embedding verisi tutar.

Tipik alanlar:

```text
id
mevzuat_id
chunk_text
chunk_index
embedding
```

### `kararlar` tablosu

Karar retrieval için ayrılmış tablodur.

Mevcut aşamada tablo vardır ancak karar verisi henüz yüklenmemiş olabilir.

Tipik hedef alanlar:

```text
id
mahkeme
daire
esas_no
karar_no
tarih
baslik
icerik
embedding
```

Karar verisi yoksa sistem karar / içtihat uydurmaz.

---

## `structured_content` Formatı

Madde içindeki fıkraları ve bentleri ayrıştırmak için kullanılır.

Basit format:

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

- mevzuatı `mevzuat` tablosuna yükler
- chunk üretir
- embedding oluşturur
- chunk tablosunu doldurur

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

| Status | Açıklama |
|---|---|
| `matched` | İstenen fıkra bulundu |
| `partial_match` | İstenen fıkra/bent kısmen bulundu |
| `not_structured` | Veri yeterince ayrışmadı |
| `not_requested` | Soru fıkra istemiyor |

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
deterministic RAG checks
↓
karar intent / karar gate
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
LLM answer if needed
↓
answer validator
↓
source-strict fallback / safe document template
```

---

## Deterministic RAG Cevapları

Aşağıdaki cevaplar LLM’e gitmeden üretilir.

### Çıplak madde sorgusu

```text
TBK 49
```

Cevap:

```text
Kısa cevap:

Türk Borçlar Kanunu Madde 49, madde metnine göre şu hükmü içerir: ...
```

### Basit açıklama

```text
TBK 49'u iki cümleyle açıkla
TBK 49 kısaca açıkla
```

Sadece madde metnine dayalı kısa cevap döner.

### Madde metni

```text
TBK 49 metnini aynen ver
TBK 49 lafzını göster
```

Madde metni doğrudan döner.

### Fıkra sayısı

```text
TBK 49 kaç fıkra?
```

`structured_content.fikralar` üzerinden cevaplanır.

### Belirli fıkra

```text
TBK 49 birinci fıkra
TBK 49 2. fıkra
```

Sadece ilgili fıkra döner.

### Madde içinde ifade arama

```text
TBK 49 içinde illiyet bağı geçiyor mu?
TBK 49 metninde kusurlu var mı?
```

Sadece madde lafzında arama yapılır.

Örnek:

```text
Hayır. Türk Borçlar Kanunu Madde 49 metninde “illiyet bağı” ifadesi açıkça geçmez.
```

Bu cevap yalnızca madde lafzına ilişkindir; doktrin, içtihat veya uygulama değerlendirmesi yapılmaz.

### Karar yok cevabı

```text
TBK 49 hakkında karar var mı?
```

Karar tablosunda kaynak yoksa:

```text
Bu konuda veritabanımda ilgili karar/içtihat kaynağı bulunamadı.
Karar kaynağı bulunmadığı için Yargıtay, Danıştay veya emsal karar değerlendirmesi yapamam.
```

---

## Retrieval Source Türleri

| Source | Açıklama |
|---|---|
| `direct_article_lookup` | Doğrudan kanun + madde |
| `direct_yonetmelik_lookup` | Doğrudan yönetmelik + madde |
| `keyword` | Keyword search sonucu |
| `semantic` | Semantic search sonucu |
| `previous_article_ref` | Önceki madde genişletmesi |
| `reference_graph` | Madde referans ağı üzerinden gelen sonuç |

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

- cevap boş mu
- kaynak var mı
- karar kaynağı yokken Yargıtay / Danıştay / AYM / emsal karar ifadeleri kullanılmış mı
- cevapta izinli kaynak atfı var mı
- cevapta kullanılan mevzuat atfı retrieved kaynaklarla uyumlu mu
- kaynak metninde bulunmayan bazı riskli teknik terimler eklenmiş mi

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
Kısa cevap:

Türk Borçlar Kanunu Madde 49, madde metnine göre şu hükmü içerir:
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

- Apilex benzeri sade belge formatı
- kaynak dışı usul/sonuç eklenmesini önlemek
- kısa belge isteklerinde kullanıcı sınırına uymak
- üretimin LLM davranışına bağlı kalmaması

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

## Karar / İçtihat Güvenliği

Şu an karar tablosunda veri bulunmayabilir.

Bu durumda sistem:

- karar uydurmaz
- Yargıtay / Danıştay değerlendirmesi yapmaz
- mevzuatı karar yerine göstermez
- kullanıcıdan daha somut sorgu ister veya karar bulunamadığını söyler

Örnek:

```text
TBK 49 hakkında Yargıtay kararı var mı?
```

Cevap:

```text
Bu konuda veritabanımda ilgili karar/içtihat kaynağı bulunamadı.
Karar kaynağı bulunmadığı için Yargıtay, Danıştay veya emsal karar değerlendirmesi yapamam.
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

Ancak birçok temel sorgu artık LLM’e gitmeden deterministic cevaplandığı için Gemini kotası daha az kullanılır.

---

## RAG Mode Logging

Backend terminalinde hangi cevap yolunun çalıştığını görmek için `RAG_MODE` logları kullanılır.

Örnek loglar:

```text
RAG_MODE=deterministic_plain_article_lookup question='TBK 49'
RAG_MODE=deterministic_article_text_contains question='TBK 49 içinde illiyet bağı geçiyor mu?'
RAG_MODE=deterministic_no_karar question='TBK 49 hakkında karar var mı?'
RAG_MODE=deterministic_generic_karar_search question='karar ara'
RAG_MODE=deterministic_document_template question='TBK 49 dayalı ihtarname hazırla'
RAG_MODE=deterministic_article_brief_explanation question="Haksız fiil sorumluluğunu TBK 49'a göre açıkla"
RAG_MODE=llm_generation question='...' extra={'model': 'gemini-2.5-flash'}
```

Bu loglar kullanıcıya dönmez; yalnızca debug, maliyet ve kalite kontrolü içindir.

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

- single article
- range
- devamı
- contextual range
- previous / next article
- ek madde
- geçici madde
- ek geçici madde
- mükerrer madde
- yönetmelik lookup
- fıkra / bent extraction
- ranking / coverage

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

- belge isteği detection
- safe ihtarname template
- source-strict fallback
- standart hukuki uyarının otomatik eklenmesi
- kaynak dışı terimlerin engellenmesi
- kısa TBK atıf formatlarının kabulü
- karar yokken içtihat / Yargıtay yorumu reddi
- kaynak atfı yoksa cevabın reddi
- lafzi madde metni kontrolü
- madde metnini aynen verme
- fıkra sayısı
- belirli fıkra
- basit madde açıklaması
- çıplak madde sorgusu

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

- `/api/chat/` yalnızca `question` alanını kabul eder
- `message` veya `soru` alanları chat sorusu olarak kabul edilmez
- boş `question` 400 döner
- 5000 karakterden uzun `question` 400 döner
- `history` liste değilse 400 döner
- `history` en fazla son 20 mesajla sınırlandırılır
- her history mesajı en fazla 4000 karaktere kırpılır
- `/api/chat/` SSE response döner
- `/api/karar-ara/` boş ve uzun query değerlerini reddeder
- `/api/karar-ara/` generic karar aramasında mevzuat fallback yapmaz
- `/api/karar-ara/` salt karar numarası sorgusunda mevzuat döndürmez
- `/api/karar-ara/` karar intent sorgusunda yalnızca karar arar
- `/api/editor/` boş soru ve 20000 karakterden uzun belge içeriğini reddeder

Çalıştırma:

```bash
pytest tests/test_api_contract.py -q
```

---

### Tüm Aktif Testler

```bash
pytest tests/test_api_contract.py tests/test_answer_safety.py tests/test_retrieval.py -q
```

Güncel aktif sonuç:

```text
147 passed, 3 warnings
```

Test dağılımı:

```text
tests/test_api_contract.py
13 passed

tests/test_answer_safety.py
37 passed

tests/test_retrieval.py
97 passed

combined
147 passed
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

Önceki benchmark sonucu:

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

- 1136 — Avukatlık Kanunu
- 2004 — İcra ve İflas Kanunu
- 2577 — İdari Yargılama Usulü Kanunu
- 4721 — Türk Medeni Kanunu
- 4857 — İş Kanunu
- 5237 — Türk Ceza Kanunu
- 5271 — Ceza Muhakemesi Kanunu
- 6098 — Türk Borçlar Kanunu
- 6100 — Hukuk Muhakemeleri Kanunu
- 6325 — Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu
- 6502 — Tüketicinin Korunması Hakkında Kanun
- 7036 — İş Mahkemeleri Kanunu
- 7201 — Tebligat Kanunu

Ayrıca bazı yönetmelik kaynakları da desteklenir.

---

## Bilinen Sınırlamalar

1. Bazı maddeler hâlâ tek blok metindir. Bu nedenle fıkra ayrıştırma her kanunda aynı kalitede olmayabilir.

2. Bent parsing desteklenmeye başlamıştır ancak tüm kanunlarda aynı doğrulukta değildir. `structured_content` kalitesi belgeye göre değişebilir.

3. Karar tablosu vardır ancak henüz yeterli karar verisi yüklenmemiş olabilir. Sistem bu durumda karar uydurmaz.

4. Belge üretimi için şu an ihtarname odaklı güvenli template vardır. Dilekçe, sözleşme, protokol, KVKK metni gibi belge türleri için ayrı deterministic template motoru geliştirilmelidir.

5. API production güvenliği ayrıca güçlendirilmelidir. Auth, rate limit, request size limit, CORS kısıtları ve audit logging production öncesi tamamlanmalıdır.

6. Answer validator bilinçli olarak dar bir riskli terim listesiyle başlar. Aşırı agresif yapılırsa doğru cevapları da kesebilir. Bu nedenle yeni terimler testle eklenmelidir.

---

## Sonraki Yol Haritası

### Retrieval

- `structured_content` v2
- bent parser iyileştirmesi
- kanunlar arası graph genişletme
- yönetmelik coverage artırımı
- ranking refactor
- deterministic RAG kapsamını genişletme

### Karar / İçtihat

- karar metadata normalize
- mahkeme / daire / esas / karar / tarih alanları
- karar paragraf chunking
- mevzuat maddesiyle karar eşleştirme
- “en güncel karar” sorguları için tarih bazlı ranking
- karar bulunamadığında güvenli cevap standardı

### Belge Modu

- ihtarname template motoru genişletme
- dava dilekçesi template
- cevap dilekçesi template
- sözleşme maddesi template
- KVKK aydınlatma metni template
- editöre aktar / indir çıktısı
- belge türü bazlı validator

### Production Hardening

- auth / user bazlı erişim
- API rate limit
- query logging
- answer audit
- source usage audit
- error monitoring
- CORS production ayarı
- deployment checklist

---

## Not

`backfill_structured_content.py` ve `extract_mevzuat_references.py` asıl mevzuat metnini değiştirmek için değil, yardımcı veri üretmek için vardır:

- `icerik` = asıl resmi madde metni
- `structured_content` = fıkra / bent ayrıştırma sonucu
- `mevzuat_references` = madde referans ağı

Asıl otorite her zaman `icerik` alanıdır.

---

## Hukuki Uyarı

HukukAI tarafından üretilen cevaplar genel hukuki bilgi niteliğindedir.

Sistem kaynak kontrollü çalışacak şekilde tasarlanmış olsa da, üretilen içerikler bağlayıcı hukuki görüş veya avukatlık hizmeti yerine geçmez. Somut dosya bakımından uzman bir avukattan görüş alınmalıdır.