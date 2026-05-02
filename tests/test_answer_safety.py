import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from chat.rag import (
    build_safe_document_answer,
    build_source_strict_answer,
    ensure_standard_disclaimer,
    is_document_request,
    is_generic_karar_search_query,
    is_pure_case_number_query,
    should_use_safe_document_template,
    validate_answer_against_sources,
)


TBK_49_DOC = {
    "id": 3328,
    "source_type": "mevzuat",
    "kanun_no": "6098",
    "kanun_adi": "Türk Borçlar Kanunu",
    "madde_no": "49",
    "madde_tipi": "madde",
    "icerik": (
        "Türk Borçlar Kanunu Madde 49: Kusurlu ve hukuka aykırı bir fiille "
        "başkasına zarar veren, bu zararı gidermekle yükümlüdür. "
        "Zarar verici fiili yasaklayan bir hukuk kuralı bulunmasa bile, "
        "ahlaka aykırı bir fiille başkasına kasten zarar veren de, "
        "bu zararı gidermekle yükümlüdür."
    ),
}


def test_document_request_detected_for_ihtarname():
    question = "TBK 49 dayalı 5 cümlelik kısa ihtarname hazırla"

    assert is_document_request(question) is True
    assert should_use_safe_document_template(question) is True


def test_safe_ihtarname_template_uses_source_and_safe_format():
    question = "TBK 49 dayalı 5 cümlelik kısa ihtarname hazırla"

    answer = build_safe_document_answer(
        question=question,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert "İHTARNAME" in answer
    assert "İHTAR EDEN" in answer
    assert "MUHATAP" in answer
    assert "KONU" in answer
    assert "AÇIKLAMALAR" in answer
    assert "SONUÇ VE İHTAR" in answer
    assert "Türk Borçlar Kanunu Madde 49" in answer

    forbidden_terms = [
        "ihtiyati haciz",
        "arabuluculuk",
        "faiz",
        "zamanaşımı",
        "görevli mahkeme",
        "yetkili mahkeme",
        "dava şartı",
        "son uyarı",
        "vekalet ücreti",
        "vekâlet ücreti",
    ]

    answer_lower = answer.lower()

    for term in forbidden_terms:
        assert term not in answer_lower


def test_validator_accepts_allowed_tbk_reference_formats():
    answer = (
        "Türk Borçlar Kanunu Madde 49 uyarınca, kusurlu ve hukuka aykırı "
        "fiille zarar veren kişi zararı gidermekle yükümlüdür."
    )

    is_valid, reason = validate_answer_against_sources(
        answer=answer,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert is_valid is True
    assert reason == "ok"


def test_validator_accepts_tbk_short_reference_format():
    answer = (
        "TBK m. 49 uyarınca, kusurlu ve hukuka aykırı fiille zarar veren kişi "
        "zararı gidermekle yükümlüdür."
    )

    is_valid, reason = validate_answer_against_sources(
        answer=answer,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert is_valid is True
    assert reason == "ok"


def test_validator_rejects_case_law_when_no_karar_source():
    answer = (
        "Türk Borçlar Kanunu Madde 49 uyarınca zarar giderilmelidir. "
        "Yargıtay uygulamasına göre de bu sonuç kabul edilmektedir."
    )

    is_valid, reason = validate_answer_against_sources(
        answer=answer,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert is_valid is False
    assert reason.startswith("forbidden_case_term")


def test_validator_rejects_answer_without_allowed_source_reference():
    answer = "Kusurlu ve hukuka aykırı fiille zarar veren kişi zararı gidermekle yükümlüdür."

    is_valid, reason = validate_answer_against_sources(
        answer=answer,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert is_valid is False
    assert reason == "no_allowed_reference"

def test_ensure_standard_disclaimer_appends_when_missing():
    answer = "Türk Borçlar Kanunu Madde 49 uyarınca zarar giderilmelidir."

    result = ensure_standard_disclaimer(answer)

    assert "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız." in result
    assert result.startswith(answer)


def test_ensure_standard_disclaimer_does_not_duplicate():
    answer = (
        "Türk Borçlar Kanunu Madde 49 uyarınca zarar giderilmelidir.\n\n"
        "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
    )

    result = ensure_standard_disclaimer(answer)

    assert result.count("Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.") == 1


def test_validator_rejects_unsupported_illiyet_bagi_when_not_in_source():
    answer = (
        "Türk Borçlar Kanunu Madde 49 uyarınca haksız fiil sorumluluğu için "
        "hukuka aykırı fiil, kusur, zarar ve illiyet bağı gerekir."
    )

    is_valid, reason = validate_answer_against_sources(
        answer=answer,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert is_valid is False
    assert reason == "unsupported_legal_term:illiyet_bagi"


def test_validator_rejects_unsupported_faiz_when_not_in_source():
    answer = (
        "Türk Borçlar Kanunu Madde 49 uyarınca zarar giderilmelidir. "
        "Ayrıca yasal faiz talep edilebilir."
    )

    is_valid, reason = validate_answer_against_sources(
        answer=answer,
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert is_valid is False
    assert reason == "unsupported_legal_term:faiz"

def test_source_strict_answer_does_not_claim_service_busy():
    answer = build_source_strict_answer(
        question="TBK 49",
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    assert "Yanıt oluşturma servisi şu anda yoğun" not in answer
    assert "Türk Borçlar Kanunu Madde 49" in answer
    assert "Kısa Cevap" in answer
    assert "Dayandığı Kaynaklar" in answer


def test_source_strict_answer_does_not_add_unsupported_legal_terms():
    answer = build_source_strict_answer(
        question="TBK 49",
        mevzuat_docs=[TBK_49_DOC],
        karar_docs=[],
    )

    forbidden_terms = [
        "illiyet bağı",
        "nedensellik",
        "faiz",
        "arabuluculuk",
        "zamanaşımı",
        "görevli mahkeme",
        "yetkili mahkeme",
    ]

    answer_lower = answer.lower()

    for term in forbidden_terms:
        assert term not in answer_lower


def test_pure_case_number_query_detected():
    assert is_pure_case_number_query("2022/585") is True
    assert is_pure_case_number_query("2022/585 E.") is True
    assert is_pure_case_number_query("2022/585 E., 2023/418 K.") is True
    assert is_pure_case_number_query("Yargıtay 2022/585") is True
    assert is_pure_case_number_query("2022/585 kararını bul") is True
    assert is_pure_case_number_query("2022/585 kararını göster") is True


def test_pure_case_number_query_does_not_match_article_query():
    assert is_pure_case_number_query("TBK 2022/585") is False
    assert is_pure_case_number_query("2022 sayılı Kanun 585") is False
    assert is_pure_case_number_query("HMK 114/1") is False

def test_normalize_does_not_block_raw_case_number_gate():
    from chat.rag import get_rag_response

    answer, mevzuat_docs, karar_docs = get_rag_response("2022/585", history=[])

    assert mevzuat_docs == []
    assert "ilgili karar/içtihat kaynağı bulunamadı" in answer

def test_case_number_with_search_words_does_not_fallback_to_mevzuat():
    from chat.rag import get_rag_response

    answer, mevzuat_docs, karar_docs = get_rag_response("2022/585 kararını bul", history=[])

    assert mevzuat_docs == []
    assert "ilgili karar/içtihat kaynağı bulunamadı" in answer

def test_generic_karar_search_query_detected():
    assert is_generic_karar_search_query("karar ara") is True
    assert is_generic_karar_search_query("Yargıtay karar ara") is True
    assert is_generic_karar_search_query("emsal karar bul") is True
    assert is_generic_karar_search_query("içtihat ara") is True


def test_generic_karar_search_query_does_not_match_specific_queries():
    assert is_generic_karar_search_query("TBK 49 hakkında Yargıtay kararı var mı?") is False
    assert is_generic_karar_search_query("2022/585 kararını bul") is False
    assert is_generic_karar_search_query("işe iade hakkında emsal karar ara") is False


def test_generic_karar_search_does_not_fallback_to_mevzuat():
    from chat.rag import get_rag_response

    answer, mevzuat_docs, karar_docs = get_rag_response("karar ara", history=[])

    assert mevzuat_docs == []
    assert karar_docs == []
    assert "daha somut bir konu" in answer
