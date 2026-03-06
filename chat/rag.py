from google import genai
from google.genai import types
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

SYSTEM_PROMPT = """
Sen HukukAI, Türk hukuku uzmanı bir yapay zeka asistanısın.

KESİN KURALLAR:
1. SADECE aşağıdaki KAYNAKLAR bölümündeki bilgilere dayan.
2. Her iddianda kaynak belirt: [Kanun Adı Md.X] veya [Mahkeme - Daire - Esas/Karar No]
3. Kaynaklarda bilgi yoksa: "Bu konuda veritabanımda yeterli kaynak bulunamadı." de.
4. Cevap formatı:
   → Hukuki değerlendirme (2-3 paragraf)
   → Dayandığı kaynaklar (liste)
   → Pratik öneri
5. Sonunda şunu ekle: "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
"""

def embed_query(text: str) -> list:
    result = client.models.embed_content(
        model='gemini-embedding-001',
        contents=text[:2000],
        config=types.EmbedContentConfig(task_type='RETRIEVAL_QUERY')
    )
    return result.embeddings[0].values

def search_mevzuat(embedding: list, count=3):
    try:
        res = supabase.rpc('match_mevzuat', {
            'query_embedding': embedding,
            'match_count': count
        }).execute()
        return res.data or []
    except Exception as e:
        print(f"Mevzuat arama hatası: {e}")
        return []

def search_kararlar(embedding: list, count=5):
    try:
        res = supabase.rpc('match_kararlar', {
            'query_embedding': embedding,
            'match_count': count
        }).execute()
        return res.data or []
    except Exception as e:
        print(f"Karar arama hatası: {e}")
        return []

def get_rag_response(question: str, history: list = []):
    # 1. Soruyu vektöre çevir
    embedding = embed_query(question)

    # 2. Supabase'den ilgili belgeleri bul
    mevzuat_docs = search_mevzuat(embedding, 3)
    karar_docs   = search_kararlar(embedding, 5)

    # 3. Bağlam oluştur
    context_parts = []
    for m in mevzuat_docs:
        context_parts.append(
            f"[{m['kanun_adi']} Madde {m['madde_no']}]\n{m['icerik']}"
        )
    for k in karar_docs:
        context_parts.append(
            f"[{k['daire']} - {k['esas_no']} / {k['karar_no']}]\n{k['icerik']}"
        )

    context = "\n\n---\n\n".join(context_parts) if context_parts else "Veritabanında henüz kaynak bulunmamaktadır."

    # 4. Gemini'ye gönder
    gemini_history = []
    for msg in history:
        gemini_history.append(
            types.Content(
                role='user' if msg['role'] == 'user' else 'model',
                parts=[types.Part(text=msg['content'])]
            )
        )

    full_system = SYSTEM_PROMPT + f"\n\nKAYNAKLAR:\n{context}"

    response = client.models.generate_content_stream(
        model='gemini-2.0-flash',
        contents=gemini_history + [
            types.Content(role='user', parts=[types.Part(text=question)])
        ],
        config=types.GenerateContentConfig(
            system_instruction=full_system,
        )
    )

    return response, mevzuat_docs, karar_docs