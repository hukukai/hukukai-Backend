from .rag_parsing import (
    LAW_ALIASES,
    _canon_text,
    get_context_text_for_doc,
)


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
