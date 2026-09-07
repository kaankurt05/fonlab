# -*- coding: utf-8 -*-
"""BIST hisse gunluk fiyat serisi (Is Yatirim acik JSON ucu) + disk onbellegi.

Fonun oynakligini *tuttugu hisselerin* oynakligiyla karsilastirabilmek icin
gerekli. TEFAS yalnizca fon fiyati veriyor; hisse tarafi buradan geliyor.

Uc bot korumasi arkasinda degil, duz HTTP ile calisiyor:
  /_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTekil
     ?hisse=<KOD>&startdate=GG-AA-YYYY&enddate=GG-AA-YYYY
Donen kayitlarda HGDG_TARIH (GG-AA-YYYY) ve HGDG_KAPANIS alanlari kullanilir.
"""
import json, os, time, urllib.request, urllib.error

UC = ('https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/'
      'Data.aspx/HisseTekil')
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')
CACHE_DIR = os.environ.get('FONLAB_CACHE',
                           os.path.join(os.path.dirname(os.path.abspath(__file__)), '.onbellek'))
CACHE_TTL = int(os.environ.get('FONLAB_TTL', 6 * 3600))


class HisseHata(RuntimeError):
    pass


def _iso(g):
    """'02-01-2026' -> '2026-01-02'"""
    gg, aa, yyyy = g.split('-')
    return f'{yyyy}-{aa}-{gg}'


def _tr(iso):
    """'2026-01-02' -> '02-01-2026'"""
    y, a, g = iso.split('-')
    return f'{g}-{a}-{y}'


def fiyat_serisi(kod, bas, bit, taze=False, deneme=3):
    """[(tarih_iso, kapanis)] — tarihe gore sirali, sifir/bos kapanislar ayiklanir."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    yol = os.path.join(CACHE_DIR, f'hisse_{kod}_{bas}_{bit}.json')
    if not taze and os.path.exists(yol) and time.time() - os.path.getmtime(yol) < CACHE_TTL:
        with open(yol, encoding='utf-8') as f:
            j = json.load(f)
    else:
        url = f'{UC}?hisse={kod}&startdate={_tr(bas)}&enddate={_tr(bit)}'
        req = urllib.request.Request(url, headers={
            'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/'
                       f'sirket-karti.aspx?hisse={kod}'})
        son = None
        for i in range(deneme):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.loads(r.read().decode('utf-8'))
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                son = e
                time.sleep(1.5 * (i + 1))
        else:
            raise HisseHata(f'{kod}: {son}')
        with open(yol, 'w', encoding='utf-8') as f:
            json.dump(j, f)
    if not j.get('ok'):
        raise HisseHata(f'{kod}: {j.get("errorDescription")}')
    seen = {}
    for r in (j.get('value') or []):
        k = r.get('HGDG_KAPANIS')
        if k and float(k) > 0:
            seen[_iso(r['HGDG_TARIH'])] = float(k)
    rows = sorted(seen.items())
    if not rows:
        raise HisseHata(f'{kod}: seri bos')
    return rows
