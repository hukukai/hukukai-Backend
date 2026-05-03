from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import json
import traceback

from .rag import (
    get_rag_response_text,
    is_generic_karar_search_query,
    is_pure_case_number_query,
    search_kararlar_by_case_number,
    should_retrieve_kararlar,
)

def sse_event(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

MAX_QUESTION_LENGTH = 5000
MAX_QUERY_LENGTH = 1000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT_LENGTH = 4000
MAX_DOC_CONTENT_LENGTH = 20000


def _get_request_value(request, key, default=None):
    try:
        return request.data.get(key, default)
    except Exception:
        return default


def _clean_text_value(value, max_length: int, field_name: str):
    if value is None:
        value = ""

    if not isinstance(value, str):
        return None, f"{field_name} metin formatında olmalı."

    value = value.strip()

    if not value:
        return None, f"{field_name} boş olamaz."

    if len(value) > max_length:
        return None, f"{field_name} en fazla {max_length} karakter olabilir."

    return value, None


def _clean_optional_text_value(value, max_length: int, field_name: str):
    if value is None:
        return "", None

    if not isinstance(value, str):
        return None, f"{field_name} metin formatında olmalı."

    value = value.strip()

    if len(value) > max_length:
        return None, f"{field_name} en fazla {max_length} karakter olabilir."

    return value, None


def _clean_history(value):
    if value is None:
        return [], None

    if not isinstance(value, list):
        return None, "history liste formatında olmalı."

    cleaned = []

    for item in value[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role", "")
        content = item.get("content", "")

        if role not in {"user", "assistant", "model"}:
            role = "assistant"

        if not isinstance(content, str):
            content = ""

        content = content.strip()[:MAX_HISTORY_CONTENT_LENGTH]

        if not content:
            continue

        cleaned.append({
            "role": role,
            "content": content,
        })

    return cleaned, None

def build_mevzuat_baslik(m):
    madde_tipi = m.get("madde_tipi", "madde")
    madde_no = m.get("madde_no", "?")
    source_type = m.get("source_type", "mevzuat")

    if source_type == "yonetmelik":
        kanun_adi = m.get("yonetmelik_adi") or m.get("kanun_adi", "Yönetmelik")
    else:
        kanun_adi = m.get("kanun_adi", "Kanun")

    if madde_tipi == "madde":
        return f"{kanun_adi} Madde {madde_no}"
    if madde_tipi == "ek":
        return f"{kanun_adi} Ek Madde {madde_no}"
    if madde_tipi == "gecici":
        return f"{kanun_adi} Geçici Madde {madde_no}"
    if madde_tipi == "ek_gecici":
        return f"{kanun_adi} Ek Geçici Madde {madde_no}"
    return f"{kanun_adi} {madde_tipi} {madde_no}"


def format_mevzuat_source(m):
    baslik = build_mevzuat_baslik(m)

    source_type = m.get("source_type", "mevzuat")
    kanun_adi = m.get("kanun_adi", "Kanun")
    yonetmelik_adi = m.get("yonetmelik_adi")

    if source_type == "yonetmelik" and yonetmelik_adi:
        kanun_adi = yonetmelik_adi

    return {
        "id": m.get("id"),
        "source_type": source_type,
        "baslik": baslik,
        "title": baslik,
        "kanun_adi": kanun_adi,
        "yonetmelik_adi": yonetmelik_adi,
        "kanun_no": m.get("kanun_no"),
        "madde_no": m.get("madde_no", "?"),
        "madde_tipi": m.get("madde_tipi", "madde"),
        "icerik": m.get("icerik", ""),
        "snippet": m.get("chunk_text") or m.get("icerik", "")[:500],
        "similarity": m.get("similarity"),
        "chunk_index": m.get("chunk_index"),
    }


def format_karar_source(k):
    daire = k.get("daire", "Mahkeme")
    esas_no = k.get("esas_no", "?")
    karar_no = k.get("karar_no", "?")
    baslik = f"{daire} - {esas_no} / {karar_no}"

    return {
        "id": k.get("id"),
        "source_type": "karar",
        "baslik": baslik,
        "title": baslik,
        "daire": daire,
        "esas_no": esas_no,
        "karar_no": karar_no,
        "icerik": k.get("icerik", ""),
        "snippet": k.get("icerik", "")[:500],
        "similarity": k.get("similarity"),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def chat_view(request):
    raw_question = _get_request_value(request, "question", "")
    question, question_error = _clean_text_value(
        raw_question,
        MAX_QUESTION_LENGTH,
        "Soru",
    )

    if question_error:
        return Response({"error": question_error}, status=400)

    raw_history = _get_request_value(request, "history", [])
    history, history_error = _clean_history(raw_history)

    if history_error:
        return Response({"error": history_error}, status=400)

    def stream_generator():
        try:
            response_text, mevzuat, kararlar = get_rag_response_text(question, history)
            formatted_mevzuat = [format_mevzuat_source(m) for m in mevzuat]
            formatted_kararlar = [format_karar_source(k) for k in kararlar]

            sources = {
                'type': 'sources',
                'mevzuat': formatted_mevzuat,
                'kararlar': formatted_kararlar,
                'all_sources': formatted_mevzuat + formatted_kararlar,
            }
            yield sse_event(sources)

            data = {'type': 'text', 'content': response_text}
            yield sse_event(data)

        except Exception as e:
            error_sources = {
                'type': 'sources',
                'mevzuat': [],
                'kararlar': [],
                'all_sources': [],
            }
            yield sse_event(error_sources)

            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                data = {
                    'type': 'text',
                    'content': "Şu anda yanıt oluşturma servisi yoğun. Lütfen kısa bir süre sonra tekrar deneyin."
                }
            else:
                data = {
                    'type': 'text',
                    'content': "Yanıt hazırlanırken bir sorun oluştu. Lütfen tekrar deneyin."
                }

            yield sse_event(data)
        yield sse_event({"type": "done"})

    response = StreamingHttpResponse(
        stream_generator(),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def karar_ara_view(request):
    raw_query = _get_request_value(request, "query", "")
    query, query_error = _clean_text_value(
        raw_query,
        MAX_QUERY_LENGTH,
        "Arama metni",
    )

    if query_error:
        return Response({"error": query_error}, status=400)

    # Genel / boş karar aramalarında mevzuat semantic fallback yapılmasın.
    # Örn. "karar ara", "Yargıtay karar ara"
    if is_generic_karar_search_query(query):
        return Response({
            'results': [],
            'mevzuat': [],
            'kararlar': [],
            'toplam': 0,
            'fallback': False,
            'needs_more_specific_query': True,
            'message': (
                "Karar araması yapabilmem için lütfen daha somut bir konu, "
                "kanun maddesi veya esas/karar numarası belirtin."
            ),
            'examples': [
                "TBK 49 hakkında Yargıtay kararı var mı?",
                "2022/585 kararını bul",
                "İşe iade davası hakkında emsal karar ara",
            ],
        }, status=200)

    # Salt esas/karar numarası sorgularında doğrudan karar tablosunda ara;
    # mevzuat semantic fallback yapma.
    if is_pure_case_number_query(query):
        karar_docs = search_kararlar_by_case_number(query, count=8)

        return Response({
            'results': karar_docs,
            'mevzuat': [],
            'kararlar': karar_docs,
            'toplam': len(karar_docs),
            'fallback': False,
        }, status=200)

    from .rag import embed_query, search_mevzuat, search_kararlar, keyword_search_mevzuat

    # Kullanıcı açıkça karar/içtihat istiyorsa bu endpoint mevzuat sonuçlarını
    # karara alternatif gibi göstermesin. Sadece karar tablosunda arasın.
    # Örn. "TBK 49 hakkında karar var mı?"
    if should_retrieve_kararlar(query):
        try:
            embedding = embed_query(query)
            karar_docs = search_kararlar(embedding, 8)
        except Exception:
            karar_docs = []

        return Response({
            'results': karar_docs,
            'mevzuat': [],
            'kararlar': karar_docs,
            'toplam': len(karar_docs),
            'fallback': False,
            'karar_only': True,
            'message': (
                "Karar/içtihat odaklı arama yapıldı. "
                "Bu endpointte mevzuat sonuçları karara alternatif olarak gösterilmez."
            ),
        }, status=200)

    try:
        embedding = embed_query(query)
        mevzuat_docs = search_mevzuat(embedding, 8)
        karar_docs = search_kararlar(embedding, 8)

        formatted_mevzuat_results = [
            {
                "id": m.get("id"),
                "baslik": build_mevzuat_baslik(m),
                "mahkeme": m.get("kanun_adi"),
                "tur": "Mevzuat",
                "tarih": None,
                "eslesme": round((m.get("similarity") or 0) * 100, 2),
                "alintiler": [m.get("icerik", "")],
                "url": None,
                "kanun_no": m.get("kanun_no"),
                "madde_no": m.get("madde_no"),
                "madde_tipi": m.get("madde_tipi"),
                "icerik": m.get("icerik", ""),
                "snippet": m.get("chunk_text") or m.get("icerik", "")[:500],
                "similarity": m.get("similarity"),
            }
            for m in mevzuat_docs
        ]

        results = karar_docs + formatted_mevzuat_results

        return Response({
            'results': results,
            'mevzuat': mevzuat_docs,
            'kararlar': karar_docs,
            'toplam': len(mevzuat_docs) + len(karar_docs),
            'fallback': False,
        }, status=200)

    except Exception as e:
        msg = str(e)

        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            mevzuat_docs = keyword_search_mevzuat(query, 8)

            formatted_results = [
                {
                    "id": m.get("id"),
                    "baslik": build_mevzuat_baslik(m),
                    "mahkeme": m.get("kanun_adi"),
                    "tur": "Mevzuat",
                    "tarih": None,
                    "eslesme": None,
                    "alintiler": [m.get("icerik", "")],
                    "url": None,
                    "kanun_no": m.get("kanun_no"),
                    "madde_no": m.get("madde_no"),
                    "madde_tipi": m.get("madde_tipi"),
                    "icerik": m.get("icerik", ""),
                    "snippet": m.get("icerik", "")[:500],
                    "similarity": None,
                }
                for m in mevzuat_docs
            ]

            return Response({
                'results': formatted_results,
                'mevzuat': mevzuat_docs,
                'kararlar': [],
                'toplam': len(formatted_results),
                'fallback': True,
                'error': 'Arama servisi şu anda yoğun. Geçici olarak metin eşleşmesine göre sonuçlar gösteriliyor.'
            }, status=200)

        if settings.DEBUG:
            print("karar_ara_view hatası:")
            traceback.print_exc()

        return Response({
            'results': [],
            'mevzuat': [],
            'kararlar': [],
            'toplam': 0,
            'error': 'Arama sırasında bir sorun oluştu. Lütfen tekrar deneyin.'
        }, status=200)


@api_view(['POST'])
@permission_classes([AllowAny])
def editor_view(request):
    raw_question = _get_request_value(request, "question", "")
    question, question_error = _clean_text_value(
        raw_question,
        MAX_QUESTION_LENGTH,
        "Soru",
    )

    if question_error:
        return Response({"error": question_error}, status=400)

    raw_history = _get_request_value(request, "history", [])
    history, history_error = _clean_history(raw_history)

    if history_error:
        return Response({"error": history_error}, status=400)

    raw_doc_content = _get_request_value(request, "doc_content", "")
    doc_content, doc_content_error = _clean_optional_text_value(
        raw_doc_content,
        MAX_DOC_CONTENT_LENGTH,
        "Belge içeriği",
    )

    if doc_content_error:
        return Response({"error": doc_content_error}, status=400)

    EDITOR_SYSTEM = """Sen HukukAI, Türk hukuku uzmanı bir yapay zeka asistanısın.
Hukuki belge oluşturma, düzenleme ve analiz konusunda yardım edersin.
Dilekçe, ihtarname, sözleşme taslağı hazırlayabilirsin.
Her zaman Türk hukuku terminolojisini ve formatını kullan.
Belge oluştururken başlık, taraflar, konu, açıklama ve imza bölümlerini ekle."""

    if doc_content:
        EDITOR_SYSTEM += f"\n\nMevcut belge içeriği:\n{doc_content[:3000]}"

    def stream_generator():
        try:
            response_text, mevzuat, kararlar = get_rag_response_text(question, history)

            formatted_mevzuat = [format_mevzuat_source(m) for m in mevzuat]
            formatted_kararlar = [format_karar_source(k) for k in kararlar]

            sources = {
                'type': 'sources',
                'mevzuat': formatted_mevzuat,
                'kararlar': formatted_kararlar,
                'all_sources': formatted_mevzuat + formatted_kararlar,
            }
            yield sse_event(sources)

            data = {'type': 'text', 'content': response_text}
            yield sse_event(data)

        except Exception as e:
            error_sources = {
                'type': 'sources',
                'mevzuat': [],
                'kararlar': [],
                'all_sources': [],
            }
            yield sse_event(error_sources)

            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                data = {
                    'type': 'text',
                    'content': "Şu anda yanıt oluşturma servisi yoğun. Lütfen kısa bir süre sonra tekrar deneyin."
                }
            else:
                data = {
                    'type': 'text',
                    'content': "Yanıt hazırlanırken bir sorun oluştu. Lütfen tekrar deneyin."
                }

            yield sse_event(data)

        yield sse_event({"type": "done"})

    response = StreamingHttpResponse(
        stream_generator(),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
