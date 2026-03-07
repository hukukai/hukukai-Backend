# HukukAI Backend

Django REST API — Türk hukuku RAG sistemi.

## Kurulum
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## .env dosyası
```
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Çalıştırma
```bash
python manage.py runserver
```

## Veri Yükleme
```bash
cd data
python embed_and_upload.py
```

## Endpointler

| Method | URL | Açıklama |
|--------|-----|----------|
| POST | /api/chat/ | SSE streaming sohbet |
| POST | /api/karar-ara/ | Mevzuat ve karar arama |