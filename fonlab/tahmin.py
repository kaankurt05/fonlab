# -*- coding: utf-8 -*-
"""Ertesi gunun getirisini tahmin eder ve isabeti durustce olcer.

Amac bir alim-satim sinyali degil, **olcum**: bir fonun ertesi gunu ne kadar
ongorulebilirse, net varlik degeri o kadar mekanik uretiliyor demektir.
Canli piyasaya gore isaretlenen bir fonda ertesi gunun yonu yazi-turadir.

Dort model, hepsi seffaf ve tek satirlik:
  yukari : her gun "arti" de                    (taban model)
  dun    : dunku getirinin isaretini tekrarla   (oto-korelasyonu somurur)
  ar1    : r_t = rho * r_{t-1}                  (rho gecmisten kestiriliyor)
  ort    : son N gunun ortalamasinin isareti

KRITIK OLCU ham isabet degil, **beceri** = isabet - taban oran.
Gunlerinin %98'i arti olan bir fonda "hep arti de" %98 tutturur ve sifir
bilgi tasir. Beceri, o bedava isabeti dusup geriye ne kaldigini soyluyor.

Iki ayri kayit tutuluyor:
  1. Geriye donuk yuruyen test (walk-forward) - bugun hesaplanabilir
  2. Ileriye donuk kayit (tahmin_kayit.json) - her calismada ertesi gun icin
     tahmin yazilir, bir sonraki calismada gerceklesenle puanlanir. Zamanla
     birikir ve tek gercek disorneklem kanittir.
"""
import json, math, os, time

from . import metrik, tefas

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
# FONLAB_KAYIT: test/deneme kosularinin gercek sicili bozmamasi icin
KAYIT = os.environ.get('FONLAB_KAYIT') or os.path.join(KOK, 'tahmin_kayit.json')

PENCERE = 120     # yuruyen testte kac gun puanlanacak
ASGARI_EGITIM = 60  # bir tahmin uretmek icin gereken en az gecmis


# ---------------------------------------------------------------- modeller
def _rho(rs):
    n = len(rs)
    if n < 12:
        return 0.0
    m = sum(rs) / n
    ust = sum((rs[i] - m) * (rs[i - 1] - m) for i in range(1, n))
    alt = sum((r - m) ** 2 for r in rs)
    return ust / alt if alt else 0.0


def _modeller(gecmis):
    """gecmis: bugune kadarki gunluk getiriler -> {model: tahmin_getiri}"""
    son = gecmis[-1]
    rho = _rho(gecmis[-250:])
    ort = sum(gecmis[-20:]) / min(20, len(gecmis))
    return {
        'yukari': abs(ort) or 1e-6,      # isaret pozitif olsun; buyukluk onemsiz
        'dun': son,
        'ar1': rho * son,
        'ort': ort,
    }


MODEL_AD = {'yukari': 'hep artı', 'dun': 'dünü tekrarla',
            'ar1': 'AR(1): ρ×dün', 'ort': '20 gün ortalaması'}


# ------------------------------------------------------- yuruyen test
def yuruyen(rs, pencere=PENCERE, asgari=ASGARI_EGITIM):
    """Disorneklem yuruyen test. Her gun icin yalnizca o gune kadarki veriyle
    tahmin uretilir; boylece gelecege bakma (look-ahead) yok."""
    n = len(rs)
    bas = max(asgari, n - pencere)
    if n - bas < 30:
        return None
    skor = {m: {'dogru': 0, 'n': 0, 'mae': 0.0} for m in MODEL_AD}
    arti = 0
    mae0 = 0.0        # "sifir tahmin et" - buyukluk icin durust taban model
    for t in range(bas, n):
        gercek = rs[t]
        if gercek > 0:
            arti += 1
        mae0 += abs(gercek)
        tah = _modeller(rs[:t])
        for m, v in tah.items():
            s = skor[m]
            s['n'] += 1
            if (v > 0) == (gercek > 0):
                s['dogru'] += 1
            s['mae'] += abs(v - gercek)
    adet = n - bas
    taban = max(arti, adet - arti) / adet      # cogunluk sinifi orani
    mae0 /= adet
    out = {}
    for m, s in skor.items():
        isabet = s['dogru'] / s['n']
        mae = s['mae'] / s['n']
        out[m] = {'isabet': isabet, 'beceri': isabet - taban,
                  'mae': mae,
                  # <1 ise model "sifir tahmin et"ten iyi; buyuklukte beceri var
                  'mae_orani': (mae / mae0) if mae0 else None,
                  'n': s['n']}
    en_iyi = max(out, key=lambda m: out[m]['beceri'])
    en_iyi_mae = min(out, key=lambda m: out[m]['mae'])
    return {'gun': adet, 'taban': taban, 'arti_oran': arti / adet,
            'mae0': mae0,
            'mae_en_iyi': en_iyi_mae, 'mae_orani': out[en_iyi_mae]['mae_orani'],
            'model': out, 'en_iyi': en_iyi,
            'en_iyi_isabet': out[en_iyi]['isabet'],
            'en_iyi_beceri': out[en_iyi]['beceri']}


def tahmin_et(rs, model=None):
    """Yarin icin tahmin. model verilmezse 'ar1'."""
    t = _modeller(rs)
    m = model if model in t else 'ar1'
    return {'model': m, 'getiri': t[m], 'yon': 1 if t[m] > 0 else -1}


# ------------------------------------------------------- ileriye donuk kayit
# Gunluk calisiyor. Her kosuda once bekleyen tahminler gerceklesen veriyle
# puanlaniyor, sonra ertesi gun icin yenileri yaziliyor.
#
# Boyut disiplini: gunde 1.200 kayit tutulursa dosya yilda 300 bine cikar.
# Onun yerine (a) fon basina kosan sicil, (b) gun basina tek ozet satiri,
# (c) yalnizca izleme listesi icin ayrintili kayit tutuluyor.

DETAY_AZAMI = 400        # ayrintili kayitta tutulacak en fazla satir


def kayit_yukle(yol=KAYIT):
    if os.path.exists(yol):
        with open(yol, encoding='utf-8') as f:
            k = json.load(f)
    else:
        k = {}
    k.setdefault('olusturma', None)
    k.setdefault('bekleyen', [])
    k.setdefault('sicil', {})      # kod -> [n, dogru, mae_toplam]
    k.setdefault('gunluk', [])     # {tarih, n, dogru, mae_toplam, arti}
    k.setdefault('detay', [])      # izleme listesi icin satir satir
    k.setdefault('ozet', {})
    return k


def kayit_yaz(k, yol=KAYIT):
    k['olusturma'] = time.strftime('%Y-%m-%d %H:%M')
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, separators=(',', ':'), default=float)
    return yol


def puanla_ve_tahmin(kodlar, seriler, izleme=(), yol=KAYIT, hazir=None):
    """Bekleyenleri puanla, yeni tahminleri yaz.

    seriler: {kod: metrik.Seri}
    hazir:   {kod: {'model':..., 'getiri':...}} - tara zaten hesapladiysa
             yuruyen test burada bir daha calistirilmaz. Ayni hesabin gunde
             iki kez yapilmasinin onune geciyor.

    Her gun icin, ayni puanlanan kume uzerinde "hep arti" diyen naif modelin
    isabeti de kaydediliyor (`arti`). Cunku tek basina "isabet %81" yaniltici:
    o gun naif model %86 tutturmus olabilir. Karsilastirma olmadan sicil bir
    sey anlatmiyor.
    """
    k = kayit_yukle(yol)
    izleme = set(izleme)
    kalan, gun_say = [], {}

    for t in k['bekleyen']:
        s = seriler.get(t['kod'])
        if not s:
            kalan.append(t); continue
        sonraki = [d for d in s.tarihler if d > t['bas_tarih']]
        if not sonraki:
            kalan.append(t); continue          # henuz yeni islem gunu yok
        g = sonraki[0]
        i = s.tarihler.index(g)
        gercek = s.px[g] / s.px[s.tarihler[i - 1]] - 1
        dogru = (t['getiri'] > 0) == (gercek > 0)
        hata = abs(t['getiri'] - gercek)

        sc = k['sicil'].setdefault(t['kod'], [0, 0, 0.0])
        sc[0] += 1; sc[1] += int(dogru); sc[2] += hata

        d = gun_say.setdefault(g, [0, 0, 0.0, 0])
        d[0] += 1; d[1] += int(dogru); d[2] += hata; d[3] += int(gercek > 0)

        if t['kod'] in izleme:
            k['detay'].append({'kod': t['kod'], 'tahmin_gun': t['bas_tarih'],
                               'gercek_gun': g, 'model': t['model'],
                               'tahmin': t['getiri'], 'gercek': gercek,
                               'dogru': dogru})
    k['bekleyen'] = kalan
    k['detay'] = k['detay'][-DETAY_AZAMI:]

    for g, (n, dg, mae, arti) in sorted(gun_say.items()):
        var = next((x for x in k['gunluk'] if x['tarih'] == g), None)
        if var:
            var['n'] += n; var['dogru'] += dg; var['mae_toplam'] += mae
            var['arti'] = var.get('arti', 0) + arti
        else:
            k['gunluk'].append({'tarih': g, 'n': n, 'dogru': dg,
                                'mae_toplam': mae, 'arti': arti})
    k['gunluk'].sort(key=lambda x: x['tarih'])

    # yeni tahminler - ayni fon+gun icin ikinci kez yazilmiyor
    mevcut = {(t['kod'], t['bas_tarih']) for t in k['bekleyen']}
    for kod in kodlar:
        s = seriler.get(kod)
        if not s or len(s.tarihler) < ASGARI_EGITIM:
            continue
        bas = s.tarihler[-1]
        if (kod, bas) in mevcut:
            continue
        h = (hazir or {}).get(kod)
        if h and h.get('model') and h.get('getiri') is not None:
            model, getiri = h['model'], h['getiri']
        else:
            rs = metrik.getiriler([s.px[d] for d in s.tarihler])
            y = yuruyen(rs)
            t = tahmin_et(rs, y['en_iyi'] if y else 'ar1')
            model, getiri = t['model'], t['getiri']
        k['bekleyen'].append({'kod': kod, 'bas_tarih': bas, 'model': model,
                              'getiri': round(getiri, 6),
                              'yon': 1 if getiri > 0 else -1,
                              'yazildi': time.strftime('%Y-%m-%d')})

    top_n = sum(v[0] for v in k['sicil'].values())
    top_d = sum(v[1] for v in k['sicil'].values())
    top_m = sum(v[2] for v in k['sicil'].values())
    # Naif karsilastirma yalnizca 'arti' kaydedilmis gunler uzerinden.
    # Eski gunlerde bu alan yok; onlari hesaba katmak yaniltici olurdu.
    ng = [g for g in k['gunluk'] if g.get('arti') is not None]
    naif_n = sum(g['n'] for g in ng)
    naif_d = sum(g['dogru'] for g in ng)
    naif_a = sum(g['arti'] for g in ng)
    k['ozet'] = {
        'adet': top_n,
        'isabet': (top_d / top_n) if top_n else None,
        'mae': (top_m / top_n) if top_n else None,
        'naif': (naif_a / naif_n) if naif_n else None,
        'naif_isabet': (naif_d / naif_n) if naif_n else None,
        'naif_gun': len(ng),
        'fon': len(k['sicil']),
        'gun': len(k['gunluk']),
        'ilk': k['gunluk'][0]['tarih'] if k['gunluk'] else None,
        'son': k['gunluk'][-1]['tarih'] if k['gunluk'] else None,
        'bekleyen': len(k['bekleyen']),
    }
    kayit_yaz(k, yol)
    return k['ozet']
