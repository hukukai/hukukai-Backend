# HukukAI Backend

Django REST API — Türk hukuku için geliştirilmiş RAG (Retrieval Augmented Generation) sistemi.

---

# Kurulum

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

# .env Dosyası

```
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

# Çalıştırma

```bash
python manage.py runserver
```

Server:

```
http://127.0.0.1:8000
```

---

# Endpointler

| Method | URL             | Açıklama              |
| ------ | --------------- | --------------------- |
| POST   | /api/chat/      | SSE streaming chat    |
| POST   | /api/karar-ara/ | mevzuat + karar arama |

---

# Veri Yükleme

```bash
cd data
python embed_and_upload.py
```

---

# Structured Content (Fıkra Parsing)

Mevzuat maddeleri **structured_content** alanında fıkralara ayrılır.

Örnek:

```json
{
 "fikralar": {
   "1": "(1) ...",
   "2": "(2) ...",
   "3": "(3) ..."
 }
}
```

### Oluşturma

```bash
python backfill_structured_content.py
```

---

# Bağlamsal Fıkra Çözümü

Sistem yalnızca açık fıkra numaralarını değil bağlamsal fıkra referanslarını da çözer.

Örnekler:

```
birinci fıkra
ikinci fıkra
bu fıkra
önceki fıkra
yukarıdaki fıkralar
```

Debug statüleri:

| Status         | Açıklama                           |
| -------------- | ---------------------------------- |
| matched        | istenen fıkra bulundu              |
| partial_match  | çoğul fıkraların bir kısmı bulundu |
| not_structured | madde fıkralara ayrılamadı         |
| not_requested  | soru fıkra istemiyor               |

---

# RAG Pipeline

```
User Question
↓
explicit article parsing
↓
intra-article parsing
↓
contextual fikra resolution
↓
direct article lookup
↓
semantic search
↓
keyword search
↓
previous article expansion
↓
reference graph expansion
↓
context build
↓
LLM answer or fallback
```

---

# Retrieval Source Türleri

| Source                | Açıklama                     |
| --------------------- | ---------------------------- |
| direct_article_lookup | doğrudan kanun + madde       |
| semantic_or_keyword   | semantic veya keyword search |
| previous_article      | önceki madde                 |
| reference_graph       | madde referans ağı           |

---

# Fıkra Extraction Status

Debug çıktısında fıkra extraction durumu görünür.

| Status         | Açıklama                  |
| -------------- | ------------------------- |
| matched        | istenen fıkra bulundu     |
| partial_match  | bazı fıkralar bulundu     |
| not_structured | veri yeterince ayrışmamış |
| not_requested  | fıkra talebi yok          |

---

# Mevzuat Referans Graph

Kanun maddeleri içindeki referanslar çıkarılır.

Örnek:

```
İş Kanunu 17
↓
18, 19, 20, 21
```

Script:

```bash
python extract_mevzuat_references.py
```

---

# Debug Retrieval

LLM kullanmadan retrieval test edilebilir.

```python
from rag import debug_retrieve_mevzuat

print(debug_retrieve_mevzuat("İş Kanunu 17"))
print(debug_retrieve_mevzuat("TBK 2 birinci fıkra"))
```

---

# Mevcut Kanun Dataset

| Kanun                     | No   | Durum         |
| ------------------------- | ---- | ------------- |
| Türk Borçlar Kanunu       | 6098 | yüklü         |
| İş Kanunu                 | 4857 | yüklü         |
| Türk Ceza Kanunu          | 5237 | dataset hazır |
| Hukuk Muhakemeleri Kanunu | 6100 | dataset hazır |

---

# Not

`upload_mevzuat_json.py` scripti:

* mevzuatı DB’ye yükler
* structured_content üretir
* embedding oluşturur
* chunk tablosunu doldurur

Gemini kotası doluysa upload embedding aşamasında durabilir.

Bu durumda:

1️⃣ kod güncellenir
2️⃣ kota açılınca upload tekrar çalıştırılır
3️⃣ gerekirse backfill scripti çalıştırılır
