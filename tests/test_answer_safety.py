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