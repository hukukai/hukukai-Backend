---

# HukukAI Backend

Django REST API — Türk hukuku için geliştirilmiş **RAG (Retrieval Augmented Generation)** sistemi.

Sistem:

* mevzuat maddelerini
* madde içi fıkraları
* madde referanslarını
* semantic search
* fallback retrieval

birleştirerek hukuk sorularına cevap üretir.

---

# Temel Teknoloji Stack

| Katman     | Teknoloji                        |
| ---------- | -------------------------------- |
| Backend    | Django + Django REST             |
| Vector DB  | Supabase (PostgreSQL + pgvector) |
| LLM        | Google Gemini                    |
| Embedding  | gemini-embedding-001             |
| Chat Model | gemini-2.0-flash                 |
| Streaming  | SSE                              |

---

# Kurulum

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

# .env dosyası

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

---

# Endpointler

| Method | URL               | Açıklama               |
| ------ | ----------------- | ---------------------- |
| POST   | `/api/chat/`      | SSE streaming sohbet   |
| POST   | `/api/karar-ara/` | Mevzuat ve karar arama |

---

# Veri Yükleme

Kanun verileri JSON olarak yüklenir.

```bash
cd data/mevzuat
python upload_mevzuat_json.py 6098_tbk
```

---

# Structured Content (Fıkra Parsing)

Her madde için `structured_content` alanı oluşturulur.

Örnek:

```json
{
  "fikralar": {
    "1": "...",
    "2": "..."
  }
}
```

Bu sayede sistem şu sorguları anlayabilir:

```
TBK 2 birinci fıkra
İş Kanunu 17 ikinci fıkra
```

Backfill script:

```bash
python backfill_structured_content.py
```

---

# Mevzuat Reference Graph

Sistem artık maddeler arası referansları otomatik çıkarır.

Örnek:

```
İş Kanunu 17
→ 18
→ 19
→ 20
→ 21
→ 32
```

Bu referanslar şu tabloda saklanır:

```
mevzuat_references
```

Alanlar:

| Alan            | Açıklama                   |
| --------------- | -------------------------- |
| source_kanun_no | referansı yapan kanun      |
| source_madde_no | referansı yapan madde      |
| target_kanun_no | atıf yapılan kanun         |
| target_madde_no | atıf yapılan madde         |
| ref_type        | referans tipi              |
| raw_match       | metindeki orijinal eşleşme |

---

# Referans Extraction Script

Kanun içindeki madde atıflarını otomatik çıkarır.

```bash
python extract_mevzuat_references.py
```

Örnek yakalanan patternler:

```
18 inci madde
32 nci maddenin
18, 19, 20 ve 21 inci maddeleri
```

---

# RAG Pipeline

Sistem şu sırayla çalışır:

```
User Question
    ↓
explicit article parsing
    ↓
direct article lookup
    ↓
semantic retrieval
    ↓
previous article expansion
    ↓
reference graph expansion
    ↓
context build
    ↓
LLM
```

---

# Retrieval Source Türleri

Debug çıktısında retrieval kaynağı görülür.

| Tür                   | Açıklama                         |
| --------------------- | -------------------------------- |
| direct_article_lookup | Kullanıcı doğrudan madde sordu   |
| semantic_or_keyword   | semantic search sonucu           |
| reference_graph       | madde referans grafından eklendi |

---

# Gemini Quota Fallback

Gemini kotası dolarsa sistem çökmez.

Fallback mekanizması devreye girer ve sadece retrieval sonucu gösterilir:

```
Otomatik cevap üretimi şu anda kullanılamıyor.
Ancak bulunan ilgili kaynaklar aşağıdadır.
```

---

# Mevcut Kanun Dataset

Şu kanunlar sisteme yüklenmiştir:

| Kanun               | No   |
| ------------------- | ---- |
| Türk Borçlar Kanunu | 6098 |
| İş Kanunu           | 4857 |

Hazır dataset klasörleri:

```
data/mevzuat/
 4857_is_kanunu
 5237_tck
 6098_tbk
 6100_hmk
```

---

# Debug Retrieval

LLM kullanmadan retrieval test edilebilir:

```python
from rag import debug_retrieve_mevzuat

print(debug_retrieve_mevzuat("İş Kanunu 17"))
```

---

# Sistem Özellikleri

* kanun alias parsing
* madde parsing
* fıkra parsing
* structured law retrieval
* reference graph
* fallback response
* semantic + keyword retrieval

---

# Gelecek Geliştirmeler

Planlanan geliştirmeler:

* bent parsing `(a), (b), (c)`
* karar referans graph
* cross-law references
* doctrine dataset
* web fallback search

---

# Proje Amacı

Türk hukuk mevzuatını:

* semantic search
* madde referans grafı
* fıkra seviyesinde retrieval

ile analiz eden bir **legal AI backend** oluşturmak.

---

## Küçük tavsiye

README’nin en üstüne şunu da koymanı öneririm:

```
⚠️ This project is under active development.
```

---
