from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import json
from .rag import get_rag_response

@api_view(['POST'])
@permission_classes([AllowAny])
def chat_view(request):
    question = request.data.get('question', '').strip()
    history  = request.data.get('history', [])

    if not question:
        from rest_framework.response import Response
        return Response({'error': 'Soru boş olamaz'}, status=400)

    def stream_generator():
        response, mevzuat, kararlar = get_rag_response(question, history)

        # Önce kaynakları gönder
        sources = {
            'type': 'sources',
            'mevzuat': mevzuat,
            'kararlar': kararlar
        }
        yield f"data: {json.dumps(sources, ensure_ascii=False)}\n\n"

        # Sonra streaming metin
        for chunk in response:
            if chunk.text:
                data = {'type': 'text', 'content': chunk.text}
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        yield 'data: {"type": "done"}\n\n'

    return StreamingHttpResponse(
        stream_generator(),
        content_type='text/event-stream'
    )