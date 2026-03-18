import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

# structured_content üretimi için mevcut ortak util'i kullan
sys.path.append(str(PROJECT_ROOT))
from data.mevzuat.structured_content_utils import build_structured_content  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

load_dotenv(PROJECT_ROOT / ".env")

SUPABASE_URL = __import__("os").environ.get("SUPABASE_URL")
SUPABASE_KEY = __import__("os").environ.get("SUPABASE_SERVICE_ROLE_KEY") or __import__("os").environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (.env) eksik.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize_record(row: dict) -> dict:
    bagli_kanun_no = str(row["bagli_kanun_no"]).strip()
    yonetmelik_adi = str(row["yonetmelik_adi"]).strip()
    madde_no = str(row["madde_no"]).strip()
    madde_tipi = str(row.get("madde_tipi", "madde")).strip()
    icerik = str(row["icerik"]).strip()

    structured_content = row.get("structured_content")
    if not structured_content:
        structured_content = build_structured_content(icerik)

    return {
        "bagli_kanun_no": bagli_kanun_no,
        "yonetmelik_adi": yonetmelik_adi,
        "madde_no": madde_no,
        "madde_tipi": madde_tipi,
        "icerik": icerik,
        "structured_content": structured_content,
        "source_type": "yonetmelik",
    }


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python upload_yonetmelik_json.py 6698_verbis_ym")
        return

    klasor = sys.argv[1]
    folder = BASE_DIR / klasor

    if not folder.exists():
        raise FileNotFoundError(f"Klasör bulunamadı: {folder}")

    json_files = list(folder.glob("*_yonetmelik_preview.json"))
    if not json_files:
        raise FileNotFoundError(f"Preview JSON bulunamadı: {folder}")

    json_path = json_files[0]

    with open(json_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON liste formatında değil.")

    rows = [normalize_record(row) for row in data]

    print(f"Dosya: {json_path.name}")
    print(f"Yüklenecek kayıt sayısı: {len(rows)}")

    batch_size = 200
    uploaded = 0

    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]

        (
            supabase.table("yonetmelik")
            .upsert(
                chunk,
                on_conflict="bagli_kanun_no,yonetmelik_adi,madde_tipi,madde_no"
            )
            .execute()
        )

        uploaded += len(chunk)
        print(f"Upsert tamamlandı: {uploaded}/{len(rows)}")

    print("Tamamlandı.")


if __name__ == "__main__":
    main()