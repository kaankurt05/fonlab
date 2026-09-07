# -*- coding: utf-8 -*-
"""TEFAS veri katmani: cekme + disk onbellegi.

TEFAS 2026'da yeni siteye gecti. Eski `/api/DB/BindHistoryInfo` ucu kapatildi;
calisan uc `/api/funds/fonFiyatBilgiGetir`. HTML sayfalari F5/Shape bot
korumasi arkasinda ama /api/* yollari korumasiz, duz HTTP ile calisiyor.
"""
import json, os, time, urllib.request, urllib.error

BASE = 'https://www.tefas.gov.tr/api/funds/'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')
CACHE_DIR = os.environ.get('FONLAB_CACHE',
                           os.path.join(os.path.dirname(os.path.abspath(__file__)), '.onbellek'))
CACHE_TTL = int(os.environ.get('FONLAB_TTL', 6 * 3600))   # saniye
MAX_PERIYOD = 60                                          # TEFAS ay tavani (5 yil)


class TefasHata(RuntimeError):
    pass


def _cache_path(ad):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, ad + '.json')


def _cached(ad, ttl=None):
    p = _cache_path(ad)
    ttl = CACHE_TTL if ttl is None else ttl
    if os.path.exists(p) and (ttl < 0 or time.time() - os.path.getmtime(p) < ttl):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return None


def _store(ad, veri):
    with open(_cache_path(ad), 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False)
    return veri


def cagir(uc, govde, referer_kod=None, deneme=3):
    """TEFAS API'sine POST at, JSON don. Hata mesajini yukari tasi."""
    data = json.dumps(govde).encode('utf-8')
    ref = ('https://www.tefas.gov.tr/tr/fon-detayli-analiz/' + referer_kod
           if referer_kod else 'https://www.tefas.gov.tr/tr')
    son = None
    for i in range(deneme):
        req = urllib.request.Request(BASE + uc, data=data, method='POST', headers={
            'Content-Type': 'application/json', 'Accept': 'application/json',
            'User-Agent': UA, 'Referer': ref, 'X-Requested-With': 'XMLHttpRequest'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read().decode('utf-8'))
            if j.get('errorMessage'):
                raise TefasHata(f'{uc}: {j["errorMessage"]}')
            return j
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            son = e
            time.sleep(1.5 * (i + 1))
    raise TefasHata(f'{uc} basarisiz: {son}')


def fiyat_serisi(kod, periyod=MAX_PERIYOD, taze=False):
    """Gunluk birim pay fiyatlari -> [(tarih, fiyat)], tarihe gore sirali.
    Sifir fiyatli gozlemler (fonun ilk gunu bazen 0 geliyor) ayiklanir."""
    if periyod > MAX_PERIYOD:
        raise ValueError(f'TEFAS periyod tavani {MAX_PERIYOD} ay; {periyod} istendi')
    ad = f'fiyat_{kod}_{periyod}'
    j = None if taze else _cached(ad)
    if j is None:
        j = _store(ad, cagir('fonFiyatBilgiGetir',
                             {'fonKodu': kod, 'dil': 'TR', 'periyod': periyod}, kod))
    rows = [(x['tarih'], float(x['fiyat'])) for x in (j.get('resultList') or [])
            if x.get('fiyat') and float(x['fiyat']) > 0]
    rows.sort()
    if not rows:
        raise TefasHata(f'{kod}: fiyat serisi bos')
    return rows


def kunye(kod, taze=False):
    """Fon buyuklugu, yatirimci sayisi, kategori derecesi vb."""
    ad = f'kunye_{kod}'
    j = None if taze else _cached(ad)
    if j is None:
        j = _store(ad, cagir('fonBilgiGetir', {'fonKodu': kod, 'dil': 'TR'}, kod))
    rl = j.get('resultList') or []
    if not rl:
        raise TefasHata(f'{kod}: kunye bos')
    return rl[0]


def evren(taze=False):
    """Tum fon evreni -> {kod: unvan}. Govde ne olursa olsun tam listeyi doner."""
    j = None if taze else _cached('evren', ttl=7 * 24 * 3600)
    if j is None:
        j = _store('evren', cagir('fonUnvanAra', {'dil': 'TR'}))
    return {x['fonKodu']: x['fonUnvan'] for x in (j.get('resultList') or [])}


def ara(desen, haric=('EMEKLİLİK',), limit=25):
    """Fon evreninde unvana gore ara. `python3 -m fonlab ara "PARA PİYASASI"`"""
    import re
    d = re.compile(desen, re.I)
    out = []
    for kod, unvan in sorted(evren().items(), key=lambda kv: kv[1]):
        if d.search(unvan) and not any(h in unvan for h in haric):
            out.append((kod, unvan))
            if len(out) >= limit:
                break
    return out


# Not: varlik dagilimi (`dagilimSiraliGetirT`) API'den NullPointer donuyor;
# o veri simdilik fon detay sayfasindan DOM ile okunmali - `yapilandirma.py`
# icindeki `dagilim` alanina elle giriliyor.
