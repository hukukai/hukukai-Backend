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

SOURCE_STRICT_TECHNICAL_TERMS = {
    "illiyet bağı": ["illiyet bagi", "illiyet bağı", "nedensellik", "nedensellik bagi", "nedensellik bağı"],
    "faiz": ["faiz", "yasal faiz", "temerrut faizi", "temerrüt faizi"],
    "zamanaşımı": ["zamanasimi", "zamanaşımı"],
    "hak düşürücü süre": ["hak dusurucu sure", "hak düşürücü süre"],
    "arabuluculuk": ["arabuluculuk"],
    "görevli mahkeme": ["gorevli mahkeme", "görevli mahkeme"],
    "yetkili mahkeme": ["yetkili mahkeme"],
    "dava şartı": ["dava sarti", "dava şartı"],
}


def extract_source_strict_technical_term(question: str):
    """
    Kaynakta açıkça bulunmadığında LLM'e bırakılmaması gereken teknik kavramı çıkarır.

    Amaç:
    - 'TBK 49'da illiyet bağı şart mı?'
    - 'TBK 49'a göre faiz istenir mi?'
    - 'TBK 49'da zamanaşımı var mı?'

    Bu tip sorular explicit madde bulunduğunda LLM'e gitmeden,
    yalnızca madde lafzı üzerinden cevaplanır.
    """
    q = _canon_text(question or "")

    if not q:
        return None

    for canonical_term, variants in SOURCE_STRICT_TECHNICAL_TERMS.items():
        for variant in variants:
            if _canon_text(variant) in q:
                return canonical_term

    return None


def is_source_strict_technical_article_query(question: str) -> bool:
    """
    Explicit madde + riskli teknik kavram içeren soruları yakalar.

    Burada amaç kullanıcının sorduğu kavram kaynakta yoksa,
    LLM'in genel hukuk bilgisiyle cevap üretmesini engellemektir.
    """
    q = _canon_text(question or "")

    if not q:
        return False

    technical_term = extract_source_strict_technical_term(question)
    if not technical_term:
        return False

    question_patterns = [
        "var mi",
        "var mı",
        "gecer mi",
        "geçer mi",
        "geciyor mu",
        "geçiyor mu",
        "sart mi",
        "şart mı",
        "kosul mu",
        "koşul mu",
        "gerekir mi",
        "istenebilir mi",
        "talep edilebilir mi",
        "uygulanir mi",
        "uygulanır mı",
        "mümkun mu",
        "mümkün mü",
        "mumkun mu",
    ]

    return any(pattern in q for pattern in question_patterns)


def build_source_strict_technical_article_answer(question: str, mevzuat_docs: list) -> str:
    """
    Riskli teknik kavram sorusunu yalnızca madde metni üzerinden cevaplar.
    Kaynakta kavram yoksa hukuki değerlendirme yapmaz.
    """
    if not mevzuat_docs:
        return build_no_source_answer()

    doc = mevzuat_docs[0]

    title = (
        doc.get("baslik")
        or doc.get("title")
        or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    content = doc.get("icerik") or doc.get("snippet") or ""
    term = extract_source_strict_technical_term(question)

    if not term:
        return build_source_strict_answer(question, mevzuat_docs, [])

    term_variants = SOURCE_STRICT_TECHNICAL_TERMS.get(term, [term])
    content_canon = _canon_text(content)

    found = any(_canon_text(variant) in content_canon for variant in term_variants)

    if found:
        answer = (
            f"Kısa cevap:\n\n"
            f"Evet. {title} metninde “{term}” kavramı açıkça yer almaktadır.\n\n"
            f"Bu cevap yalnızca ilgili madde metninin lafzına ilişkindir; "
            f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}"
        )
    else:
        answer = (
            f"Kısa cevap:\n\n"
            f"{title} metninde “{term}” kavramı açıkça yer almamaktadır.\n\n"
            f"Kaynakta bu kavram açıkça bulunmadığı için, “{term}” bakımından "
            f"şart, sonuç, süre, talep veya uygulama değerlendirmesi yapamam.\n\n"
            f"Bu cevap yalnızca ilgili madde metninin lafzına ilişkindir; "
            f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}"
        )

    return ensure_standard_disclaimer(answer)

def is_article_text_contains_query(question: str) -> bool:
    """
    'TBK 49 içinde illiyet bağı geçiyor mu?'
    'TBK 49 metninde kusurlu var mı?'
    gibi lafzi madde metni kontrolü isteyen sorguları tespit eder.

    Bu tip sorularda LLM'e gitmeden, yalnızca bulunan madde metni içinde
    aranan ifadenin geçip geçmediği deterministic olarak cevaplanır.
    """
    q = _canon_text(question or "")

    if not q:
        return False

    location_terms = [
        "icinde",
        "içinde",
        "icerisinde",
        "içerisinde",
        "metninde",
        "lafzinda",
        "lafzında",
    ]

    search_terms = [
        "geciyor mu",
        "geçiyor mu",
        "gecer mi",
        "geçer mi",
        "var mi",
        "var mı",
        "yer aliyor mu",
        "yer alıyor mu",
    ]

    return any(term in q for term in location_terms) and any(term in q for term in search_terms)


def extract_article_text_search_phrase(question: str) -> str:
    """
    Lafzi arama sorusundan aranacak ifadeyi çıkarır.

    Örn:
    'TBK 49 içinde illiyet bağı geçiyor mu?' -> 'illiyet bağı'
    'TBK 49 metninde kusurlu var mı?' -> 'kusurlu'
    """
    raw = (question or "").strip()

    if not raw:
        return ""

    patterns = [
        r"(?:içinde|icinde|içerisinde|icerisinde|metninde|lafzında|lafzinda)\s+(.+?)\s+(?:geçiyor\s+mu|geciyor\s+mu|geçer\s+mi|gecer\s+mi|var\s+mı|var\s+mi|yer\s+alıyor\s+mu|yer\s+aliyor\s+mu)\??$",
        r"(?:madde\s+metninde)\s+(.+?)\s+(?:geçiyor\s+mu|geciyor\s+mu|var\s+mı|var\s+mi)\??$",
    ]

    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            phrase = match.group(1).strip()
            return phrase.strip("“”\"'`.,;:!? ")

    return ""


def build_article_text_contains_answer(question: str, mevzuat_docs: list) -> str:
    """
    Bulunan madde metni içinde belirli bir ifadenin geçip geçmediğini
    kaynak-sıkı ve deterministic cevaplar.
    """
    phrase = extract_article_text_search_phrase(question)

    if not phrase or not mevzuat_docs:
        return build_source_strict_answer(question, mevzuat_docs, [])

    doc = mevzuat_docs[0]

    title = (
            doc.get("baslik")
            or doc.get("title")
            or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    content = doc.get("icerik") or doc.get("snippet") or ""
    phrase_canon = _canon_text(phrase)
    content_canon = _canon_text(content)

    found = bool(phrase_canon and phrase_canon in content_canon)

    if found:
        answer = (
            f"Evet. {title} metninde “{phrase}” ifadesi geçer.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}\n\n"
            f"Bu cevap yalnızca ilgili madde metninin lafzına ilişkindir; "
            f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır."
        )
    else:
        answer = (
            f"Hayır. {title} metninde “{phrase}” ifadesi açıkça geçmez.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}\n\n"
            f"Bu cevap yalnızca ilgili madde metninin lafzına ilişkindir; "
            f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır."
        )

    return ensure_standard_disclaimer(answer)


def is_article_full_text_request(question: str) -> bool:
    """
    'TBK 49 metnini aynen ver'
    'TBK 49 lafzını göster'
    'TBK 49 tam metin'
    gibi doğrudan madde metni isteyen sorguları tespit eder.
    """
    q = _canon_text(question or "")

    if not q:
        return False

    patterns = [
        "metnini aynen ver",
        "metnini ver",
        "madde metnini ver",
        "lafzini goster",
        "lafzını göster",
        "lafzini ver",
        "lafzını ver",
        "tam metin",
        "tam metnini ver",
        "aynen ver",
        "aynen goster",
        "aynen göster",
    ]

    return any(pattern in q for pattern in patterns)


def build_article_full_text_answer(question: str, mevzuat_docs: list) -> str:
    """
    Bulunan açık maddeyi LLM'e gitmeden aynen döndürür.
    """
    if not mevzuat_docs:
        return build_no_source_answer()

    doc = mevzuat_docs[0]

    title = (
            doc.get("baslik")
            or doc.get("title")
            or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    content = doc.get("icerik") or doc.get("snippet") or ""

    answer = (
        f"{title} metni aşağıdadır:\n\n"
        f"{content}\n\n"
        f"Dayandığı Kaynaklar:\n"
        f"- {title}\n\n"
        f"Bu cevap yalnızca ilgili madde metninin aktarımına ilişkindir; "
        f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır."
    )

    return ensure_standard_disclaimer(answer)


def get_fikralar_from_doc(doc: dict) -> dict:
    """
    structured_content içindeki fıkraları güvenli biçimde döndürür.
    structured_content dict veya JSON string olabilir.
    """
    structured = doc.get("structured_content") or {}

    if isinstance(structured, str):
        try:
            structured = json.loads(structured)
        except Exception:
            structured = {}

    if not isinstance(structured, dict):
        return {}

    fikralar = structured.get("fikralar") or {}

    if not isinstance(fikralar, dict):
        return {}

    return fikralar


def is_article_paragraph_count_query(question: str) -> bool:
    """
    'TBK 49 kaç fıkra?'
    'TBK 49 fıkra sayısı nedir?'
    gibi sorguları tespit eder.
    """
    q = _canon_text(question or "")

    if not q:
        return False

    return (
            ("kac fikra" in q or "kaç fıkra" in q)
            or ("fikra sayisi" in q or "fıkra sayısı" in q)
    )


def build_article_paragraph_count_answer(question: str, mevzuat_docs: list) -> str:
    """
    structured_content.fikralar üzerinden fıkra sayısını deterministic cevaplar.
    """
    if not mevzuat_docs:
        return build_no_source_answer()

    doc = mevzuat_docs[0]

    title = (
            doc.get("baslik")
            or doc.get("title")
            or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    fikralar = get_fikralar_from_doc(doc)

    if not fikralar:
        answer = (
            f"{title} için fıkra ayrıştırması mevcut değil.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}\n\n"
            f"Bu cevap yalnızca sistemdeki structured_content verisine ilişkindir."
        )
        return ensure_standard_disclaimer(answer)

    count = len(fikralar)

    answer = (
        f"{title} sistemde {count} fıkra olarak ayrıştırılmıştır.\n\n"
        f"Dayandığı Kaynaklar:\n"
        f"- {title}\n\n"
        f"Bu cevap yalnızca sistemdeki structured_content verisine ilişkindir; "
        f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır."
    )

    return ensure_standard_disclaimer(answer)


def extract_requested_paragraph_number(question: str):
    """
    'birinci fıkra', '2. fıkra', 'ikinci fıkra' gibi ifadelerden fıkra numarasını çıkarır.
    """
    q = _canon_text(question or "")

    ordinal_map = {
        "birinci": "1",
        "ilk": "1",
        "ikinci": "2",
        "ucuncu": "3",
        "üçüncü": "3",
        "dorduncu": "4",
        "dördüncü": "4",
        "besinci": "5",
        "beşinci": "5",
        "altinci": "6",
        "altıncı": "6",
        "yedinci": "7",
        "sekizinci": "8",
        "dokuzuncu": "9",
        "onuncu": "10",
    }

    for word, number in ordinal_map.items():
        if f"{word} fikra" in q or f"{word} fıkra" in q:
            return number

    match = re.search(r"\b(\d+)\s*\.?\s*(?:fikra|fıkra)\b", q)
    if match:
        return match.group(1)

    return None


def is_article_specific_paragraph_query(question: str) -> bool:
    """
    'TBK 49 birinci fıkra'
    'TBK 49 2. fıkra'
    gibi belirli fıkra isteyen sorguları tespit eder.
    """
    return extract_requested_paragraph_number(question) is not None


def build_article_specific_paragraph_answer(question: str, mevzuat_docs: list) -> str:
    """
    structured_content.fikralar üzerinden belirli fıkrayı deterministic döndürür.
    """
    if not mevzuat_docs:
        return build_no_source_answer()

    doc = mevzuat_docs[0]

    title = (
            doc.get("baslik")
            or doc.get("title")
            or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    paragraph_no = extract_requested_paragraph_number(question)
    fikralar = get_fikralar_from_doc(doc)

    if not paragraph_no or not fikralar:
        answer = (
            f"{title} için istenen fıkra sistemde ayrıştırılmış olarak bulunamadı.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}\n\n"
            f"Bu cevap yalnızca sistemdeki structured_content verisine ilişkindir."
        )
        return ensure_standard_disclaimer(answer)

    paragraph_text = fikralar.get(str(paragraph_no))
    if isinstance(paragraph_text, dict):
        paragraph_text = paragraph_text.get("text") or paragraph_text.get("icerik") or ""

    if isinstance(paragraph_text, list):
        paragraph_text = "\n".join(str(item) for item in paragraph_text)

    paragraph_text = str(paragraph_text).strip()

    if not paragraph_text:
        answer = (
            f"{title} içinde {paragraph_no}. fıkra sistemde ayrıştırılmış olarak bulunamadı.\n\n"
            f"Dayandığı Kaynaklar:\n"
            f"- {title}\n\n"
            f"Bu cevap yalnızca sistemdeki structured_content verisine ilişkindir."
        )
        return ensure_standard_disclaimer(answer)

    answer = (
        f"{title} {paragraph_no}. fıkra metni aşağıdadır:\n\n"
        f"{paragraph_text}\n\n"
        f"Dayandığı Kaynaklar:\n"
        f"- {title}\n\n"
        f"Bu cevap yalnızca ilgili fıkra metninin aktarımına ilişkindir; "
        f"içtihat, doktrin veya uygulama değerlendirmesi yapılmamıştır."
    )

    return ensure_standard_disclaimer(answer)

def is_plain_article_lookup_query(question: str) -> bool:
    """
    'TBK 49', 'HMK 114', 'CMK 100' gibi çıplak açık madde sorgularını tespit eder.

    Bu sorgularda LLM'e gitmeden kaynak metnine dayalı kısa cevap verilir.
    Daha özel talepler (ihtarname, karar, fıkra, metinde arama vb.) bu kategoriye girmez.
    """
    raw = (question or "").strip()
    q = _canon_text(raw)

    if not q:
        return False

    # Özel amaçlı sorgular plain lookup değildir.
    excluded_terms = [
        "karar", "ictihat", "içtihat", "emsal",
        "ihtar", "ihtarname", "dilekce", "dilekçe", "sozlesme", "sözleşme",
        "hazirla", "hazırla", "yaz", "taslak",
        "icinde", "içinde", "metninde", "lafzinda", "lafzında",
        "geciyor", "geçiyor", "var mi", "var mı",
        "kac fikra", "kaç fıkra", "fikra sayisi", "fıkra sayısı",
        "fikra", "fıkra", "bent",
        "acikla", "açıkla", "anlat", "ozetle", "özetle", "kisaca", "kısaca",
        "metnini", "aynen", "tam metin", "lafzini", "lafzını",
    ]

    if any(term in q for term in excluded_terms):
        return False

    refs = parse_explicit_article_refs(raw)

    if len(refs) != 1:
        return False

    ref = refs[0]
    if not ref.get("kanun_no") or not ref.get("madde_no"):
        return False

    # Sorgu çok uzunsa muhtemelen plain lookup değil, açıklamalı/bağlamlı sorudur.
    token_count = len(re.findall(r"[a-z0-9çğıöşü]+", q))
    return token_count <= 5

def is_article_elements_request(question: str) -> bool:
    """
    'TBK 49 şartları nelerdir?'
    'TBK 49 unsurları nelerdir?'
    gibi madde lafzından unsur/şart isteyen sorguları tespit eder.

    Bu cevap yalnızca madde metnindeki açık ifadelerle sınırlıdır.
    Doktrin, içtihat veya kaynak dışı teknik unsur eklenmez.
    """
    q = _canon_text(question or "")

    if not q:
        return False

    element_terms = [
        "sartlari",
        "sartlari nelerdir",
        "kosullari",
        "kosullari nelerdir",
        "unsurlari",
        "unsurlari nelerdir",
        "hangi sartlar",
        "hangi kosullar",
        "hangi unsurlar",
    ]

    document_terms = [
        "ihtarname",
        "dilekce",
        "sozlesme",
        "taslak",
        "hazirla",
        "yaz",
    ]

    karar_terms = [
        "karar",
        "ictihat",
        "emsal",
        "yargitay",
        "danistay",
        "aym",
    ]

    if any(term in q for term in document_terms):
        return False

    if any(term in q for term in karar_terms):
        return False

    return any(term in q for term in element_terms)


def build_article_elements_answer(question: str, mevzuat_docs: list) -> str:
    """
    Açık madde için LLM kullanmadan, yalnızca madde lafzına dayalı
    unsur/şart cevabı üretir.

    Önemli:
    - Kaynak metninde açıkça bulunmayan 'illiyet bağı', 'zamanaşımı',
      'faiz', 'arabuluculuk' gibi teknik unsurlar eklenmez.
    - Cevap, madde metninin lafzıyla sınırlı olduğunu açıkça söyler.
    """
    if not mevzuat_docs:
        return build_no_source_answer()

    doc = mevzuat_docs[0]

    title = (
        doc.get("baslik")
        or doc.get("title")
        or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    content = doc.get("icerik") or doc.get("snippet") or ""
    clean_content = strip_article_title_from_content(content, title)

    if not clean_content:
        return build_source_strict_answer(question, mevzuat_docs, [])

    answer = (
        f"Kısa cevap:\n\n"
        f"{title} bakımından, sistemdeki madde metnine göre değerlendirme "
        f"yalnızca şu lafzi çerçeveyle sınırlıdır:\n\n"
        f"{clean_content}\n\n"
        f"Bu nedenle bu cevap, sadece madde metninde açıkça yer alan ifadelerle "
        f"sınırlıdır; kaynakta bulunmayan doktrin, içtihat veya uygulama unsuru eklenmemiştir.\n\n"
        f"Dayandığı Kaynaklar:\n"
        f"- {title}"
    )

    return ensure_standard_disclaimer(answer)

def is_article_brief_explanation_request(question: str) -> bool:
    """
    'TBK 49'u iki cümleyle açıkla'
    'TBK 49 kısaca açıkla'
    'TBK 49 özetle'
    gibi basit madde açıklaması isteyen sorguları tespit eder.

    Bu tip sorgularda açık madde bulunduysa LLM'e gitmeden,
    yalnızca madde metnine dayalı kısa cevap verilir.
    """
    q = _canon_text(question or "")

    if not q:
        return False

    explanation_terms = [
        "acikla",
        "açıkla",
        "anlat",
        "ozetle",
        "özetle",
        "kisa cevap",
        "kısa cevap",
        "kisaca",
        "kısaca",
        "iki cumle",
        "iki cümle",
        "2 cumle",
        "2 cümle",
    ]

    document_terms = [
        "ihtarname",
        "dilekce",
        "dilekçe",
        "sozlesme",
        "sözleşme",
        "taslak",
        "hazirla",
        "hazırla",
        "yaz",
    ]

    if any(term in q for term in document_terms):
        return False

    return any(term in q for term in explanation_terms)


def strip_article_title_from_content(content: str, title: str = "") -> str:
    """
    'Türk Borçlar Kanunu Madde 49: ...' tekrarını azaltmak için
    madde başlığını içerikten ayıklar.
    """
    text = (content or "").strip()

    if not text:
        return ""

    if ":" in text:
        before, after = text.split(":", 1)
        if "madde" in _canon_text(before) and len(before) < 120:
            return after.strip()

    return text


def build_article_brief_explanation_answer(question: str, mevzuat_docs: list) -> str:
    """
    Açık madde için LLM kullanmadan kısa, kaynak-sıkı açıklama üretir.
    """
    if not mevzuat_docs:
        return build_no_source_answer()

    doc = mevzuat_docs[0]

    title = (
        doc.get("baslik")
        or doc.get("title")
        or f"{doc.get('kanun_adi', 'Kanun')} Madde {doc.get('madde_no', '?')}"
    )

    content = doc.get("icerik") or doc.get("snippet") or ""
    clean_content = strip_article_title_from_content(content, title)

    if not clean_content:
        return build_source_strict_answer(question, mevzuat_docs, [])

    answer = (
        f"Kısa cevap:\n\n"
        f"{title}, madde metnine göre şu hükmü içerir: {clean_content}\n\n"
        f"Bu açıklama yalnızca ilgili madde metnine dayalıdır; içtihat, doktrin "
        f"veya uygulama değerlendirmesi yapılmamıştır.\n\n"
        f"Dayandığı Kaynaklar:\n"
        f"- {title}"
    )

    return ensure_standard_disclaimer(answer)

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


def build_fallback_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    Gemini/generation kullanılamadığında kullanıcıya kaynak temelli kısa fallback cevap döndürür.
    """
    lines = []
    lines = [
        "Yanıt oluşturma servisi şu anda yoğun görünüyor.",
        "Ama ilgili kaynakları senin için buldum:",
        ""
    ]

    if mevzuat_docs:
        lines.append("İlgili mevzuat ve yönetmelik:")
        for m in mevzuat_docs[:10]:
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


def build_source_strict_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    LLM cevabı validator'dan geçmezse, kullanıcıya "servis yoğun" demek yerine
    yalnızca retrieved kaynak metnine dayalı kısa ve güvenli cevap döndürür.

    Bu fonksiyon hukuki unsur, süre, içtihat veya yorum üretmez.
    Sadece kaynak metnini kullanıcı dostu formatta sunar.
    """
    lines = []

    if mevzuat_docs:
        primary = mevzuat_docs[0]

        source_type = primary.get("source_type", "mevzuat")
        if source_type == "yonetmelik":
            source_name = primary.get("yonetmelik_adi") or primary.get("kanun_adi", "Yönetmelik")
        else:
            source_name = primary.get("kanun_adi", "Kanun")

        madde_no = primary.get("madde_no", "?")
        madde_tipi = primary.get("madde_tipi", "madde")
        source_text = get_context_text_for_doc(primary, question)

        if madde_tipi == "madde":
            source_label = f"{source_name} Madde {madde_no}"
        else:
            source_label = f"{source_name} {madde_tipi} {madde_no}"

        lines.extend([
            "Kısa Cevap",
            "",
            f"{source_label} metnine göre:",
            source_text,
            "",
        ])

        if len(mevzuat_docs) > 1:
            lines.append("İlgili Diğer Kaynaklar:")
            for m in mevzuat_docs[1:5]:
                m_source_type = m.get("source_type", "mevzuat")
                if m_source_type == "yonetmelik":
                    m_source_name = m.get("yonetmelik_adi") or m.get("kanun_adi", "Yönetmelik")
                else:
                    m_source_name = m.get("kanun_adi", "Kanun")

                m_madde_no = m.get("madde_no", "?")
                m_madde_tipi = m.get("madde_tipi", "madde")
                m_text = get_context_text_for_doc(m, question)

                if m_madde_tipi == "madde":
                    m_label = f"{m_source_name} Madde {m_madde_no}"
                else:
                    m_label = f"{m_source_name} {m_madde_tipi} {m_madde_no}"

                lines.append(f"- [{m_label}] {m_text}")

            lines.append("")

        lines.extend([
            "Dayandığı Kaynaklar:",
            f"- {source_label}",
        ])

        return "\n".join(lines)

    if karar_docs:
        lines.extend([
            "Kısa Cevap",
            "",
            "Elimdeki karar veritabanında bulunan kaynaklar aşağıdadır:",
            "",
        ])

        for k in karar_docs[:3]:
            daire = k.get("daire", "Mahkeme")
            esas_no = k.get("esas_no", "?")
            karar_no = k.get("karar_no", "?")
            text = k.get("icerik", "")
            label = f"{daire} - {esas_no} / {karar_no}"
            lines.append(f"- [{label}] {text}")

        return "\n".join(lines)

    return build_no_source_answer()


STANDARD_LEGAL_DISCLAIMER = "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."


def ensure_standard_disclaimer(answer: str) -> str:
    """
    Her kullanıcı cevabının sonunda standart hukuki uyarı bulunmasını garanti eder.
    LLM bazen prompta rağmen uyarıyı eklemeyebilir; production'da bunu modele bırakmıyoruz.
    """
    answer = (answer or "").strip()

    if not answer:
        return STANDARD_LEGAL_DISCLAIMER

    if _canon_text(STANDARD_LEGAL_DISCLAIMER) in _canon_text(answer):
        return answer

    return answer + "\n\n" + STANDARD_LEGAL_DISCLAIMER


def is_document_request(question: str) -> bool:
    """
    Kullanıcının belge/dilekçe/ihtarname/taslak üretimi istediğini tespit eder.
    """
    q = _canon_text(question)

    document_terms = [
        "ihtarname",
        "ihtar",
        "dilekce",
        "dilekçe",
        "taslak",
        "sozlesme maddesi",
        "sözleşme maddesi",
        "metin hazirla",
        "metin hazırla",
        "belge hazirla",
        "belge hazırla",
        "taahhutname",
        "taahhütname",
        "protokol",
        "muvafakatname",
        "basvuru",
        "başvuru",
    ]

    return any(term in q for term in document_terms)


def should_use_safe_document_template(question: str) -> bool:
    """
    Basit / şablon belge isteklerinde LLM'e bırakmadan
    deterministic belge şablonu döndürür.

    Amaç:
    - Apilex tarzı standart belge formatı
    - kaynak dışı usul/sonuç eklenmesini önlemek
    - kısa belge isteklerinde kullanıcı sınırına uymak
    """
    q = _canon_text(question)

    if not is_document_request(question):
        return False

    template_signals = [
        "ornek",
        "örnek",
        "sablon",
        "şablon",
        "kisa",
        "kısa",
        "5 cumle",
        "5 cümle",
        "bes cumle",
        "beş cümle",
        "genel",
        "standart",
    ]

    # "ihtarname örneği ver", "kısa ihtarname hazırla" gibi istekler
    # deterministic şablona gitsin.
    if any(signal in q for signal in template_signals):
        return True

    # Sadece "ihtarname hazırla" gibi somut olay içermeyen belge talepleri de
    # şablon kabul edilsin.
    has_ihtar = "ihtar" in q or "ihtarname" in q
    has_concrete_facts = any(term in q for term in [
        "olay su",
        "olay şu",
        "müvekkil",
        "muvekkil",
        "karsi taraf",
        "karşı taraf",
        "tarihinde",
        "fatura",
        "sozlesme",
        "sözleşme",
        "kira",
        "trafik kazasi",
        "trafik kazası",
    ])

    if has_ihtar and not has_concrete_facts:
        return True

    return False


def build_safe_document_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    LLM cevabı üretilemezse veya validator'dan geçemezse,
    kaynaklara dayalı güvenli belge şablonu döndürür.

    Şimdilik ihtarname odaklıdır.
    """
    q = _canon_text(question)

    primary_source = None
    if mevzuat_docs:
        primary_source = mevzuat_docs[0]

    source_label = "ilgili mevzuat"
    source_text = ""

    if primary_source:
        source_type = primary_source.get("source_type", "mevzuat")
        if source_type == "yonetmelik":
            source_name = primary_source.get("yonetmelik_adi") or primary_source.get("kanun_adi", "Yönetmelik")
        else:
            source_name = primary_source.get("kanun_adi", "Kanun")

        madde_no = primary_source.get("madde_no", "?")
        madde_tipi = primary_source.get("madde_tipi", "madde")
        source_text = get_context_text_for_doc(primary_source, question)

        if madde_tipi == "madde":
            source_label = f"{source_name} Madde {madde_no}"
        else:
            source_label = f"{source_name} {madde_tipi} {madde_no}"

    # Şimdilik belge tipi ihtarname ise Apilex benzeri sade şablon üret.
    if "ihtar" in q or "ihtarname" in q:
        is_short = any(term in q for term in ["kisa", "kısa", "5 cumle", "5 cümle", "bes cumle", "beş cümle"])

        if is_short:
            lines = [
                "İHTARNAME",
                "",
                "İHTAR EDEN:",
                "[Ad / Unvan]",
                "[Adres]",
                "",
                "MUHATAP:",
                "[Ad / Unvan]",
                "[Adres]",
                "",
                "KONU:",
                "Hukuka aykırı fiil nedeniyle doğan zararın giderilmesi talebidir.",
                "",
                "AÇIKLAMALAR:",
                f"Tarafınızca gerçekleştirilen [olayın kısa açıklaması] nedeniyle [zarar gören kişi/şirket] zarara uğramıştır. {source_label} uyarınca, kusurlu ve hukuka aykırı bir fiille başkasına zarar veren kişi bu zararı gidermekle yükümlüdür. Bu nedenle [zarar tutarı / zarar kalemi] tutarındaki zararın işbu ihtarnamenin tebliğinden itibaren [süre] içinde giderilmesini talep ederiz.",
                "",
                "SONUÇ VE İHTAR:",
                "Belirtilen süre içinde zararın giderilmemesi halinde, yasal haklarımızı kullanacağımızı ihtaren bildiririz.",
                "",
                "İHTAR EDEN / VEKİLİ",
                "[Ad / Unvan]",
                "[İmza]",
                "",
                "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.",
            ]
            return "\n".join(lines)

        lines = [
            "Kısa hukuki not",
            f"Bu taslak, {source_label} kapsamında genel amaçlı bir ihtarname örneği olarak hazırlanmıştır.",
            "Somut olay, taraf bilgileri, zarar/borç tutarı ve süre alanları doldurulmadan kullanılmamalıdır.",
            "",
            "İHTARNAME ÖRNEĞİ",
            "",
            "İHTARNAME",
            "",
            "İHTAR EDEN:",
            "[Ad Soyad / Unvan]",
            "[T.C. Kimlik No / Vergi No]",
            "[Adres]",
            "",
            "MUHATAP:",
            "[Ad Soyad / Unvan]",
            "[T.C. Kimlik No / Vergi No]",
            "[Adres]",
            "",
            "KONU:",
            "[Hukuka aykırı fiil nedeniyle doğan zararın tazmini] talebimizden ibarettir.",
            "",
            "AÇIKLAMALAR:",
            "",
            f"1. {source_label} uyarınca, kusurlu ve hukuka aykırı bir fiille başkasına zarar veren kişi, bu zararı gidermekle yükümlüdür.",
            "",
            "2. Muhatap tarafından [tarih] tarihinde gerçekleştirilen [olayın kısa açıklaması] nedeniyle ihtar eden taraf zarara uğramıştır.",
            "",
            "3. Söz konusu fiil nedeniyle doğan zarar [zarar kalemi ve tutar] olarak belirlenmiş olup, bu zararın giderilmesi talep edilmektedir.",
            "",
            "4. Bu kapsamda muhatabın, işbu ihtarnamenin tebliğinden itibaren [süre] içinde [zararın/edimin] yerine getirmesi gerekmektedir.",
            "",
            "5. Belirtilen süre içinde yükümlülüğün yerine getirilmemesi halinde, ihtar eden tarafın yasal haklarını kullanma hakkı saklıdır.",
            "",
            "HUKUKİ NEDENLER:",
            f"{source_label} ve ilgili sair mevzuat.",
            "",
            "DELİLLER:",
            "[Sözleşme, fatura, yazışmalar, tutanak, fotoğraf, video, banka kayıtları, bilirkişi raporu ve sair yasal deliller]",
            "",
            "SONUÇ VE İHTAR:",
            "Yukarıda açıklanan nedenlerle; işbu ihtarnamenin tebliğinden itibaren [süre] içinde [zararın/edimin] yerine getirilmesini, aksi halde yasal haklarımızı kullanacağımızı ihtaren bildiririz.",
            "",
            "İHTAR EDEN / VEKİLİ",
            "[Ad Soyad / Unvan]",
            "[İmza]",
            "",
            "Uygulama Notları:",
            "- Köşeli parantez içindeki alanlar somut olaya göre doldurulmalıdır.",
            "- Zararın veya borcun miktarı açık ve belgeye dayalı yazılmalıdır.",
            "- Belge gönderim yöntemi ve süre seçimi somut olaya göre ayrıca değerlendirilmelidir.",
            "",
            "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.",
        ]

        return "\n".join(lines)

    # Diğer belge türleri için şimdilik güvenli genel cevap.
    return build_fallback_answer(question, mevzuat_docs, karar_docs)


def build_no_source_answer() -> str:
    """
    Kaynak bulunamadığında LLM çağırmadan dönen güvenli cevap.
    Production kuralı: kaynak yoksa hukuki değerlendirme yok.
    """
    return (
        "Bu konuda veritabanımda yeterli kaynak bulunamadı. "
        "Kaynak bulunmadığı için hukuki değerlendirme yapamam.\n\n"
        "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
    )


def build_no_karar_answer(question: str, mevzuat_docs: list) -> str:
    """
    Kullanıcı karar/içtihat istemiş ama karar kaynağı bulunamamışsa
    LLM çağırmadan dönen güvenli cevap.
    """
    lines = [
        "Bu konuda veritabanımda ilgili karar/içtihat kaynağı bulunamadı.",
        "Karar kaynağı bulunmadığı için Yargıtay, Danıştay veya emsal karar değerlendirmesi yapamam.",
    ]

    if mevzuat_docs:
        lines.append("")
        lines.append("Ancak ilgili mevzuat kaynakları aşağıdadır:")

        for m in mevzuat_docs[:5]:
            source_type = m.get("source_type", "mevzuat")
            kanun_adi = m.get("kanun_adi", "Kanun")

            if source_type == "yonetmelik":
                kanun_adi = m.get("yonetmelik_adi") or kanun_adi

            madde_no = m.get("madde_no", "?")
            madde_tipi = m.get("madde_tipi", "madde")
            text = get_context_text_for_doc(m, question)

            if madde_tipi == "madde":
                label = f"{kanun_adi} Madde {madde_no}"
            else:
                label = f"{kanun_adi} {madde_tipi} {madde_no}"

            lines.append(f"- [{label}] {text}")

    lines.append("")
    lines.append("Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.")
    return "\n".join(lines)


def _source_text_contains_any(mevzuat_docs: list, terms: list[str]) -> bool:
    """
    Verilen terimlerden herhangi biri retrieved mevzuat metninde geçiyor mu?
    Kaynak dışı teknik unsur eklemelerini yakalamak için kullanılır.
    """
    source_text = " ".join(
        str(doc.get("icerik", "") or "") for doc in (mevzuat_docs or [])
    )
    source_canon = _canon_text(source_text)

    for term in terms:
        if _canon_text(term) in source_canon:
            return True

    return False


def validate_unsupported_legal_terms(answer: str, mevzuat_docs: list, karar_docs: list) -> tuple[bool, str]:
    """
    İlk seviye kaynak dışı hukuki unsur kontrolü.

    Amaç:
    - Modelin tek madde kaynağından genel hukuk bilgisiyle ek unsur üretmesini azaltmak.
    - Örn. TBK 49 metninde açıkça geçmeyen "illiyet bağı" unsurunu eklemesini engellemek.

    Not:
    Bu liste bilinçli olarak dar tutulur. Aşırı agresif olursa doğru cevapları da kesebilir.
    """
    answer_canon = _canon_text(answer)

    unsupported_groups = {
        "illiyet_bagi": [
            "illiyet bağı",
            "illiyet bagi",
            "nedensellik bağı",
            "nedensellik bagi",
            "nedensellik",
        ],
        "zamanaşımı": [
            "zamanaşımı",
            "zamanasimi",
        ],
        "hak_dusurucu_sure": [
            "hak düşürücü süre",
            "hak dusurucu sure",
        ],
        "faiz": [
            "faiz",
            "temerrüt faizi",
            "temerrut faizi",
            "yasal faiz",
        ],
        "arabuluculuk": [
            "arabuluculuk",
            "dava şartı arabuluculuk",
            "dava sarti arabuluculuk",
        ],
        "gorev_yetki": [
            "görevli mahkeme",
            "gorevli mahkeme",
            "yetkili mahkeme",
        ],
    }

    for reason, terms in unsupported_groups.items():
        answer_has_term = any(_canon_text(term) in answer_canon for term in terms)

        if not answer_has_term:
            continue

        # Eğer aynı terim kaynak metinde veya karar kaynağında varsa izin ver.
        if _source_text_contains_any(mevzuat_docs, terms):
            continue

        karar_text = " ".join(str(k.get("icerik", "") or "") for k in (karar_docs or []))
        karar_canon = _canon_text(karar_text)
        if any(_canon_text(term) in karar_canon for term in terms):
            continue

        return False, f"unsupported_legal_term:{reason}"

    return True, "ok"


def validate_answer_against_sources(answer: str, mevzuat_docs: list, karar_docs: list) -> tuple[bool, str]:
    """
    LLM cevabının temel kaynak güvenlik kurallarına uyup uymadığını kontrol eder.
    Bu validator tam hukuki doğrulama yapmaz; ilk production güvenlik bariyeridir.
    """
    if not answer or not answer.strip():
        return False, "empty_answer"

    if not mevzuat_docs and not karar_docs:
        return False, "no_sources"

    unsupported_ok, unsupported_reason = validate_unsupported_legal_terms(
        answer,
        mevzuat_docs,
        karar_docs,
    )
    if not unsupported_ok:
        return False, unsupported_reason

    answer_lower = answer.lower()

    # Karar kaynağı yokken içtihat/mahkeme uygulaması iddiası kurmasını engelle.
    if not karar_docs:
        forbidden_case_terms = [
            "yargıtay",
            "danıştay",
            "anayasa mahkemesi",
            "aym",
            "emsal karar",
            "yerleşik içtihat",
            "içtihatlarda",
            "kararlarda",
            "mahkeme kararlarında",
        ]

        for term in forbidden_case_terms:
            if term in answer_lower:
                return False, f"forbidden_case_term:{term}"

    allowed_refs = []

    for m in mevzuat_docs:
        source_type = m.get("source_type", "mevzuat")
        kanun_no = str(m.get("kanun_no", "") or "")

        if source_type == "yonetmelik":
            kanun_adi = m.get("yonetmelik_adi") or m.get("kanun_adi", "Yönetmelik")
        else:
            kanun_adi = m.get("kanun_adi", "Kanun")

        madde_no = str(m.get("madde_no", "?"))
        madde_tipi = str(m.get("madde_tipi", "madde"))

        law_aliases = [kanun_adi]

        if kanun_no:
            law_aliases.append(kanun_no)
            law_aliases.append(f"{kanun_no} sayılı Kanun")

            # LAW_ALIASES içindeki kısa adları da kabul et.
            # Örn: 6098 -> TBK, Türk Borçlar Kanunu
            for alias, alias_kanun_no in LAW_ALIASES.items():
                if str(alias_kanun_no) == kanun_no:
                    law_aliases.append(alias)

        # Çok genel veya fazla uzun aliasları azalt.
        clean_aliases = []
        for alias in law_aliases:
            alias = str(alias or "").strip()
            if not alias:
                continue

            # Çok uzun resmi adlar zaten kanun_adi ile var; alias tarafında kısa kullanımları tercih ediyoruz.
            if alias not in clean_aliases:
                clean_aliases.append(alias)

        for alias in clean_aliases:
            if madde_tipi == "madde":
                allowed_refs.extend([
                    f"{alias} Madde {madde_no}",
                    f"{alias} madde {madde_no}",
                    f"{alias} Md. {madde_no}",
                    f"{alias} Md.{madde_no}",
                    f"{alias} md. {madde_no}",
                    f"{alias} md.{madde_no}",
                    f"{alias} m. {madde_no}",
                    f"{alias} m.{madde_no}",
                    f"{alias} m {madde_no}",
                    f"{alias} {madde_no}",
                ])
            else:
                allowed_refs.extend([
                    f"{alias} {madde_tipi} {madde_no}",
                    f"{alias} {madde_tipi.title()} Madde {madde_no}",
                ])

    for k in karar_docs:
        daire = k.get("daire", "Mahkeme")
        esas_no = k.get("esas_no", "?")
        karar_no = k.get("karar_no", "?")
        allowed_refs.append(f"{daire} - {esas_no} / {karar_no}")

    # Cevapta en az bir izinli kaynak etiketi geçsin.
    # Normalize ederek kontrol ediyoruz:
    # "TBK m. 49", "tbk 49", "Türk Borçlar Kanunu Madde 49" gibi varyasyonlar yakalansın.
    if allowed_refs:
        answer_canon = _canon_text(answer)
        allowed_refs_canon = [_canon_text(ref) for ref in allowed_refs if ref]

        if not any(ref in answer_canon for ref in allowed_refs_canon):
            return False, "no_allowed_reference"

    return True, "ok"


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
