from google import genai
from google.genai import types
from supabase import create_client
from dotenv import load_dotenv
import os
import re

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not GOOGLE_API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("GOOGLE_API_KEY, SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

client = genai.Client(api_key=GOOGLE_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EMBED_DIM = 1536
EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """
Sen HukukAI, Türk hukuku uzmanı bir yapay zeka asistanısın.

KESİN KURALLAR:
1. SADECE aşağıdaki KAYNAKLAR bölümündeki bilgilere dayan.
2. Her iddianda kaynak belirt: [Kanun Adı Md.X] veya [Mahkeme - Daire - Esas/Karar No]
3. Kaynaklarda bilgi yoksa: "Bu konuda veritabanımda yeterli kaynak bulunamadı." de.
4. Cevap formatı:
   → Hukuki değerlendirme (2-3 paragraf)
   → Dayandığı kaynaklar (liste)
   → Pratik öneri
5. Sonunda şunu ekle: "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
"""

# "yukarıdaki madde" tarzı referansları yakalamak için basit patternler
PREVIOUS_ARTICLE_PATTERNS = [
    r"\byukarıdaki maddede\b",
    r"\byukarıdaki madde\b",
    r"\bönceki maddede\b",
    r"\bönceki madde\b",
    r"\bbir üst maddede\b",
    r"\bbir üst madde\b",
]

# İleride genişletmek için burada tutuyoruz
INTRA_ARTICLE_PATTERNS = [
    r"\bbirinci fıkra\b",
    r"\bikinci fıkra\b",
    r"\büçüncü fıkra\b",
    r"\bdördüncü fıkra\b",
    r"\byukarıdaki fıkra\b",
    r"\başağıdaki fıkra\b",
]


def embed_query(text: str) -> list:
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=(text or "")[:2000],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBED_DIM,
        ),
    )
    return result.embeddings[0].values


def embed_document(text: str) -> list:
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=(text or "")[:2000],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_DIM,
        ),
    )
    return result.embeddings[0].values


def search_mevzuat_chunks(embedding: list, count=5):
    """
    mevzuat_chunks tablosunda semantic arama yapar.
    match_mevzuat_chunks RPC fonksiyonuna dayanır.
    """
    try:
        res = supabase.rpc(
            "match_mevzuat_chunks",
            {
                "query_embedding": embedding,
                "match_count": count,
            },
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"Mevzuat chunk arama hatası: {e}")
        return []


def get_mevzuat_by_ids(ids: list[int]):
    if not ids:
        return []

    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik")
            .in_("id", ids)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Mevzuat kayıt çekme hatası: {e}")
        return []


def get_mevzuat_by_article(kanun_no: str, madde_no: str, madde_tipi: str = "madde"):
    """
    Aynı kanundaki belirli maddeyi çeker.
    """
    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik")
            .eq("kanun_no", str(kanun_no))
            .eq("madde_no", str(madde_no))
            .eq("madde_tipi", madde_tipi)
            .limit(1)
            .execute()
        )
        data = res.data or []
        return data[0] if data else None
    except Exception as e:
        print(f"Tekil mevzuat çekme hatası: {e}")
        return None


def search_mevzuat(embedding: list, count=8):
    chunks = search_mevzuat_chunks(embedding, count)

    if not chunks:
        return []

    best_chunks_by_doc = {}

    for c in chunks:
        mevzuat_id = c.get("mevzuat_id")
        similarity = c.get("similarity") or 0

        if not mevzuat_id:
            continue

        current = best_chunks_by_doc.get(mevzuat_id)
        if current is None or similarity > (current.get("similarity") or 0):
            best_chunks_by_doc[mevzuat_id] = c

    mevzuat_ids = list(best_chunks_by_doc.keys())
    full_docs = get_mevzuat_by_ids(mevzuat_ids)
    full_docs_map = {doc["id"]: doc for doc in full_docs}

    results = []

    sorted_best_chunks = sorted(
        best_chunks_by_doc.values(),
        key=lambda x: x.get("similarity") or 0,
        reverse=True
    )

    for c in sorted_best_chunks:
        mevzuat_id = c.get("mevzuat_id")
        full_doc = full_docs_map.get(mevzuat_id)

        if not full_doc:
            continue

        results.append({
            "id": full_doc.get("id"),
            "kanun_no": full_doc.get("kanun_no"),
            "kanun_adi": full_doc.get("kanun_adi"),
            "madde_no": full_doc.get("madde_no"),
            "madde_tipi": full_doc.get("madde_tipi"),
            "icerik": full_doc.get("icerik"),
            "chunk_text": c.get("chunk_text", ""),
            "similarity": c.get("similarity"),
            "chunk_index": c.get("chunk_index"),
        })

    return results


def search_kararlar(embedding: list, count=5):
    try:
        res = supabase.rpc(
            "match_kararlar",
            {
                "query_embedding": embedding,
                "match_count": count,
            },
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"Karar arama hatası: {e}")
        return []


def keyword_search_mevzuat(query: str, count=8):
    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik")
            .ilike("icerik", f"%{query}%")
            .limit(count)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Keyword mevzuat arama hatası: {e}")
        return []


def _normalize_doc(doc: dict) -> dict:
    """
    Semantic search sonucu ile keyword search sonucu aynı formatta olsun.
    """
    return {
        "id": doc.get("id"),
        "kanun_no": doc.get("kanun_no"),
        "kanun_adi": doc.get("kanun_adi"),
        "madde_no": doc.get("madde_no"),
        "madde_tipi": doc.get("madde_tipi", "madde"),
        "icerik": doc.get("icerik", ""),
        "chunk_text": doc.get("chunk_text", ""),
        "similarity": doc.get("similarity"),
        "chunk_index": doc.get("chunk_index"),
    }


def _doc_key(doc: dict) -> tuple:
    return (
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def merge_mevzuat_docs(primary_docs: list, extra_docs: list, limit: int = 12) -> list:
    """
    Duplicate'leri kaldırarak listeyi birleştirir.
    """
    merged = []
    seen = set()

    for doc in primary_docs + extra_docs:
        if not doc:
            continue

        normalized = _normalize_doc(doc)
        key = _doc_key(normalized)

        if key in seen:
            continue

        seen.add(key)
        merged.append(normalized)

        if len(merged) >= limit:
            break

    return merged


def detect_previous_article_reference(text: str) -> bool:
    text = (text or "").lower()
    return any(re.search(pattern, text) for pattern in PREVIOUS_ARTICLE_PATTERNS)


def expand_previous_article_refs(mevzuat_docs: list, max_extra_docs: int = 4) -> list:
    """
    'yukarıdaki maddede' gibi referans varsa bir önceki maddeyi ekler.
    Şimdilik sadece numerik normal 'madde' tipinde çalışır.
    """
    extras = []
    seen = {_doc_key(doc) for doc in mevzuat_docs}

    for doc in mevzuat_docs:
        icerik = doc.get("icerik", "")
        if not detect_previous_article_reference(icerik):
            continue

        madde_tipi = doc.get("madde_tipi")
        madde_no = str(doc.get("madde_no") or "").strip()
        kanun_no = str(doc.get("kanun_no") or "").strip()

        # Şimdilik sadece "madde 110 -> 109" gibi düz numerik senaryo
        if madde_tipi != "madde" or not madde_no.isdigit():
            continue

        prev_madde_no = str(int(madde_no) - 1)
        if int(prev_madde_no) <= 0:
            continue

        prev_doc = get_mevzuat_by_article(
            kanun_no=kanun_no,
            madde_no=prev_madde_no,
            madde_tipi="madde",
        )

        if not prev_doc:
            continue

        normalized_prev = _normalize_doc(prev_doc)
        prev_key = _doc_key(normalized_prev)

        if prev_key in seen:
            continue

        seen.add(prev_key)
        extras.append(normalized_prev)

        if len(extras) >= max_extra_docs:
            break

    return extras


def build_context(mevzuat_docs: list, karar_docs: list) -> str:
    context_parts = []

    for m in mevzuat_docs:
        kanun_adi = m.get("kanun_adi", "Kanun")
        madde_no = m.get("madde_no", "?")
        madde_tipi = m.get("madde_tipi", "madde")
        icerik = m.get("icerik", "")

        if madde_tipi == "madde":
            label = f"{kanun_adi} Madde {madde_no}"
        else:
            label = f"{kanun_adi} {madde_tipi} {madde_no}"

        context_parts.append(f"[{label}]\n{icerik}")

    for k in karar_docs:
        daire = k.get("daire", "Mahkeme")
        esas_no = k.get("esas_no", "?")
        karar_no = k.get("karar_no", "?")
        icerik = k.get("icerik", "")
        context_parts.append(f"[{daire} - {esas_no} / {karar_no}]\n{icerik}")

    if not context_parts:
        return "Veritabanında henüz kaynak bulunmamaktadır."

    return "\n\n---\n\n".join(context_parts)


def build_gemini_history(history=None):
    if history is None:
        return []

    gemini_history = []

    for msg in history:
        role = "user" if msg.get("role") == "user" else "model"
        content = msg.get("content", "")

        gemini_history.append(
            types.Content(
                role=role,
                parts=[types.Part(text=content)],
            )
        )

    return gemini_history


def get_rag_response(question: str, history=None):
    history = history or []

    embedding = embed_query(question)

    # 1) Semantic retrieval
    semantic_mevzuat_docs = search_mevzuat(embedding, 8)

    # 2) Keyword fallback - semantic sonuç azsa veya soru çok açık metin içeriyorsa yardımcı olur
    keyword_mevzuat_docs = keyword_search_mevzuat(question, 4)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=semantic_mevzuat_docs,
        extra_docs=keyword_mevzuat_docs,
        limit=10,
    )

    # 3) Cross-reference expansion
    ref_docs = expand_previous_article_refs(mevzuat_docs, max_extra_docs=4)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=ref_docs,
        limit=12,
    )

    karar_docs = search_kararlar(embedding, 5)

    context = build_context(mevzuat_docs, karar_docs)
    gemini_history = build_gemini_history(history)

    full_system = SYSTEM_PROMPT + f"\n\nKAYNAKLAR:\n{context}"

    response = client.models.generate_content_stream(
        model=CHAT_MODEL,
        contents=gemini_history + [
            types.Content(role="user", parts=[types.Part(text=question)])
        ],
        config=types.GenerateContentConfig(
            system_instruction=full_system,
        ),
    )

    return response, mevzuat_docs, karar_docs