import json
import re

from .rag_parsing import (
    _canon_text,
    parse_explicit_article_refs,
)

from .rag_safety import (
    build_no_source_answer,
    build_source_strict_answer,
    ensure_standard_disclaimer,
)


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
