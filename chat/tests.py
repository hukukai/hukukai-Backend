import re


def build_structured_content(article_text: str) -> dict:
    """
    Tam madde metninden structured_content üretir.
    Şimdilik yalnızca fıkra ayırımı yapar.
    """
    text = (article_text or "").strip()

    if not text:
        return {"fikralar": {}}

    # (1) (2) (3) formatı varsa ayır
    parts = re.split(r"(\(\d+\))", text)

    if len(parts) >= 3:
        fikra_map = {}
        current_no = None

        for part in parts:
            if re.fullmatch(r"\(\d+\)", part or ""):
                current_no = part.strip("()")
                fikra_map[current_no] = part
            else:
                if current_no:
                    fikra_map[current_no] += part.strip()

        if fikra_map:
            return {"fikralar": fikra_map}

    # fallback: fıkra yapısı yoksa tüm metni 1. fıkra gibi sakla
    return {
        "fikralar": {
            "1": text
        }
    }