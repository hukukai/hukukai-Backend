import os
import json
import sys
import time
import re
import hashlib
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple

from dotenv import load_dotenv
from supabase import create_client
from google import genai
from google.genai import types

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MEVZUAT_DIR = BASE_DIR

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or not GOOGLE_API_KEY:
    raise ValueError("SUPABASE_URL, SUPABASE_KEY ve GOOGLE_API_KEY .env içinde tanımlı olmalı.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY)

BATCH_SIZE = 100
EMBED_DIM = 1536
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_MODEL = "gemini-embedding-001"

MAX_RETRIES = 8
DEFAULT_RETRY_SECONDS = 20


# =========================================================
# BASIC HELPERS
# =========================================================

def normalize_record(m: Dict[str, Any]) -> Dict[str, str]:
    return {
        "kanun_no": str(m.get("kanun_no", "")).strip(),
        "kanun_adi": str(m.get("kanun_adi", "")).strip(),
        "madde_no": str(m.get("madde_no", "")).strip(),
        "madde_tipi": str(m.get("madde_tipi", "")).strip(),
        "icerik": str(m.get("icerik", "")).strip(),
    }


def build_structured_content(text: str):
    import re

    if not text:
        return {"fikralar": {"1": ""}}

    text = text.strip()

    # (1) (2) formatı
    parts = re.split(r"\(\s*(\d+)\s*\)", text)

    if len(parts) >= 3:
        fikra_map = {}
        current_no = None

        for part in parts:
            part = part.strip()

            if part.isdigit():
                current_no = part
                fikra_map[current_no] = ""

            else:
                if current_no:
                    fikra_map[current_no] += part + " "

        return {"fikralar": {k: v.strip() for k, v in fikra_map.items()}}

    # paragraf fallback
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    if len(paragraphs) > 1:
        fikra_map = {}

        for i, p in enumerate(paragraphs):
            fikra_map[str(i+1)] = p

        return {"fikralar": fikra_map}

    # son fallback
    return {"fikralar": {"1": text}}


def normalize_text_for_hash(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        start = max(0, end - overlap)

    return chunks


# =========================================================
# RETRY LOGIC
# =========================================================

def parse_retry_seconds(error_text: str) -> int:
    patterns = [
        r"retry in\s+(\d+(?:\.\d+)?)s",
        r"'retryDelay':\s*'(\d+)s'",
        r'"retryDelay":\s*"(\d+)s"',
    ]

    for pattern in patterns:
        m = re.search(pattern, error_text, flags=re.IGNORECASE)
        if m:
            try:
                return max(5, int(float(m.group(1))) + 2)
            except Exception:
                pass

    return DEFAULT_RETRY_SECONDS


def is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).upper()

    retry_tokens = [
        "429",
        "RESOURCE_EXHAUSTED",
        "503",
        "UNAVAILABLE",
        "500",
        "INTERNAL",
        "502",
        "BAD_GATEWAY",
        "504",
        "DEADLINE_EXCEEDED",
    ]

    return any(token in msg for token in retry_tokens)


def sleep_with_backoff(attempt: int, exc: Exception) -> None:
    parsed = parse_retry_seconds(str(exc))
    expo = min(60, (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, 1.5)
    wait_seconds = max(parsed, expo) + jitter
    print(f"⏳ Geçici servis hatası. {wait_seconds:.1f} saniye bekleniyor... (deneme {attempt}/{MAX_RETRIES})")
    time.sleep(wait_seconds)


def embed_document_with_retry(text: str) -> List[float]:
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=text[:2000],
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBED_DIM,
                ),
            )
            return result.embeddings[0].values

        except Exception as e:
            last_error = e

            if is_retryable_error(e) and attempt < MAX_RETRIES:
                sleep_with_backoff(attempt, e)
                continue

            raise

    raise last_error


# =========================================================
# FILE / JSON
# =========================================================

def find_preview_json(folder: Path) -> Path:
    json_files = list(folder.glob("*_preview.json"))
    if not json_files:
        raise FileNotFoundError(f"Preview JSON bulunamadı: {folder}")
    return json_files[0]


# =========================================================
# DB HELPERS
# =========================================================
def fetch_mevzuat_chunk_counts(kanun_no: str) -> Dict[str, int]:
    res = (
        supabase.table("mevzuat_chunks")
        .select("madde_tipi, madde_no, id")
        .eq("kanun_no", kanun_no)
        .execute()
    )

    counts: Dict[str, int] = {}
    for row in (res.data or []):
        key = f"{row['madde_tipi']}|{row['madde_no']}"
        counts[key] = counts.get(key, 0) + 1

    return counts


def fetch_existing_mevzuat_map(kanun_no: str) -> Dict[str, Dict[str, Any]]:
    res = (
        supabase.table("mevzuat")
        .select("id, kanun_no, kanun_adi, madde_no, madde_tipi, icerik, content_hash")
        .eq("kanun_no", kanun_no)
        .execute()
    )

    mapping: Dict[str, Dict[str, Any]] = {}
    for row in (res.data or []):
        key = f"{row['madde_tipi']}|{row['madde_no']}"
        mapping[key] = row
    return mapping


def upsert_mevzuat_batch(rows: List[Dict[str, Any]]) -> None:
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        (
            supabase.table("mevzuat")
            .upsert(batch, on_conflict="kanun_no,madde_tipi,madde_no")
            .execute()
        )
        print(f"✅ Mevzuat upsert: {min(i + len(batch), len(rows))}/{len(rows)}")


def fetch_mevzuat_ids(kanun_no: str) -> Dict[str, int]:
    res = (
        supabase.table("mevzuat")
        .select("id, madde_no, madde_tipi")
        .eq("kanun_no", kanun_no)
        .execute()
    )

    mapping = {}
    for row in (res.data or []):
        key = f"{row['madde_tipi']}|{row['madde_no']}"
        mapping[key] = row["id"]

    return mapping


def delete_chunks_for_mevzuat_id(mevzuat_id: int) -> None:
    supabase.table("mevzuat_chunks").delete().eq("mevzuat_id", mevzuat_id).execute()


# =========================================================
# DIFF LOGIC
# =========================================================
def build_upsert_rows_and_change_set(
        records: List[Dict[str, str]],
        source_file: str,
        existing_map: Dict[str, Dict[str, Any]],
        chunk_count_map: Dict[str, int],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    upsert_rows: List[Dict[str, Any]] = []
    change_map: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        key = f"{rec['madde_tipi']}|{rec['madde_no']}"
        content_hash = sha256_text(normalize_text_for_hash(rec["icerik"]))
        old = existing_map.get(key)
        chunk_count = chunk_count_map.get(key, 0)

        row = {
            "kanun_no": rec["kanun_no"],
            "kanun_adi": rec["kanun_adi"],
            "madde_no": rec["madde_no"],
            "madde_tipi": rec["madde_tipi"],
            "icerik": rec["icerik"],
            "content_hash": content_hash,
            "source_file": source_file,
            "embedding_model": EMBED_MODEL,
            "embedding_dim": EMBED_DIM,
            "last_embedded_at": None,
        }
        upsert_rows.append(row)

        changed = False
        reason = "same"

        if not old:
            changed = True
            reason = "new"
        else:
            old_hash = old.get("content_hash")

            if old_hash != content_hash:
                changed = True
                reason = "content_changed"
            elif chunk_count == 0:
                changed = True
                reason = "missing_chunks"
            else:
                changed = False
                reason = "same"

        change_map[key] = {
            "changed": changed,
            "reason": reason,
            "content_hash": content_hash,
            "chunk_count": chunk_count,
        }

    return upsert_rows, change_map


# =========================================================
# CHUNK INSERT
# =========================================================

def insert_chunks_for_record(rec: Dict[str, str], mevzuat_id: int) -> int:
    chunks = chunk_text(rec["icerik"])
    rows = []

    for idx, chunk in enumerate(chunks):
        chunk_hash = sha256_text(normalize_text_for_hash(chunk))
        emb = embed_document_with_retry(chunk)

        rows.append({
            "mevzuat_id": mevzuat_id,
            "kanun_no": rec["kanun_no"],
            "kanun_adi": rec["kanun_adi"],
            "madde_no": rec["madde_no"],
            "madde_tipi": rec["madde_tipi"],
            "chunk_index": idx,
            "chunk_text": chunk,
            "chunk_hash": chunk_hash,
            "embedding": emb,
            "embedding_model": EMBED_MODEL,
            "embedding_dim": EMBED_DIM,
        })

        time.sleep(0.2)

    if rows:
        supabase.table("mevzuat_chunks").insert(rows).execute()
        supabase.table("mevzuat").update({
            "last_embedded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }).eq("id", mevzuat_id).execute()

    return len(rows)


# =========================================================
# MAIN
# =========================================================

def main():
    if len(sys.argv) < 2:
        print("Kullanım: python upload_mevzuat_json.py 4857_is_kanunu")
        return

    klasor = sys.argv[1]
    folder = MEVZUAT_DIR / klasor

    if not folder.exists():
        print(f"Klasör bulunamadı: {folder}")
        return

    try:
        json_file = find_preview_json(folder)
    except Exception as e:
        print(str(e))
        return

    try:
        raw_data = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"JSON okunamadı: {e}")
        return

    if not isinstance(raw_data, list) or not raw_data:
        print("Preview JSON boş veya liste formatında değil.")
        return

    data = [normalize_record(m) for m in raw_data if str(m.get("icerik", "")).strip()]

    if not data:
        print("İşlenecek kayıt bulunamadı.")
        return

    kanun_no = data[0]["kanun_no"]
    kanun_adi = data[0]["kanun_adi"]

    print(f"📘 Dosya: {json_file.name}")
    print(f"📚 Kanun: {kanun_adi} ({kanun_no})")
    print(f"📄 Toplam madde: {len(data)}")

    try:
        existing_map = fetch_existing_mevzuat_map(kanun_no)
        chunk_count_map = fetch_mevzuat_chunk_counts(kanun_no)

        mevzuat_rows, change_map = build_upsert_rows_and_change_set(
            records=data,
            source_file=json_file.name,
            existing_map=existing_map,
            chunk_count_map=chunk_count_map,
        )

        # 1) Full article text upsert
        upsert_mevzuat_batch(mevzuat_rows)

        # 2) Fresh mevzuat_id map after upsert
        mevzuat_id_map = fetch_mevzuat_ids(kanun_no)

        total_chunks_inserted = 0
        changed_count = 0
        skipped_count = 0

        # 3) Only changed/new articles are re-chunked
        for i, rec in enumerate(data, start=1):
            key = f"{rec['madde_tipi']}|{rec['madde_no']}"
            mevzuat_id = mevzuat_id_map.get(key)

            if not mevzuat_id:
                raise ValueError(
                    f"mevzuat_id bulunamadı: {rec['kanun_no']} {rec['madde_tipi']} {rec['madde_no']}"
                )

            diff_info = change_map[key]

            if not diff_info["changed"]:
                skipped_count += 1
                print(
                    f"⏭️ [{i}/{len(data)}] {rec['kanun_adi']} {rec['madde_tipi']} {rec['madde_no']} "
                    f"| mevzuat_id={mevzuat_id} | değişmedi, skip"
                )
                continue

            changed_count += 1

            # Sadece değişen/yeni maddede eski chunkları sil
            delete_chunks_for_mevzuat_id(mevzuat_id)

            inserted_chunk_count = insert_chunks_for_record(rec, mevzuat_id)
            total_chunks_inserted += inserted_chunk_count

            print(
                f"✅ [{i}/{len(data)}] {rec['kanun_adi']} {rec['madde_tipi']} {rec['madde_no']} "
                f"| mevzuat_id={mevzuat_id} | neden={diff_info['reason']} "
                f"| chunk={inserted_chunk_count} | toplam_chunk={total_chunks_inserted}"
            )

        print("\n🎉 Upload tamamlandı")
        print(f"Toplam mevzuat kaydı : {len(mevzuat_rows)}")
        print(f"Değişen/yeni madde   : {changed_count}")
        print(f"Skip edilen madde    : {skipped_count}")
        print(f"Eklenen chunk sayısı : {total_chunks_inserted}")

    except Exception as e:
        print(f"\n❌ İşlem durdu: {e}")


if __name__ == "__main__":
    main()
