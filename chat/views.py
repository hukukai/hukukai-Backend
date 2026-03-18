from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import json
import traceback

from .rag import get_rag_response_text, client

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
    question = request.data.get('question', '').strip()
    history = request.data.get('history', [])

    if not question:
        return Response({'error': 'Soru boş olamaz'}, status=400)

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
            yield f"data: {json.dumps(sources, ensure_ascii=False)}\n\n"

            data = {'type': 'text', 'content': response_text}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_sources = {
                'type': 'sources',
                'mevzuat': [],
                'kararlar': [],
                'all_sources': [],
            }
            yield f"data: {json.dumps(error_sources, ensure_ascii=False)}\n\n"

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

            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield 'data: {"type": "done"}\n\n'

    response = StreamingHttpResponse(
        stream_generator(),
        content_type='text/event-stream'
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def karar_ara_view(request):
    query = request.data.get('query', '').strip()

    if not query:
        return Response({'error': 'Arama metni boş olamaz.'}, status=400)

    from .rag import embed_query, search_mevzuat, search_kararlar, keyword_search_mevzuat

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
    question = request.data.get('question', '').strip()
    history = request.data.get('history', [])
    doc_content = request.data.get('doc_content', '')

    if not question:
        return Response({'error': 'Soru boş olamaz'}, status=400)

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
            yield f"data: {json.dumps(sources, ensure_ascii=False)}\n\n"

            data = {'type': 'text', 'content': response_text}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_sources = {
                'type': 'sources',
                'mevzuat': [],
                'kararlar': [],
                'all_sources': [],
            }
            yield f"data: {json.dumps(error_sources, ensure_ascii=False)}\n\n"

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

            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield 'data: {"type": "done"}\n\n'

    response = StreamingHttpResponse(
        stream_generator(),
        content_type='text/event-stream'
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response