import json

import pytest
from django.test import Client


TBK_49_DOC = {
    "id": 3328,
    "source_type": "mevzuat",
    "kanun_no": "6098",
    "kanun_adi": "Türk Borçlar Kanunu",
    "madde_no": "49",
    "madde_tipi": "madde",
    "icerik": (
        "Türk Borçlar Kanunu Madde 49: Kusurlu ve hukuka aykırı bir fiille "
        "başkasına zarar veren, bu zararı gidermekle yükümlüdür."
    ),
    "similarity": None,
    "chunk_index": None,
}


@pytest.fixture
def client():
    return Client()


def _json_post(client, path, payload):
    return client.post(
        path,
        data=json.dumps(payload, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
    )


def _stream_text(response):
    return b"".join(response.streaming_content).decode("utf-8")


def test_chat_rejects_empty_question(client):
    response = _json_post(client, "/api/chat/", {"question": ""})

    assert response.status_code == 400
    assert response.json() == {"error": "Soru boş olamaz."}


def test_chat_rejects_missing_question_even_if_message_exists(client):
    response = _json_post(client, "/api/chat/", {"message": "TBK 49"})

    assert response.status_code == 400
    assert response.json() == {"error": "Soru boş olamaz."}


def test_chat_rejects_missing_question_even_if_soru_exists(client):
    response = _json_post(client, "/api/chat/", {"soru": "TBK 49"})

    assert response.status_code == 400
    assert response.json() == {"error": "Soru boş olamaz."}


def test_chat_rejects_too_long_question(client):
    response = _json_post(client, "/api/chat/", {"question": "a" * 5001})

    assert response.status_code == 400
    assert response.json() == {"error": "Soru en fazla 5000 karakter olabilir."}


def test_chat_rejects_invalid_history_type(client):
    response = _json_post(
        client,
        "/api/chat/",
        {
            "question": "TBK 49",
            "history": "not-a-list",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": "history liste formatında olmalı."}


def test_chat_sanitizes_history_and_returns_sse(client, monkeypatch):
    captured = {}

    def fake_get_rag_response_text(question, history=None):
        captured["question"] = question
        captured["history"] = history or []
        return (
            "Türk Borçlar Kanunu Madde 49 kaynaklı test cevabı.\n\n"
            "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.",
            [TBK_49_DOC],
            [],
        )

    monkeypatch.setattr(
        "chat.views.get_rag_response_text",
        fake_get_rag_response_text,
    )

    history = []
    for i in range(25):
        history.append({
            "role": "bad-role",
            "content": "x" * 5000,
        })

    response = _json_post(
        client,
        "/api/chat/",
        {
            "question": "TBK 49",
            "history": history,
        },
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert "charset=utf-8" in response["Content-Type"]

    body = _stream_text(response)

    assert 'data: {"type": "sources"' in body
    assert 'data: {"type": "text"' in body
    assert 'data: {"type": "done"}' in body
    assert "Türk Borçlar Kanunu Madde 49" in body

    assert captured["question"] == "TBK 49"
    assert len(captured["history"]) == 20
    assert all(item["role"] == "assistant" for item in captured["history"])
    assert all(len(item["content"]) == 4000 for item in captured["history"])


def test_karar_ara_rejects_empty_query(client):
    response = _json_post(client, "/api/karar-ara/", {"query": ""})

    assert response.status_code == 400
    assert response.json() == {"error": "Arama metni boş olamaz."}


def test_karar_ara_rejects_too_long_query(client):
    response = _json_post(client, "/api/karar-ara/", {"query": "a" * 1001})

    assert response.status_code == 400
    assert response.json() == {"error": "Arama metni en fazla 1000 karakter olabilir."}


def test_editor_rejects_empty_question(client):
    response = _json_post(client, "/api/editor/", {"question": ""})

    assert response.status_code == 400
    assert response.json() == {"error": "Soru boş olamaz."}


def test_editor_rejects_too_long_doc_content(client):
    response = _json_post(
        client,
        "/api/editor/",
        {
            "question": "Bu belgeyi düzenle",
            "doc_content": "a" * 20001,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": "Belge içeriği en fazla 20000 karakter olabilir."}


def test_karar_ara_rejects_generic_karar_search(client):
    response = client.post(
        "/api/karar-ara/",
        {"query": "karar ara"},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()

    assert data["results"] == []
    assert data["mevzuat"] == []
    assert data["kararlar"] == []
    assert data["toplam"] == 0
    assert data["needs_more_specific_query"] is True
    assert "daha somut" in data["message"]


def test_karar_ara_case_number_does_not_return_mevzuat(client):
    response = client.post(
        "/api/karar-ara/",
        {"query": "2022/585 kararını bul"},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()

    assert data["mevzuat"] == []
    assert "kararlar" in data
    assert "toplam" in data


def test_karar_ara_article_specific_karar_query_does_not_return_mevzuat(client):
    response = client.post(
        "/api/karar-ara/",
        {"query": "TBK 49 hakkında karar var mı?"},
        format="json",
    )

    assert response.status_code == 200
    data = response.json()

    assert data["mevzuat"] == []
    assert "kararlar" in data
    assert "toplam" in data
    assert data["karar_only"] is True