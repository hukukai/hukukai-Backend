"""
AYM Bireysel Başvuru Karar Scraper - v4
----------------------------------------
v3'ten fark:
- Sayfalama: /Ara ile başlat, aynı session'da /Sayfa/N ile devam et
- wait_for_kararlar timeout artırıldı (15→25s)
- Sayfa geçişinde retry mekanizması eklendi
- metin 15000 char limit kaldırıldı (tam metin)
- bilgiler alanından metadata parse edildi (başvuru_no, tur, bolum, tarihler)

Kurulum:
    pip install selenium webdriver-manager beautifulsoup4

Kullanım:
    python aym_scraper_v4.py debug     # HTML yapı analizi
    python aym_scraper_v4.py list      # Sadece liste (detaysız, hızlı)
    python aym_scraper_v4.py           # Tam scrape (metin dahil)
    python aym_scraper_v4.py upload    # Scrape + Supabase'e yükle
"""

import json
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://kararlarbilgibankasi.anayasa.gov.tr"
SEARCH_URL = f"{BASE_URL}/Ara"
OUTPUT_FILE = "aym_kararlar_v4.json"

# Sonuç parametreleri
SONUC_KODLARI = {
    "ihlal": "7",
    "ihlal_olmadigi": "8",
    "kabul_edilemezlik": "3",
    "hepsi": None,
}


def create_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def wait_for_kararlar(driver, timeout=25):
    """div.birkarar elementlerinin yüklenmesini bekle."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "birkarar"))
        )
        return True
    except Exception:
        return False


def parse_bilgiler(bilgiler_str):
    """
    "2023/38564 | Esas (İhlal)| Birinci Bölüm | Başvuru Tarihi : 15/05/2023 | Karar Tarihi : 06/01/2026"
    → dict
    """
    result = {
        "basvuru_no": "",
        "tur": "",
        "bolum": "",
        "basvuru_tarihi": "",
        "karar_tarihi": "",
    }
    if not bilgiler_str:
        return result

    parts = [p.strip() for p in bilgiler_str.split("|")]
    if len(parts) >= 1:
        result["basvuru_no"] = parts[0].strip()
    if len(parts) >= 2:
        result["tur"] = parts[1].strip()
    if len(parts) >= 3:
        result["bolum"] = parts[2].strip()
    for part in parts:
        if "Başvuru Tarihi" in part:
            result["basvuru_tarihi"] = part.split(":")[-1].strip()
        elif "Karar Tarihi" in part:
            result["karar_tarihi"] = part.split(":")[-1].strip()

    return result


def parse_karar_list(html):
    """HTML'den karar listesini parse et."""
    soup = BeautifulSoup(html, "html.parser")
    kararlar = []
    seen = set()

    for birkarar in soup.find_all("div", class_="birkarar"):
        link = birkarar.find("a", href=lambda h: h and "/BB/" in h and "Dil=" not in h)
        if not link:
            continue
        href = link["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        if href in seen:
            continue
        seen.add(href)

        titles_el = birkarar.find("titles")
        baslik = titles_el.get_text(strip=True) if titles_el else ""

        bilgiler_el = birkarar.find("div", class_="kararbilgileri")
        bilgiler_str = bilgiler_el.get_text(strip=True) if bilgiler_el else ""
        bilgiler = parse_bilgiler(bilgiler_str)

        konu_el = birkarar.find("div", class_="basvurukonualani")
        basvuru_konusu = konu_el.get_text(strip=True) if konu_el else ""

        kararlar.append({
            "url": href,
            "baslik": baslik,
            "basvuru_konusu": basvuru_konusu[:600],
            **bilgiler,
        })

    return kararlar


def get_total_count(html):
    soup = BeautifulSoup(html, "html.parser")
    sayac = soup.find("div", class_="bulunankararsayisi")
    if sayac:
        text = sayac.get_text(strip=True)
        parts = text.split()
        if parts and parts[0].replace(".", "").isdigit():
            return int(parts[0].replace(".", ""))
    return 0


def get_karar_detail(driver, url):
    """Karar detay sayfasından tam metni çek."""
    try:
        driver.set_page_load_timeout(30)
        try:
            driver.get(url)
        except Exception:
            # Timeout veya partial load — devam et, page_source'u al
            pass
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Sidebar kaldır
        for el in soup.find_all("div", class_="filtreler"):
            el.decompose()
        for el in soup.find_all("div", class_="aravetemizle"):
            el.decompose()
        for el in soup.find_all(["script", "style"]):
            el.decompose()

        # Ana içerik
        icerik_el = (
            soup.find("div", class_="kararsonucalani")
            or soup.find("div", class_="ortaalan")
        )

        if icerik_el:
            metin = icerik_el.get_text(separator="\n", strip=True)
        else:
            metin = soup.get_text(separator="\n", strip=True)

        # Baştaki navigasyon gürültüsünü temizle
        # "TÜRKİYE CUMHURİYETİ" ile başlayan yere git
        idx = metin.find("TÜRKİYE CUMHURİYETİ")
        if idx > 0:
            metin = metin[idx:]

        return {
            "metin": metin,
            "metin_uzunluk": len(metin),
            "scrape_tarihi": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"    [!] Detay hatası ({url}): {e}")
        return None


def goto_page(driver, page_num, sonuc_kodu, retry=3):
    """
    Belirtilen sayfaya git.
    Pagination URL formatı: /Ara?Sonuc%5B0%5D=7&page=N
    (HTML'deki pagination linklerinden tespit edildi)
    """
    if sonuc_kodu:
        url = f"{SEARCH_URL}?Sonuc%5B0%5D={sonuc_kodu}&page={page_num}"
    else:
        url = f"{SEARCH_URL}?page={page_num}"

    for attempt in range(retry):
        try:
            driver.get(url)
        except Exception as e:
            print(f"    [!] goto_page driver hatası: {e}")
            return False
        time.sleep(3)
        if wait_for_kararlar(driver, timeout=25):
            return True
        print(f"    [!] Sayfa {page_num} yüklenemedi (deneme {attempt+1}/{retry}), bekleniyor...")
        time.sleep(5)

    return False


def scrape_all(max_pages=None, sonuc_turu="ihlal", headless=True, detail=True, start_page=1, resume_file=None):
    """
    Ana scrape fonksiyonu.

    Args:
        max_pages: Kaç sayfa çekileceği (None = tümü)
        sonuc_turu: "ihlal", "ihlal_olmadigi", "kabul_edilemezlik", "hepsi"
        headless: Chrome görünür olsun mu
        detail: Karar detay sayfaları da çekilsin mi
    """
    sonuc_kodu = SONUC_KODLARI.get(sonuc_turu, "7")
    all_kararlar = []
    if resume_file:
        try:
            with open(resume_file, encoding="utf-8") as f:
                all_kararlar = json.load(f)
            print(f"  ← Resume: {len(all_kararlar)} karar yüklendi ({resume_file})")
        except Exception:
            pass

    print(f"\nSelenium başlatılıyor... (headless={headless})")
    driver = create_driver(headless=headless)

    try:
        print(f"Tarama başlıyor | Tür: {sonuc_turu} | Max sayfa: {max_pages or 'tümü'}\n")

        # İlk sayfayı yükle
        if not goto_page(driver, start_page, sonuc_kodu):
            print("[!] İlk sayfa yüklenemedi!")
            with open("debug_hata.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return []

        toplam = get_total_count(driver.page_source)
        sayfa_basi = 10  # Site varsayılanı
        toplam_sayfa = (toplam + sayfa_basi - 1) // sayfa_basi
        if max_pages:
            toplam_sayfa = min(toplam_sayfa, max_pages)

        print(f"Toplam karar: {toplam} | Toplam sayfa: {toplam_sayfa}")

        prev_urls = set()

        for page in range(start_page, toplam_sayfa + 1):
            print(f"\n{'='*50}")
            print(f"[Sayfa {page}/{toplam_sayfa}]")

            if page > 1:
                try:
                    driver.title
                except Exception:
                    print(f"  [!] Sayfa geçişinde driver çöktü, yeniden başlatılıyor...")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    driver = create_driver(headless=headless)
                if not goto_page(driver, page, sonuc_kodu):
                    print(f"  [!] Sayfa {page} yüklenemedi, durduruluyor.")
                    break

            kararlar = parse_karar_list(driver.page_source)

            if not kararlar:
                print("  Karar bulunamadı.")
                break

            current_urls = {k["url"] for k in kararlar}
            if current_urls == prev_urls:
                print(f"  [!] Sayfa {page} öncekiyle aynı, durduruluyor.")
                break
            prev_urls = current_urls

            print(f"  {len(kararlar)} karar bulundu.")

            for i, karar in enumerate(kararlar):
                print(f"  [{i+1}/{len(kararlar)}] {karar['baslik'][:65]}")

                if detail:
                    # Driver crash recovery
                    try:
                        driver.title  # session hala açık mı kontrol et
                    except Exception:
                        print("  [!] Driver çöktü, yeniden başlatılıyor...")
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        driver = create_driver(headless=headless)
                        # Mevcut sayfaya geri dön
                        goto_page(driver, page, sonuc_kodu)

                    det = get_karar_detail(driver, karar["url"])
                    if det:
                        karar.update(det)
                        q = "✓" if det["metin_uzunluk"] > 1000 else "⚠ KISA"
                        print(f"           {det['metin_uzunluk']:,} karakter {q}")
                    time.sleep(1)

            all_kararlar.extend(kararlar)
            print(f"  Toplam çekilen: {len(all_kararlar)}")

            # Ara kayıt (her 50 kararda)
            if len(all_kararlar) % 50 < len(kararlar):
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_kararlar, f, ensure_ascii=False, indent=2)
                print(f"  → Ara kayıt: {len(all_kararlar)} karar")

    finally:
        driver.quit()

    return all_kararlar


def debug_mode():
    driver = create_driver(headless=False)
    try:
        url = f"{SEARCH_URL}?Sonuc%5B0%5D=7&page=1"
        print(f"Açılıyor: {url}")
        driver.get(url)
        time.sleep(5)

        with open("debug_search_v4.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        kararlar = parse_karar_list(driver.page_source)
        toplam = get_total_count(driver.page_source)
        print(f"Toplam: {toplam} | Bu sayfada: {len(kararlar)} karar\n")

        for i, k in enumerate(kararlar):
            print(f"  [{i+1}] {k['baslik']}")
            print(f"       No: {k['basvuru_no']} | {k['tur']} | {k['bolum']}")
            print(f"       Karar: {k['karar_tarihi']} | URL: {k['url']}\n")

        # Sayfa 2 testi
        print("\nSayfa 2 testi...")
        driver.get(f"{SEARCH_URL}?Sonuc%5B0%5D=7&page=2")
        time.sleep(5)

        with open("debug_sayfa2_v4.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        kararlar2 = parse_karar_list(driver.page_source)
        print(f"Sayfa 2: {len(kararlar2)} karar")
        if kararlar2:
            print("  ✓ Sayfalama çalışıyor!")
            print(f"  İlk: {kararlar2[0]['baslik'][:60]}")
        else:
            print("  ✗ Sayfa 2 boş!")
            print(f"  Mevcut URL: {driver.current_url}")

    finally:
        input("\nEnter'a bas, tarayıcı kapansın...")
        driver.quit()


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "scrape"

    if mode == "debug":
        debug_mode()

    elif mode == "list":
        kararlar = scrape_all(
            max_pages=20,
            sonuc_turu="ihlal",
            headless=True,
            detail=False,
        )
        out = "aym_liste_v4.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(kararlar, f, ensure_ascii=False, indent=2)
        print(f"\n{len(kararlar)} karar → '{out}'")

    elif mode == "upload":
        # Önce scrape, sonra embed_and_upload.py ile yükle
        kararlar = scrape_all(
            max_pages=10,
            sonuc_turu="ihlal",
            headless=True,
            detail=True,
        )
        if kararlar:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(kararlar, f, ensure_ascii=False, indent=2)
            print(f"\n{len(kararlar)} karar kaydedildi → {OUTPUT_FILE}")
            print("Şimdi embed_and_upload.py çalıştır.")

    elif mode == "resume":
        # Kaldığı yerden devam: python aym_scraper_v4.py resume 41 947
        start_p = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        max_p_arg = int(sys.argv[3]) if len(sys.argv) > 3 else None
        kararlar = scrape_all(
            max_pages=max_p_arg,
            sonuc_turu="ihlal",
            headless=True,
            detail=True,
            start_page=start_p,
            resume_file=OUTPUT_FILE,
        )
        if kararlar:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(kararlar, f, ensure_ascii=False, indent=2)
            print(f"\n✓ Toplam {len(kararlar)} karar → '{OUTPUT_FILE}'")

    else:
        # Tam scrape
        max_p = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        kararlar = scrape_all(
            max_pages=max_p,
            sonuc_turu="ihlal",
            headless=True,
            detail=True,
        )
        if kararlar:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(kararlar, f, ensure_ascii=False, indent=2)
            print(f"\n✓ {len(kararlar)} karar → '{OUTPUT_FILE}'")
            kisa = [k for k in kararlar if k.get("metin_uzunluk", 0) < 1000]
            print(f"  Normal (>1000 kar): {len(kararlar)-len(kisa)} ✓")
            print(f"  Kısa (<1000 kar):   {len(kisa)} ⚠")
        else:
            print("\nHiç karar çekilemedi.")