import re
from typing import Any, Dict


def _split_bentler(text: str) -> Dict[str, str]:
    """
    Fıkra içindeki bentleri ayırır.
    İlk sürüm:
    - a) ... b) ... c) ...
    - yalnızca temel bent formatını destekler
    """
    text = (text or "").strip()
    if not text:
        return {}

    pattern = r"(?:(?<=\s)|^)([a-zçğıöşü])\)"
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))

    if not matches:
        return {}

    bentler: Dict[str, str] = {}

    for i, match in enumerate(matches):
        bent_key = match.group(1).lower()
        start = match.start()

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()

        if chunk:
            bentler[bent_key] = chunk

    return bentler


def _wrap_fikra_text(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    return {
        "text": text,
        "bentler": _split_bentler(text),
    }

def _find_bent_spans(text: str):
    pattern = r"(?:(?<=\s)|^)([a-zçğıöşü])\)"
    return list(re.finditer(pattern, text, flags=re.IGNORECASE))


def _split_single_block_with_bent_heuristic(text: str) -> Dict[str, Any] | None:
    """
    Tek blok gelen ama içinde bent listesi olan maddelerde
    kaba bir fıkra ayrımı yapmaya çalışır.

    Heuristik:
    - bentlerden önceki giriş = fikra 1
    - bentlerin başladığı yerden itibaren kalan bölüm = fikra 2
    - bentler fikra 2 altında tutulur
    """
    text = (text or "").strip()
    if not text:
        return None

    matches = _find_bent_spans(text)
    if len(matches) < 2:
        return None

    first_bent_start = matches[0].start()
    intro = text[:first_bent_start].strip()
    bent_block = text[first_bent_start:].strip()

    if not intro or not bent_block:
        return None

    bentler = _split_bentler(bent_block)
    if len(bentler) < 2:
        return None

    return {
        "fikralar": {
            "1": {
                "text": intro,
                "bentler": {}
            },
            "2": {
                "text": bent_block,
                "bentler": bentler
            }
        }
    }

def build_structured_content(article_text: str) -> dict:
    """
    Tam madde metninden structured_content üretir.

    Öncelik:
    1) (1) (2) (3) gibi açık fıkra numaraları
    2) boş satıra göre paragraf ayrımı
    3) tek parça fallback

    Yeni yapı:
    {
      "fikralar": {
        "1": {"text": "...", "bentler": {...}},
        "2": {"text": "...", "bentler": {...}}
      }
    }
    """
    text = (article_text or "").strip()

    if not text:
        return {"fikralar": {}}

    # 1) Açık numaralı fıkra ayrımı: (1) ... (2) ...
    parts = re.split(r"(\(\d+\))", text)

    if len(parts) >= 3:
        fikra_map = {}
        current_no = None

        for part in parts:
            part = (part or "").strip()

            if re.fullmatch(r"\(\d+\)", part):
                current_no = part.strip("()")
                fikra_map[current_no] = part
            else:
                if current_no:
                    if fikra_map[current_no]:
                        fikra_map[current_no] += " " + part
                    else:
                        fikra_map[current_no] = part

        fikra_map = {k: v.strip() for k, v in fikra_map.items() if v.strip()}
        if fikra_map:
            return {
                "fikralar": {
                    k: _wrap_fikra_text(v)
                    for k, v in fikra_map.items()
                }
            }

    # 2) Paragraf bazlı ayırma
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    if len(paragraphs) > 1:
        return {
            "fikralar": {
                str(i + 1): _wrap_fikra_text(p)
                for i, p in enumerate(paragraphs)
            }
        }
    # 3) Tek blok ama bent yoğun yapı: giriş + bent listesi
    heuristic = _split_single_block_with_bent_heuristic(text)
    if heuristic:
        return heuristic

    # 4) Son fallback: tek parça
    return {
        "fikralar": {
            "1": _wrap_fikra_text(text)
        }
    }
