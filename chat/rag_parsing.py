import json
import re
import unicodedata


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
