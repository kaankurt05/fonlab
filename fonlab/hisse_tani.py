# -*- coding: utf-8 -*-
"""BIST hisseleri icin tani katmani.

Fon tarayicisindaki yontemin hisseye uygulanmis hali. Ayni ilke: **hukum
degil soru**. Hicbir ciktisi "al" ya da "alma" demez; fiyat serisinin nasil
davrandigini ve sorulmasi gereken seyleri gosterir.

Onemli bir hizalama notu
------------------------
Piyasa cipasi olarak BIST 100 endeks fonu (DZE) kullaniliyor, cunku Is
Yatirim'in acik ucu endeks kodlarini vermiyor (XU100 bos, EndeksTekil 401).
Ama TEFAS fon fiyati piyasanin **bir gun gerisinde**: olculdu, hissenin
gunluk getirisi DZE'nin *ertesi gun* getirisiyle ortusuyor.

    ham (kaydirmasiz) beta:  TUPRS -0,06  THYAO -0,13  SASA +0,01  AKBNK +0,04
    bir gun kaydirilmis   :  TUPRS  0,87  THYAO  1,06  SASA  1,05  AKBNK  1,22

Kaydirmasiz hesap BIST 30 hisseleri icin sifir beta uretiyordu - acikca
yanlis. Bu yuzden beta/korelasyon GECIKME kadar kaydirilarak hesaplaniyor.
Fon-fon karsilastirmalarinda bu gecikme iki tarafta da ayni oldugu icin
sadelesir; sorun yalnizca hisse-fon kiyasinda ortaya cikiyor.
"""
import json, math, os, re, time, urllib.request

from . import hisse, metrik, tefas

BURASI = os.path.dirname(os.path.abspath(__file__))
ONBELLEK = os.environ.get('FONLAB_CACHE', os.path.join(BURASI, '.onbellek'))
KART_TTL = int(os.environ.get('FONLAB_KART_TTL', 24 * 3600))
GECIKME = 1          # DZE'nin piyasaya gore gun cinsinden gecikmesi
LIMIT_ESIK = 0.095   # BIST gunluk fiyat marji ~%10; tabana/tavana yapisma
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0 Safari/537.36')

# Kivilcim kodlamasi tarayici.py ile ayni alfabeyi kullaniyor (nokta basina
# tek karakter, 64 seviye) ki sayfa tarafinda tek cozucu yetsin.
KV_ALFABE = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'


def kivilcim(v, nokta=64):
    if not v or len(v) < 4:
        return '', None, None
    adim = max(1, len(v) // nokta)
    ornek = [v[i] / v[0] * 100 for i in range(0, len(v), adim)][:nokta + 1]
    if ornek and abs(ornek[-1] - v[-1] / v[0] * 100) > 1e-9:
        ornek.append(v[-1] / v[0] * 100)
    lo, hi = min(ornek), max(ornek)
    ar = (hi - lo) or 1
    return ''.join(KV_ALFABE[int(round((x - lo) / ar * 63))] for x in ornek), lo, hi


def piyasa_iliskisi(s, ex, d0, d1, kaydir=GECIKME):
    """Hisse ile piyasa cipasi arasinda beta/korelasyon.

    `kaydir` gun kadar cipa ileri alinarak hizalanir (bkz. modul basligi).
    Hem duzeltilmis hem ham deger doner; sayfa ikisini birlikte gosterip
    duzeltmenin neden gerektigini kaniti ile anlatabilsin.
    """
    ortak = [d for d in sorted(set(s.tarihler) & set(ex.tarihler)) if d0 <= d <= d1]
    if len(ortak) < 40:
        return None
    rh = [s.px[ortak[i]] / s.px[ortak[i - 1]] - 1 for i in range(1, len(ortak))]
    rx = [ex.px[ortak[i]] / ex.px[ortak[i - 1]] - 1 for i in range(1, len(ortak))]

    def ols(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        kov = sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / n
        va = sum((x - ma) ** 2 for x in a) / n
        vb = sum((x - mb) ** 2 for x in b) / n
        if va <= 0 or vb <= 0:
            return None
        r = kov / math.sqrt(va * vb)
        return {'beta': kov / vb, 'r': r, 'r2': r * r, 'n': n}

    ham = ols(rh, rx)
    duz = ols(rh[:-kaydir], rx[kaydir:]) if kaydir and len(rh) > kaydir else ham
    return {'beta': duz['beta'], 'r': duz['r'], 'r2': duz['r2'], 'n': duz['n'],
            'kaydir': kaydir, 'ham_beta': ham['beta'], 'ham_r2': ham['r2']}


def kart(kod, taze=False):
    """Is Yatirim sirket kartindan halka aciklik, piyasa degeri, net borc."""
    os.makedirs(ONBELLEK, exist_ok=True)
    yol = os.path.join(ONBELLEK, f'kart_{kod}.json')
    if not taze and os.path.exists(yol) and time.time() - os.path.getmtime(yol) < KART_TTL:
        with open(yol, encoding='utf-8') as f:
            return json.load(f)
    url = ('https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/'
           f'sirket-karti.aspx?hisse={kod}')
    h = urllib.request.urlopen(
        urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60
    ).read().decode('utf-8', 'replace')
    d = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h))

    def sayi(desen):
        m = re.search(desen, d)
        if not m:
            return None
        try:
            return float(m.group(1).replace('.', '').replace(',', '.'))
        except ValueError:
            return None

    v = {'kod': kod,
         'halka_acik': sayi(r'Halka Açıklık Oranı \(%\) ([\d.,]+)'),
         'piyasa_degeri_mn': sayi(r'Piyasa Değeri ([\d.,-]+) mnTL'),
         # Bankalarda net borc yayimlanmiyor; None burada hata degil.
         'net_borc_mn': sayi(r'Net Borç ([\d.,-]+) mnTL')}
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(v, f, ensure_ascii=False)
    return v


def _pencere(s, d0, d1):
    ds, v = s.dilim(d0, d1)
    if len(ds) < 20:
        return None
    rs = metrik.getiriler(v)
    mdd, zirve, dip, topar = metrik.maks_dusus(ds, v)
    return {'bas': ds[0], 'bit': ds[-1], 'gun': len(ds),
            'toplam': v[-1] / v[0] - 1,
            'vol': metrik.std(rs) * math.sqrt(metrik.ISLEM_GUNU),
            'mdd': mdd, 'mdd_zirve': zirve, 'mdd_dip': dip,
            'zirveden': v[-1] / max(v) - 1,
            'arti_oran': sum(1 for r in rs if r > 0) / len(rs),
            'rho': metrik.otokorelasyon(rs),
            'en_iyi': max(rs), 'en_kotu': min(rs),
            'limit_gun': sum(1 for r in rs if abs(r) >= LIMIT_ESIK)}


def tani(kod, ex, bas, bit, son12_bas):
    s = metrik.Seri(kod, hisse.fiyat_serisi(kod, bas, bit))
    ds, v = s.dilim(bas, bit)
    kv, lo, hi = kivilcim(v)
    # Ayrica 12 aylik pencere icin ikinci bir kivilcim: portfoy sekmesi fon
    # serileriyle (hepsi 12 aylik) ayni zaman izgarasinda birlestirmek zorunda.
    # Tam donem serisiyle karistirmak agirlikli seriyi anlamsiz yapardi.
    v12 = s.dilim(son12_bas, bit)[1]
    kv12, lo12, hi12 = kivilcim(v12)
    out = {'kod': kod, 'son_fiyat': v[-1], 'kivilcim': kv, 'kv_lo': lo, 'kv_hi': hi,
           'kv12': kv12, 'kv12_lo': lo12, 'kv12_hi': hi12,
           'tam': _pencere(s, bas, bit),
           'son12': _pencere(s, son12_bas, bit),
           'piyasa': piyasa_iliskisi(s, ex, bas, bit),
           'yogunlasma': metrik.yogunlasma(s, bas, bit),
           'kovalar': metrik.kovala_simetrik(metrik.getiriler(
               s.dilim(son12_bas, bit)[1])),
           'yillik': []}
    for yil in sorted({d[:4] for d in ds}):
        p = _pencere(s, f'{yil}-01-01', f'{yil}-12-31')
        if p:
            p['yil'] = yil
            out['yillik'].append(p)
    try:
        out['kart'] = kart(kod)
    except Exception as e:
        out['kart'] = {'kod': kod, 'hata': str(e)[:60]}
    return out


def paket(kodlar, bas, bit, endeks='DZE'):
    ex = metrik.Seri(endeks, tefas.fiyat_serisi(endeks, 60))
    return {'olusturma': time.strftime('%Y-%m-%d %H:%M'),
            'bas': bas, 'bit': bit, 'endeks': endeks, 'gecikme': GECIKME,
            'hisseler': [tani(k, ex, bas, bit, son12_bas=_yil_once(bit))
                         for k in kodlar]}


def _yil_once(bit):
    y, a, g = map(int, bit.split('-'))
    return f'{y - 1}-{a:02d}-{g:02d}'
