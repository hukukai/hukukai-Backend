from google import genai
from google.genai import types
from supabase import create_client
from dotenv import load_dotenv
import os
import re
import unicodedata

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not GOOGLE_API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("GOOGLE_API_KEY, SUPABASE_URL ve SUPABASE_KEY .env içinde tanımlı olmalı.")

client = genai.Client(api_key=GOOGLE_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EMBED_DIM = 1536
EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash-lite")

SYSTEM_PROMPT = """
Sen HukukAI, Türk hukuku için kaynak kontrollü bir hukuk araştırma ve belge hazırlama asistanısın.

GENEL İLKE:
Cevapların akıcı olabilir; ancak hukuki iddiaların yalnızca KAYNAKLAR bölümündeki mevzuat, karar ve belge içeriklerine dayanmalıdır.
Kaynakta bulunmayan kanun, süre, şart, istisna, içtihat, mahkeme uygulaması veya olay bilgisi üretme.

KATI CEVAP KURALLARI:
1. Yalnızca KAYNAKLAR bölümündeki metinlere dayan.
2. KAYNAKLAR bölümünde açıkça bulunmayan hiçbir kanun, süre, şart, istisna, mahkeme içtihadı veya yorum yazma.
3. Genel hukuk bilgini, eğitim verini veya tahminini kullanarak hukuki sonuç üretme.
4. Kaynaklarda cevap yoksa bunu açıkça söyle.
5. Karar kaynağı yoksa Yargıtay, Danıştay, AYM, emsal karar, yerleşik içtihat veya mahkeme uygulaması varmış gibi konuşma.
6. Mevzuat kaynağı yoksa madde numarası uydurma.
7. Kullanıcı belirsiz soru sorarsa, kesin cevap vermek yerine hangi bilginin eksik olduğunu belirt.
8. Cevapta kullandığın her temel hukuki sonucu en az bir kaynak adıyla destekle.
9. Kaynak atıflarında yalnızca verilen kaynakların adını, madde numarasını veya karar künyesini kullan.
10. Sonunda şu uyarıyı ekle:
   "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."

CEVAP STİLİ:
- Gereksiz uzun giriş yapma.
- Önce kısa ve doğrudan cevap ver.
- Sonra yasal çerçeveyi açıkla.
- Sonra somut/pratik değerlendirme yap.
- Gerektiğinde tablo kullan.
- Kullanıcı belge, dilekçe, ihtarname, sözleşme maddesi veya metin isterse belge taslağı üret.
- Belge üretirken kaynaklı hukuki dayanağı kısa tut, sonra belgeyi ver.

STANDART CEVAP FORMATI:
1. Kısa Cevap
2. Yasal Çerçeve
3. Hukuki Değerlendirme
4. Sonuç / Özet
5. Dayandığı Kaynaklar

KARAR / İÇTİHAT SORULARINDA:
- Eğer karar kaynağı varsa "Elimdeki karar veritabanında..." ifadesiyle başla.
- Karar künyesini açık yaz.
- Kararın hukuki önemini açıkla.
- Karar kaynağı yoksa karar değerlendirmesi yapma.

BELGE TASLAĞI İSTENİRSE:
1. Kullanıcı belge, dilekçe, ihtarname, sözleşme maddesi veya benzeri metin isterse belge moduna geç.
2. Kullanıcı "kısa", "5 cümlelik", "özet" gibi sınırlama verdiyse buna kesin uy; uzun analiz yazma.
3. Belge üretiminde Apilex tarzı sade format kullan:
   - Başlık
   - İHTAR EDEN / TALEP EDEN / BAŞVURAN
   - MUHATAP
   - KONU
   - AÇIKLAMALAR
   - SONUÇ VE İHTAR / TALEP
   - İMZA
4. Belge taslağından önce en fazla 2 cümlelik kısa hukuki dayanak yaz.
5. Belge taslağında resmi, ölçülü, avukat üslubuna uygun dil kullan.
6. "Şüpheniz olmasın", "hemen", "kesinlikle kazanırsınız", "mutlaka", "son uyarı" gibi konuşma dili, tehdit dili veya garanti veren ifadeler kullanma.
7. "İhtiyati haciz", "arabuluculuk", "faiz", "zamanaşımı", "görevli mahkeme", "yetkili mahkeme", "dava şartı" gibi kaynakta bulunmayan özel usul/sonuç bilgilerini ekleme.
8. Kaynakta açıkça yoksa içtihat, Yargıtay, Danıştay, mahkeme uygulaması veya emsal karar yazma.
9. Bilinmeyen taraf, tarih, tutar, olay, adres, banka bilgisi gibi alanları köşeli parantez içinde bırak.
10. İhtarname için özel olarak şu sade yapıyı kullan:

İHTARNAME

İHTAR EDEN:
[Ad / Unvan]
[Adres]

MUHATAP:
[Ad / Unvan]
[Adres]

KONU:
[Kaynağa dayalı kısa konu]

AÇIKLAMALAR:
[Olay ve kaynak dayanağı]

SONUÇ VE İHTAR:
[Talep, süre ve yasal yollara başvuru ihtarı]

İHTAR EDEN:
[Ad / Unvan]
[İmza]

11. Sonunda "Uygulama Notları" başlığı altında en fazla 3 kısa ve nötr madde ekle.
12. Belge taslağından sonra şu uyarıyı ekle:
   "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
"""

# "yukarıdaki madde" tarzı referansları yakalamak için basit patternler
PREVIOUS_ARTICLE_PATTERNS = [
    r"\byukarıdaki maddede\b",
    r"\byukarıdaki madde\b",
    r"\bönceki maddede\b",
    r"\bönceki madde\b",
    r"\bbir üst maddede\b",
    r"\bbir üst madde\b",
]

# İleride genişletmek için burada tutuyoruz
INTRA_ARTICLE_PATTERNS = [
    r"\bbirinci fıkra\b",
    r"\bikinci fıkra\b",
    r"\büçüncü fıkra\b",
    r"\bdördüncü fıkra\b",
    r"\byukarıdaki fıkra\b",
    r"\başağıdaki fıkra\b",
]


def _canon_text(text: str) -> str:
    """
    Türkçe karakter / birleşik karakter sorunlarını azaltmak için
    metni normalize eder.
    Özellikle:
    - ı -> i
    - İ -> i
    - ü -> u
    - ö -> o
    - ç -> c
    - ş -> s
    - ğ -> g
    """
    text = (text or "").strip().casefold()

    text = (
        text.replace("ı", "i")
        .replace("İ", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def embed_query(text: str) -> list:
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=(text or "")[:2000],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBED_DIM,
        ),
    )
    return result.embeddings[0].values


def embed_document(text: str) -> list:
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=(text or "")[:2000],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_DIM,
        ),
    )
    return result.embeddings[0].values


def search_mevzuat_chunks(embedding: list, count=5):
    """
    mevzuat_chunks tablosunda semantic arama yapar.
    match_mevzuat_chunks RPC fonksiyonuna dayanır.
    """
    try:
        res = supabase.rpc(
            "match_mevzuat_chunks",
            {
                "query_embedding": embedding,
                "match_count": count,
            },
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"Mevzuat chunk arama hatası: {e}")
        return []


def get_mevzuat_by_ids(ids: list[int]):
    if not ids:
        return []

    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").in_("id", ids)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Mevzuat kayıt çekme hatası: {e}")
        return []


def get_mevzuat_by_article(kanun_no: str, madde_no: str, madde_tipi: str = "madde"):
    """
    Aynı kanundaki belirli maddeyi çeker.
    """
    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").eq("kanun_no",
                                                                                                    str(kanun_no))
            .eq("madde_no", str(madde_no))
            .eq("madde_tipi", madde_tipi)
            .limit(1)
            .execute()
        )
        data = res.data or []
        return data[0] if data else None
    except Exception as e:
        print(f"Tekil mevzuat çekme hatası: {e}")
        return None


def search_mevzuat(embedding: list, count=8):
    chunks = search_mevzuat_chunks(embedding, count)

    if not chunks:
        return []

    best_chunks_by_doc = {}

    for c in chunks:
        mevzuat_id = c.get("mevzuat_id")
        similarity = c.get("similarity") or 0

        if not mevzuat_id:
            continue

        current = best_chunks_by_doc.get(mevzuat_id)
        if current is None or similarity > (current.get("similarity") or 0):
            best_chunks_by_doc[mevzuat_id] = c

    mevzuat_ids = list(best_chunks_by_doc.keys())
    full_docs = get_mevzuat_by_ids(mevzuat_ids)
    full_docs_map = {doc["id"]: doc for doc in full_docs}

    results = []

    sorted_best_chunks = sorted(
        best_chunks_by_doc.values(),
        key=lambda x: x.get("similarity") or 0,
        reverse=True
    )

    for c in sorted_best_chunks:
        mevzuat_id = c.get("mevzuat_id")
        full_doc = full_docs_map.get(mevzuat_id)

        if not full_doc:
            continue

        results.append({
            "id": full_doc.get("id"),
            "kanun_no": full_doc.get("kanun_no"),
            "kanun_adi": full_doc.get("kanun_adi"),
            "madde_no": full_doc.get("madde_no"),
            "madde_tipi": full_doc.get("madde_tipi"),
            "icerik": full_doc.get("icerik"),
            "structured_content": full_doc.get("structured_content"),
            "chunk_text": c.get("chunk_text", ""),
            "similarity": c.get("similarity"),
            "chunk_index": c.get("chunk_index"),
            "retrieval_source": "semantic",
            "source_type": "mevzuat",
        })

    return results


def search_kararlar(embedding: list, count=5):
    try:
        res = supabase.rpc(
            "match_kararlar",
            {
                "query_embedding": embedding,
                "match_count": count,
            },
        ).execute()
        return res.data or []
    except Exception as e:
        print(f"Karar arama hatası: {e}")
        return []


def keyword_search_mevzuat(query: str, count=8):
    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content")
            .ilike("icerik", f"%{query}%")
            .limit(count)
            .execute()
        )

        rows = res.data or []
        results = []

        for row in rows:
            row["retrieval_source"] = "keyword"
            row["source_type"] = "mevzuat"
            results.append(row)

        return results

    except Exception as e:
        print(f"Keyword mevzuat arama hatası: {e}")
        return []


LAW_ALIASES = {
    "tck": "5237",
    "türk ceza kanunu": "5237",
    "5237": "5237",

    "tbk": "6098",
    "türk borçlar kanunu": "6098",
    "6098": "6098",

    "hmk": "6100",
    "hukuk muhakemeleri kanunu": "6100",
    "6100": "6100",

    "cmk": "5271",
    "ceza muhakemesi kanunu": "5271",
    "5271": "5271",

    "tmk": "4721",
    "türk medeni kanunu": "4721",
    "4721": "4721",
    "ttk": "6102",
    "türk ticaret kanunu": "6102",
    "turk ticaret kanunu": "6102",
    "6102": "6102",

    "iik": "2004",
    "icra ve iflas kanunu": "2004",
    "icra iflas kanunu": "2004",
    "2004": "2004",

    "iş kanunu": "4857",
    "4857": "4857",

    "avk": "1136",
    "avukatlık kanunu": "1136",
    "avukatlik kanunu": "1136",
    "1136": "1136",

    "iyuk": "2577",
    "idari yargılama usulü kanunu": "2577",
    "idari yargilama usulu kanunu": "2577",
    "2577": "2577",

    "arabuluculuk kanunu": "6325",
    "hukuk uyuşmazlıklarında arabuluculuk kanunu": "6325",
    "hukuk uyusmazliklarinda arabuluculuk kanunu": "6325",
    "6325": "6325",

    "tkhk": "6502",
    "tüketicinin korunması hakkında kanun": "6502",
    "tuketicinin korunmasi hakkinda kanun": "6502",
    "6502": "6502",

    "iş mahkemeleri kanunu": "7036",
    "is mahkemeleri kanunu": "7036",
    "7036": "7036",

    "tebligat kanunu": "7201",
    "7201": "7201",

    "amme alacaklarının tahsil usulü hakkında kanun": "6183",
    "amme alacaklarinin tahsil usulu hakkinda kanun": "6183",
    "6183": "6183",

    "bim kanunu": "2576",
    "bölge idare mahkemeleri idare mahkemeleri ve vergi mahkemelerinin kuruluşu ve görevleri hakkında kanun": "2576",
    "bolge idare mahkemeleri idare mahkemeleri ve vergi mahkemelerinin kurulusu ve gorevleri hakkinda kanun": "2576",
    "2576": "2576",

    "kvkk": "6698",
    "kişisel verilerin korunması kanunu": "6698",
    "kisisel verilerin korunmasi kanunu": "6698",
    "6698": "6698",

    "aatuhk": "6183",
    "amme alacaklari kanunu": "6183",

    "bim": "2576",
    "bolge idare mahkemeleri kanunu": "2576",
    "idare ve vergi mahkemeleri kanunu": "2576",

    "tutun kanunu": "4733",
    "tütün kanunu": "4733",
    "4733": "4733",

    "borclar kanunu": "6098",
    "borçlar kanunu": "6098",

    "medeni kanun": "4721",
    "ticaret kanunu": "6102",
    "icra iflas": "2004",
    "tebligat": "7201",
    "is mahkemeleri": "7036",

    "hukuk uyuşmazlıklarında arabuluculuk": "6325",
    "hukuk uyusmazliklarinda arabuluculuk": "6325",
    "arabuluculuk": "6325",

    "is kanunu": "4857",
    "calisma sureleri": "4857",

    "tebligat kan": "7201",

    "amme alacaklari": "6183",

    "tutun": "4733",
    "tebligat k": "7201",
}


def get_short_law_aliases() -> list[str]:
    """
    Parser için kısa / pratik alias listesi üretir.
    Kısa alias mantığı:
    - rakam olmayan
    - çok uzun cümle olmayan
    - en fazla 2 kelimeli doğal kısa kullanım olabilen
    """
    aliases = []

    for alias in LAW_ALIASES.keys():
        alias_c = _canon_text(alias)

        if not alias_c:
            continue
        if alias_c.isdigit():
            continue

        word_count = len(alias_c.split())
        if word_count > 2:
            continue

        if len(alias_c) > 24:
            continue

        aliases.append(alias_c)

    aliases = sorted(set(aliases), key=len, reverse=True)
    return aliases


def get_short_law_alias_pattern() -> str:
    aliases = get_short_law_aliases()
    escaped = [re.escape(a) for a in aliases]
    return r"(?:%s)" % "|".join(escaped)


def get_explicit_law_aliases() -> list[str]:
    """
    Açık kanun referansı tespitinde kullanılacak daha güvenli alias listesi.

    Burada çok genel / bağlamdan bağımsız kullanılabilecek kelimeleri dışarıda bırakırız.
    Örn:
    - tebligat
    - arabuluculuk
    - tutun
    gibi tek başına teknik/konu adı olabilen kelimeler explicit-law detection için fazla gevşektir.
    """
    blocked = {
        "tebligat",
        "arabuluculuk",
        "tutun",
        "amme alacaklari",
        "calisma sureleri",
        "ticaret kanunu",
        "medeni kanun",
        "borclar kanunu",
    }

    aliases = []

    for alias in LAW_ALIASES.keys():
        alias_c = _canon_text(alias)

        if not alias_c:
            continue
        if alias_c.isdigit():
            continue
        if alias_c in blocked:
            continue

        aliases.append(alias_c)

    return sorted(set(aliases), key=len, reverse=True)


def get_explicit_law_alias_pattern() -> str:
    escaped = [re.escape(a) for a in get_explicit_law_aliases()]
    return r"(?:%s)" % "|".join(escaped)


EXPLICIT_LAW_ALIAS_PATTERN = get_explicit_law_alias_pattern()

SHORT_LAW_ALIAS_PATTERN = get_short_law_alias_pattern()

YONETMELIK_ALIASES = {
    "veri sorumlulari sicili hakkinda yonetmelik": {
        "bagli_kanun_no": "6698",
        "yonetmelik_adi": "Veri Sorumluları Sicili Hakkında Yönetmelik",
    },
    "verbis yonetmeligi": {
        "bagli_kanun_no": "6698",
        "yonetmelik_adi": "Veri Sorumluları Sicili Hakkında Yönetmelik",
    },
    "kvkk yonetmeligi": {
        "bagli_kanun_no": "6698",
        "yonetmelik_adi": "Veri Sorumluları Sicili Hakkında Yönetmelik",
    },

    "mesafeli sozlesmeler yonetmeligi": {
        "bagli_kanun_no": "6502",
        "yonetmelik_adi": "Mesafeli Sözleşmeler Yönetmeliği",
    },
    "tuketici mesafeli sozlesmeler yonetmeligi": {
        "bagli_kanun_no": "6502",
        "yonetmelik_adi": "Mesafeli Sözleşmeler Yönetmeliği",
    },

    "is kanununa iliskin calisma sureleri yonetmeligi": {
        "bagli_kanun_no": "4857",
        "yonetmelik_adi": "İş Kanununa İlişkin Çalışma Süreleri Yönetmeliği",
    },
    "calisma sureleri yonetmeligi": {
        "bagli_kanun_no": "4857",
        "yonetmelik_adi": "İş Kanununa İlişkin Çalışma Süreleri Yönetmeliği",
    },
    "4857 calisma sureleri yonetmeligi": {
        "bagli_kanun_no": "4857",
        "yonetmelik_adi": "İş Kanununa İlişkin Çalışma Süreleri Yönetmeliği",
    },
    "hukuk uyusmazliklarinda arabuluculuk kanunu yonetmeligi": {
        "bagli_kanun_no": "6325",
        "yonetmelik_adi": "Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu Yönetmeliği",
    },
    "arabuluculuk yonetmeligi": {
        "bagli_kanun_no": "6325",
        "yonetmelik_adi": "Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu Yönetmeliği",
    },
    "6325 arabuluculuk yonetmeligi": {
        "bagli_kanun_no": "6325",
        "yonetmelik_adi": "Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu Yönetmeliği",
    },

    "ticaret sicili yonetmeligi": {
        "bagli_kanun_no": "6102",
        "yonetmelik_adi": "Ticaret Sicili Yönetmeliği",
    },
    "6102 ticaret sicili yonetmeligi": {
        "bagli_kanun_no": "6102",
        "yonetmelik_adi": "Ticaret Sicili Yönetmeliği",
    },
    "elektronik tebligat yonetmeligi": {
        "bagli_kanun_no": "7201",
        "yonetmelik_adi": "Elektronik Tebligat Yönetmeliği",
    },
    "7201 elektronik tebligat yonetmeligi": {
        "bagli_kanun_no": "7201",
        "yonetmelik_adi": "Elektronik Tebligat Yönetmeliği",
    },
    "e tebligat yonetmeligi": {
        "bagli_kanun_no": "7201",
        "yonetmelik_adi": "Elektronik Tebligat Yönetmeliği",
    },
    "mesafeli sozlesmeler yon.": {
        "bagli_kanun_no": "6502",
        "yonetmelik_adi": "Mesafeli Sözleşmeler Yönetmeliği",
    },
    "mesafeli sozlesmeler yon": {
        "bagli_kanun_no": "6502",
        "yonetmelik_adi": "Mesafeli Sözleşmeler Yönetmeliği",
    },

    "elektronik tebligat yon.": {
        "bagli_kanun_no": "7201",
        "yonetmelik_adi": "Elektronik Tebligat Yönetmeliği",
    },
    "elektronik tebligat yon": {
        "bagli_kanun_no": "7201",
        "yonetmelik_adi": "Elektronik Tebligat Yönetmeliği",
    },

    "ticaret sicili yon.": {
        "bagli_kanun_no": "6102",
        "yonetmelik_adi": "Ticaret Sicili Yönetmeliği",
    },
    "ticaret sicili yon": {
        "bagli_kanun_no": "6102",
        "yonetmelik_adi": "Ticaret Sicili Yönetmeliği",
    },
}


def get_yonetmelik_aliases() -> list[str]:
    aliases = sorted(
        {_canon_text(alias) for alias in YONETMELIK_ALIASES.keys() if alias},
        key=len,
        reverse=True,
    )
    return aliases


def get_yonetmelik_alias_pattern() -> str:
    escaped = [re.escape(a) for a in get_yonetmelik_aliases()]
    return r"(?:%s)" % "|".join(escaped)


SHORT_YONETMELIK_ALIAS_PATTERN = get_yonetmelik_alias_pattern()

TURKISH_NUMBER_WORDS = {
    "sifir": 0,
    "bir": 1,
    "iki": 2,
    "uc": 3,
    "dort": 4,
    "bes": 5,
    "alti": 6,
    "yedi": 7,
    "sekiz": 8,
    "dokuz": 9,
    "on": 10,
    "yirmi": 20,
    "otuz": 30,
    "kirk": 40,
    "elli": 50,
    "altmis": 60,
    "yetmis": 70,
    "seksen": 80,
    "doksan": 90,
    "yuz": 100,
    "bin": 1000,
}

TURKISH_ORDINAL_WORDS = {
    "birinci": 1,
    "ikinci": 2,
    "ucuncu": 3,
    "dorduncu": 4,
    "besinci": 5,
    "altinci": 6,
    "yedinci": 7,
    "sekizinci": 8,
    "dokuzuncu": 9,
    "onuncu": 10,
    "onbirinci": 11,
    "onikinci": 12,
    "onucuncu": 13,
    "ondorduncu": 14,
    "onbesinci": 15,
    "onaltinci": 16,
    "onyedinci": 17,
    "onsekizinci": 18,
    "ondokuzuncu": 19,
    "yirminci": 20,
    "otuzuncu": 30,
    "kirkinci": 40,
    "ellinci": 50,
    "altmisinci": 60,
    "yetmisinci": 70,
    "sekseninci": 80,
    "doksaninci": 90,
    "yuzuncu": 100,
    "bininci": 1000,
}

NUMBER_WORD_TOKENS = set(TURKISH_NUMBER_WORDS.keys())
ORDINAL_WORD_TOKENS = set(TURKISH_ORDINAL_WORDS.keys())

COMPACT_NUMBER_REPLACEMENTS = {
    "sekseniki": "seksen iki",
    "kirkdokuz": "kirk dokuz",
    "yuzondort": "yuz on dort",
    "yuzonbir": "yuz on bir",
    "yuziki": "yuz iki",
    "yuzuc": "yuz uc",
    "yuzyirmi": "yuz yirmi",
}

COMPACT_ORDINAL_REPLACEMENTS = {
    "dorduncu": "dorduncu",
    "ondorduncu": "on dorduncu",
    "yuzondorduncu": "yuz on dorduncu",
    "yuzbirinci": "yuz birinci",
    "yuzikinci": "yuz ikinci",
    "yuzuncu": "yuzuncu",
}

ARTICLE_SUFFIX_PATTERN = r"(?:madde|maddesi|fikra|fikrasi|fıkra|fıkrası|bent|bendi)"
ARTICLE_PREFIX_PATTERN = r"(?:m\.?|md\.?|madd?e(?:si)?)"

NUMBER_TOKEN_PATTERN = (
    r"(?:bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz|on|yirmi|otuz|kirk|elli|"
    r"altmis|yetmis|seksen|doksan|yuz|bin)"
)

ORDINAL_TOKEN_PATTERN = (
    r"(?:birinci|ikinci|ucuncu|dorduncu|besinci|altinci|yedinci|sekizinci|"
    r"dokuzuncu|onuncu|onbirinci|onikinci|onucuncu|ondorduncu|onbesinci|"
    r"onaltinci|onyedinci|onsekizinci|ondokuzuncu|yirminci|otuzuncu|"
    r"kirkinci|ellinci|altmisinci|yetmisinci|sekseninci|doksaninci|"
    r"yuzuncu|bininci)"
)

SPELLED_NUMBER_SEQUENCE_PATTERN = rf"{NUMBER_TOKEN_PATTERN}(?:\s+{NUMBER_TOKEN_PATTERN})*"
SPELLED_ORDINAL_SEQUENCE_PATTERN = rf"(?:{NUMBER_TOKEN_PATTERN}\s+)*{ORDINAL_TOKEN_PATTERN}"


def turkish_number_words_to_int(text: str):
    words = [_canon_text(w) for w in (text or "").strip().split()]
    if not words:
        return None

    total = 0
    current = 0

    for w in words:
        if w not in TURKISH_NUMBER_WORDS:
            return None

        val = TURKISH_NUMBER_WORDS[w]

        if val == 100:
            current = max(1, current) * 100
        elif val == 1000:
            current = max(1, current) * 1000
            total += current
            current = 0
        else:
            current += val

    return total + current


def turkish_ordinal_words_to_int(text: str):
    canon = _canon_text(text)
    if not canon:
        return None

    words = canon.split()
    if not words:
        return None

    last_word = words[-1]
    if last_word not in TURKISH_ORDINAL_WORDS:
        return None

    if len(words) == 1:
        return TURKISH_ORDINAL_WORDS[last_word]

    cardinal_part = " ".join(words[:-1])
    cardinal_value = turkish_number_words_to_int(cardinal_part)
    ordinal_base_value = TURKISH_ORDINAL_WORDS[last_word]

    if cardinal_value is None:
        return None

    if ordinal_base_value in {10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 1000}:
        return cardinal_value + ordinal_base_value

    return cardinal_value - (cardinal_value % 10) + ordinal_base_value


def normalize_turkish_number_word_orthography(question: str) -> str:
    """
    Sadece sayı kelimelerini ASCII-kanonik forma çevirir.
    Örn:
    - yüz -> yuz
    - dört -> dort
    - kırk -> kirk
    - üçüncü -> ucuncu
    """
    q = question or ""

    canon_number_vocab = NUMBER_WORD_TOKENS | ORDINAL_WORD_TOKENS

    def repl(match):
        original = match.group(0)
        canon = _canon_text(original)
        if canon in canon_number_vocab:
            return canon
        return original

    return re.sub(r"\b[^\W\d_]+\b", repl, q, flags=re.IGNORECASE)


def normalize_compact_turkish_number_words(question: str) -> str:
    q = question or ""

    canon_map = {}
    for src, dst in {**COMPACT_NUMBER_REPLACEMENTS, **COMPACT_ORDINAL_REPLACEMENTS}.items():
        canon_map[_canon_text(src)] = dst

    def repl(match):
        original = match.group(0)
        canon = _canon_text(original)
        replacement = canon_map.get(canon)
        return replacement if replacement else original

    return re.sub(r"\b[^\W\d_]+\b", repl, q, flags=re.IGNORECASE)


def normalize_spelled_ordinal_article_numbers(question: str) -> str:
    q = question or ""

    pattern = re.compile(
        rf"\b({SPELLED_ORDINAL_SEQUENCE_PATTERN})\s+({ARTICLE_SUFFIX_PATTERN})\b",
        flags=re.IGNORECASE,
    )

    def repl(match):
        ordinal_part = match.group(1)
        suffix = match.group(2)

        value = turkish_ordinal_words_to_int(ordinal_part)
        if value is None:
            return match.group(0)

        return f"{value}. {suffix}"

    return pattern.sub(repl, q)


def normalize_spelled_article_numbers(question: str) -> str:
    q = question or ""

    patterns = [
        re.compile(
            rf"\b({ARTICLE_PREFIX_PATTERN})\s+({SPELLED_NUMBER_SEQUENCE_PATTERN})\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b({SPELLED_NUMBER_SEQUENCE_PATTERN})\s+({ARTICLE_SUFFIX_PATTERN})\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b((?:{SHORT_LAW_ALIAS_PATTERN}))\s+({SPELLED_NUMBER_SEQUENCE_PATTERN})\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b(({NUMBER_TOKEN_PATTERN}(?:\s+{NUMBER_TOKEN_PATTERN})*))\b",
            flags=re.IGNORECASE,
        ),
    ]

    def replace_with_number(match):
        groups = match.groups()

        if len(groups) == 2:
            left = match.group(1)
            number_part = match.group(2)
            value = turkish_number_words_to_int(number_part)
            if value is None:
                return match.group(0)
            return f"{left} {value}"

        if len(groups) == 1:
            number_part = match.group(1)
            value = turkish_number_words_to_int(number_part)
            if value is None:
                return match.group(0)
            return str(value)

        return match.group(0)

    # önce daha spesifik kalıplar, sonra en genel kalıp
    for pattern in patterns[:-1]:
        q = pattern.sub(replace_with_number, q)

    # genel kalıp sadece açık hukuk sorgularında çalışsın
    if normalize_law_name_to_no(q) or re.search(r"\b(?:m\.|md\.|madde|maddesi)\b", _canon_text(q)):
        q = patterns[-1].sub(replace_with_number, q)

    return q


def normalize_user_legal_query(question: str) -> str:
    q = question or ""
    # 0) hukuk kısaltmalarını normalize et
    q = re.sub(r"\byon\.\s*", "yonetmeligi ", q, flags=re.IGNORECASE)
    q = re.sub(r"\byon\s+(?=\d)", "yonetmeligi ", q, flags=re.IGNORECASE)
    q = re.sub(r"\bk\.\s*(?=\d)", "kanunu ", q, flags=re.IGNORECASE)

    # 0) sayı kelimelerini kanonikleştir
    q = normalize_turkish_number_word_orthography(q)

    # 1) bitişik yazımları önce ayır
    q = normalize_compact_turkish_number_words(q)
    # 1.5) 114/1 ve 7/2-a formatlarını normalize et
    q = re.sub(r"\b(\d+)\s*/\s*(\d+)\s*-\s*([a-zA-Z])\b", r"\1 \2. fıkra \3 bendi", q, flags=re.IGNORECASE)
    q = re.sub(r"\b(\d+)\s*/\s*(\d+)\b", r"\1 \2. fıkra", q)

    # 2) ordinal yapılarını sayılaştır
    q = normalize_spelled_ordinal_article_numbers(q)

    # 3) cardinal sayı sözcüklerini sayılaştır
    q = normalize_spelled_article_numbers(q)

    # 4) küçük temizlikler
    q = re.sub(r"\bm\s*\.\s*(\d+)\b", r"m. \1", q, flags=re.IGNORECASE)
    q = re.sub(r"\bmd\s*\.\s*(\d+)\b", r"md. \1", q, flags=re.IGNORECASE)
    q = re.sub(r"\s{2,}", " ", q).strip()

    return q


MADDE_NO_PATTERN = r"\d+(?:/[A-Z])?"
RANGE_SEPARATOR_PATTERN = r"(?:-|–|—|ila)"
MULTI_NUMBER_LIST_PATTERN = rf"(?:{MADDE_NO_PATTERN}\s*,\s*)*{MADDE_NO_PATTERN}\s*(?:ve\s*{MADDE_NO_PATTERN})?"


def normalize_law_name_to_no(text: str):
    text_c = _canon_text(text)

    alias_items = []
    for alias, kanun_no in LAW_ALIASES.items():
        alias_c = _canon_text(alias)
        if not alias_c:
            continue
        alias_items.append((alias_c, kanun_no))

    # uzun alias önce denensin
    alias_items.sort(key=lambda x: len(x[0]), reverse=True)

    for alias_c, kanun_no in alias_items:
        pattern = rf"(?<!\w){re.escape(alias_c)}(?!\w)"
        if re.search(pattern, text_c, flags=re.IGNORECASE):
            return kanun_no

    return None


def normalize_yonetmelik_ref(text: str):
    text_c = _canon_text(text)

    alias_items = []
    for alias, meta in YONETMELIK_ALIASES.items():
        alias_c = _canon_text(alias)
        if not alias_c:
            continue
        alias_items.append((alias_c, meta))

    alias_items.sort(key=lambda x: len(x[0]), reverse=True)

    for alias_c, meta in alias_items:
        pattern = rf"(?<!\w){re.escape(alias_c)}(?!\w)"
        if re.search(pattern, text_c, flags=re.IGNORECASE):
            return meta

    return None


def parse_explicit_article_refs(question: str):
    """
    Kullanıcı sorusundan açık kanun/madde atıflarını yakalar.

    Desteklenen örnekler:
    - TCK 109
    - TCK m.109
    - 5237 sayılı Kanun 109
    - 5237 sayılı Kanun madde 110
    - madde 110
    - İş Kanunu 17
    - Türk Borçlar Kanunu 2
    - CMK 100
    """
    original_q = (question or "").strip()
    q = _canon_text(original_q)
    refs = []

    detected_kanun_no = normalize_law_name_to_no(original_q)

    def has_explicit_law_reference(text: str) -> bool:
        text_c = _canon_text(text)

        if re.search(r"\b\d{3,4}\s+say[ıi]l[ıi]\s+kanun\b", text_c, flags=re.IGNORECASE):
            return True

        if re.search(rf"\b{EXPLICIT_LAW_ALIAS_PATTERN}\b", text_c, flags=re.IGNORECASE):
            return True

        explicit_alias_set = set(get_explicit_law_aliases())

        for alias in LAW_ALIASES:
            if alias.isdigit():
                continue

            alias_c = _canon_text(alias)
            if alias_c not in explicit_alias_set:
                continue

            pattern = rf"(?<!\w){re.escape(alias_c)}(?!\w)"
            if re.search(pattern, text_c, flags=re.IGNORECASE):
                return True

        return False

    explicit_law_detected = has_explicit_law_reference(original_q)

    def add_range_refs(kanun_no, start_no, end_no):
        if not kanun_no:
            return

        try:
            start = int(start_no)
            end = int(end_no)
        except Exception:
            return

        if start > end:
            start, end = end, start

        # aşırı geniş aralığı engelle
        if end - start > 50:
            return

        for no in range(start, end + 1):
            refs.append({
                "kanun_no": kanun_no,
                "madde_no": str(no),
                "madde_tipi": "madde",
            })

    def add_multi_refs(kanun_no, raw_numbers):
        if not kanun_no or not raw_numbers:
            return

        nums = re.findall(MADDE_NO_PATTERN, raw_numbers, flags=re.IGNORECASE)
        if not nums:
            return

        # aşırı uzun saçma listeyi engelle
        if len(nums) > 20:
            return

        for no in nums:
            madde_no = str(no).upper().replace(" ", "")
            refs.append({
                "kanun_no": kanun_no,
                "madde_no": madde_no,
                "madde_tipi": "madde",
            })

    def add_following_refs(kanun_no, start_no, length=5):
        if not kanun_no:
            return

        try:
            start = int(start_no)
        except Exception:
            return

        if length < 1:
            return

        if length > 10:
            length = 10

        for no in range(start, start + length):
            refs.append({
                "kanun_no": kanun_no,
                "madde_no": str(no),
                "madde_tipi": "madde",
            })

    def add_single_ref(kanun_no, madde_no, madde_tipi="madde"):
        if not kanun_no or not madde_no:
            return

        refs.append({
            "kanun_no": str(kanun_no),
            "madde_no": str(madde_no).upper().replace(" ", ""),
            "madde_tipi": madde_tipi,
        })

    def add_special_single_ref(kanun_no, madde_no, special_type: str):
        special_type = (special_type or "").strip().lower()

        madde_tipi_map = {
            "ek": "ek",
            "gecici": "gecici",
            "ek_gecici": "ek_gecici",
        }

        madde_tipi = madde_tipi_map.get(special_type)
        if not madde_tipi:
            return

        add_single_ref(kanun_no, madde_no, madde_tipi=madde_tipi)

    def add_mukerrer_ref(kanun_no, base_no):
        if not kanun_no or not base_no:
            return

        add_single_ref(kanun_no, f"{str(base_no)}/A", madde_tipi="madde")

    # 1) Genel madde yazım varyasyonları:
    # Sadece açık kanun referansı yoksa generic parse üret.
    general_article_patterns = [
        r"(?:m\.|m|md|madde)\s*(?:no\s*)?(\d+)\b",
        r"\b(\d+)\.\s*madde\b",
        r"\b(\d+)\s*(?:inci|nci|uncu|üncü)\s*madde\b",
        r"\b(\d+)\.\s*maddesi\b",
        r"\b(\d+)\s*maddesi\b",
    ]

    if not explicit_law_detected:
        # "madde 18 ve devamı"
        for match in re.finditer(
                r"(?:m\.|m|md|madde)\s*(?:no\s*)?(\d+)\s+ve\s+devam[ıi]\b",
                q
        ):
            start_no = match.group(1)
            add_following_refs(detected_kanun_no, start_no, length=5)

        for pattern in general_article_patterns:
            for match in re.finditer(pattern, q):
                madde_no = match.group(1)
                refs.append({
                    "kanun_no": detected_kanun_no,
                    "madde_no": madde_no,
                    "madde_tipi": "madde",
                })

    # 2X) "2004 sayılı Kanun Ek Madde 1"
    for match in re.finditer(
            r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+kanun\s+ek\s+madde\s+(\d+)\b",
            q,
            flags=re.IGNORECASE,
    ):
        kanun_no = match.group(1)
        madde_no = match.group(2)
        add_special_single_ref(kanun_no, madde_no, "ek")

    # 2Y) "2004 sayılı Kanun Geçici Madde 1"
    for match in re.finditer(
            r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+kanun\s+gecici\s+madde\s+(\d+)\b",
            q,
            flags=re.IGNORECASE,
    ):
        kanun_no = match.group(1)
        madde_no = match.group(2)
        add_special_single_ref(kanun_no, madde_no, "gecici")

    # 2Z) "1136 sayılı Kanun Ek Geçici Madde 1"
    for match in re.finditer(
            r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+kanun\s+ek\s+gecici\s+madde\s+(\d+)\b",
            q,
            flags=re.IGNORECASE,
    ):
        kanun_no = match.group(1)
        madde_no = match.group(2)
        add_special_single_ref(kanun_no, madde_no, "ek_gecici")

    # 2W) "1136 sayılı Kanun Mükerrer Madde 35"
    for match in re.finditer(
            r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+kanun\s+mukerrer\s+madde\s+(\d+)\b",
            q,
            flags=re.IGNORECASE,
    ):
        kanun_no = match.group(1)
        base_no = match.group(2)
        add_mukerrer_ref(kanun_no, base_no)

    # 2A) "6100 sayılı Kanun 114-118" / "6100 sayılı Kanun 114 ila 118"
    for match in re.finditer(
            rf"\b(\d{{3,4}})\s+say[ıi]l[ıi]\s+kanun\s*(?:m\.|madde)?\s*({MADDE_NO_PATTERN})\s*{RANGE_SEPARATOR_PATTERN}\s*({MADDE_NO_PATTERN})\b",
            q,
            flags=re.IGNORECASE,
    ):
        kanun_no = match.group(1)
        start_no = match.group(2)
        end_no = match.group(3)
        add_range_refs(kanun_no, start_no, end_no)

    # 2B) "6100 sayılı Kanun 114, 115 ve 116"
    for match in re.finditer(
            rf"\b(\d{{3,4}})\s+say[ıi]l[ıi]\s+kanun\s*(?:m\.|madde)?\s*({MULTI_NUMBER_LIST_PATTERN})\b",
            q,
            flags=re.IGNORECASE,
    ):
        kanun_no = match.group(1)
        raw_numbers = match.group(2)
        add_multi_refs(kanun_no, raw_numbers)

    # 2C) "6100 sayılı Kanun 114 ve devamı"
    for match in re.finditer(
            r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+kanun\s*(?:m\.|madde)?\s*(\d+)\s+ve\s+devam[ıi]\b",
            q
    ):
        kanun_no = match.group(1)
        start_no = match.group(2)
        add_following_refs(kanun_no, start_no, length=5)

    # 2) "5237 sayılı Kanun 109" / "5237 sayılı Kanun madde 109"
    # Kanun numarası ile madde numarası arasında gerçek bir ayırıcı zorunlu olsun
    for match in re.finditer(
            r"\b(\d{3,4})\s+say[ıi]l[ıi]\s+kanun\s*(?:m\.|madde)?\s*(\d+)\b",
            q
    ):
        kanun_no = match.group(1)
        madde_no = match.group(2)
        refs.append({
            "kanun_no": kanun_no,
            "madde_no": madde_no,
            "madde_tipi": "madde",
        })

    # 3A) "TBK 18-21" / "TBK 18 ila 21" / "HMK m. 114 ila 118"
    for match in re.finditer(
            rf"\b({SHORT_LAW_ALIAS_PATTERN})\s*(?:m\.|md\.|madde)?\s*({MADDE_NO_PATTERN})\s*{RANGE_SEPARATOR_PATTERN}\s*({MADDE_NO_PATTERN})\b",
            q,
            flags=re.IGNORECASE,
    ):
        alias = match.group(1)
        start_no = match.group(2)
        end_no = match.group(3)
        kanun_no = LAW_ALIASES.get(alias)
        add_range_refs(kanun_no, start_no, end_no)

    # 3B) "TBK 18, 19, 20 ve 21" / "HMK m. 114, 115 ve 116"
    for match in re.finditer(
            rf"\b({SHORT_LAW_ALIAS_PATTERN})\s*(?:m\.|md\.|madde)?\s*({MULTI_NUMBER_LIST_PATTERN})\b",
            q,
            flags=re.IGNORECASE,
    ):
        alias = match.group(1)
        raw_numbers = match.group(2)
        kanun_no = LAW_ALIASES.get(alias)
        add_multi_refs(kanun_no, raw_numbers)

    # 3C) "TBK 18 ve devamı" / "HMK m. 114 ve devamı"
    for match in re.finditer(
            rf"\b({SHORT_LAW_ALIAS_PATTERN})\s*(?:m\.|md\.|madde)?\s*(\d+)\s+ve\s+devam[ıi]\b",
            q
    ):
        alias = match.group(1)
        start_no = match.group(2)
        kanun_no = LAW_ALIASES.get(alias)
        add_following_refs(kanun_no, start_no, length=5)

    # 3) "TCK 109" / "TBK 1" / "CMK 100"
    for match in re.finditer(rf"\b({SHORT_LAW_ALIAS_PATTERN})\s*(?:m\.|md\.|madde)?\s*(\d+)\b", q):
        alias = match.group(1)
        madde_no = match.group(2)
        kanun_no = LAW_ALIASES.get(alias)
        refs.append({
            "kanun_no": kanun_no,
            "madde_no": madde_no,
            "madde_tipi": "madde",
        })

    # 4) "iş kanunu 17" / "turk borclar kanunu 2" / "ceza muhakemesi kanunu 100"
    # 4A) aynı formatın madde aralığı hali: "Türk Borçlar Kanunu 18-21"
    for alias, kanun_no in LAW_ALIASES.items():
        if alias.isdigit():
            continue

        alias_c = _canon_text(alias)

        ek_pattern = rf"\b{re.escape(alias_c)}\s+ek\s+madde\s+(\d+)\b"
        gecici_pattern = rf"\b{re.escape(alias_c)}\s+gecici\s+madde\s+(\d+)\b"
        ek_gecici_pattern = rf"\b{re.escape(alias_c)}\s+ek\s+gecici\s+madde\s+(\d+)\b"
        mukerrer_pattern = rf"\b{re.escape(alias_c)}\s+mukerrer\s+madde\s+(\d+)\b"
        for match in re.finditer(mukerrer_pattern, q, flags=re.IGNORECASE):
            base_no = match.group(1)
            add_mukerrer_ref(kanun_no, base_no)
        for match in re.finditer(ek_gecici_pattern, q, flags=re.IGNORECASE):
            madde_no = match.group(1)
            add_special_single_ref(kanun_no, madde_no, "ek_gecici")

        for match in re.finditer(gecici_pattern, q, flags=re.IGNORECASE):
            madde_no = match.group(1)
            add_special_single_ref(kanun_no, madde_no, "gecici")

        for match in re.finditer(ek_pattern, q, flags=re.IGNORECASE):
            madde_no = match.group(1)
            add_special_single_ref(kanun_no, madde_no, "ek")

        range_pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.?|md\.?|madde|maddesi)?\s*({MADDE_NO_PATTERN})\s*{RANGE_SEPARATOR_PATTERN}\s*({MADDE_NO_PATTERN})\b"

        for match in re.finditer(range_pattern, q, flags=re.IGNORECASE):
            start_no = match.group(1)
            end_no = match.group(2)
            add_range_refs(kanun_no, start_no, end_no)

        multi_pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.?|md\.?|madde|maddesi)?\s*({MULTI_NUMBER_LIST_PATTERN})\b"

        for match in re.finditer(multi_pattern, q, flags=re.IGNORECASE):
            raw_numbers = match.group(1)
            add_multi_refs(kanun_no, raw_numbers)

        follow_pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.?|md\.?|madde|maddesi)?\s*(\d+)\s+ve\s+devam[ıi]\b"

        for match in re.finditer(follow_pattern, q):
            start_no = match.group(1)
            add_following_refs(kanun_no, start_no, length=5)

        pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.?|md\.?|madde|maddesi)?\s*(\d+)\b"
        for match in re.finditer(pattern, q):
            madde_no = match.group(1)
            refs.append({
                "kanun_no": kanun_no,
                "madde_no": madde_no,
                "madde_tipi": "madde",
            })

    # duplicate temizle
    deduped = []
    seen = set()

    for ref in refs:
        key = (ref.get("kanun_no"), ref.get("madde_no"), ref.get("madde_tipi"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)

    return deduped


def debug_parse_explicit_article_refs(question: str):
    return {
        "question": question,
        "normalized_question": _canon_text(question),
        "refs": parse_explicit_article_refs(question),
    }


def debug_detect_explicit_law_reference(question: str):
    q = (question or "").strip()

    def has_explicit_law_reference(text: str) -> bool:
        text_c = _canon_text(text)

        if re.search(r"\b\d{3,4}\s+say[ıi]l[ıi]\s+kanun\b", text_c, flags=re.IGNORECASE):
            return True

        if re.search(rf"\b{EXPLICIT_LAW_ALIAS_PATTERN}\b", text_c, flags=re.IGNORECASE):
            return True

        explicit_alias_set = set(get_explicit_law_aliases())

        for alias in LAW_ALIASES:
            if alias.isdigit():
                continue

            alias_c = _canon_text(alias)
            if alias_c not in explicit_alias_set:
                continue

            pattern = rf"(?<!\w){re.escape(alias_c)}(?!\w)"
            if re.search(pattern, text_c, flags=re.IGNORECASE):
                return True

        return False

    return {
        "question": q,
        "normalized_question": _canon_text(q),
        "explicit_law_detected": has_explicit_law_reference(q),
    }


def extract_last_law_from_history(history=None):
    """
    Konuşma geçmişinden son açık geçen kanunu bulmaya çalışır.
    Amaç:
    - "bu Kanunun 18 inci maddesi"
    - "önceki madde"
    gibi devam sorularında retrieval'a yardımcı olmak.
    """
    history = history or []

    for msg in reversed(history):
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        refs = parse_explicit_article_refs(content)
        if refs:
            for ref in reversed(refs):
                if ref.get("kanun_no"):
                    return {
                        "kanun_no": ref.get("kanun_no"),
                        "madde_no": ref.get("madde_no"),
                        "madde_tipi": ref.get("madde_tipi", "madde"),
                    }

    return None


def resolve_contextual_article_question(question: str, history=None):
    """
    Soru açık kanun adı içermiyorsa ama 'bu Kanun', 'önceki madde' gibi
    bağlamsal ifade içeriyorsa history'den son kanunu taşır.
    """
    q = _canon_text(question)
    last_ref = extract_last_law_from_history(history)

    if not last_ref:
        return question

    kanun_no = last_ref.get("kanun_no")
    last_madde_no = last_ref.get("madde_no")
    # "bu Kanunun 48 ve devamı"
    m = re.search(
        r"\bbu\s+kanun(?:un|unun|nun|nın|na|nda|daki)?\s+(\d+)\s+ve\s+devam[ıi]\b",
        q,
        flags=re.IGNORECASE,
    )
    if m:
        start_no = m.group(1)
        return f"{kanun_no} sayılı Kanun madde {start_no} ve devamı"

    # "bu Kanunun 18-21" / "bu Kanunun 18 ila 21" / "bu Kanunun 18-21. maddeleri"
    m = re.search(
        rf"\bbu\s+kanun(?:un|unun|nun|nın|na|nda|daki)?\s+({MADDE_NO_PATTERN})\s*{RANGE_SEPARATOR_PATTERN}\s*({MADDE_NO_PATTERN})(?:\.?\s*madd(?:e|esi|eleri)?)?\b",
        q,
        flags=re.IGNORECASE,
    )
    if m:
        start_no = m.group(1)
        end_no = m.group(2)
        return f"{kanun_no} sayılı Kanun madde {start_no}-{end_no}"

    # "bu Kanunun 18, 19 ve 20. maddeleri"
    # "bu Kanunun 48, 49 ve 50 maddeleri"
    m = re.search(
        r"\bbu\s+kanun(?:un|unun|nun|nın|na|nda|daki)?\s+((?:\d+\s*,\s*)+\d+\s*(?:ve\s*\d+)?)\.?\s*madd(?:e|eleri|esi)?",
        q,
        flags=re.IGNORECASE,
    )
    if m:
        raw_numbers = m.group(1).strip()
        return f"{kanun_no} sayılı Kanun madde {raw_numbers}"

    # "bu Kanunun 18 inci maddesi"
    m = re.search(
        r"\bbu\s+kanun(?:un|unun|nun|nın|na|nda|daki)?\s+(\d+)\s*(?:inci|nci|uncu|üncü)\s*madd",
        q,
        flags=re.IGNORECASE,
    )
    if m:
        madde_no = m.group(1)
        return f"{kanun_no} sayılı Kanun madde {madde_no}"

    # "bu kanunun 18 maddesi"
    m = re.search(
        r"\bbu\s+kanun(?:un|unun|nun|nın|na|nda|daki)?\s+(\d+)\s*madd(?:e|esi)?\b",
        q,
        flags=re.IGNORECASE,
    )
    if m:
        madde_no = m.group(1)
        return f"{kanun_no} sayılı Kanun madde {madde_no}"

    # "bu Kanunun 18. maddesi" / "bu kanunun 18. madde"
    m = re.search(
        r"\bbu\s+kanun(?:un|unun|nun|nın|na|nda|daki)?\s+(\d+)\.\s*madd(?:e|esi)?\b",
        q,
        flags=re.IGNORECASE,
    )
    if m:
        madde_no = m.group(1)
        return f"{kanun_no} sayılı Kanun madde {madde_no}"

    if re.search(r"\bbu\s+madde(?:yi|ye|de|den)?\b", q, flags=re.IGNORECASE):
        if last_madde_no:
            return f"{kanun_no} sayılı Kanun madde {last_madde_no}"

    if re.search(r"\b(onceki|önceki|yukaridaki|yukarıdaki)\s+madde\b", q, flags=re.IGNORECASE):
        if last_madde_no and str(last_madde_no).isdigit():
            prev_no = max(1, int(last_madde_no) - 1)
            return f"{kanun_no} sayılı Kanun madde {prev_no}"

    if re.search(r"\b(sonraki|asagidaki|aşağıdaki)\s+madde\b", q, flags=re.IGNORECASE):
        if last_madde_no and str(last_madde_no).isdigit():
            next_no = int(last_madde_no) + 1
            return f"{kanun_no} sayılı Kanun madde {next_no}"
    return question


def parse_intra_article_refs(question: str):
    """
    Soru içindeki fıkra ve bent atıflarını yakalar.
    """
    q = _canon_text(normalize_user_legal_query(question))
    refs = []

    patterns = [
        (r"\bbirinci\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "1"),
        (r"\bikinci\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "2"),
        (r"\bucuncu\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "3"),
        (r"\bdorduncu\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "4"),

        (r"\b1\.\s*f[ıi]kra\b", "1"),
        (r"\b2\.\s*f[ıi]kra\b", "2"),
        (r"\b3\.\s*f[ıi]kra\b", "3"),
        (r"\b4\.\s*f[ıi]kra\b", "4"),

        (r"\b1\s*(?:inci|nci|uncu|uncu)\s*f[ıi]kra\b", "1"),
        (r"\b2\s*(?:inci|nci|uncu|uncu)\s*f[ıi]kra\b", "2"),
        (r"\b3\s*(?:inci|nci|uncu|uncu)\s*f[ıi]kra\b", "3"),
        (r"\b4\s*(?:inci|nci|uncu|uncu)\s*f[ıi]kra\b", "4"),

        (r"\byukaridaki\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "previous"),
        (r"\bonceki\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "previous"),
        (r"\bbu\s*f[ıi]kra(?:[a-zçğıöşü]*)?\b", "current"),

        (r"\byukaridaki\s*f[ıi]kralar(?:[a-zçğıöşü]*)?\b", "previous_plural"),
        (r"\bonceki\s*f[ıi]kralar(?:[a-zçğıöşü]*)?\b", "previous_plural"),
    ]

    for pattern, ref_value in patterns:
        if re.search(pattern, q, flags=re.IGNORECASE):
            refs.append({
                "type": "fikra",
                "value": ref_value,
            })

    bent_patterns = [
        r"\b([a-zçğıöşü])\s*bendi\b",
        r"\b([a-zçğıöşü])\s*bent\b",
        r"\(([a-zçğıöşü])\)\s*bendi\b",
        r"\(([a-zçğıöşü])\)\s*bent\b",
    ]

    for pattern in bent_patterns:
        for match in re.finditer(pattern, q, flags=re.IGNORECASE):
            bent_value = match.group(1).lower()
            refs.append({
                "type": "bent",
                "value": bent_value,
            })

    numeric_bent_patterns = [
        (r"\b1\.\s*bent\b", "1"),
        (r"\b2\.\s*bent\b", "2"),
        (r"\b3\.\s*bent\b", "3"),
        (r"\b4\.\s*bent\b", "4"),

        (r"\b1\s*numarali\s*bent\b", "1"),
        (r"\b2\s*numarali\s*bent\b", "2"),
        (r"\b3\s*numarali\s*bent\b", "3"),
        (r"\b4\s*numarali\s*bent\b", "4"),

        (r"\bbirinci\s*bent\b", "1"),
        (r"\bikinci\s*bent\b", "2"),
        (r"\bucuncu\s*bent\b", "3"),
        (r"\bdorduncu\s*bent\b", "4"),
    ]

    for pattern, bent_value in numeric_bent_patterns:
        if re.search(pattern, q, flags=re.IGNORECASE):
            refs.append({
                "type": "numeric_bent",
                "value": bent_value,
            })

    return refs


def resolve_contextual_fikra_refs(intra_refs: list):
    """
    Açık ve bağlamsal fıkra atıflarını birlikte çözer.
    Örn:
    - ["2", "current"] -> current = 2
    - ["3", "previous"] -> previous = 2
    - ["4", "previous_plural"] -> [1,2,3]
    """
    explicit_nums = [r.get("value") for r in intra_refs if r.get("value") in {"1", "2", "3", "4"}]

    current_explicit = explicit_nums[-1] if explicit_nums else None
    resolved = []

    for ref in intra_refs:
        value = ref.get("value")

        if value in {"1", "2", "3", "4"}:
            resolved.append({
                "type": "fikra",
                "value": value,
                "resolved": value,
            })

        elif value == "current":
            resolved.append({
                "type": "fikra",
                "value": value,
                "resolved": current_explicit,
            })

        elif value == "previous":
            prev_value = None
            if current_explicit and current_explicit.isdigit():
                n = int(current_explicit)
                if n > 1:
                    prev_value = str(n - 1)

            resolved.append({
                "type": "fikra",
                "value": value,
                "resolved": prev_value,
            })

        elif ref.get("type") == "bent":
            resolved.append({
                "type": "bent",
                "value": value,
                "resolved": value,
            })

        elif value == "previous_plural":
            prev_values = []
            if current_explicit and current_explicit.isdigit():
                n = int(current_explicit)
                if n > 1:
                    prev_values = [str(i) for i in range(1, n)]

            resolved.append({
                "type": "fikra",
                "value": value,
                "resolved": prev_values,
            })

    return resolved


def debug_parse_intra_article_refs(question: str):
    normalized = normalize_user_legal_query(question)
    return {
        "question": question,
        "normalized_question": _canon_text(normalized),
        "refs": parse_intra_article_refs(normalized),
    }


def extract_requested_fikra_text(article_text: str, intra_refs: list, structured_content: dict = None):
    """
    Tam madde metni içinden veya structured_content içinden istenen fıkrayı/bendi çıkarmaya çalışır.
    Önce structured_content'e bakar, bulamazsa eski regex fallback kullanır.
    """
    if not intra_refs:
        return None

    resolved_refs = resolve_contextual_fikra_refs(intra_refs)

    requested = None
    requested_list = None
    requested_bent = None
    requested_numeric_bent = None

    for ref in intra_refs:
        if ref.get("type") == "bent":
            requested_bent = ref.get("value")
        elif ref.get("type") == "numeric_bent":
            requested_numeric_bent = ref.get("value")

    # 1) previous_plural varsa onu kullan
    for ref in resolved_refs:
        resolved_value = ref.get("resolved")
        value_type = ref.get("value")

        if value_type == "previous_plural" and isinstance(resolved_value, list) and resolved_value:
            requested_list = resolved_value
            break

    # 2) tekli resolved / explicit fıkra
    if requested_list is None:
        for ref in resolved_refs:
            resolved_value = ref.get("resolved")
            if isinstance(resolved_value, str) and resolved_value in {"1", "2", "3", "4"}:
                requested = resolved_value

    if not requested and not requested_list and not requested_bent and not requested_numeric_bent:
        return None

    def _extract_text_from_fikra_value(value):
        if isinstance(value, str):
            text = value.strip()

            if requested_numeric_bent:
                pattern = rf"(?:(?<=\s)|^){re.escape(requested_numeric_bent)}\.\s*(.+?)(?=(?:(?<=\s)|^)\d+\.\s|$)"
                m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
                if m:
                    return f"{requested_numeric_bent}. {m.group(1).strip()}"

            return text

        if isinstance(value, dict):
            text = value.get("text", "").strip()
            bentler = value.get("bentler", {}) or {}

            if requested_bent:
                bent_text = bentler.get(requested_bent)
                if bent_text:
                    return bent_text

            if requested_numeric_bent:
                pattern = rf"(?:(?<=\s)|^){re.escape(requested_numeric_bent)}\.\s*(.+?)(?=(?:(?<=\s)|^)\d+\.\s|$)"
                m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
                if m:
                    return f"{requested_numeric_bent}. {m.group(1).strip()}"

            return text

        return None

    # 1) Önce structured_content'ten bak
    if structured_content and isinstance(structured_content, dict):
        fikralar = structured_content.get("fikralar", {})
        if isinstance(fikralar, dict):
            if requested_list:
                parts = []
                for no in requested_list:
                    value = fikralar.get(no)
                    extracted = _extract_text_from_fikra_value(value)
                    if extracted:
                        parts.append(extracted)

                if parts:
                    return "\n".join(parts)

            if requested:
                value = fikralar.get(requested)
                extracted = _extract_text_from_fikra_value(value)
                if extracted:
                    return extracted
            # İstenen fıkra bulunamadıysa ama bent istendiyse,
            # yapının yanlış/eksik kurulmuş olma ihtimaline karşı
            # tüm fıkralarda aynı benti ara.
            if requested and requested_bent:
                for _, value in fikralar.items():
                    if isinstance(value, dict):
                        bentler = value.get("bentler", {}) or {}
                        bent_text = bentler.get(requested_bent)
                        if bent_text:
                            return bent_text

            # Sadece bent sorulmuşsa ve açık fıkra istenmemişse:
            if requested_bent and not requested and not requested_list:
                for _, value in fikralar.items():
                    if isinstance(value, dict):
                        bentler = value.get("bentler", {}) or {}
                        bent_text = bentler.get(requested_bent)
                        if bent_text:
                            return bent_text

            # Sadece numaralı bent sorulmuşsa (örn: 1. bent), tüm fıkralarda ara
            if requested_numeric_bent and not requested and not requested_list:
                for _, value in fikralar.items():
                    extracted = _extract_text_from_fikra_value(value)
                    if extracted:
                        return extracted

    # 2) Fallback: ham metinden eski fıkra ayrımı
    text = (article_text or "").strip()
    # 2A) Numaralı bent için ham metinden doğrudan çekmeye çalış
    if requested_numeric_bent:
        pattern = rf"(?:(?<=\s)|^){re.escape(requested_numeric_bent)}\.\s*(.+?)(?=(?:(?<=\s)|^)\d+\.\s|$)"
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return f"{requested_numeric_bent}. {m.group(1).strip()}"
    parts = re.split(r"(\(\d+\))", text)

    if len(parts) < 3:
        return None

    fikra_map = {}
    current_no = None

    for part in parts:
        if re.fullmatch(r"\(\d+\)", part or ""):
            current_no = part.strip("()")
            fikra_map[current_no] = part
        else:
            if current_no:
                fikra_map[current_no] += part

    if requested_list:
        out = []
        for no in requested_list:
            value = fikra_map.get(no)
            if value:
                out.append(value)
        if out:
            return "\n".join(out)

    if requested:
        return fikra_map.get(requested)

    return None


def get_context_text_for_doc(doc: dict, question: str) -> str:
    """
    Context'e tam madde mi, yoksa istenen fıkra mı girecek onu belirler.
    """
    full_text = doc.get("icerik") or ""
    structured_content = doc.get("structured_content")
    intra_refs = parse_intra_article_refs(question)

    fikra_text = extract_requested_fikra_text(
        full_text,
        intra_refs,
        structured_content=structured_content,
    )

    if fikra_text:
        return fikra_text

    return full_text


def get_mevzuat_article(kanun_no: str, madde_no: str, madde_tipi: str = "madde"):
    """
    mevzuat tablosundan doğrudan madde çeker.
    Chunk olmasa bile çalışır.
    """
    if not kanun_no or not madde_no:
        return None

    try:
        res = (
            supabase.table("mevzuat")
            .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, structured_content").eq("kanun_no",
                                                                                                    str(kanun_no))
            .eq("madde_no", str(madde_no))
            .eq("madde_tipi", madde_tipi)
            .limit(1)
            .execute()
        )

        data = res.data or []
        if not data:
            return None

        doc = data[0]
        doc["retrieval_source"] = "direct_article_lookup"
        doc["source_type"] = "mevzuat"
        return doc

    except Exception as e:
        print(f"Direct article lookup hatası: {e}")
        return None


def get_yonetmelik_article(bagli_kanun_no: str, yonetmelik_adi: str, madde_no: str, madde_tipi: str = "madde"):
    try:
        res = (
            supabase.table("yonetmelik")
            .select("id, bagli_kanun_no, yonetmelik_adi, madde_no, madde_tipi, icerik, structured_content, source_type")
            .eq("bagli_kanun_no", str(bagli_kanun_no))
            .eq("yonetmelik_adi", str(yonetmelik_adi))
            .eq("madde_no", str(madde_no))
            .eq("madde_tipi", madde_tipi)
            .limit(1)
            .execute()
        )

        data = res.data or []
        if not data:
            return None

        doc = data[0]
        doc["retrieval_source"] = "direct_yonetmelik_lookup"
        doc["source_type"] = "yonetmelik"
        doc["kanun_no"] = doc.get("bagli_kanun_no")
        doc["kanun_adi"] = doc.get("yonetmelik_adi")
        return doc

    except Exception as e:
        print(f"Tekil yönetmelik çekme hatası: {e}")
        return None


def get_explicitly_requested_articles(question: str):
    refs = parse_explicit_article_refs(question)
    docs = []

    for ref in refs:
        kanun_no = ref.get("kanun_no")
        madde_no = ref.get("madde_no")
        madde_tipi = ref.get("madde_tipi", "madde")

        doc = get_mevzuat_article(kanun_no, madde_no, madde_tipi)
        if doc:
            docs.append(doc)

    return docs


def get_explicitly_requested_yonetmelik_articles(question: str):
    q = _canon_text(question)
    docs = []

    for alias, meta in YONETMELIK_ALIASES.items():
        alias_c = _canon_text(alias)

        pattern = rf"\b{re.escape(alias_c)}\s*(?:m\.?|md\.?|madde|maddesi)?\s*({MADDE_NO_PATTERN})\b"
        for match in re.finditer(pattern, q, flags=re.IGNORECASE):
            madde_no = match.group(1)

            doc = get_yonetmelik_article(
                bagli_kanun_no=meta["bagli_kanun_no"],
                yonetmelik_adi=meta["yonetmelik_adi"],
                madde_no=madde_no,
                madde_tipi="madde",
            )
            if doc:
                docs.append(doc)

    return dedupe_mevzuat_docs(docs)


def debug_get_explicitly_requested_yonetmelik_articles(question: str):
    docs = get_explicitly_requested_yonetmelik_articles(question)
    return {
        "question": question,
        "normalized_question": _canon_text(question),
        "count": len(docs),
        "docs": [
            {
                "bagli_kanun_no": d.get("bagli_kanun_no"),
                "yonetmelik_adi": d.get("yonetmelik_adi"),
                "madde_no": d.get("madde_no"),
                "madde_tipi": d.get("madde_tipi"),
                "retrieval_source": d.get("retrieval_source"),
            }
            for d in docs
        ],
    }


def dedupe_mevzuat_docs(docs: list):
    result = []
    seen = set()

    for doc in docs:
        if not doc:
            continue

        source_type = str(doc.get("source_type") or "mevzuat")

        if source_type == "yonetmelik":
            key = (
                source_type,
                str(doc.get("bagli_kanun_no") or doc.get("kanun_no") or ""),
                str(doc.get("yonetmelik_adi") or doc.get("kanun_adi") or ""),
                str(doc.get("madde_tipi") or "madde"),
                str(doc.get("madde_no") or ""),
            )
        else:
            key = (
                source_type,
                str(doc.get("kanun_no") or ""),
                str(doc.get("madde_tipi") or "madde"),
                str(doc.get("madde_no") or ""),
            )

        if key in seen:
            continue

        seen.add(key)
        result.append(doc)

    return result


def _normalize_doc(doc: dict) -> dict:
    """
    Semantic search sonucu ile keyword search sonucu aynı formatta olsun.
    """
    return {
        "id": doc.get("id"),
        "kanun_no": doc.get("kanun_no"),
        "kanun_adi": doc.get("kanun_adi"),
        "madde_no": doc.get("madde_no"),
        "madde_tipi": doc.get("madde_tipi", "madde"),
        "icerik": doc.get("icerik", ""),
        "structured_content": doc.get("structured_content"),
        "chunk_text": doc.get("chunk_text", ""),
        "similarity": doc.get("similarity"),
        "chunk_index": doc.get("chunk_index"),
        "retrieval_source": doc.get("retrieval_source", "semantic_or_keyword"),
        "source_type": doc.get("source_type", "mevzuat"),
    }


def _get_retrieval_priority(doc: dict) -> int:
    """
    Aynı madde birden fazla kaynaktan gelirse hangisinin tutulacağını belirler.
    Büyük sayı = daha güçlü kaynak.
    """
    source = str(doc.get("retrieval_source") or "")

    priority_map = {
        "direct_article_lookup": 100,
        "direct_yonetmelik_lookup": 95,
        "semantic_or_keyword": 60,
        "keyword": 50,
        "semantic": 70,
        "reference_graph": 30,
        "previous_article_ref": 20,
    }

    return priority_map.get(source, 10)


def _get_doc_sort_score(doc: dict) -> tuple:
    """
    Merge sonrası sıralama için skor üretir.
    Önce retrieval gücü, sonra similarity kullanılır.
    """
    priority = _get_retrieval_priority(doc)

    similarity = doc.get("similarity")
    try:
        similarity = float(similarity) if similarity is not None else 0.0
    except Exception:
        similarity = 0.0

    return (priority, similarity)


def _choose_better_doc(existing: dict, candidate: dict) -> dict:
    """
    Aynı madde iki farklı retrieval kaynağından geldiyse
    daha iyi olan versiyonu seç.
    """
    if not existing:
        return candidate
    if not candidate:
        return existing

    existing_score = _get_doc_sort_score(existing)
    candidate_score = _get_doc_sort_score(candidate)

    if candidate_score > existing_score:
        return candidate

    return existing


def _safe_int(value):
    try:
        return int(str(value))
    except Exception:
        return None


def build_ranking_context(question: str) -> dict:
    """
    Ranking sırasında tekrar tekrar parse yapmamak için
    soru bazlı yardımcı verileri tek yerde hazırlar.
    """
    refs = parse_explicit_article_refs(question)

    explicit_ref_keys = set()
    anchor_numbers = []
    primary_law_no = None

    for ref in refs:
        kanun_no = str(ref.get("kanun_no") or "")
        madde_tipi = str(ref.get("madde_tipi") or "madde")
        madde_no = str(ref.get("madde_no") or "")

        explicit_ref_keys.add((kanun_no, madde_tipi, madde_no))

        if primary_law_no is None and kanun_no:
            primary_law_no = kanun_no

        if madde_no.isdigit():
            anchor_numbers.append(int(madde_no))

    if primary_law_no is None:
        primary_law_no = normalize_law_name_to_no(question)

    return {
        "explicit_ref_keys": explicit_ref_keys,
        "primary_law_no": primary_law_no,
        "anchor_numbers": anchor_numbers,
    }


def should_retrieve_kararlar(question: str) -> bool:
    """
    Kullanıcı açıkça içtihat / karar odaklı soruyorsa karar retrieval açılır.
    Salt mevzuat sorularında gereksiz yere açılmaz.
    """
    q = _canon_text(question)

    strong_patterns = [
        r"\byargitay\b",
        r"\bdanistay\b",
        r"\baym\b",
        r"\banayasa mahkemesi\b",
        r"\bemsal\b",
        r"\bictihat\b",
        r"\biçtihat\b",
        r"\bhgk\b",
        r"\bceza genel kurulu\b",
        r"\bhukuk genel kurulu\b",
        r"\bkarar no\b",
        r"\besas no\b",
    ]

    has_strong = any(re.search(pattern, q, flags=re.IGNORECASE) for pattern in strong_patterns)

    # Güçlü sinyal varsa direkt aç
    if has_strong:
        return True

    # Sadece zayıf sinyaller yetmesin
    return False


def compute_mevzuat_doc_rank_score(
        doc: dict,
        question: str,
        ranking_context: dict | None = None,
) -> float:
    """
    Dokümanı soru ile ilişkisine göre puanla.
    Büyük skor = daha üst sırada görünmeli.
    """
    score = 0.0

    if ranking_context is None:
        ranking_context = build_ranking_context(question)

    explicit_ref_keys = ranking_context.get("explicit_ref_keys", set())
    primary_law_no = ranking_context.get("primary_law_no")
    anchor_numbers = ranking_context.get("anchor_numbers", [])

    # 1) retrieval source baz puanı
    source_priority = _get_retrieval_priority(doc)
    score += float(source_priority)

    # 2) similarity bonus
    similarity = doc.get("similarity")
    try:
        similarity = float(similarity) if similarity is not None else 0.0
    except Exception:
        similarity = 0.0
    score += similarity * 20.0

    # 3) explicit requested article exact match bonus
    doc_key = _doc_key(doc)
    if doc_key in explicit_ref_keys:
        score += 1000.0

    # 4) same law bonus
    if primary_law_no and str(doc.get("kanun_no") or "") == str(primary_law_no):
        score += 120.0

    # 5) proximity bonus
    doc_madde_no = _safe_int(doc.get("madde_no"))

    if anchor_numbers and doc_madde_no is not None:
        closest_distance = min(abs(doc_madde_no - n) for n in anchor_numbers)

        if closest_distance == 0:
            score += 150.0
        elif closest_distance == 1:
            score += 60.0
        elif closest_distance <= 3:
            score += 30.0
        elif closest_distance <= 5:
            score += 10.0

    # 6) expansion penalty
    source = str(doc.get("retrieval_source") or "")
    if source == "reference_graph":
        score -= 20.0
    elif source == "previous_article_ref":
        score -= 30.0

    return score


def rank_mevzuat_docs(docs: list, question: str, limit: int | None = None) -> list:
    """
    Dokümanları production-friendly şekilde sırala.
    """
    normalized_docs = [_normalize_doc(doc) for doc in docs if doc]
    ranking_context = build_ranking_context(question)

    ranked = sorted(
        normalized_docs,
        key=lambda d: (
            -compute_mevzuat_doc_rank_score(d, question, ranking_context=ranking_context),
            -_get_doc_sort_score(d)[0],
            -_get_doc_sort_score(d)[1],
        )
    )

    if limit is not None:
        return ranked[:limit]

    return ranked


def _doc_key(doc: dict) -> tuple:
    source_type = str(doc.get("source_type") or "mevzuat")

    if source_type == "yonetmelik":
        return (
            source_type,
            str(doc.get("bagli_kanun_no") or doc.get("kanun_no") or ""),
            str(doc.get("yonetmelik_adi") or doc.get("kanun_adi") or ""),
            str(doc.get("madde_tipi") or "madde"),
            str(doc.get("madde_no") or ""),
        )

    return (
        source_type,
        str(doc.get("kanun_no") or ""),
        str(doc.get("madde_tipi") or "madde"),
        str(doc.get("madde_no") or ""),
    )


def merge_mevzuat_docs(primary_docs: list, extra_docs: list, limit: int = 12) -> list:
    """
    Duplicate'leri kaldırarak listeyi birleştirir.
    Aynı madde birden fazla kaynaktan gelirse en iyi versiyonu tutar.
    """
    best_by_key = {}
    first_seen_order = {}

    all_docs = primary_docs + extra_docs

    for idx, doc in enumerate(all_docs):
        if not doc:
            continue

        normalized = _normalize_doc(doc)
        key = _doc_key(normalized)

        if key not in first_seen_order:
            first_seen_order[key] = idx

        current_best = best_by_key.get(key)
        best_by_key[key] = _choose_better_doc(current_best, normalized)

    merged = list(best_by_key.values())

    merged.sort(
        key=lambda d: (
            -_get_doc_sort_score(d)[0],
            -_get_doc_sort_score(d)[1],
            first_seen_order.get(_doc_key(d), 10 ** 9),
        )
    )

    return merged[:limit]


def detect_previous_article_reference(text: str) -> bool:
    text = (text or "").lower()
    return any(re.search(pattern, text) for pattern in PREVIOUS_ARTICLE_PATTERNS)


def expand_previous_article_refs(mevzuat_docs: list, max_extra_docs: int = 4) -> list:
    """
    'yukarıdaki maddede' gibi referans varsa bir önceki maddeyi ekler.
    Şimdilik sadece numerik normal 'madde' tipinde çalışır.
    """
    extras = []
    seen = {_doc_key(doc) for doc in mevzuat_docs}

    for doc in mevzuat_docs:
        icerik = doc.get("icerik", "")
        if not detect_previous_article_reference(icerik):
            continue

        madde_tipi = doc.get("madde_tipi")
        madde_no = str(doc.get("madde_no") or "").strip()
        kanun_no = str(doc.get("kanun_no") or "").strip()

        # Şimdilik sadece "madde 110 -> 109" gibi düz numerik senaryo
        if madde_tipi != "madde" or not madde_no.isdigit():
            continue

        prev_madde_no = str(int(madde_no) - 1)
        if int(prev_madde_no) <= 0:
            continue

        prev_doc = get_mevzuat_by_article(
            kanun_no=kanun_no,
            madde_no=prev_madde_no,
            madde_tipi="madde",
        )

        if not prev_doc:
            continue

        prev_doc["retrieval_source"] = "previous_article_ref"
        normalized_prev = _normalize_doc(prev_doc)
        prev_key = _doc_key(normalized_prev)

        if prev_key in seen:
            continue

        seen.add(prev_key)
        extras.append(normalized_prev)

        if len(extras) >= max_extra_docs:
            break

    return extras


def get_referenced_mevzuat_docs(mevzuat_docs: list, max_extra_docs: int = 6) -> list:
    """
    mevzuat_references tablosundan bağlı maddeleri çek.
    """
    extras = []
    seen = {_doc_key(doc) for doc in mevzuat_docs}

    for doc in mevzuat_docs:
        kanun_no = str(doc.get("kanun_no") or "").strip()
        madde_tipi = str(doc.get("madde_tipi") or "madde").strip()
        madde_no = str(doc.get("madde_no") or "").strip()

        if not kanun_no or not madde_no:
            continue

        try:
            res = (
                supabase.table("mevzuat_references")
                .select(
                    "target_kanun_no, target_madde_tipi, target_madde_no"
                )
                .eq("source_kanun_no", kanun_no)
                .eq("source_madde_tipi", madde_tipi)
                .eq("source_madde_no", madde_no)
                .execute()
            )

            refs = res.data or []

            for ref in refs:
                target_doc = get_mevzuat_by_article(
                    kanun_no=ref.get("target_kanun_no"),
                    madde_no=ref.get("target_madde_no"),
                    madde_tipi=ref.get("target_madde_tipi", "madde"),
                )

                if not target_doc:
                    continue

                target_doc["retrieval_source"] = "reference_graph"
                normalized_target = _normalize_doc(target_doc)
                key = _doc_key(normalized_target)

                if key in seen:
                    continue

                seen.add(key)
                extras.append(normalized_target)

                if len(extras) >= max_extra_docs:
                    return extras

        except Exception as e:
            print(f"Reference graph retrieval hatası: {e}")

    return extras


def build_context(mevzuat_docs: list, karar_docs: list, question: str = "") -> str:
    context_parts = []

    for m in mevzuat_docs:
        source_type = m.get("source_type", "mevzuat")
        kanun_adi = m.get("kanun_adi", "Kanun")

        if source_type == "yonetmelik":
            kanun_adi = m.get("yonetmelik_adi") or kanun_adi
        madde_no = m.get("madde_no", "?")
        madde_tipi = m.get("madde_tipi", "madde")
        icerik = get_context_text_for_doc(m, question)

        if madde_tipi == "madde":
            label = f"{kanun_adi} Madde {madde_no}"
        else:
            label = f"{kanun_adi} {madde_tipi} {madde_no}"

        context_parts.append(f"[{label}]\n{icerik}")

    for k in karar_docs:
        daire = k.get("daire", "Mahkeme")
        esas_no = k.get("esas_no", "?")
        karar_no = k.get("karar_no", "?")
        icerik = k.get("icerik", "")
        context_parts.append(f"[{daire} - {esas_no} / {karar_no}]\n{icerik}")

    if not context_parts:
        return "Veritabanında henüz kaynak bulunmamaktadır."

    return "\n\n---\n\n".join(context_parts)


def build_gemini_history(history=None):
    if history is None:
        return []

    gemini_history = []

    for msg in history:
        role = "user" if msg.get("role") == "user" else "model"
        content = msg.get("content", "")

        gemini_history.append(
            types.Content(
                role=role,
                parts=[types.Part(text=content)],
            )
        )

    return gemini_history


def build_fallback_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    Gemini/generation kullanılamadığında kullanıcıya kaynak temelli kısa fallback cevap döndürür.
    """
    lines = []
    lines = [
        "Yanıt oluşturma servisi şu anda yoğun görünüyor.",
        "Ama ilgili kaynakları senin için buldum:",
        ""
    ]

    if mevzuat_docs:
        lines.append("İlgili mevzuat ve yönetmelik:")
        for m in mevzuat_docs[:10]:
            kanun_adi = m.get("kanun_adi", "Kanun")
            madde_no = m.get("madde_no", "?")
            madde_tipi = m.get("madde_tipi", "madde")
            text = get_context_text_for_doc(m, question)

            if madde_tipi == "madde":
                label = f"{kanun_adi} Madde {madde_no}"
            else:
                label = f"{kanun_adi} {madde_tipi} {madde_no}"

            lines.append(f"- [{label}] {text}")

    if karar_docs:
        lines.append("\nİlgili kararlar:")
        for k in karar_docs[:3]:
            daire = k.get("daire", "Mahkeme")
            esas_no = k.get("esas_no", "?")
            karar_no = k.get("karar_no", "?")
            text = k.get("icerik", "")
            lines.append(f"- [{daire} - {esas_no} / {karar_no}] {text}")

    if not mevzuat_docs and not karar_docs:
        lines.append("Bu konuda veritabanında ilgili kaynak bulunamadı.")

    lines.append("\nBu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.")
    return "\n".join(lines)


def build_source_strict_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    LLM cevabı validator'dan geçmezse, kullanıcıya "servis yoğun" demek yerine
    yalnızca retrieved kaynak metnine dayalı kısa ve güvenli cevap döndürür.

    Bu fonksiyon hukuki unsur, süre, içtihat veya yorum üretmez.
    Sadece kaynak metnini kullanıcı dostu formatta sunar.
    """
    lines = []

    if mevzuat_docs:
        primary = mevzuat_docs[0]

        source_type = primary.get("source_type", "mevzuat")
        if source_type == "yonetmelik":
            source_name = primary.get("yonetmelik_adi") or primary.get("kanun_adi", "Yönetmelik")
        else:
            source_name = primary.get("kanun_adi", "Kanun")

        madde_no = primary.get("madde_no", "?")
        madde_tipi = primary.get("madde_tipi", "madde")
        source_text = get_context_text_for_doc(primary, question)

        if madde_tipi == "madde":
            source_label = f"{source_name} Madde {madde_no}"
        else:
            source_label = f"{source_name} {madde_tipi} {madde_no}"

        lines.extend([
            "Kısa Cevap",
            "",
            f"{source_label} metnine göre:",
            source_text,
            "",
        ])

        if len(mevzuat_docs) > 1:
            lines.append("İlgili Diğer Kaynaklar:")
            for m in mevzuat_docs[1:5]:
                m_source_type = m.get("source_type", "mevzuat")
                if m_source_type == "yonetmelik":
                    m_source_name = m.get("yonetmelik_adi") or m.get("kanun_adi", "Yönetmelik")
                else:
                    m_source_name = m.get("kanun_adi", "Kanun")

                m_madde_no = m.get("madde_no", "?")
                m_madde_tipi = m.get("madde_tipi", "madde")
                m_text = get_context_text_for_doc(m, question)

                if m_madde_tipi == "madde":
                    m_label = f"{m_source_name} Madde {m_madde_no}"
                else:
                    m_label = f"{m_source_name} {m_madde_tipi} {m_madde_no}"

                lines.append(f"- [{m_label}] {m_text}")

            lines.append("")

        lines.extend([
            "Dayandığı Kaynaklar:",
            f"- {source_label}",
        ])

        return "\n".join(lines)

    if karar_docs:
        lines.extend([
            "Kısa Cevap",
            "",
            "Elimdeki karar veritabanında bulunan kaynaklar aşağıdadır:",
            "",
        ])

        for k in karar_docs[:3]:
            daire = k.get("daire", "Mahkeme")
            esas_no = k.get("esas_no", "?")
            karar_no = k.get("karar_no", "?")
            text = k.get("icerik", "")
            label = f"{daire} - {esas_no} / {karar_no}"
            lines.append(f"- [{label}] {text}")

        return "\n".join(lines)

    return build_no_source_answer()


STANDARD_LEGAL_DISCLAIMER = "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."


def ensure_standard_disclaimer(answer: str) -> str:
    """
    Her kullanıcı cevabının sonunda standart hukuki uyarı bulunmasını garanti eder.
    LLM bazen prompta rağmen uyarıyı eklemeyebilir; production'da bunu modele bırakmıyoruz.
    """
    answer = (answer or "").strip()

    if not answer:
        return STANDARD_LEGAL_DISCLAIMER

    if _canon_text(STANDARD_LEGAL_DISCLAIMER) in _canon_text(answer):
        return answer

    return answer + "\n\n" + STANDARD_LEGAL_DISCLAIMER


def is_document_request(question: str) -> bool:
    """
    Kullanıcının belge/dilekçe/ihtarname/taslak üretimi istediğini tespit eder.
    """
    q = _canon_text(question)

    document_terms = [
        "ihtarname",
        "ihtar",
        "dilekce",
        "dilekçe",
        "taslak",
        "sozlesme maddesi",
        "sözleşme maddesi",
        "metin hazirla",
        "metin hazırla",
        "belge hazirla",
        "belge hazırla",
        "taahhutname",
        "taahhütname",
        "protokol",
        "muvafakatname",
        "basvuru",
        "başvuru",
    ]

    return any(term in q for term in document_terms)


def should_use_safe_document_template(question: str) -> bool:
    """
    Basit / şablon belge isteklerinde LLM'e bırakmadan
    deterministic belge şablonu döndürür.

    Amaç:
    - Apilex tarzı standart belge formatı
    - kaynak dışı usul/sonuç eklenmesini önlemek
    - kısa belge isteklerinde kullanıcı sınırına uymak
    """
    q = _canon_text(question)

    if not is_document_request(question):
        return False

    template_signals = [
        "ornek",
        "örnek",
        "sablon",
        "şablon",
        "kisa",
        "kısa",
        "5 cumle",
        "5 cümle",
        "bes cumle",
        "beş cümle",
        "genel",
        "standart",
    ]

    # "ihtarname örneği ver", "kısa ihtarname hazırla" gibi istekler
    # deterministic şablona gitsin.
    if any(signal in q for signal in template_signals):
        return True

    # Sadece "ihtarname hazırla" gibi somut olay içermeyen belge talepleri de
    # şablon kabul edilsin.
    has_ihtar = "ihtar" in q or "ihtarname" in q
    has_concrete_facts = any(term in q for term in [
        "olay su",
        "olay şu",
        "müvekkil",
        "muvekkil",
        "karsi taraf",
        "karşı taraf",
        "tarihinde",
        "fatura",
        "sozlesme",
        "sözleşme",
        "kira",
        "trafik kazasi",
        "trafik kazası",
    ])

    if has_ihtar and not has_concrete_facts:
        return True

    return False


def build_safe_document_answer(question: str, mevzuat_docs: list, karar_docs: list) -> str:
    """
    LLM cevabı üretilemezse veya validator'dan geçemezse,
    kaynaklara dayalı güvenli belge şablonu döndürür.

    Şimdilik ihtarname odaklıdır.
    """
    q = _canon_text(question)

    primary_source = None
    if mevzuat_docs:
        primary_source = mevzuat_docs[0]

    source_label = "ilgili mevzuat"
    source_text = ""

    if primary_source:
        source_type = primary_source.get("source_type", "mevzuat")
        if source_type == "yonetmelik":
            source_name = primary_source.get("yonetmelik_adi") or primary_source.get("kanun_adi", "Yönetmelik")
        else:
            source_name = primary_source.get("kanun_adi", "Kanun")

        madde_no = primary_source.get("madde_no", "?")
        madde_tipi = primary_source.get("madde_tipi", "madde")
        source_text = get_context_text_for_doc(primary_source, question)

        if madde_tipi == "madde":
            source_label = f"{source_name} Madde {madde_no}"
        else:
            source_label = f"{source_name} {madde_tipi} {madde_no}"

    # Şimdilik belge tipi ihtarname ise Apilex benzeri sade şablon üret.
    if "ihtar" in q or "ihtarname" in q:
        is_short = any(term in q for term in ["kisa", "kısa", "5 cumle", "5 cümle", "bes cumle", "beş cümle"])

        if is_short:
            lines = [
                "İHTARNAME",
                "",
                "İHTAR EDEN:",
                "[Ad / Unvan]",
                "[Adres]",
                "",
                "MUHATAP:",
                "[Ad / Unvan]",
                "[Adres]",
                "",
                "KONU:",
                "Hukuka aykırı fiil nedeniyle doğan zararın giderilmesi talebidir.",
                "",
                "AÇIKLAMALAR:",
                f"Tarafınızca gerçekleştirilen [olayın kısa açıklaması] nedeniyle [zarar gören kişi/şirket] zarara uğramıştır. {source_label} uyarınca, kusurlu ve hukuka aykırı bir fiille başkasına zarar veren kişi bu zararı gidermekle yükümlüdür. Bu nedenle [zarar tutarı / zarar kalemi] tutarındaki zararın işbu ihtarnamenin tebliğinden itibaren [süre] içinde giderilmesini talep ederiz.",
                "",
                "SONUÇ VE İHTAR:",
                "Belirtilen süre içinde zararın giderilmemesi halinde, yasal haklarımızı kullanacağımızı ihtaren bildiririz.",
                "",
                "İHTAR EDEN / VEKİLİ",
                "[Ad / Unvan]",
                "[İmza]",
                "",
                "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.",
            ]
            return "\n".join(lines)

        lines = [
            "Kısa hukuki not",
            f"Bu taslak, {source_label} kapsamında genel amaçlı bir ihtarname örneği olarak hazırlanmıştır.",
            "Somut olay, taraf bilgileri, zarar/borç tutarı ve süre alanları doldurulmadan kullanılmamalıdır.",
            "",
            "İHTARNAME ÖRNEĞİ",
            "",
            "İHTARNAME",
            "",
            "İHTAR EDEN:",
            "[Ad Soyad / Unvan]",
            "[T.C. Kimlik No / Vergi No]",
            "[Adres]",
            "",
            "MUHATAP:",
            "[Ad Soyad / Unvan]",
            "[T.C. Kimlik No / Vergi No]",
            "[Adres]",
            "",
            "KONU:",
            "[Hukuka aykırı fiil nedeniyle doğan zararın tazmini] talebimizden ibarettir.",
            "",
            "AÇIKLAMALAR:",
            "",
            f"1. {source_label} uyarınca, kusurlu ve hukuka aykırı bir fiille başkasına zarar veren kişi, bu zararı gidermekle yükümlüdür.",
            "",
            "2. Muhatap tarafından [tarih] tarihinde gerçekleştirilen [olayın kısa açıklaması] nedeniyle ihtar eden taraf zarara uğramıştır.",
            "",
            "3. Söz konusu fiil nedeniyle doğan zarar [zarar kalemi ve tutar] olarak belirlenmiş olup, bu zararın giderilmesi talep edilmektedir.",
            "",
            "4. Bu kapsamda muhatabın, işbu ihtarnamenin tebliğinden itibaren [süre] içinde [zararın/edimin] yerine getirmesi gerekmektedir.",
            "",
            "5. Belirtilen süre içinde yükümlülüğün yerine getirilmemesi halinde, ihtar eden tarafın yasal haklarını kullanma hakkı saklıdır.",
            "",
            "HUKUKİ NEDENLER:",
            f"{source_label} ve ilgili sair mevzuat.",
            "",
            "DELİLLER:",
            "[Sözleşme, fatura, yazışmalar, tutanak, fotoğraf, video, banka kayıtları, bilirkişi raporu ve sair yasal deliller]",
            "",
            "SONUÇ VE İHTAR:",
            "Yukarıda açıklanan nedenlerle; işbu ihtarnamenin tebliğinden itibaren [süre] içinde [zararın/edimin] yerine getirilmesini, aksi halde yasal haklarımızı kullanacağımızı ihtaren bildiririz.",
            "",
            "İHTAR EDEN / VEKİLİ",
            "[Ad Soyad / Unvan]",
            "[İmza]",
            "",
            "Uygulama Notları:",
            "- Köşeli parantez içindeki alanlar somut olaya göre doldurulmalıdır.",
            "- Zararın veya borcun miktarı açık ve belgeye dayalı yazılmalıdır.",
            "- Belge gönderim yöntemi ve süre seçimi somut olaya göre ayrıca değerlendirilmelidir.",
            "",
            "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.",
        ]

        return "\n".join(lines)

    # Diğer belge türleri için şimdilik güvenli genel cevap.
    return build_fallback_answer(question, mevzuat_docs, karar_docs)


def build_no_source_answer() -> str:
    """
    Kaynak bulunamadığında LLM çağırmadan dönen güvenli cevap.
    Production kuralı: kaynak yoksa hukuki değerlendirme yok.
    """
    return (
        "Bu konuda veritabanımda yeterli kaynak bulunamadı. "
        "Kaynak bulunmadığı için hukuki değerlendirme yapamam.\n\n"
        "Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız."
    )


def build_no_karar_answer(question: str, mevzuat_docs: list) -> str:
    """
    Kullanıcı karar/içtihat istemiş ama karar kaynağı bulunamamışsa
    LLM çağırmadan dönen güvenli cevap.
    """
    lines = [
        "Bu konuda veritabanımda ilgili karar/içtihat kaynağı bulunamadı.",
        "Karar kaynağı bulunmadığı için Yargıtay, Danıştay veya emsal karar değerlendirmesi yapamam.",
    ]

    if mevzuat_docs:
        lines.append("")
        lines.append("Ancak ilgili mevzuat kaynakları aşağıdadır:")

        for m in mevzuat_docs[:5]:
            source_type = m.get("source_type", "mevzuat")
            kanun_adi = m.get("kanun_adi", "Kanun")

            if source_type == "yonetmelik":
                kanun_adi = m.get("yonetmelik_adi") or kanun_adi

            madde_no = m.get("madde_no", "?")
            madde_tipi = m.get("madde_tipi", "madde")
            text = get_context_text_for_doc(m, question)

            if madde_tipi == "madde":
                label = f"{kanun_adi} Madde {madde_no}"
            else:
                label = f"{kanun_adi} {madde_tipi} {madde_no}"

            lines.append(f"- [{label}] {text}")

    lines.append("")
    lines.append("Bu bilgiler genel hukuki bilgi niteliğindedir, avukattan görüş alınız.")
    return "\n".join(lines)


def _source_text_contains_any(mevzuat_docs: list, terms: list[str]) -> bool:
    """
    Verilen terimlerden herhangi biri retrieved mevzuat metninde geçiyor mu?
    Kaynak dışı teknik unsur eklemelerini yakalamak için kullanılır.
    """
    source_text = " ".join(
        str(doc.get("icerik", "") or "") for doc in (mevzuat_docs or [])
    )
    source_canon = _canon_text(source_text)

    for term in terms:
        if _canon_text(term) in source_canon:
            return True

    return False


def validate_unsupported_legal_terms(answer: str, mevzuat_docs: list, karar_docs: list) -> tuple[bool, str]:
    """
    İlk seviye kaynak dışı hukuki unsur kontrolü.

    Amaç:
    - Modelin tek madde kaynağından genel hukuk bilgisiyle ek unsur üretmesini azaltmak.
    - Örn. TBK 49 metninde açıkça geçmeyen "illiyet bağı" unsurunu eklemesini engellemek.

    Not:
    Bu liste bilinçli olarak dar tutulur. Aşırı agresif olursa doğru cevapları da kesebilir.
    """
    answer_canon = _canon_text(answer)

    unsupported_groups = {
        "illiyet_bagi": [
            "illiyet bağı",
            "illiyet bagi",
            "nedensellik bağı",
            "nedensellik bagi",
            "nedensellik",
        ],
        "zamanaşımı": [
            "zamanaşımı",
            "zamanasimi",
        ],
        "hak_dusurucu_sure": [
            "hak düşürücü süre",
            "hak dusurucu sure",
        ],
        "faiz": [
            "faiz",
            "temerrüt faizi",
            "temerrut faizi",
            "yasal faiz",
        ],
        "arabuluculuk": [
            "arabuluculuk",
            "dava şartı arabuluculuk",
            "dava sarti arabuluculuk",
        ],
        "gorev_yetki": [
            "görevli mahkeme",
            "gorevli mahkeme",
            "yetkili mahkeme",
        ],
    }

    for reason, terms in unsupported_groups.items():
        answer_has_term = any(_canon_text(term) in answer_canon for term in terms)

        if not answer_has_term:
            continue

        # Eğer aynı terim kaynak metinde veya karar kaynağında varsa izin ver.
        if _source_text_contains_any(mevzuat_docs, terms):
            continue

        karar_text = " ".join(str(k.get("icerik", "") or "") for k in (karar_docs or []))
        karar_canon = _canon_text(karar_text)
        if any(_canon_text(term) in karar_canon for term in terms):
            continue

        return False, f"unsupported_legal_term:{reason}"

    return True, "ok"


def validate_answer_against_sources(answer: str, mevzuat_docs: list, karar_docs: list) -> tuple[bool, str]:
    """
    LLM cevabının temel kaynak güvenlik kurallarına uyup uymadığını kontrol eder.
    Bu validator tam hukuki doğrulama yapmaz; ilk production güvenlik bariyeridir.
    """
    if not answer or not answer.strip():
        return False, "empty_answer"

    if not mevzuat_docs and not karar_docs:
        return False, "no_sources"

    unsupported_ok, unsupported_reason = validate_unsupported_legal_terms(
        answer,
        mevzuat_docs,
        karar_docs,
    )
    if not unsupported_ok:
        return False, unsupported_reason

    answer_lower = answer.lower()

    # Karar kaynağı yokken içtihat/mahkeme uygulaması iddiası kurmasını engelle.
    if not karar_docs:
        forbidden_case_terms = [
            "yargıtay",
            "danıştay",
            "anayasa mahkemesi",
            "aym",
            "emsal karar",
            "yerleşik içtihat",
            "içtihatlarda",
            "kararlarda",
            "mahkeme kararlarında",
        ]

        for term in forbidden_case_terms:
            if term in answer_lower:
                return False, f"forbidden_case_term:{term}"

    allowed_refs = []

    for m in mevzuat_docs:
        source_type = m.get("source_type", "mevzuat")
        kanun_no = str(m.get("kanun_no", "") or "")

        if source_type == "yonetmelik":
            kanun_adi = m.get("yonetmelik_adi") or m.get("kanun_adi", "Yönetmelik")
        else:
            kanun_adi = m.get("kanun_adi", "Kanun")

        madde_no = str(m.get("madde_no", "?"))
        madde_tipi = str(m.get("madde_tipi", "madde"))

        law_aliases = [kanun_adi]

        if kanun_no:
            law_aliases.append(kanun_no)
            law_aliases.append(f"{kanun_no} sayılı Kanun")

            # LAW_ALIASES içindeki kısa adları da kabul et.
            # Örn: 6098 -> TBK, Türk Borçlar Kanunu
            for alias, alias_kanun_no in LAW_ALIASES.items():
                if str(alias_kanun_no) == kanun_no:
                    law_aliases.append(alias)

        # Çok genel veya fazla uzun aliasları azalt.
        clean_aliases = []
        for alias in law_aliases:
            alias = str(alias or "").strip()
            if not alias:
                continue

            # Çok uzun resmi adlar zaten kanun_adi ile var; alias tarafında kısa kullanımları tercih ediyoruz.
            if alias not in clean_aliases:
                clean_aliases.append(alias)

        for alias in clean_aliases:
            if madde_tipi == "madde":
                allowed_refs.extend([
                    f"{alias} Madde {madde_no}",
                    f"{alias} madde {madde_no}",
                    f"{alias} Md. {madde_no}",
                    f"{alias} Md.{madde_no}",
                    f"{alias} md. {madde_no}",
                    f"{alias} md.{madde_no}",
                    f"{alias} m. {madde_no}",
                    f"{alias} m.{madde_no}",
                    f"{alias} m {madde_no}",
                    f"{alias} {madde_no}",
                ])
            else:
                allowed_refs.extend([
                    f"{alias} {madde_tipi} {madde_no}",
                    f"{alias} {madde_tipi.title()} Madde {madde_no}",
                ])

    for k in karar_docs:
        daire = k.get("daire", "Mahkeme")
        esas_no = k.get("esas_no", "?")
        karar_no = k.get("karar_no", "?")
        allowed_refs.append(f"{daire} - {esas_no} / {karar_no}")

    # Cevapta en az bir izinli kaynak etiketi geçsin.
    # Normalize ederek kontrol ediyoruz:
    # "TBK m. 49", "tbk 49", "Türk Borçlar Kanunu Madde 49" gibi varyasyonlar yakalansın.
    if allowed_refs:
        answer_canon = _canon_text(answer)
        allowed_refs_canon = [_canon_text(ref) for ref in allowed_refs if ref]

        if not any(ref in answer_canon for ref in allowed_refs_canon):
            return False, "no_allowed_reference"

    return True, "ok"


def get_fikra_extraction_status(question: str, doc: dict, matched_text: str | None) -> str:
    """
    Fıkra / bent extraction sonucunu daha dürüst sınıflandır.
    """
    intra_refs = parse_intra_article_refs(question)
    if not intra_refs:
        return "not_requested"

    resolved_refs = resolve_contextual_fikra_refs(intra_refs)

    requested_single = None
    requested_list = None
    requested_bent = None
    requested_numeric_bent = None

    for ref in intra_refs:
        if ref.get("type") == "bent":
            requested_bent = ref.get("value")
        elif ref.get("type") == "numeric_bent":
            requested_numeric_bent = ref.get("value")

    for ref in resolved_refs:
        resolved_value = ref.get("resolved")

        if isinstance(resolved_value, list) and resolved_value:
            requested_list = resolved_value

        elif isinstance(resolved_value, str) and resolved_value in {"1", "2", "3", "4"}:
            requested_single = resolved_value

    structured_content = doc.get("structured_content") or {}
    fikralar = structured_content.get("fikralar", {}) if isinstance(structured_content, dict) else {}

    def _fikra_has_bent(fikra_value, bent_key: str) -> bool:
        if not isinstance(fikra_value, dict):
            return False
        bentler = fikra_value.get("bentler", {}) or {}
        return bool(bentler.get(bent_key))

    if requested_list:
        found = [no for no in requested_list if isinstance(fikralar, dict) and fikralar.get(no)]
        if not found:
            return "not_structured"
        if len(found) < len(requested_list):
            return "partial_match"

        if requested_bent:
            bent_found = [no for no in requested_list if _fikra_has_bent(fikralar.get(no), requested_bent)]
            if not bent_found:
                return "not_structured"
            if len(bent_found) < len(requested_list):
                return "partial_match"

        return "matched"

    if requested_single:
        fikra_value = fikralar.get(requested_single) if isinstance(fikralar, dict) else None

        if not fikra_value:
            # İstenen fıkra yapıda yok ama fallback ile yine de bir bent/metin bulduysak
            # bunu tam eşleşme değil, kısmi eşleşme say.
            if matched_text:
                return "partial_match"
            return "not_structured"

        if requested_bent and not _fikra_has_bent(fikra_value, requested_bent):
            # İstenen bent o fıkrada yok ama fallback ile başka yerden bir bent bulduysak
            # yine partial_match diyelim.
            if matched_text:
                return "partial_match"
            return "not_structured"

        return "matched"

    if requested_numeric_bent:
        if matched_text:
            return "partial_match"
        return "not_structured"

    if requested_bent:
        if isinstance(fikralar, dict):
            for _, fikra_value in fikralar.items():
                if _fikra_has_bent(fikra_value, requested_bent):
                    return "matched"
        return "not_structured"

    if matched_text:
        return "matched"

    return "not_structured"


def debug_retrieve_mevzuat(question: str, history=None):
    """
    Gemini cevap üretmeden sadece retrieval sonucunu döndürür.
    Böylece quota doluyken bile hangi maddelerin geldiğini test edebilirsin.
    """
    history = history or []
    question = normalize_user_legal_query(question)
    resolved_question = resolve_contextual_article_question(question, history)
    karar_intent = should_retrieve_kararlar(resolved_question)
    explicit_mevzuat_docs = get_explicitly_requested_articles(resolved_question)
    explicit_yonetmelik_docs = get_explicitly_requested_yonetmelik_articles(resolved_question)

    explicit_docs = merge_mevzuat_docs(
        explicit_mevzuat_docs,
        explicit_yonetmelik_docs,
        limit=10,
    )
    if explicit_docs:
        semantic_mevzuat_docs = []
        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=explicit_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )
    else:
        try:
            embedding = embed_query(resolved_question)
            semantic_mevzuat_docs = search_mevzuat(embedding, 8)

        except Exception as e:
            print(f"Semantic retrieval atlandı / hata: {e}")
            semantic_mevzuat_docs = []

        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=semantic_mevzuat_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )

    prev_ref_docs = expand_previous_article_refs(mevzuat_docs, max_extra_docs=4)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=prev_ref_docs,
        limit=12,
    )

    graph_ref_docs = get_referenced_mevzuat_docs(mevzuat_docs, max_extra_docs=6)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=graph_ref_docs,
        limit=18,
    )

    mevzuat_docs = rank_mevzuat_docs(
        mevzuat_docs,
        resolved_question,
        limit=18,
    )

    intra_refs = parse_intra_article_refs(resolved_question)
    ranking_context = build_ranking_context(resolved_question)
    docs_out = []
    for d in mevzuat_docs:
        full_text = d.get("icerik") or ""
        fikra_text = extract_requested_fikra_text(
            full_text,
            intra_refs,
            structured_content=d.get("structured_content"),
        )
        fikra_status = get_fikra_extraction_status(resolved_question, d, fikra_text)

        docs_out.append({
            "kanun_no": d.get("kanun_no"),
            "kanun_adi": d.get("kanun_adi"),
            "madde_tipi": d.get("madde_tipi"),
            "madde_no": d.get("madde_no"),
            "retrieval_source": d.get("retrieval_source", "semantic_or_keyword"),
            "rank_score": compute_mevzuat_doc_rank_score(
                d,
                resolved_question,
                ranking_context=ranking_context,
            ),
            "similarity": d.get("similarity"),
            "matched_fikra_text": fikra_text,
            "fikra_extraction_status": fikra_status,
            "preview": (fikra_text or full_text)[:300],
        })

    return {
        "question": question,
        "resolved_question": resolved_question,
        "karar_retrieval_intent": karar_intent,
        "intra_article_refs": intra_refs,
        "count": len(mevzuat_docs),
        "docs": docs_out,
    }


def get_rag_response(question: str, history=None):
    history = history or []
    question = normalize_user_legal_query(question)
    resolved_question = resolve_contextual_article_question(question, history)

    # 1) Önce açık madde / kanun referansı var mı bak
    explicit_mevzuat_docs = get_explicitly_requested_articles(resolved_question)
    explicit_yonetmelik_docs = get_explicitly_requested_yonetmelik_articles(resolved_question)

    explicit_docs = merge_mevzuat_docs(
        explicit_mevzuat_docs,
        explicit_yonetmelik_docs,
        limit=10,
    )
    # Eğer kullanıcı açıkça madde istemişse ve sonuç bulunduysa,
    # embedding çağrısını zorunlu kılmayalım.
    if explicit_docs:
        semantic_mevzuat_docs = []
        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=explicit_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )
    else:
        # Açık madde yoksa normal retrieval akışı
        try:
            embedding = embed_query(resolved_question)
            semantic_mevzuat_docs = search_mevzuat(embedding, 8)

        except Exception as e:
            print(f"Semantic retrieval atlandı / hata: {e}")
            semantic_mevzuat_docs = []

        keyword_mevzuat_docs = keyword_search_mevzuat(resolved_question, 4)

        mevzuat_docs = merge_mevzuat_docs(
            primary_docs=semantic_mevzuat_docs,
            extra_docs=keyword_mevzuat_docs,
            limit=10,
        )

    # Cross-reference expansion: previous article
    prev_ref_docs = expand_previous_article_refs(mevzuat_docs, max_extra_docs=4)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=prev_ref_docs,
        limit=12,
    )

    # Reference graph expansion: explicit referenced articles
    graph_ref_docs = get_referenced_mevzuat_docs(mevzuat_docs, max_extra_docs=6)

    mevzuat_docs = merge_mevzuat_docs(
        primary_docs=mevzuat_docs,
        extra_docs=graph_ref_docs,
        limit=18,
    )

    mevzuat_docs = rank_mevzuat_docs(
        mevzuat_docs,
        resolved_question,
        limit=18,
    )

    # Karar retrieval intent bazlı çalışsın
    karar_docs = []
    karar_intent = should_retrieve_kararlar(resolved_question)

    try:
        if karar_intent:
            embedding = embed_query(resolved_question)
            karar_docs = search_kararlar(embedding, 5)
    except Exception as e:
        print(f"Karar retrieval atlandı / hata: {e}")
        karar_docs = []

    # Production safety gate:
    # Kaynak yoksa LLM çağırma.
    if not mevzuat_docs and not karar_docs:
        return build_no_source_answer(), [], []

    # Kullanıcı karar/içtihat istemiş ama karar bulunamamışsa,
    # LLM'in içtihat uydurma riskini engelle.
    if karar_intent and not karar_docs:
        return build_no_karar_answer(resolved_question, mevzuat_docs), mevzuat_docs, []

    # Basit belge/şablon taleplerinde LLM'e bırakma.
    # Production belge güvenliği için deterministic şablon döndür.
    if should_use_safe_document_template(resolved_question):
        return build_safe_document_answer(resolved_question, mevzuat_docs, karar_docs), mevzuat_docs, karar_docs

    context = build_context(mevzuat_docs, karar_docs, question=resolved_question)
    gemini_history = build_gemini_history(history)

    full_system = SYSTEM_PROMPT + f"\n\nKAYNAKLAR:\n{context}"

    try:
        response = client.models.generate_content_stream(
            model=CHAT_MODEL,
            contents=gemini_history + [
                types.Content(role="user", parts=[types.Part(text=resolved_question)])
            ],
            config=types.GenerateContentConfig(
                system_instruction=full_system,
            ),
        )
        return response, mevzuat_docs, karar_docs


    except Exception as e:

        print(f"LLM generation fallback devrede: {e}")

        fallback_text = build_fallback_answer(resolved_question, mevzuat_docs, karar_docs)

        return fallback_text, mevzuat_docs, karar_docs


def get_rag_response_text(question: str, history=None):
    result, mevzuat_docs, karar_docs = get_rag_response(question, history=history)

    if isinstance(result, str):
        return ensure_standard_disclaimer(result), mevzuat_docs, karar_docs

    normalized_question = normalize_user_legal_query(question)
    resolved_question = resolve_contextual_article_question(normalized_question, history)

    try:
        full_text = ""
        for chunk in result:
            if hasattr(chunk, "text") and chunk.text:
                full_text += chunk.text

        if full_text.strip():
            is_valid, validation_reason = validate_answer_against_sources(
                full_text,
                mevzuat_docs,
                karar_docs,
            )

            if is_valid:
                return ensure_standard_disclaimer(full_text), mevzuat_docs, karar_docs

            print(f"Answer validation failed: {validation_reason}")

            if is_document_request(resolved_question):
                fallback_text = build_safe_document_answer(
                    resolved_question,
                    mevzuat_docs,
                    karar_docs,
                )
            else:
                fallback_text = build_source_strict_answer(
                    resolved_question,
                    mevzuat_docs,
                    karar_docs,
                )

            return ensure_standard_disclaimer(fallback_text), mevzuat_docs, karar_docs

        fallback_text = build_fallback_answer(resolved_question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs

    except Exception as e:
        print(f"Stream tüketiminde fallback devrede: {e}")
        fallback_text = build_fallback_answer(resolved_question, mevzuat_docs, karar_docs)
        return fallback_text, mevzuat_docs, karar_docs
