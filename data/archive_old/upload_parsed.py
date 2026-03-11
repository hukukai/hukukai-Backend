
from google import genai
from google.genai import types
from supabase import create_client
from dotenv import load_dotenv
import os
import json
import time

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EMBED_DIM = 1536

JSON_FILES = [
    "preview_4857.json",
]


def split_text(text: str, chunk_size=1000, overlap=200) -> list[str]:
    chunks = []
    text = text.strip()
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def embed_text(text: str) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text[:2000],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_DIM,
        ),
    )
    return result.embeddings[0].values


def main_kayit_var_mi(kanun_no: str, madde_no: str, madde_tipi: str):
    res = (
        supabase.table("mevzuat")
        .select("id, kanun_no, madde_no, madde_tipi")
        .eq("kanun_no", kanun_no)
        .eq("madde_no", madde_no)
        .eq("madde_tipi", madde_tipi)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def delete_existing_chunks(mevzuat_id: int):
    supabase.table("mevzuat_chunks").delete().eq("mevzuat_id", mevzuat_id).execute()


def upsert_madde(madde: dict) -> int:
    mevcut = main_kayit_var_mi(
        madde["kanun_no"],
        madde["madde_no"],
        madde["madde_tipi"],
    )

    payload = {
        "kanun_no": madde["kanun_no"],
        "kanun_adi": madde["kanun_adi"],
        "madde_no": madde["madde_no"],
        "madde_tipi": madde["madde_tipi"],
        "icerik": madde["icerik"],
    }

    if mevcut:
        mevzuat_id = mevcut["id"]
        supabase.table("mevzuat").update(payload).eq("id", mevzuat_id).execute()
        return mevzuat_id

    insert_res = supabase.table("mevzuat").insert(payload).execute()
    return insert_res.data[0]["id"]


def process_madde(madde: dict) -> int:
    chunks = split_text(madde["icerik"], chunk_size=1000, overlap=200)

    chunk_rows = []
    for idx, chunk_text in enumerate(chunks):
        embedding = embed_text(chunk_text)
        chunk_rows.append({
            "kanun_no": madde["kanun_no"],
            "kanun_adi": madde["kanun_adi"],
            "madde_no": madde["madde_no"],
            "madde_tipi": madde["madde_tipi"],
            "chunk_index": idx,
            "chunk_text": chunk_text,
            "embedding": embedding,
        })
        time.sleep(0.4)

    mevzuat_id = upsert_madde(madde)
    delete_existing_chunks(mevzuat_id)

    for row in chunk_rows:
        row["mevzuat_id"] = mevzuat_id
        supabase.table("mevzuat_chunks").insert(row).execute()

    return len(chunk_rows)


def load_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise RuntimeError(f"{path} bir liste değil.")
    return data


def main():
    toplam_madde = 0
    toplam_chunk = 0
    gunluk_limit_doldu = False

    for json_file in JSON_FILES:
        if gunluk_limit_doldu:
            break

        print(f"\nJSON yükleniyor: {json_file}")
        maddeler = load_json(json_file)
        print(f"  {len(maddeler)} kayıt bulundu")

        for madde in maddeler:
            if gunluk_limit_doldu:
                break

            try:
                chunk_sayisi = process_madde(madde)
                toplam_madde += 1
                toplam_chunk += chunk_sayisi
                print(
                    f"  ✅ {madde['madde_tipi']} {madde['madde_no']} yüklendi "
                    f"({chunk_sayisi} chunk)"
                )
                time.sleep(0.5)

            except Exception as e:
                err_str = str(e)

                if "429" in err_str:
                    if "PerDay" in err_str or "per_day" in err_str.lower():
                        print("\n🛑 GÜNLÜK LİMİT DOLDU!")
                        print("   Yarın tekrar çalıştırın.")
                        print(
                            f"   Bu oturumda {toplam_madde} kayıt ve {toplam_chunk} chunk yüklendi."
                        )
                        gunluk_limit_doldu = True
                        break
                    else:
                        print("  ⏸️ Dakikalık limit! 65 saniye bekleniyor...")
                        time.sleep(65)
                else:
                    print(
                        f"  ❌ {madde['madde_tipi']} {madde['madde_no']} hata: {e}"
                    )

    print("\n🎉 Oturum tamamlandı!")
    print(f"   Yüklenen kayıt : {toplam_madde}")
    print(f"   Yüklenen chunk : {toplam_chunk}")


if __name__ == "__main__":
    main()
