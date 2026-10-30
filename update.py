#!/usr/bin/env python3
"""TCMB EVDS3'ten kur ve endeks verisini çekip data.json'u günceller."""
import json, os, ssl, sys, time, urllib.request
from datetime import date, datetime, timedelta

BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
KUR_SERILERI = ["TP.DK.USD.S.YTL", "TP.DK.EUR.S.YTL"]
ENDEKS_SERILERI = ["TP.TUKFIY2025.GENEL", "TP.TUFE1YI.T1"]
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


def fetch(series, start, end):
    """EVDS3 isteği: parametreler '?' olmadan yola eklenir, anahtar 'key' başlığında."""
    key = os.environ.get("EVDS_API_KEY", "").strip()
    if not key:
        sys.exit("HATA: EVDS_API_KEY tanımlı değil (GitHub Secrets).")
    url = (f"{BASE}series={'-'.join(series)}&startDate={start:%d-%m-%Y}"
           f"&endDate={end:%d-%m-%Y}&type=json")
    ctx = ssl.create_default_context()
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT: TCMB sunucusu için gerekli
    req = urllib.request.Request(url, headers={"key": key, "User-Agent": "kur-dashboard/1.0"})
    last = None
    for deneme in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                govde = r.read().decode("utf-8")
            try:
                return json.loads(govde)
            except ValueError:
                sys.exit(f"HATA: Yanıt JSON değil (adres/anahtar sorunu olabilir): {govde[:200]!r}")
        except Exception as e:  # ağ hatası: tekrar dene
            last = e
            time.sleep(5 * (deneme + 1))
    sys.exit(f"HATA: EVDS'ye ulaşılamadı: {last}")


def num(v):
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else None
    except ValueError:
        return None


def parse_kur(resp):
    out = {}
    for it in resp.get("items", []):
        d = datetime.strptime(it["Tarih"], "%d-%m-%Y").date().isoformat()
        usd, eur = num(it.get("TP_DK_USD_S_YTL")), num(it.get("TP_DK_EUR_S_YTL"))
        if usd and eur:  # TCMB'nin kur yayımlamadığı günler boş gelir
            out[d] = [d, usd, eur]
    return out


def parse_endeks(resp):
    out = {}
    for it in resp.get("items", []):
        y, m = it["Tarih"].split("-")[:2]
        ay = f"{int(y):04d}-{int(m):02d}"
        tufe, ufe = num(it.get("TP_TUKFIY2025_GENEL")), num(it.get("TP_TUFE1YI_T1"))
        if tufe and ufe:  # henüz açıklanmamış aylar boş gelir
            out[ay] = [ay, tufe, ufe]
    return out


def main():
    data = json.load(open(DATA, encoding="utf-8"))
    kur = {r[0]: r for r in data["kur"]}
    endeks = {r[0]: r for r in data["endeks"]}
    bugun = date.today()

    # Kur: son kayıttan 10 gün geriden başla (düzeltmeleri de yakalar)
    bas = datetime.strptime(max(kur), "%Y-%m-%d").date() - timedelta(days=10)
    yeni = parse_kur(fetch(KUR_SERILERI, bas, bugun))
    if not yeni:
        sys.exit("HATA: Kur verisi boş geldi; yanıt biçimini kontrol edin.")
    kur.update(yeni)

    # Endeks: son 4 ay (TÜİK revizyonlarını yakalar)
    b = bugun.replace(day=1)
    for _ in range(4):
        b = (b - timedelta(days=1)).replace(day=1)
    yeni_e = parse_endeks(fetch(ENDEKS_SERILERI, b, bugun))
    endeks.update(yeni_e)

    data["kur"] = [kur[k] for k in sorted(kur)]
    data["endeks"] = [endeks[k] for k in sorted(endeks)]
    data["guncelleme"] = bugun.isoformat()
    json.dump(data, open(DATA, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    print(f"Kur: {len(yeni)} gün, son {data['kur'][-1]}")
    print(f"Endeks: {len(yeni_e)} ay, son {data['endeks'][-1]}")


if __name__ == "__main__":
    main()
