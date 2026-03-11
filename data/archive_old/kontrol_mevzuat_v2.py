from supabase import create_client
import requests, fitz, re, os
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

# Resmi madde sayıları (mevzuat.gov.tr'den kontrol edilmiş)
KANUN_BILGI = {
    "4857": {"ad": "İş Kanunu",                              "beklenen": 121},
    "6098": {"ad": "Türk Borçlar Kanunu",                    "beklenen": 649},
    "4721": {"ad": "Türk Medeni Kanunu",                     "beklenen": 1030},
    "6502": {"ad": "Tüketicinin Korunması Hakkında Kanun",   "beklenen": 95},
    "2709": {"ad": "Türkiye Cumhuriyeti Anayasası",          "beklenen": 177},
    "5237": {"ad": "Türk Ceza Kanunu",                       "beklenen": 345},
    "5271": {"ad": "Ceza Muhakemesi Kanunu",                 "beklenen": 332},
    "2577": {"ad": "İdari Yargılama Usulü Kanunu",           "beklenen": 65},
    "213":  {"ad": "Vergi Usul Kanunu",                      "beklenen": 413},
    "6100": {"ad": "Hukuk Muhakemeleri Kanunu",              "beklenen": 447},
    "2004": {"ad": "İcra ve İflas Kanunu",                   "beklenen": 367},
    "5510": {"ad": "Sosyal Sigortalar Kanunu",               "beklenen": 108},
    "4734": {"ad": "Kamu İhale Kanunu",                      "beklenen": 67},
    "6362": {"ad": "Sermaye Piyasası Kanunu",                "beklenen": 139},
    "6102": {"ad": "Türk Ticaret Kanunu",                    "beklenen": 1535},
    "193":  {"ad": "Gelir Vergisi Kanunu",                   "beklenen": 123},
    "3065": {"ad": "Katma Değer Vergisi Kanunu",             "beklenen": 63},
    "5520": {"ad": "Kurumlar Vergisi Kanunu",                "beklenen": 40},
    "7036": {"ad": "İş Mahkemeleri Kanunu",                  "beklenen": 14},
}


def get_pdf_maddeler(kanun_no: str) -> set:
    """PDF'den madde numaralarını çeker."""
    url = f"https://www.mevzuat.gov.tr/MevzuatMetin/1.5.{kanun_no}.pdf"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code != 200:
        return set()
    tmp = f"tmp_{kanun_no}.pdf"
    with open(tmp, 'wb') as f:
        f.write(r.content)
    doc = fitz.open(tmp)
    text = "".join(p.get_text() for p in doc)
    doc.close()
    os.remove(tmp)
    pattern = r'(?:MADDE|Madde)\s+(\d+)\s*[–\-—]?\s*'
    parcalar = re.split(pattern, text)
    maddeler = set()
    for i in range(1, len(parcalar), 2):
        madde_no = parcalar[i].strip()
        icerik = parcalar[i+1].strip()[:1500] if i+1 < len(parcalar) else ""
        icerik = re.sub(r'\s+', ' ', icerik).strip()
        if len(icerik) > 80:
            maddeler.add(madde_no)
    return maddeler


def get_supabase_maddeler(kanun_no: str) -> set:
    """Supabase'deki madde numaralarını çeker."""
    offset = 0
    maddeler = set()
    while True:
        res = supabase.table('mevzuat').select('madde_no').eq('kanun_no', kanun_no).range(offset, offset+999).execute()
        if not res.data:
            break
        for r in res.data:
            maddeler.add(r['madde_no'])
        if len(res.data) < 1000:
            break
        offset += 1000
    return maddeler


def main():
    print("=" * 70)
    print("MEVZUAT DOĞRULAMA RAPORU")
    print("=" * 70)

    sorunlu = []

    for kanun_no, bilgi in KANUN_BILGI.items():
        print(f"\n📖 {bilgi['ad']} ({kanun_no})")

        # Supabase'deki maddeler
        sb_maddeler = get_supabase_maddeler(kanun_no)
        sb_sayisi = len(sb_maddeler)

        # PDF'deki maddeler
        print(f"   PDF indiriliyor...")
        pdf_maddeler = get_pdf_maddeler(kanun_no)
        pdf_sayisi = len(pdf_maddeler)

        # Karşılaştır
        beklenen = bilgi['beklenen']
        eksik_pdf = sorted([int(m) for m in pdf_maddeler - sb_maddeler if m.isdigit()])
        fazla_sb = sorted([int(m) for m in sb_maddeler - pdf_maddeler if m.isdigit()])

        print(f"   Beklenen madde : {beklenen}")
        print(f"   PDF'de bulunan : {pdf_sayisi}")
        print(f"   Supabase'de    : {sb_sayisi}")

        if eksik_pdf:
            print(f"   ⚠️  PDF'de var, Supabase'de YOK ({len(eksik_pdf)} adet): {eksik_pdf[:20]}")
            sorunlu.append((kanun_no, bilgi['ad'], eksik_pdf))
        else:
            print(f"   ✅ Supabase tam")

        if fazla_sb:
            print(f"   ℹ️  Supabase'de var, PDF'de yok ({len(fazla_sb)} adet): {fazla_sb[:10]}")

        if abs(pdf_sayisi - beklenen) > 10:
            print(f"   ⚠️  PDF parse sayısı beklenenden çok farklı! (fark: {pdf_sayisi - beklenen})")

    print("\n" + "=" * 70)
    print("ÖZET")
    print("=" * 70)
    if sorunlu:
        print(f"\n⚠️  {len(sorunlu)} kanunda eksik madde var:")
        for kanun_no, ad, eksikler in sorunlu:
            print(f"   {kanun_no} {ad}: {len(eksikler)} eksik → {eksikler[:10]}")
    else:
        print("\n✅ Tüm kanunlar Supabase'de tam!")

    print("\nNot: Mülga (kaldırılmış) maddeler PDF'de farklı formatta olduğundan")
    print("parse edilemeyebilir. Bu normaldir.")


if __name__ == '__main__':
    main()