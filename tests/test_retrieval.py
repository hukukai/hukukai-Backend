import json
import sys
from pathlib import Path

import pytest

# Proje root'unu path'e ekle
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chat.rag import debug_retrieve_mevzuat, resolve_contextual_article_question


TEST_CASES_PATH = ROOT_DIR / "tests" / "retrieval_test_cases.json"


def load_test_cases():
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def doc_key(doc: dict) -> tuple[str, str, str]:
    return (
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def expected_doc_key(doc: dict) -> tuple[str, str, str]:
    return (
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def extract_actual_top_doc_keys(result: dict) -> list[tuple[str, str, str]]:
    docs = result.get("docs", [])
    return [doc_key(d) for d in docs]


def assert_expected_top_docs(case_id: str, result: dict, expected_top_docs: list[dict]):
    actual_keys = extract_actual_top_doc_keys(result)
    expected_keys = [expected_doc_key(d) for d in expected_top_docs]

    # Beklenen tüm maddeler actual sonuç içinde olmalı
    missing = [k for k in expected_keys if k not in actual_keys]
    assert not missing, (
        f"[{case_id}] Beklenen maddeler bulunamadı.\n"
        f"Missing: {missing}\n"
        f"Actual: {actual_keys}"
    )

    # Eğer beklenen doküman sayısı kadar sonuç varsa sıralamayı da kontrol et
    actual_prefix = actual_keys[: len(expected_keys)]
    assert actual_prefix == expected_keys, (
        f"[{case_id}] Üst sıralama beklenenden farklı.\n"
        f"Expected prefix: {expected_keys}\n"
        f"Actual prefix:   {actual_prefix}"
    )


@pytest.mark.parametrize("case", load_test_cases(), ids=lambda c: c.get("id", "unknown_case"))
def test_retrieval_cases(case: dict):
    case_id = case.get("id", "unknown_case")
    question = case["question"]
    history = case.get("history", [])
    expected = case.get("expected", {})

    result = debug_retrieve_mevzuat(question, history=history)

    # resolved_question kontrolü
    if "resolved_question" in expected:
        assert result.get("resolved_question") == expected["resolved_question"], (
            f"[{case_id}] resolved_question farklı.\n"
            f"Expected: {expected['resolved_question']}\n"
            f"Actual:   {result.get('resolved_question')}"
        )

    # intent kontrolü
    if "karar_retrieval_intent" in expected:
        assert result.get("karar_retrieval_intent") == expected["karar_retrieval_intent"], (
            f"[{case_id}] karar_retrieval_intent farklı.\n"
            f"Expected: {expected['karar_retrieval_intent']}\n"
            f"Actual:   {result.get('karar_retrieval_intent')}"
        )

    # top_docs kontrolü
    if "top_docs" in expected:
        assert_expected_top_docs(case_id, result, expected["top_docs"])


def test_resolve_contextual_article_question_smoke():
    resolved = resolve_contextual_article_question(
        "bu Kanunun 48 ila 52",
        history=[{"role": "user", "content": "TBK 49"}],
    )
    assert resolved == "6098 sayılı Kanun madde 48-52"