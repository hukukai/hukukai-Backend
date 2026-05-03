from google import genai
from google.genai import types
from supabase import create_client
from dotenv import load_dotenv
import os
import re
import json

from .rag_parsing import (
    ARTICLE_PREFIX_PATTERN,
    ARTICLE_SUFFIX_PATTERN,
    COMPACT_NUMBER_REPLACEMENTS,
    COMPACT_ORDINAL_REPLACEMENTS,
    EXPLICIT_LAW_ALIAS_PATTERN,
    INTRA_ARTICLE_PATTERNS,
    LAW_ALIASES,
    MADDE_NO_PATTERN,
    MULTI_NUMBER_LIST_PATTERN,
    NUMBER_TOKEN_PATTERN,
    NUMBER_WORD_TOKENS,
    ORDINAL_TOKEN_PATTERN,
    ORDINAL_WORD_TOKENS,
    PREVIOUS_ARTICLE_PATTERNS,
    RANGE_SEPARATOR_PATTERN,
    SHORT_LAW_ALIAS_PATTERN,
    SHORT_YONETMELIK_ALIAS_PATTERN,
    SPELLED_NUMBER_SEQUENCE_PATTERN,
    SPELLED_ORDINAL_SEQUENCE_PATTERN,
    TURKISH_NUMBER_WORDS,
    TURKISH_ORDINAL_WORDS,
    YONETMELIK_ALIASES,
    _canon_text,
    debug_detect_explicit_law_reference,
    debug_parse_explicit_article_refs,
    debug_parse_intra_article_refs,
    extract_last_law_from_history,
    extract_requested_fikra_text,
    get_context_text_for_doc,
    get_explicit_law_alias_pattern,
    get_explicit_law_aliases,
    get_short_law_alias_pattern,
    get_short_law_aliases,
    get_yonetmelik_alias_pattern,
    get_yonetmelik_aliases,
    normalize_compact_turkish_number_words,
    normalize_law_name_to_no,
    normalize_spelled_article_numbers,
    normalize_spelled_ordinal_article_numbers,
    normalize_turkish_number_word_orthography,
    normalize_user_legal_query,
    normalize_yonetmelik_ref,
    parse_explicit_article_refs,
    parse_intra_article_refs,
    resolve_contextual_article_question,
    resolve_contextual_fikra_refs,
    turkish_number_words_to_int,
    turkish_ordinal_words_to_int,
)

from .rag_safety import (
    STANDARD_LEGAL_DISCLAIMER,
    build_fallback_answer,
    build_no_karar_answer,
    build_no_source_answer,
    build_source_strict_answer,
    ensure_standard_disclaimer,
    validate_answer_against_sources,
    validate_unsupported_legal_terms,
)

from .rag_deterministic import (
    SOURCE_STRICT_TECHNICAL_TERMS,
    build_article_brief_explanation_answer,
    build_article_elements_answer,
    build_article_full_text_answer,
    build_article_paragraph_count_answer,
    build_article_specific_paragraph_answer,
    build_article_text_contains_answer,
    build_source_strict_technical_article_answer,
    extract_article_text_search_phrase,
    extract_requested_paragraph_number,
    extract_source_strict_technical_term,
    get_fikralar_from_doc,
    is_article_brief_explanation_request,
    is_article_elements_request,
    is_article_full_text_request,
    is_article_paragraph_count_query,
    is_article_specific_paragraph_query,
    is_article_text_contains_query,
    is_plain_article_lookup_query,
    is_source_strict_technical_article_query,
    strip_article_title_from_content,
)

from .rag_documents import (
    build_safe_document_answer,
    is_document_request,
    should_use_safe_document_template,
)

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
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """
Sen HukukAI, Türk hukuku için kaynak kontrollü bir hukuk araştırma ve belge hazırlama asistanısın.

GENEL İLKE:
Cevapların akıcı olabilir; ancak hukuki iddiaların yalnızca KAYNAKLAR bölümündeki mevzuat, karar ve belge içeriklerine dayanmalıdır.
Kaynakta bulunmayan kanun, süre, şart, istisna, içtihat, mahkeme uygulaması veya olay bilgisi üretme.

KATI CEVAP KURALLARI:
1. Yalnızca KAYNAKLAR bölümündeki metinlere dayan.
2. KAYNAKLAR bölümünde açıkça bulunmayan hiçbir kanun, süre, şart, istisna, mahkeme içtihadı veya yorum yazma.
3. Genel hukuk bilgini, eğitim verini veya tahminini kullanarak hukuki sonuç üretme.
4. Kaynaklarda cevap yoksa bunu açıkça söyle.
5. Karar kaynağı yoksa Yargıtay, Danıştay, AYM, emsal karar, yerleşik içtihat veya mahkeme uygulaması varmış gibi konuşma.
6. Mevzuat kaynağı yoksa madde numarası uydurma.
7. Kullanıcı belirsiz soru sorarsa, kesin cevap vermek yerine hangi bilginin eksik olduğunu belirt.
8. Cevapta kullandığın her temel hukuki sonucu en az bir kaynak adıyla destekle.
9. Kaynak atıflarında yalnızca verilen kaynakların adını, madde numarasını veya karar künyesini kullan.
10. Sonunda şu uyarıyı ekle:
   "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."

CEVAP STİLİ:
- Gereksiz uzun giriş yapma.
- Önce kısa ve doğrudan cevap ver.
- Sonra yasal çerçeveyi açıkla.
- Sonra somut/pratik değerlendirme yap.
- Gerektiğinde tablo kullan.
- Kullanıcı belge, dilekçe, ihtarname, sözleşme maddesi veya metin isterse belge taslağı üret.
- Belge üretirken kaynaklı hukuki dayanağı kısa tut, sonra belgeyi ver.

STANDART CEVAP FORMATI:
1. Kısa Cevap
2. Yasal Çerçeve
3. Hukuki Değerlendirme
4. Sonuç / Özet
5. Dayandığı Kaynaklar

KARAR / İÇTİHAT SORULARINDA:
- Eğer karar kaynağı varsa "Elimdeki karar veritabanında..." ifadesiyle başla.
- Karar künyesini açık yaz.
- Kararın hukuki önemini açıkla.
- Karar kaynağı yoksa karar değerlendirmesi yapma.

BELGE TASLAĞI İSTENİRSE:
1. Kullanıcı belge, dilekçe, ihtarname, sözleşme maddesi veya benzeri metin isterse belge moduna geç.
2. Kullanıcı "kısa", "5 cümlelik", "özet" gibi sınırlama verdiyse buna kesin uy; uzun analiz yazma.
3. Belge üretiminde Apilex tarzı sade format kullan:
   - Başlık
   - İHTAR EDEN / TALEP EDEN / BAŞVURAN
   - MUHATAP
   - KONU
   - AÇIKLAMALAR
   - SONUÇ VE İHTAR / TALEP
   - İMZA
4. Belge taslağından önce en fazla 2 cümlelik kısa hukuki dayanak yaz.
5. Belge taslağında resmi, ölçülü, avukat üslubuna uygun dil kullan.
6. "Şüpheniz olmasın", "hemen", "kesinlikle kazanırsınız", "mutlaka", "son uyarı" gibi konuşma dili, tehdit dili veya garanti veren ifadeler kullanma.
7. "İhtiyati haciz", "arabuluculuk", "faiz", "zamanaşımı", "görevli mahkeme", "yetkili mahkeme", "dava şartı" gibi kaynakta bulunmayan özel usul/sonuç bilgilerini ekleme.
8. Kaynakta açıkça yoksa içtihat, Yargıtay, Danıştay, mahkeme uygulaması veya emsal karar yazma.
9. Bilinmeyen taraf, tarih, tutar, olay, adres, banka bilgisi gibi alanları köşeli parantez içinde bırak.
10. İhtarname için özel olarak şu sade yapıyı kullan:

İHTARNAME

İHTAR EDEN:
[Ad / Unvan]
[Adres]

MUHATAP:
[Ad / Unvan]
[Adres]

KONU:
[Kaynağa dayalı kısa konu]

AÇIKLAMALAR:
[Olay ve kaynak dayanağı]

SONUÇ VE İHTAR:
[Talep, süre ve yasal yollara başvuru ihtarı]

İHTAR EDEN:
[Ad / Unvan]
[İmza]

11. Sonunda "Uygulama Notları" başlığı altında en fazla 3 kısa ve nötr madde ekle.
12. Belge taslağından sonra şu uyarıyı ekle:
   "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
"""

def log_rag_mode(mode: str, question: str = "", extra: dict | None = None) -> None:
    """
    Backend terminalinde hangi cevap yolunun çalıştığını gösterir.
    Kullanıcıya dönmez; sadece debug/maliyet kontrolü içindir.
    """
    try:
        preview = (question or "").replace("\n", " ").strip()[:120]
        payload = f"RAG_MODE={mode}"

        if preview:
            payload += f" question={preview!r}"

        if extra:
            payload += f" extra={extra}"

        print(payload)
    except Exception:
        pass

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
            "retrieval_source": "semantic",
            "source_type": "mevzuat",
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
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content")
            .ilike("icerik", f"%{query}%")
            .limit(count)
            .execute()
        )

        rows = res.data or []
        results = []

        for row in rows:
            row["retrieval_source"] = "keyword"
            row["source_type"] = "mevzuat"
            results.append(row)

        return results

    except Exception as e:
        print(f"Keyword mevzuat arama hatası: {e}")
        return []


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
        doc["source_type"] = "mevzuat"
        return doc

    except Exception as e:
        print(f"Direct article lookup hatası: {e}")
        return None


def get_yonetmelik_article(bagli_kanun_no: str, yonetmelik_adi: str, madde_no: str, madde_tipi: str = "madde"):
    try:
        res = (
            supabase.table("yonetmelik")
            .select("id, bagli_kanun_no, yonetmelik_adi, madde_no, madde_tipi, icerik, structured_content, source_type")
            .eq("bagli_kanun_no", str(bagli_kanun_no))
            .eq("yonetmelik_adi", str(yonetmelik_adi))
            .eq("madde_no", str(madde_no))
            .eq("madde_tipi", madde_tipi)
            .limit(1)
            .execute()
        )

        data = res.data or []
        if not data:
            return None

        doc = data[0]
        doc["retrieval_source"] = "direct_yonetmelik_lookup"
        doc["source_type"] = "yonetmelik"
        doc["kanun_no"] = doc.get("bagli_kanun_no")
        doc["kanun_adi"] = doc.get("yonetmelik_adi")
        return doc

    except Exception as e:
        print(f"Tekil yönetmelik çekme hatası: {e}")
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


def get_explicitly_requested_yonetmelik_articles(question: str):
    q = _canon_text(question)
    docs = []

    for alias, meta in YONETMELIK_ALIASES.items():
        alias_c = _canon_text(alias)

        pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.?|md\.?|madde|maddesi)?\s*({MADDE_NO_PATTERN})\b"
        for match in re.finditer(pattern, q, flags=re.IGNORECASE):
            madde_no = match.group(1)

            doc = get_yonetmelik_article(
                bagli_kanun_no=meta["bagli_kanun_no"],
                yonetmelik_adi=meta["yonetmelik_adi"],
                madde_no=madde_no,
                madde_tipi="madde",
            )
            if doc:
                docs.append(doc)

    return dedupe_mevzuat_docs(docs)


def debug_get_explicitly_requested_yonetmelik_articles(question: str):
    docs = get_explicitly_requested_yonetmelik_articles(question)
    return {
        "question": question,
        "normalized_question": _canon_text(question),
        "count": len(docs),
        "docs": [
            {
                "bagli_kanun_no": d.get("bagli_kanun_no"),
                "yonetmelik_adi": d.get("yonetmelik_adi"),
                "madde_no": d.get("madde_no"),
                "madde_tipi": d.get("madde_tipi"),
                "retrieval_source": d.get("retrieval_source"),
            }
            for d in docs
        ],
    }


def dedupe_mevzuat_docs(docs: list):
    result = []
    seen = set()

    for doc in docs:
        if not doc:
            continue

        source_type = str(doc.get("source_type") or "mevzuat")

        if source_type == "yonetmelik":
            key = (
                source_type,
                str(doc.get("bagli_kanun_no") or doc.get("kanun_no") or ""),
                str(doc.get("yonetmelik_adi") or doc.get("kanun_adi") or ""),
                str(doc.get("madde_tipi") or "madde"),
                str(doc.get("madde_no") or ""),
            )
        else:
            key = (
                source_type,
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
        "source_type": doc.get("source_type", "mevzuat"),
    }


def _get_retrieval_priority(doc: dict) -> int:
    """
    Aynı madde birden fazla kaynaktan gelirse hangisinin tutulacağını belirler.
    Büyük sayı = daha güçlü kaynak.
    """
    source = str(doc.get("retrieval_source") or "")

    priority_map = {
        "direct_article_lookup": 100,
        "direct_yonetmelik_lookup": 95,
        "semantic_or_keyword": 60,
        "keyword": 50,
        "semantic": 70,
        "reference_graph": 30,
        "previous_article_ref": 20,
    }

    return priority_map.get(source, 10)


def _get_doc_sort_score(doc: dict) -> tuple:
    """
    Merge sonrası sıralama için skor üretir.
    Önce retrieval gücü, sonra similarity kullanılır.
    """
    priority = _get_retrieval_priority(doc)

    similarity = doc.get("similarity")
    try:
        similarity = float(similarity) if similarity is not None else 0.0
    except Exception:
        similarity = 0.0

    return (priority, similarity)


def _choose_better_doc(existing: dict, candidate: dict) -> dict:
    """
    Aynı madde iki farklı retrieval kaynağından geldiyse
    daha iyi olan versiyonu seç.
    """
    if not existing:
        return candidate
    if not candidate:
        return existing

    existing_score = _get_doc_sort_score(existing)
    candidate_score = _get_doc_sort_score(candidate)

    if candidate_score > existing_score:
        return candidate

    return existing


def _safe_int(value):
    try:
        return int(str(value))
    except Exception:
        return None


def build_ranking_context(question: str) -> dict:
    """
    Ranking sırasında tekrar tekrar parse yapmamak için
    soru bazlı yardımcı verileri tek yerde hazırlar.
    """
    refs = parse_explicit_article_refs(question)

    explicit_ref_keys = set()
    anchor_numbers = []
    primary_law_no = None

    for ref in refs:
        kanun_no = str(ref.get("kanun_no") or "")
        madde_tipi = str(ref.get("madde_tipi") or "madde")
        madde_no = str(ref.get("madde_no") or "")

        explicit_ref_keys.add((kanun_no, madde_tipi, madde_no))

        if primary_law_no is None and kanun_no:
            primary_law_no = kanun_no

        if madde_no.isdigit():
            anchor_numbers.append(int(madde_no))

    if primary_law_no is None:
        primary_law_no = normalize_law_name_to_no(question)

    return {
        "explicit_ref_keys": explicit_ref_keys,
        "primary_law_no": primary_law_no,
        "anchor_numbers": anchor_numbers,
    }


def should_retrieve_kararlar(question: str) -> bool:
    """
    Kullanıcı açıkça içtihat / karar odaklı soruyorsa karar retrieval açılır.
    Salt mevzuat sorularında gereksiz yere açılmaz.

    Örn:
    - "TBK 49" -> False
    - "karar ara" -> False (generic gate ayrıca yönetir)
    - "TBK 49 hakkında karar var mı?" -> True
    - "TBK 49 hakkında Yargıtay kararı var mı?" -> True
    """
    q = _canon_text(question)

    strong_patterns = [
        r"\byargitay\b",
        r"\bdanistay\b",
        r"\baym\b",
        r"\banayasa mahkemesi\b",
        r"\bemsal\b",
        r"\bictihat\b",
        r"\biçtihat\b",
        r"\bhgk\b",
        r"\bceza genel kurulu\b",
        r"\bhukuk genel kurulu\b",
        r"\bkarar no\b",
        r"\besas no\b",
    ]

    has_strong = any(re.search(pattern, q, flags=re.IGNORECASE) for pattern in strong_patterns)

    # Güçlü sinyal varsa direkt aç.
    if has_strong:
        return True

    karar_terms = [
        "karar",
        "karari",
        "kararı",
        "kararini",
        "kararını",
        "ictihat",
        "içtihat",
        "emsal",
    ]

    legal_context_terms = [
        "tbk", "tck", "cmk", "hmk", "iik", "iyuk", "tmk", "ttk", "kvkk",
        "kanun", "madde", "md", "m.", "fikra", "fıkra", "bent",
        "yonetmelik", "yönetmelik",
    ]

    has_karar_term = any(term in q for term in karar_terms)
    has_legal_context = any(term in q for term in legal_context_terms)

    # "TBK 49 hakkında karar var mı?" gibi sorgularda karar retrieval aç.
    # Ama "karar ara" gibi genel sorgular burada açılmaz; generic gate onu ayrıca yönetir.
    if has_karar_term and has_legal_context:
        return True

    return False

def is_pure_case_number_query(question: str) -> bool:
    """
    2022/585, 2022/585 E., 2023/418 K. gibi salt esas/karar numarası
    sorgularını tespit eder.

    Bu tür sorgularda karar bulunamazsa mevzuat semantic fallback yapılmamalıdır.
    Aksi halde alakasız kanun maddeleri cevap gibi gösterilebilir.
    """
    q = (question or "").strip()

    if not q:
        return False

    q_canon = _canon_text(q)

    has_case_no = re.search(r"\b(19|20)\d{2}\s*/\s*\d+\b", q_canon)
    if not has_case_no:
        return False

    legal_article_terms = [
        "tbk", "tck", "cmk", "hmk", "iik", "iyuk", "tmk", "ttk", "kvkk",
        "kanun", "madde", "md", "m.", "fikra", "fıkra", "bent",
        "yonetmelik", "yönetmelik",
    ]

    if any(term in q_canon for term in legal_article_terms):
        return False

    allowed_words = {
        "e", "k", "esas", "karar", "karari", "kararı", "kararini", "kararını",
        "sayili", "sayılı",
        "bul", "ara", "getir", "goster", "göster", "var", "mi", "mı",
        "hakkinda", "hakkında",
        "yargitay", "yargıtay", "danistay", "danıştay",
        "aym", "anayasa", "mahkemesi", "hgk", "cgp", "cgk",
    }

    tokens = re.findall(r"[a-zçğıöşü]+", q_canon)
    return all(token in allowed_words for token in tokens)


def is_generic_karar_search_query(question: str) -> bool:
    """
    'karar ara', 'Yargıtay karar ara', 'emsal karar bul' gibi
    somut madde/konu/esas no içermeyen genel karar arama sorgularını tespit eder.

    Bu sorgularda mevzuat semantic fallback yapılmamalıdır.
    Aksi halde HMK 294, İİK 8/a gibi alakasız mevzuat sonuçları dönebilir.
    """
    q = (question or "").strip()

    if not q:
        return False

    q_canon = _canon_text(q)

    # Somut esas/karar numarası varsa bu generic değildir;
    # onu is_pure_case_number_query yönetir.
    if re.search(r"\b(?:19|20)\d{2}\s*/\s*\d+\b", q_canon):
        return False

    # Açık kanun/madde sorgusu varsa generic karar araması değildir.
    legal_article_terms = [
        "tbk", "tck", "cmk", "hmk", "iik", "iyuk", "tmk", "ttk", "kvkk",
        "kanun", "madde", "md", "m.", "fikra", "fıkra", "bent",
        "yonetmelik", "yönetmelik",
    ]

    if any(term in q_canon for term in legal_article_terms):
        return False

    karar_terms = {
        "karar", "karari", "kararı", "kararini", "kararını",
        "ictihat", "içtihat", "emsal",
    }

    search_words = {
        "ara", "bul", "getir", "goster", "göster",
        "var", "mi", "mı", "varmi", "varmı",
    }

    court_words = {
        "yargitay", "yargıtay", "danistay", "danıştay",
        "aym", "anayasa", "mahkemesi", "hgk", "cgp", "cgk",
    }

    tokens = re.findall(r"[a-zçğıöşü]+", q_canon)

    if not tokens:
        return False

    has_karar_term = any(token in karar_terms for token in tokens)
    has_search_word = any(token in search_words for token in tokens)
    has_court_word = any(token in court_words for token in tokens)

    if not has_karar_term:
        return False

    # Sorgu sadece karar arama dili + mahkeme adlarından oluşuyorsa generic say.
    allowed_generic_tokens = karar_terms | search_words | court_words | {
        "hakkinda", "hakkında", "ile", "ilgili",
    }

    return (has_search_word or has_court_word) and all(
        token in allowed_generic_tokens for token in tokens
    )


def search_kararlar_by_case_number(question: str, count: int = 5) -> list:
    """
    Salt esas/karar numarası sorgularında semantic mevzuat fallback yerine
    kararlar tablosunda doğrudan numara araması yapar.
    """
    q = _canon_text(question)
    case_numbers = re.findall(r"\b(19|20)\d{2}\s*/\s*\d+\b", q)

    # Yukarıdaki regex grup içerdiği için tam eşleşmeyi ayrıca alalım.
    case_numbers = re.findall(r"\b(?:19|20)\d{2}\s*/\s*\d+\b", q)

    if not case_numbers:
        return []

    results = []
    seen = set()

    for case_no in case_numbers:
        compact_case_no = re.sub(r"\s+", "", case_no)

        try:
            res = (
                supabase.table("kararlar")
                .select("*")
                .or_(
                    f"esas_no.ilike.%{compact_case_no}%,"
                    f"karar_no.ilike.%{compact_case_no}%,"
                    f"icerik.ilike.%{compact_case_no}%"
                )
                .limit(count)
                .execute()
            )

            for row in res.data or []:
                key = row.get("id") or (
                    row.get("daire"),
                    row.get("esas_no"),
                    row.get("karar_no"),
                )

                if key in seen:
                    continue

                seen.add(key)
                row["source_type"] = "karar"
                results.append(row)

                if len(results) >= count:
                    return results

        except Exception as e:
            print(f"Karar numarası arama hatası: {e}")

    return results[:count]


def compute_mevzuat_doc_rank_score(
        doc: dict,
        question: str,
        ranking_context: dict | None = None,
) -> float:
    """
    Dokümanı soru ile ilişkisine göre puanla.
    Büyük skor = daha üst sırada görünmeli.
    """
    score = 0.0

    if ranking_context is None:
        ranking_context = build_ranking_context(question)

    explicit_ref_keys = ranking_context.get("explicit_ref_keys", set())
    primary_law_no = ranking_context.get("primary_law_no")
    anchor_numbers = ranking_context.get("anchor_numbers", [])

    # 1) retrieval source baz puanı
    source_priority = _get_retrieval_priority(doc)
    score += float(source_priority)

    # 2) similarity bonus
    similarity = doc.get("similarity")
    try:
        similarity = float(similarity) if similarity is not None else 0.0
    except Exception:
        similarity = 0.0
    score += similarity * 20.0

    # 3) explicit requested article exact match bonus
    doc_key = _doc_key(doc)
    if doc_key in explicit_ref_keys:
        score += 1000.0

    # 4) same law bonus
    if primary_law_no and str(doc.get("kanun_no") or "") == str(primary_law_no):
        score += 120.0

    # 5) proximity bonus
    doc_madde_no = _safe_int(doc.get("madde_no"))

    if anchor_numbers and doc_madde_no is not None:
        closest_distance = min(abs(doc_madde_no - n) for n in anchor_numbers)

        if closest_distance == 0:
            score += 150.0
        elif closest_distance == 1:
            score += 60.0
        elif closest_distance <= 3:
            score += 30.0
        elif closest_distance <= 5:
            score += 10.0

    # 6) expansion penalty
    source = str(doc.get("retrieval_source") or "")
    if source == "reference_graph":
        score -= 20.0
    elif source == "previous_article_ref":
        score -= 30.0

    return score


def rank_mevzuat_docs(docs: list, question: str, limit: int | None = None) -> list:
    """
    Dokümanları production-friendly şekilde sırala.
    """
    normalized_docs = [_normalize_doc(doc) for doc in docs if doc]
    ranking_context = build_ranking_context(question)

    ranked = sorted(
        normalized_docs,
        key=lambda d: (
            -compute_mevzuat_doc_rank_score(d, question, ranking_context=ranking_context),
            -_get_doc_sort_score(d)[0],
            -_get_doc_sort_score(d)[1],
        )
    )

    if limit is not None:
        return ranked[:limit]

    return ranked


def _doc_key(doc: dict) -> tuple:
    source_type = str(doc.get("source_type") or "mevzuat")

    if source_type == "yonetmelik":
        return (
            source_type,
            str(doc.get("bagli_kanun_no") or doc.get("kanun_no") or ""),
            str(doc.get("yonetmelik_adi") or doc.get("kanun_adi") or ""),
            str(doc.get("madde_tipi") or "madde"),
            str(doc.get("madde_no") or ""),
        )

    return (
        source_type,
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def merge_mevzuat_docs(primary_docs: list, extra_docs: list, limit: int = 12) -> list:
    """
    Duplicate'leri kaldırarak listeyi birleştirir.
    Aynı madde birden fazla kaynaktan gelirse en iyi versiyonu tutar.
    """
    best_by_key = {}
    first_seen_order = {}

    all_docs = primary_docs + extra_docs

    for idx, doc in enumerate(all_docs):
        if not doc:
            continue

        normalized = _normalize_doc(doc)
        key = _doc_key(normalized)

        if key not in first_seen_order:
            first_seen_order[key] = idx

        current_best = best_by_key.get(key)
        best_by_key[key] = _choose_better_doc(current_best, normalized)

    merged = list(best_by_key.values())

    merged.sort(
        key=lambda d: (
            -_get_doc_sort_score(d)[0],
            -_get_doc_sort_score(d)[1],
            first_seen_order.get(_doc_key(d), 10 ** 9),
        )
    )

    return merged[:limit]


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

        prev_doc["retrieval_source"] = "previous_article_ref"
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
        source_type = m.get("source_type", "mevzuat")
        kanun_adi = m.get("kanun_adi", "Kanun")

        if source_type == "yonetmelik":
            kanun_adi = m.get("yonetmelik_adi") or kanun_adi
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


def get_fikra_extraction_status(question: str, doc: dict, matched_text: str | None) -> str:
    """
    Fıkra / bent extraction sonucunu daha dürüst sınıflandır.
    """
    intra_refs = parse_intra_article_refs(question)
    if not intra_refs:
        return "not_requested"

    resolved_refs = resolve_contextual_fikra_refs(intra_refs)

    requested_single = None
    requested_list = None
    requested_bent = None
    requested_numeric_bent = None

    for ref in intra_refs:
        if ref.get("type") == "bent":
            requested_bent = ref.get("value")
        elif ref.get("type") == "numeric_bent":
            requested_numeric_bent = ref.get("value")

    for ref in resolved_refs:
        resolved_value = ref.get("resolved")

        if isinstance(resolved_value, list) and resolved_value:
            requested_list = resolved_value

        elif isinstance(resolved_value, str) and resolved_value in {"1", "2", "3", "4"}:
            requested_single = resolved_value

    structured_content = doc.get("structured_content") or {}
    fikralar = structured_content.get("fikralar", {}) if isinstance(structured_content, dict) else {}

    def _fikra_has_bent(fikra_value, bent_key: str) -> bool:
        if not isinstance(fikra_value, dict):
            return False
        bentler = fikra_value.get("bentler", {}) or {}
        return bool(bentler.get(bent_key))

    if requested_list:
        found = [no for no in requested_list if isinstance(fikralar, dict) and fikralar.get(no)]
        if not found:
            return "not_structured"
        if len(found) < len(requested_list):
            return "partial_match"

        if requested_bent:
            bent_found = [no for no in requested_list if _fikra_has_bent(fikralar.get(no), requested_bent)]
            if not bent_found:
                return "not_structured"
            if len(bent_found) < len(requested_list):
                return "partial_match"

        return "matched"

    if requested_single:
        fikra_value = fikralar.get(requested_single) if isinstance(fikralar, dict) else None

        if not fikra_value:
            # İstenen fıkra yapıda yok ama fallback ile yine de bir bent/metin bulduysak
            # bunu tam eşleşme değil, kısmi eşleşme say.
            if matched_text:
                return "partial_match"
            return "not_structured"

        if requested_bent and not _fikra_has_bent(fikra_value, requested_bent):
            # İstenen bent o fıkrada yok ama fallback ile başka yerden bir bent bulduysak
            # yine partial_match diyelim.
            if matched_text:
                return "partial_match"
            return "not_structured"

        return "matched"

    if requested_numeric_bent:
        if matched_text:
            return "partial_match"
        return "not_structured"

    if requested_bent:
        if isinstance(fikralar, dict):
            for _, fikra_value in fikralar.items():
                if _fikra_has_bent(fikra_value, requested_bent):
                    return "matched"
        return "not_structured"

    if matched_text:
        return "matched"

    return "not_structured"


def debug_retrieve_mevzuat(question: str, history=None):
    """
    Gemini cevap üretmeden sadece retrieval sonucunu döndürür.
    Böylece quota doluyken bile hangi maddelerin geldiğini test edebilirsin.
    """
    history = history or []
    raw_question = question or ""

    if is_pure_case_number_query(raw_question):
        return {
            "question": raw_question,
            "resolved_question": raw_question,
            "karar_retrieval_intent": True,
            "pure_case_number_query": True,
            "generic_karar_search_query": False,
            "intra_article_refs": [],
            "count": 0,
            "docs": [],
        }

    if is_generic_karar_search_query(raw_question):
        return {
            "question": raw_question,
            "resolved_question": raw_question,
            "karar_retrieval_intent": True,
            "pure_case_number_query": False,
            "generic_karar_search_query": True,
            "intra_article_refs": [],
            "count": 0,
            "docs": [],
        }

    question = normalize_user_legal_query(raw_question)
    resolved_question = resolve_contextual_article_question(question, history)
    karar_intent = should_retrieve_kararlar(resolved_question)

    explicit_mevzuat_docs = get_explicitly_requested_articles(resolved_question)
    explicit_yonetmelik_docs = get_explicitly_requested_yonetmelik_articles(resolved_question)

    explicit_docs = merge_mevzuat_docs(
        explicit_mevzuat_docs,
        explicit_yonetmelik_docs,
        limit=10,
    )
    if explicit_docs:
        semantic_mevzuat_docs = []
        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=explicit_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )
    else:
        try:
            embedding = embed_query(resolved_question)
            semantic_mevzuat_docs = search_mevzuat(embedding, 8)

        except Exception as e:
            print(f"Semantic retrieval atlandı / hata: {e}")
            semantic_mevzuat_docs = []

        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

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

    mevzuat_docs = rank_mevzuat_docs(
        mevzuat_docs,
        resolved_question,
        limit=18,
    )

    intra_refs = parse_intra_article_refs(resolved_question)
    ranking_context = build_ranking_context(resolved_question)
    docs_out = []
    for d in mevzuat_docs:
        full_text = d.get("icerik") or ""
        fikra_text = extract_requested_fikra_text(
            full_text,
            intra_refs,
            structured_content=d.get("structured_content"),
        )
        fikra_status = get_fikra_extraction_status(resolved_question, d, fikra_text)

        docs_out.append({
            "kanun_no": d.get("kanun_no"),
            "kanun_adi": d.get("kanun_adi"),
            "madde_tipi": d.get("madde_tipi"),
            "madde_no": d.get("madde_no"),
            "retrieval_source": d.get("retrieval_source", "semantic_or_keyword"),
            "rank_score": compute_mevzuat_doc_rank_score(
                d,
                resolved_question,
                ranking_context=ranking_context,
            ),
            "similarity": d.get("similarity"),
            "matched_fikra_text": fikra_text,
            "fikra_extraction_status": fikra_status,
            "preview": (fikra_text or full_text)[:300],
        })

    return {
        "question": question,
        "resolved_question": resolved_question,
        "karar_retrieval_intent": karar_intent,
        "intra_article_refs": intra_refs,
        "count": len(mevzuat_docs),
        "docs": docs_out,
    }


def get_rag_response(question: str, history=None):
    history = history or []
    raw_question = question or ""

    # Salt karar/esas numarası sorgularında mevzuat semantic fallback yapılmaz.
    # Bu kontrol normalize_user_legal_query'den ÖNCE yapılmalı.
    # Çünkü normalize_user_legal_query "2022/585" ifadesini fıkra formatı gibi dönüştürebilir.
    if is_pure_case_number_query(raw_question):
        log_rag_mode("deterministic_pure_case_number", raw_question)

        karar_docs = search_kararlar_by_case_number(raw_question, count=5)

        if not karar_docs:
            return build_no_karar_answer(raw_question, []), [], []

        return build_source_strict_answer(
            raw_question,
            [],
            karar_docs,
        ), [], karar_docs

    # 'karar ara', 'Yargıtay karar ara' gibi somut konu/madde içermeyen
    # genel karar arama sorgularında mevzuat semantic fallback yapılmaz.
    if is_generic_karar_search_query(raw_question):
        log_rag_mode("deterministic_generic_karar_search", raw_question)

        return (
            "Karar araması yapabilmem için lütfen daha somut bir konu, kanun maddesi "
            "veya esas/karar numarası belirtin.\n\n"
            "Örnekler:\n"
            "- TBK 49 hakkında Yargıtay kararı var mı?\n"
            "- 2022/585 kararını bul\n"
            "- İşe iade davası hakkında emsal karar ara\n\n"
            "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
        ), [], []

    question = normalize_user_legal_query(raw_question)
    resolved_question = resolve_contextual_article_question(question, history)

    # 1) Önce açık madde / kanun referansı var mı bak
    explicit_mevzuat_docs = get_explicitly_requested_articles(resolved_question)
    explicit_yonetmelik_docs = get_explicitly_requested_yonetmelik_articles(resolved_question)

    explicit_docs = merge_mevzuat_docs(
        explicit_mevzuat_docs,
        explicit_yonetmelik_docs,
        limit=10,
    )
    # Eğer kullanıcı açıkça madde istemişse ve sonuç bulunduysa,
    # Lafzi madde metni kontrolü:
    # Örn. "TBK 49 içinde illiyet bağı geçiyor mu?"
    # Bu tip sorularda LLM'e gitmeden yalnızca madde metni içinde arama yapılır.
    if explicit_docs and is_article_text_contains_query(resolved_question):
        log_rag_mode("deterministic_article_text_contains", resolved_question)
        return build_article_text_contains_answer(resolved_question, explicit_docs), explicit_docs, []
    # Kaynakta bulunmayan riskli teknik kavram soruları:
    # Örn. "TBK 49'da illiyet bağı şart mı?"
    # Bu tip sorgularda LLM'e gitmeden yalnızca madde lafzına dayalı cevap verilir.
    if explicit_docs and is_source_strict_technical_article_query(resolved_question):
        log_rag_mode("deterministic_source_strict_technical_article", resolved_question)
        return build_source_strict_technical_article_answer(resolved_question, explicit_docs), explicit_docs, []

    # Doğrudan madde metni isteyen sorgular:
    # Örn. "TBK 49 metnini aynen ver"
    if explicit_docs and is_article_full_text_request(resolved_question):
        log_rag_mode("deterministic_article_full_text", resolved_question)
        return build_article_full_text_answer(resolved_question, explicit_docs), explicit_docs, []

    # Fıkra sayısı isteyen sorgular:
    # Örn. "TBK 49 kaç fıkra?"
    if explicit_docs and is_article_paragraph_count_query(resolved_question):
        log_rag_mode("deterministic_article_paragraph_count", resolved_question)
        return build_article_paragraph_count_answer(resolved_question, explicit_docs), explicit_docs, []

    # Belirli fıkra isteyen sorgular:
    # Örn. "TBK 49 birinci fıkra"
    if explicit_docs and is_article_specific_paragraph_query(resolved_question):
        log_rag_mode("deterministic_article_specific_paragraph", resolved_question)
        return build_article_specific_paragraph_answer(resolved_question, explicit_docs), explicit_docs, []

    # Madde şartları / unsurları:
    # Örn. "TBK 49 şartları nelerdir?"
    # Bu tip sorgularda LLM'e gitmeden yalnızca madde metnine dayalı cevap verilir.
    if explicit_docs and is_article_elements_request(resolved_question):
        log_rag_mode("deterministic_article_elements", resolved_question)
        return build_article_elements_answer(resolved_question, explicit_docs), explicit_docs, []

    # Çıplak madde sorgusu:
    # Örn. "TBK 49"
    # Bu tip sorgularda LLM'e gitmeden kaynak metnine dayalı kısa cevap verilir.
    if explicit_docs and is_plain_article_lookup_query(resolved_question):
        log_rag_mode("deterministic_plain_article_lookup", resolved_question)
        return build_article_brief_explanation_answer(resolved_question, explicit_docs), explicit_docs, []

    # embedding çağrısını zorunlu kılmayalım.
    if explicit_docs:
        semantic_mevzuat_docs = []
        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=explicit_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )
    else:
        # Açık madde yoksa normal retrieval akışı
        try:
            embedding = embed_query(resolved_question)
            semantic_mevzuat_docs = search_mevzuat(embedding, 8)

        except Exception as e:
            print(f"Semantic retrieval atlandı / hata: {e}")
            semantic_mevzuat_docs = []

        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

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

    mevzuat_docs = rank_mevzuat_docs(
        mevzuat_docs,
        resolved_question,
        limit=18,
    )

    # Karar retrieval intent bazlı çalışsın
    karar_docs = []
    karar_intent = should_retrieve_kararlar(resolved_question)

    try:
        if karar_intent:
            embedding = embed_query(resolved_question)
            karar_docs = search_kararlar(embedding, 5)
    except Exception as e:
        print(f"Karar retrieval atlandı / hata: {e}")
        karar_docs = []

    # Production safety gate:
    # Kaynak yoksa LLM çağırma.
    if not mevzuat_docs and not karar_docs:
        log_rag_mode("deterministic_no_source", resolved_question)
        return build_no_source_answer(), [], []

    # Kullanıcı karar/içtihat istemiş ama karar bulunamamışsa,
    # LLM'in içtihat uydurma riskini engelle.
    if karar_intent and not karar_docs:
        log_rag_mode("deterministic_no_karar", resolved_question)
        return build_no_karar_answer(resolved_question, mevzuat_docs), mevzuat_docs, []

    # Basit belge/şablon taleplerinde LLM'e bırakma.
    # Production belge güvenliği için deterministic şablon döndür.
    if should_use_safe_document_template(resolved_question):
        log_rag_mode("deterministic_document_template", resolved_question)
        return build_safe_document_answer(resolved_question, mevzuat_docs, karar_docs), mevzuat_docs, karar_docs

    context = build_context(mevzuat_docs, karar_docs, question=resolved_question)
    gemini_history = build_gemini_history(history)

    full_system = SYSTEM_PROMPT + f"\n\nKAYNAKLAR:\n{context}"

    log_rag_mode("llm_generation", resolved_question, extra={"model": CHAT_MODEL})

    try:
        response = client.models.generate_content_stream(
            model=CHAT_MODEL,
            contents=gemini_history + [
                types.Content(role="user", parts=[types.Part(text=resolved_question)])
            ],
            config=types.GenerateContentConfig(
                system_instruction=full_system,
            ),
        )
        return response, mevzuat_docs, karar_docs


    except Exception as e:

        print(f"LLM generation fallback devrede: {e}")

        fallback_text = build_fallback_answer(resolved_question, mevzuat_docs, karar_docs)

        return fallback_text, mevzuat_docs, karar_docs


def get_rag_response_text(question: str, history=None):
    result, mevzuat_docs, karar_docs = get_rag_response(question, history=history)

    if isinstance(result, str):
        return ensure_standard_disclaimer(result), mevzuat_docs, karar_docs

    normalized_question = normalize_user_legal_query(question)
    resolved_question = resolve_contextual_article_question(normalized_question, history)

    try:
        full_text = ""
        for chunk in result:
            if hasattr(chunk, "text") and chunk.text:
                full_text += chunk.text

        if full_text.strip():
            is_valid, validation_reason = validate_answer_against_sources(
                full_text,
                mevzuat_docs,
                karar_docs,
            )

            if is_valid:
                return ensure_standard_disclaimer(full_text), mevzuat_docs, karar_docs

            print(f"Answer validation failed: {validation_reason}")

            if is_document_request(resolved_question):
                fallback_text = build_safe_document_answer(
                    resolved_question,
                    mevzuat_docs,
                    karar_docs,
                )
            else:
                fallback_text = build_source_strict_answer(
                    resolved_question,
                    mevzuat_docs,
                    karar_docs,
                )

            return ensure_standard_disclaimer(fallback_text), mevzuat_docs, karar_docs

        fallback_text = build_fallback_answer(resolved_question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs

    except Exception as e:
        print(f"Stream tüketiminde fallback devrede: {e}")
        fallback_text = build_fallback_answer(resolved_question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs
