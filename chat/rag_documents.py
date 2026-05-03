from .rag_parsing import (
    _canon_text,
    get_context_text_for_doc,
)

from .rag_safety import (
    build_fallback_answer,
)


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
