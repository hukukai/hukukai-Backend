def test_rag_public_facade_imports():
    from chat.rag import (
        get_rag_response_text,
        is_generic_karar_search_query,
        is_pure_case_number_query,
        should_retrieve_kararlar,
    )

    assert callable(get_rag_response_text)
    assert callable(is_generic_karar_search_query)
    assert callable(is_pure_case_number_query)
    assert callable(should_retrieve_kararlar)


def test_rag_parsing_module_basic_article_parse():
    from chat.rag_parsing import parse_explicit_article_refs

    assert parse_explicit_article_refs("TBK 49") == [
        {
            "kanun_no": "6098",
            "madde_no": "49",
            "madde_tipi": "madde",
        }
    ]


def test_rag_safety_module_basic_disclaimer():
    from chat.rag_safety import ensure_standard_disclaimer

    result = ensure_standard_disclaimer("Test")
    assert "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız." in result


def test_rag_deterministic_module_basic_detection():
    from chat.rag_deterministic import (
        is_article_elements_request,
        is_source_strict_technical_article_query,
    )

    assert is_article_elements_request("TBK 49 şartları nelerdir?") is True
    assert is_source_strict_technical_article_query("TBK 49'da illiyet bağı şart mı?") is True


def test_rag_documents_module_basic_detection():
    from chat.rag_documents import should_use_safe_document_template

    assert should_use_safe_document_template("TBK 49 dayalı kısa ihtarname hazırla") is True
