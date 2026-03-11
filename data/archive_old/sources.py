# sources.py

KANUNLAR = [
    # ÇEKİRDEK İLK DALGA
    {"kanun_no": "4721", "kanun_adi": "Türk Medeni Kanunu"},
    {"kanun_no": "6098", "kanun_adi": "Türk Borçlar Kanunu"},
    {"kanun_no": "6102", "kanun_adi": "Türk Ticaret Kanunu"},
    {"kanun_no": "2004", "kanun_adi": "İcra ve İflas Kanunu"},
    {"kanun_no": "6100", "kanun_adi": "Hukuk Muhakemeleri Kanunu"},

    {"kanun_no": "4857", "kanun_adi": "İş Kanunu"},
    {"kanun_no": "5510", "kanun_adi": "Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu"},
    {"kanun_no": "6356", "kanun_adi": "Sendikalar ve Toplu İş Sözleşmesi Kanunu"},
    {"kanun_no": "6331", "kanun_adi": "İş Sağlığı ve Güvenliği Kanunu"},
    {"kanun_no": "4447", "kanun_adi": "İşsizlik Sigortası Kanunu"},

    {"kanun_no": "5237", "kanun_adi": "Türk Ceza Kanunu"},
    {"kanun_no": "5271", "kanun_adi": "Ceza Muhakemesi Kanunu"},
    {"kanun_no": "5275", "kanun_adi": "Ceza ve Güvenlik Tedbirlerinin İnfazı Hakkında Kanun"},
    {"kanun_no": "5326", "kanun_adi": "Kabahatler Kanunu"},

    {"kanun_no": "2577", "kanun_adi": "İdari Yargılama Usulü Kanunu"},
    {"kanun_no": "2575", "kanun_adi": "Danıştay Kanunu"},
    {"kanun_no": "657", "kanun_adi": "Devlet Memurları Kanunu"},
    {"kanun_no": "5018", "kanun_adi": "Kamu Mali Yönetimi ve Kontrol Kanunu"},

    {"kanun_no": "4054", "kanun_adi": "Rekabetin Korunması Hakkında Kanun"},
    {"kanun_no": "4734", "kanun_adi": "Kamu İhale Kanunu"},

    # İKİNCİ DALGA - ŞİMDİLİK YORUMDA
    # {"kanun_no": "4735", "kanun_adi": "Kamu İhale Sözleşmeleri Kanunu"},
    # {"kanun_no": "3065", "kanun_adi": "Katma Değer Vergisi Kanunu"},
    # {"kanun_no": "213", "kanun_adi": "Vergi Usul Kanunu"},
    # {"kanun_no": "193", "kanun_adi": "Gelir Vergisi Kanunu"},
    # {"kanun_no": "5520", "kanun_adi": "Kurumlar Vergisi Kanunu"},
    # {"kanun_no": "6183", "kanun_adi": "Amme Alacaklarının Tahsil Usulü Hakkında Kanun"},
    # {"kanun_no": "1136", "kanun_adi": "Avukatlık Kanunu"},
    # {"kanun_no": "6502", "kanun_adi": "Tüketicinin Korunması Hakkında Kanun"},
    # {"kanun_no": "6698", "kanun_adi": "Kişisel Verilerin Korunması Kanunu"},
    # {"kanun_no": "5651", "kanun_adi": "İnternet Ortamında Yapılan Yayınların Düzenlenmesi Hakkında Kanun"},
    # {"kanun_no": "6458", "kanun_adi": "Yabancılar ve Uluslararası Koruma Kanunu"},
    # {"kanun_no": "5901", "kanun_adi": "Türk Vatandaşlığı Kanunu"},
    # {"kanun_no": "5393", "kanun_adi": "Belediye Kanunu"},
    # {"kanun_no": "5216", "kanun_adi": "Büyükşehir Belediyesi Kanunu"},
    # {"kanun_no": "3194", "kanun_adi": "İmar Kanunu"},
    # {"kanun_no": "2863", "kanun_adi": "Kültür ve Tabiat Varlıklarını Koruma Kanunu"},
    # {"kanun_no": "3402", "kanun_adi": "Kadastro Kanunu"},
    # {"kanun_no": "2942", "kanun_adi": "Kamulaştırma Kanunu"},
]

# Mevzuat PDF versiyon override gerekiyorsa buraya ekle.
KANUN_PDF_VERSIYON = {
    "213": "1.4",
}

# İstersen belirli kanunlar için lokal PDF yolu verebilirsin.
LOCAL_PDF_MAP = {
    # "4857": r"C:\PROJELERvol2\2-active\HukukAI\hukukai-backend\data\pdfs\4857.pdf",
}