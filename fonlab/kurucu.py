# -*- coding: utf-8 -*-
"""Tek bir portfoy yonetim sirketinin tum serbest fonlarini birlikte inceler.

Neden ayri bir modul: tarayici tek tek fonlari siraliyor, ama bir fonun
sira numarasi ancak *ayni evin diger fonlariyla* birlikte okununca anlam
kazaniyor. 51 fonu olan bir kurucunun en iyisi, hicbir beceri olmasa bile
listenin tepesinde olur.

Uc olcum tasiyor:
  1. Dagilim      - fonlar kurulustan bugune nereye dagilmis
  2. Kohort       - ayni hafta acilan fonlar ne yapmis (dogal deney)
  3. Nakit esigi  - kac fon kendi omru boyunca para piyasasi fonunu gecmis

Bolunme duzeltmesi: gunluk > +%100 sicramalar pay bolunmesi/yeniden
degerleme sayilip notrleniyor. Bu duzeltme kayiplari **buyutuyor** (DHI
ham -%58 -> duzeltilmis -%99); ham TEFAS serisi kayiplari oldugundan
kucuk gosteriyor.
"""
import json, math, os
from datetime import date

from . import metrik, tefas

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
SICRAMA_ESIGI = 1.0      # gunluk > +%100 -> bolunme varsay
KOHORT_GUN = 14          # bu kadar gun icinde acilanlar ayni kohort


def _ord(g):
    y, a, gg = map(int, g.split('-'))
    return date(y, a, gg).toordinal()


def _duzelt(ds, px):
    """(duzeltilmis_toplam_getiri, atlanan_gunler) - bolunme gunleri notrlenir."""
    v = [px[d] for d in ds]
    rs = metrik.getiriler(v)
    t, atlanan = 1.0, []
    for j, r in enumerate(rs):
        if r > SICRAMA_ESIGI:
            atlanan.append([ds[j + 1], round(r, 4)])
            continue
        t *= (1 + r)
    return t - 1, atlanan


def _pencere_cagr(s, d0, d1):
    ds = [t for t in s.tarihler if d0 <= t <= d1]
    if len(ds) < 20:
        return None
    return (s.px[ds[-1]] / s.px[ds[0]]) ** (252 / len(ds)) - 1


def incele(kurucu, tarama_yolu=None, risksiz='ALE', endeks='DZE', periyod=60):
    """Kurucunun tarama evrenindeki tum fonlarini cek, olc, dondur."""
    yol = tarama_yolu or os.path.join(KOK, 'tarama.json')
    with open(yol, encoding='utf-8') as f:
        tar = json.load(f)
    kodlar = sorted(x['kod'] for x in tar['fonlar']
                    if x['ad'].upper().startswith(kurucu.upper()))
    if not kodlar:
        return None

    rf = metrik.Seri(risksiz, tefas.fiyat_serisi(risksiz, periyod))
    ex = metrik.Seri(endeks, tefas.fiyat_serisi(endeks, periyod))

    fonlar = []
    for k in kodlar:
        try:
            s = metrik.Seri(k, tefas.fiyat_serisi(k, periyod))
            ku = tefas.kunye(k)
        except Exception:
            continue
        ds = s.tarihler
        v = [s.px[d] for d in ds]
        ham = v[-1] / v[0] - 1
        duz, atlanan = _duzelt(ds, s.px)
        yil = len(ds) / metrik.ISLEM_GUNU
        fonlar.append({
            'kod': k, 'ad': ku['fonUnvan'], 'bas': ds[0], 'bit': ds[-1], 'gun': len(ds),
            'buyukluk': ku['portBuyukluk'], 'yatirimci': ku['yatirimciSayi'],
            'derece': ku['kategoriDerece'],
            'ham': ham, 'duz': duz, 'atlanan': atlanan,
            'cagr': (1 + duz) ** (1 / yil) - 1 if duz > -0.999 else -1.0,
            'nakit_cagr': _pencere_cagr(rf, ds[0], ds[-1]),
            'endeks_cagr': _pencere_cagr(ex, ds[0], ds[-1]),
            'zirveden': v[-1] / max(v) - 1,
            'zirve_t': ds[v.index(max(v))]})

    fonlar.sort(key=lambda x: x['bas'])
    g = sorted(x['duz'] for x in fonlar)
    n = len(fonlar)
    buy = sum(x['buyukluk'] or 0 for x in fonlar)
    # kaba baslangic agirligi: bugunku buyukluk / (1+getiri). Akis varsayimi yok
    # sayiyorsa da iki yanlilik da sonucu *iyi* tarafa itiyor (kazananlarin
    # buyuklugu buyuk olcude sonradan gelen para, -%100'e giden fonlar ise
    # tamamen disarida kaliyor) - yani bu tahmin iyimser taraftan hatali.
    b0 = [(((x['buyukluk'] or 0) / (1 + x['duz'])) if x['duz'] > -0.999 else 0.0, x['duz'])
          for x in fonlar]
    t0 = sum(w for w, _ in b0) or 1.0

    kohort, cur = [], [fonlar[0]]
    for x in fonlar[1:]:
        if _ord(x['bas']) - _ord(cur[0]['bas']) <= KOHORT_GUN:
            cur.append(x)
        else:
            kohort.append(cur); cur = [x]
    kohort.append(cur)

    nakit_yenen = sum(1 for x in fonlar if x['nakit_cagr'] and x['cagr'] > x['nakit_cagr'])
    endeks_yenen = sum(1 for x in fonlar if x['endeks_cagr'] and x['cagr'] > x['endeks_cagr'])
    c = sorted(x['cagr'] for x in fonlar)
    nk = sorted(x['nakit_cagr'] for x in fonlar if x['nakit_cagr'])

    return {
        'kurucu': kurucu, 'fon': n, 'fonlar': fonlar,
        'buyukluk': buy, 'yatirimci': sum(x['yatirimci'] or 0 for x in fonlar),
        'medyan': g[n // 2], 'ortalama': sum(g) / n, 'en_iyi': g[-1], 'en_kotu': g[0],
        'medyan_cagr': c[n // 2], 'nakit_medyan_cagr': nk[len(nk) // 2] if nk else None,
        'nakit_yenen': nakit_yenen, 'endeks_yenen': endeks_yenen,
        'eksi': sum(1 for x in g if x < 0),
        'yarim': sum(1 for x in g if x <= -0.5),
        'doksan': sum(1 for x in g if x <= -0.9),
        'iki_kat': sum(1 for x in g if x >= 1.0),
        'zirveden_yarim': sum(1 for x in fonlar if x['zirveden'] <= -0.5),
        'zirvede': sum(1 for x in fonlar if x['zirveden'] >= -0.05),
        'agirlik_bugun': sum((x['buyukluk'] or 0) * x['duz'] for x in fonlar) / (buy or 1),
        'agirlik_baslangic': sum(w * gg for w, gg in b0) / t0,
        'duzeltilen': [x['kod'] for x in fonlar if x['atlanan']],
        'kohort': [[x['kod'] for x in c2] for c2 in kohort if len(c2) >= 3],
    }
