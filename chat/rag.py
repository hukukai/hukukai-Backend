from google import genai
from google.genai import types
from supabase import create_client
from dotenv import load_dotenv
import os
import re
import unicodedata

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
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").in_("id", ids)
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
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").eq("kanun_no",
                                                                                                    str(kanun_no))
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
            "structured_content": full_doc.get("structured_content"),
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
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").ilike("icerik",
                                                                                                       f"%{query}%")
            .limit(count)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Keyword mevzuat arama hatası: {e}")
        return []


LAW_ALIASES = {
    "tck": "5237",
    "türk ceza kanunu": "5237",
    "5237": "5237",
    "tbk": "6098",
    "türk borçlar kanunu": "6098",
    "6098": "6098",
    "cmk": "5271",
    "ceza muhakemesi kanunu": "5271",
    "5271": "5271",
    "tmk": "4721",
    "türk medeni kanunu": "4721",
    "4721": "4721",
    "iş kanunu": "4857",
    "4857": "4857",
}


def _canon_text(text: str) -> str:
    """
    Türkçe karakter / birleşik karakter sorunlarını azaltmak için
    metni normalize eder.
    """
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def normalize_law_name_to_no(text: str):
    text_c = _canon_text(text)

    for alias, kanun_no in LAW_ALIASES.items():
        alias_c = _canon_text(alias)
        if alias_c in text_c:
            return kanun_no

    return None


def parse_explicit_article_refs(question: str):
    """
    Kullanıcı sorusundan açık kanun/madde atıflarını yakalar.

    Desteklenen örnekler:
    - TCK 109
    - TCK m.109
    - 5237 sayılı Kanun 109
    - 5237 sayılı Kanun madde 110
    - madde 110
    - İş Kanunu 17
    - Türk Borçlar Kanunu 2
    - CMK 100
    """
    original_q = (question or "").strip()
    q = _canon_text(original_q)
    refs = []

    detected_kanun_no = normalize_law_name_to_no(original_q)

    # 1) Genel madde yazım varyasyonları:
    # "madde 110", "m.110", "m 110", "md 110", "17. madde", "madde no 110", "110 inci madde"
    general_article_patterns = [
        r"(?:m\.|m|md|madde)\s*(?:no\s*)?(\d+)\b",
        r"\b(\d+)\.\s*madde\b",
        r"\b(\d+)\s*(?:inci|nci|uncu|üncü)\s*madde\b",
        r"\b(\d+)\.\s*maddesi\b",
    ]

    for pattern in general_article_patterns:
        for match in re.finditer(pattern, q):
            madde_no = match.group(1)
            refs.append({
                "kanun_no": detected_kanun_no,
                "madde_no": madde_no,
                "madde_tipi": "madde",
            })

    # 2) "5237 sayılı Kanun 109" / "5237 sayılı Kanun madde 109"
    # Kanun numarası ile madde numarası arasında gerçek bir ayırıcı zorunlu olsun
    for match in re.finditer(
            r"\b(\d{3,4})\s+sayili\s+kanun\s*(?:m\.|madde)?\s*(\d+)\b",
            q
    ):
        kanun_no = match.group(1)
        madde_no = match.group(2)
        refs.append({
            "kanun_no": kanun_no,
            "madde_no": madde_no,
            "madde_tipi": "madde",
        })

    # 3) "TCK 109" / "TBK 1" / "CMK 100"
    for match in re.finditer(r"\b(tck|tbk|cmk|tmk)\s*(?:m\.|madde)?\s*(\d+)\b", q):
        alias = match.group(1)
        madde_no = match.group(2)
        kanun_no = LAW_ALIASES.get(alias)
        refs.append({
            "kanun_no": kanun_no,
            "madde_no": madde_no,
            "madde_tipi": "madde",
        })

    # 4) "iş kanunu 17" / "turk borclar kanunu 2" / "ceza muhakemesi kanunu 100"
    for alias, kanun_no in LAW_ALIASES.items():
        if alias.isdigit():
            continue

        alias_c = _canon_text(alias)
        pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.|madde)?\s*(\d+)\b"

        for match in re.finditer(pattern, q):
            madde_no = match.group(1)
            refs.append({
                "kanun_no": kanun_no,
                "madde_no": madde_no,
                "madde_tipi": "madde",
            })

    # duplicate temizle
    deduped = []
    seen = set()

    for ref in refs:
        key = (ref.get("kanun_no"), ref.get("madde_no"), ref.get("madde_tipi"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)

    return deduped


def debug_parse_explicit_article_refs(question: str):
    return {
        "question": question,
        "normalized_question": _canon_text(question),
        "refs": parse_explicit_article_refs(question),
    }


def parse_intra_article_refs(question: str):
    """
    Soru içindeki fıkra atıflarını yakalar.
    Şimdilik sadece tespit eder; henüz ayrı paragraf çekmez.
    """
    q = _canon_text(question)

    refs = []

    patterns = [
        (r"\bbirinci\s*fıkra\b", "1"),
        (r"\bikinci\s*fıkra\b", "2"),
        (r"\bucuncu\s*fıkra\b", "3"),
        (r"\bdorduncu\s*fıkra\b", "4"),
        (r"\byukarıdaki\s*fıkra\b", "previous"),
        (r"\byukarıdaki\s*fıkralar\b", "previous_plural"),
    ]

    for pattern, ref_value in patterns:
        if re.search(pattern, q):
            refs.append({
                "type": "fikra",
                "value": ref_value,
            })

    return refs


def debug_parse_intra_article_refs(question: str):
    return {
        "question": question,
        "normalized_question": _canon_text(question),
        "refs": parse_intra_article_refs(question),
    }


def extract_requested_fikra_text(article_text: str, intra_refs: list, structured_content: dict = None):
    """
    Tam madde metni içinden veya structured_content içinden istenen fıkrayı çıkarmaya çalışır.
    Önce structured_content'e bakar, bulamazsa eski regex fallback kullanır.
    """
    if not intra_refs:
        return None

    requested = None
    for ref in intra_refs:
        if ref.get("type") == "fikra" and ref.get("value") in {"1", "2", "3", "4"}:
            requested = ref.get("value")
            break

    if not requested:
        return None

    # 1) Önce structured_content'ten bak
    if structured_content and isinstance(structured_content, dict):
        fikralar = structured_content.get("fikralar", {})
        if isinstance(fikralar, dict):
            value = fikralar.get(requested)
            if value:
                return value

    # 2) Fallback: ham metinden ayırmayı dene
    text = (article_text or "").strip()
    parts = re.split(r"(\(\d+\))", text)

    if len(parts) < 3:
        return None

    fikra_map = {}
    current_no = None

    for part in parts:
        if re.fullmatch(r"\(\d+\)", part or ""):
            current_no = part.strip("()")
            fikra_map[current_no] = part
        else:
            if current_no:
                fikra_map[current_no] += part

    return fikra_map.get(requested)


def get_context_text_for_doc(doc: dict, question: str) -> str:
    """
    Context'e tam madde mi, yoksa istenen fıkra mı girecek onu belirler.
    """
    full_text = doc.get("icerik") or ""
    structured_content = doc.get("structured_content")
    intra_refs = parse_intra_article_refs(question)

    fikra_text = extract_requested_fikra_text(
        full_text,
        intra_refs,
        structured_content=structured_content,
    )

    if fikra_text:
        return fikra_text

    return full_text


def get_mevzuat_article(kanun_no: str, madde_no: str, madde_tipi: str = "madde"):
    """
    mevzuat tablosundan doğrudan madde çeker.
    Chunk olmasa bile çalışır.
    """
    if not kanun_no or not madde_no:
        return None

    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").eq("kanun_no",
                                                                                                    str(kanun_no))
            .eq("madde_no", str(madde_no))
            .eq("madde_tipi", madde_tipi)
            .limit(1)
            .execute()
        )

        data = res.data or []
        if not data:
            return None

        doc = data[0]
        doc["retrieval_source"] = "direct_article_lookup"
        return doc

    except Exception as e:
        print(f"Direct article lookup hatası: {e}")
        return None


def get_explicitly_requested_articles(question: str):
    refs = parse_explicit_article_refs(question)
    docs = []

    for ref in refs:
        kanun_no = ref.get("kanun_no")
        madde_no = ref.get("madde_no")
        madde_tipi = ref.get("madde_tipi", "madde")

        doc = get_mevzuat_article(kanun_no, madde_no, madde_tipi)
        if doc:
            docs.append(doc)

    return docs


def dedupe_mevzuat_docs(docs: list):
    result = []
    seen = set()

    for doc in docs:
        if not doc:
            continue

        key = (
            str(doc.get("kanun_no") or ""),
            str(doc.get("madde_tipi") or "madde"),
            str(doc.get("madde_no") or ""),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(doc)

    return result


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
        "structured_content": doc.get("structured_content"),
        "chunk_text": doc.get("chunk_text", ""),
        "similarity": doc.get("similarity"),
        "chunk_index": doc.get("chunk_index"),
        "retrieval_source": doc.get("retrieval_source", "semantic_or_keyword"),
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


def get_referenced_mevzuat_docs(mevzuat_docs: list, max_extra_docs: int = 6) -> list:
    """
    mevzuat_references tablosundan bağlı maddeleri çek.
    """
    extras = []
    seen = {_doc_key(doc) for doc in mevzuat_docs}

    for doc in mevzuat_docs:
        kanun_no = str(doc.get("kanun_no") or "").strip()
        madde_tipi = str(doc.get("madde_tipi") or "madde").strip()
        madde_no = str(doc.get("madde_no") or "").strip()

        if not kanun_no or not madde_no:
            continue

        try:
            res = (
                supabase.table("mevzuat_references")
                .select(
                    "target_kanun_no, target_madde_tipi, target_madde_no"
                )
                .eq("source_kanun_no", kanun_no)
                .eq("source_madde_tipi", madde_tipi)
                .eq("source_madde_no", madde_no)
                .execute()
            )

            refs = res.data or []

            for ref in refs:
                target_doc = get_mevzuat_by_article(
                    kanun_no=ref.get("target_kanun_no"),
                    madde_no=ref.get("target_madde_no"),
                    madde_tipi=ref.get("target_madde_tipi", "madde"),
                )

                if not target_doc:
                    continue

                target_doc["retrieval_source"] = "reference_graph"
                normalized_target = _normalize_doc(target_doc)
                key = _doc_key(normalized_target)

                if key in seen:
                    continue

                seen.add(key)
                extras.append(normalized_target)

                if len(extras) >= max_extra_docs:
                    return extras

        except Exception as e:
            print(f"Reference graph retrieval hatası: {e}")

    return extras


def build_context(mevzuat_docs: list, karar_docs: list, question: str = "") -> str:
    context_parts = []

    for m in mevzuat_docs:
        kanun_adi = m.get("kanun_adi", "Kanun")
        madde_no = m.get("madde_no", "?")
        madde_tipi = m.get("madde_tipi", "madde")
        icerik = get_context_text_for_doc(m, question)

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


def build_fallback_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    Gemini/generation kullanılamadığında kullanıcıya kaynak temelli kısa fallback cevap döndürür.
    """
    lines = []
    lines.append("Otomatik cevap üretimi şu anda kullanılamıyor. Ancak bulunan ilgili kaynaklar aşağıdadır:\n")

    if mevzuat_docs:
        lines.append("İlgili mevzuat:")
        for m in mevzuat_docs[:5]:
            kanun_adi = m.get("kanun_adi", "Kanun")
            madde_no = m.get("madde_no", "?")
            madde_tipi = m.get("madde_tipi", "madde")
            text = get_context_text_for_doc(m, question)

            if madde_tipi == "madde":
                label = f"{kanun_adi} Madde {madde_no}"
            else:
                label = f"{kanun_adi} {madde_tipi} {madde_no}"

            lines.append(f"- [{label}] {text}")

    if karar_docs:
        lines.append("\nİlgili kararlar:")
        for k in karar_docs[:3]:
            daire = k.get("daire", "Mahkeme")
            esas_no = k.get("esas_no", "?")
            karar_no = k.get("karar_no", "?")
            text = k.get("icerik", "")
            lines.append(f"- [{daire} - {esas_no} / {karar_no}] {text}")

    if not mevzuat_docs and not karar_docs:
        lines.append("Bu konuda veritabanında ilgili kaynak bulunamadı.")

    lines.append("\nBu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.")
    return "\n".join(lines)


def debug_retrieve_mevzuat(question: str):
    """
    Gemini cevap üretmeden sadece retrieval sonucunu döndürür.
    Böylece quota doluyken bile hangi maddelerin geldiğini test edebilirsin.
    """
    explicit_docs = get_explicitly_requested_articles(question)

    if explicit_docs:
        semantic_mevzuat_docs = []
        keyword_mevzuat_docs = keyword_search_mevzuat(question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=explicit_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )
    else:
        try:
            embedding = embed_query(question)
            semantic_mevzuat_docs = search_mevzuat(embedding, 8)
        except Exception as e:
            print(f"Semantic retrieval atlandı / hata: {e}")
            semantic_mevzuat_docs = []

        keyword_mevzuat_docs = keyword_search_mevzuat(question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=semantic_mevzuat_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )

    prev_ref_docs = expand_previous_article_refs(mevzuat_docs, max_extra_docs=4)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=prev_ref_docs,
        limit=12,
    )

    graph_ref_docs = get_referenced_mevzuat_docs(mevzuat_docs, max_extra_docs=6)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=graph_ref_docs,
        limit=18,
    )

    intra_refs = parse_intra_article_refs(question)

    docs_out = []
    for d in mevzuat_docs:
        full_text = d.get("icerik") or ""
        fikra_text = extract_requested_fikra_text(
            full_text,
            intra_refs,
            structured_content=d.get("structured_content"),
        )
        if intra_refs:
            if fikra_text:
                fikra_status = "matched"
            else:
                fikra_status = "not_structured"
        else:
            fikra_status = "not_requested"

        docs_out.append({
            "kanun_no": d.get("kanun_no"),
            "kanun_adi": d.get("kanun_adi"),
            "madde_tipi": d.get("madde_tipi"),
            "madde_no": d.get("madde_no"),
            "retrieval_source": d.get("retrieval_source", "semantic_or_keyword"),
            "matched_fikra_text": fikra_text,
            "fikra_extraction_status": fikra_status,
            "preview": (fikra_text or full_text)[:300],
        })

    return {
        "question": question,
        "intra_article_refs": intra_refs,
        "count": len(mevzuat_docs),
        "docs": docs_out,
    }


def get_rag_response(question: str, history=None):
    history = history or []

    # 1) Önce açık madde / kanun referansı var mı bak
    explicit_docs = get_explicitly_requested_articles(question)

    # Eğer kullanıcı açıkça madde istemişse ve sonuç bulunduysa,
    # embedding çağrısını zorunlu kılmayalım.
    if explicit_docs:
        semantic_mevzuat_docs = []
        keyword_mevzuat_docs = keyword_search_mevzuat(question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=explicit_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )
    else:
        # Açık madde yoksa normal retrieval akışı
        embedding = embed_query(question)

        semantic_mevzuat_docs = search_mevzuat(embedding, 8)
        keyword_mevzuat_docs = keyword_search_mevzuat(question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=semantic_mevzuat_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )

    # Cross-reference expansion: previous article
    prev_ref_docs = expand_previous_article_refs(mevzuat_docs, max_extra_docs=4)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=prev_ref_docs,
        limit=12,
    )

    # Reference graph expansion: explicit referenced articles
    graph_ref_docs = get_referenced_mevzuat_docs(mevzuat_docs, max_extra_docs=6)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=graph_ref_docs,
        limit=18,
    )

    # Karar retrieval sadece embedding varsa çalışsın
    karar_docs = []
    try:
        if not explicit_docs:
            embedding = embed_query(question)
            karar_docs = search_kararlar(embedding, 5)
    except Exception as e:
        print(f"Karar retrieval atlandı / hata: {e}")
        karar_docs = []

    context = build_context(mevzuat_docs, karar_docs, question=question)
    gemini_history = build_gemini_history(history)

    full_system = SYSTEM_PROMPT + f"\n\nKAYNAKLAR:\n{context}"

    try:
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

    except Exception as e:
        print(f"LLM generation fallback devrede: {e}")
        fallback_text = build_fallback_answer(question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs


def get_rag_response_text(question: str, history=None):
    """
    LLM stream'ini içeride tüketir.
    Hata olursa fallback cevap döner.
    Dışarıya her zaman text (str) verir.
    """
    result, mevzuat_docs, karar_docs = get_rag_response(question, history=history)

    if isinstance(result, str):
        return result, mevzuat_docs, karar_docs

    try:
        full_text = ""
        for chunk in result:
            if hasattr(chunk, "text") and chunk.text:
                full_text += chunk.text

        if full_text.strip():
            return full_text, mevzuat_docs, karar_docs

        fallback_text = build_fallback_answer(question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs

    except Exception as e:
        print(f"Stream tüketiminde fallback devrede: {e}")
        fallback_text = build_fallback_answer(question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs
