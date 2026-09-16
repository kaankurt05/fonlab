# -*- coding: utf-8 -*-
"""tarama.json -> etkilesimli tarayici sayfasi (HTML).

Rapor bir belge; bu bir arac. Ayni tasarim dilini kullanir ama isi farklidir:
esikleri kullanici oynatir, sonuc listesi aninda daralir.
"""
import json, os
from . import kabuk
from .rapor import ascii_kilitle
from .yapilandirma import AYAR

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)

# tabloya giren alanlar — dizi olarak paketlenir (JSON boyutu ~3 kat kucuk)
ALANLAR = ['kod', 'ad', 'toplam6', 'vol6', 'rho6', 'eksi_oran6',
           'toplam', 'vol', 'rho', 'eksi_oran', 'mdd', 'x10',
           'sharpe', 'buyukluk', 'yatirimci', 'gun', 'supheli',
           'toplam_duz', 'zirveden', 'ev', 'kivilcim', 'kv_lo', 'kv_hi',
           't_taban', 't_beceri', 't_yarin', 't_model', 'en_kotu']

# Kurucu adi fon unvaninin basinda duruyor ("PARDUS PORTFÖY ONUNCU ...").
# Ayri bir kaynak yok; TEFAS unvani tek dayanak.
def _ev(ad):
    u = ad.upper()
    for ayrac in (' PORTFÖY', ' PORTFOY'):
        if ayrac in u:
            return u.split(ayrac)[0].strip()
    return u.split()[0]


# Nokta basina TEK karakter: 64 seviye. Iki haneli sayiyla tutulunca sayfa
# 533 KB'a cikip acilmiyordu; 64 seviye hem kivilcim hem karsilastirma
# grafigi icin fazlasiyla yeterli.
KV_ALFABE = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'


def _kivilcim_dizge(dizi):
    """[100, 104, 97...] -> "50629c..." — nokta basina 2 haneli, 0-99 arasi.

    Kivilcim yalnizca *sekil* tasiyor; olcek zaten tabloda. Ham tam sayi
    dizisi olarak tutulunca 1.200 fon icin ~300 KB ediyordu ve sayfa
    acilmiyordu; kendi min-maks araliginda 0-99'a olceklenince ~120 KB.
    """
    if not dizi or len(dizi) < 4:
        return ''
    lo, hi = min(dizi), max(dizi)
    ar = (hi - lo) or 1
    return ''.join(KV_ALFABE[int(round((v - lo) / ar * 63))] for v in dizi)


def _yuvarla(v, n):
    return None if v is None else round(v, n)


def _sicil(yol=None):
    """Ileriye donuk tahmin sicilinin ozeti (tahmin_kayit.json).

    Geriye donuk yuruyen test bugun hesaplanabiliyor; bu ise gercek
    disorneklem kayit - her gun yazilip ertesi gun puanlaniyor. Ikisi
    ayri sey; sayfada da ayri gosteriliyor.
    """
    yol = yol or os.path.join(KOK, 'tahmin_kayit.json')
    if not os.path.exists(yol):
        return None
    try:
        with open(yol, encoding='utf-8') as f:
            k = json.load(f)
    except Exception:
        return None
    o = k.get('ozet') or {}
    if not o.get('adet'):
        return {'adet': 0, 'bekleyen': o.get('bekleyen', 0)}
    # 'naif' = o gun ayni fonlar icin "hep arti" diyen modelin isabeti.
    # Eski kayitlarda bu alan yok; None birakiliyor, uydurulmuyor.
    gun = [{'tarih': g['tarih'], 'n': g['n'],
            'isabet': g['dogru'] / g['n'] if g['n'] else None,
            'naif': (g['arti'] / g['n']) if g.get('arti') is not None and g['n'] else None}
           for g in k.get('gunluk', [])][-40:]
    return {**o, 'gunluk': gun}


def tahmin_ozeti(fonlar, tohum=7):
    """Yon tahmininde gorulen 'beceri', sansla ayirt edilebiliyor mu?

    Her fon icin kendi taban orani ve gun sayisiyla, dort modelin *rastgele*
    uretecegi en iyi beceri benzetimle uretiliyor. Gozlemlenen dagilim bu
    dagilimla ortusuyorsa ortada beceri yok demektir.
    """
    import random
    g = sorted(x['t_beceri'] for x in fonlar if x.get('t_beceri') is not None)
    if len(g) < 50:
        return None
    rnd = random.Random(tohum)

    def bir(taban, n=120, model=4):
        en = -9.0
        for _ in range(model):
            d = sum(1 for _ in range(n) if (rnd.random() < taban) == (rnd.random() < 0.5))
            en = max(en, d / n - taban)
        return en

    sans = sorted(bir(x['t_taban']) for x in fonlar if x.get('t_taban') is not None)
    tb = sorted(x['t_taban'] for x in fonlar if x.get('t_taban') is not None)

    def yuz(dizi, p):
        return dizi[min(len(dizi) - 1, int(p * (len(dizi) - 1)))]

    return {
        'n': len(g),
        'yuzdelik': [{'p': p, 'gozlem': yuz(g, p), 'sans': yuz(sans, p)}
                     for p in (0.5, 0.9, 0.95, 0.99, 1.0)],
        'esik': [{'e': e, 'gozlem': sum(1 for x in g if x > e),
                  'sans': sum(1 for x in sans if x > e)} for e in (0.02, 0.05, 0.10)],
        'taban_medyan': yuz(tb, 0.5),
        'taban_90': sum(1 for x in tb if x >= 0.90),
        'taban_100': sum(1 for x in tb if x >= 0.999),
    }


def _kivilcim_araligi(dizi):
    """Kivilcim dizgesini gercek olcege geri cevirmek icin (alt, ust).

    Dizge fonun kendi min-maks araliginda 0-99'a olceklenmisti; bu iki sayi
    olmadan iki fon ayni eksende ust uste cizilemez (karsilastirma sepeti
    tam olarak bunu yapiyor). Degerler ilk gun = 100 tabanli.
    """
    if not dizi or len(dizi) < 4:
        return (None, None)
    return (min(dizi), max(dizi))


def evler(fonlar, asgari=5):
    """Kurucu bazinda ozet: yayilim, nakit esigi, uc degerler.

    Bir fonun kategori sirasi tek basina okununca bir basari belgesi gibi
    duruyor; ayni evin diger fonlariyla birlikte okununca baska bir sey
    soyluyor. Tarayicinin bu gorunumu tam olarak onu gosteriyor.
    """
    grup = {}
    for x in fonlar:
        grup.setdefault(_ev(x['ad']), []).append(x)

    def yuzdelik(dizi, p):
        i = p * (len(dizi) - 1)
        alt = int(i)
        return dizi[alt] + (dizi[min(alt + 1, len(dizi) - 1)] - dizi[alt]) * (i - alt)

    out = []
    for ev, fs in grup.items():
        if len(fs) < asgari:
            continue
        # bolunmesi olan fonlarda duzeltilmis getiri kullaniliyor
        g = sorted((x.get('toplam_duz') if x.get('supheli') else x['toplam']) for x in fs)
        vol = sorted(x['vol'] for x in fs)
        yat = [x.get('yatirimci') or 0 for x in fs]
        out.append({
            'ev': ev, 'fon': len(fs),
            'p90': yuzdelik(g, 0.90), 'p10': yuzdelik(g, 0.10),
            'yayilim': yuzdelik(g, 0.90) - yuzdelik(g, 0.10),
            'medyan': g[len(g) // 2], 'en_iyi': g[-1], 'en_kotu': g[0],
            'eksi': sum(1 for x in g if x < 0),
            'yarim': sum(1 for x in g if x <= -0.5),
            'medyan_vol': vol[len(vol) // 2],
            'buyukluk': sum(x.get('buyukluk') or 0 for x in fs),
            'yatirimci': sum(yat),
            'yat_ort': (sum(yat) // len(fs)) if fs else 0,
            'bolunmeli': sum(1 for x in fs if x.get('supheli')),
            'kod': sorted(x['kod'] for x in fs)})
    out.sort(key=lambda r: -r['yayilim'])
    return out


def incelenen():
    """Rapordaki 'incelendi' rozetini AYAR'dan turet.

    Elle tutulan bir liste degil: ana fonlar KAP bolumune, ek vakalar
    vakalar bolumune baglanir. Boylece yeni bir vaka eklendiginde rozet
    kendiliginden dogru yere isaret eder (elle liste bir kez unutuldu).
    """
    m = {k: 'kap' for k in AYAR['fonlar']}
    m.update({k: 'vakalar' for k in (AYAR.get('vakalar') or {})})
    return m


def paket(tarama_yolu=None):
    yol = tarama_yolu or os.path.join(KOK, 'tarama.json')
    with open(yol, encoding='utf-8') as f:
        t = json.load(f)
    satirlar = []
    for x in t['fonlar']:
        satirlar.append([
            x['kod'], x['ad'],
            round(x['toplam6'], 4), round(x['vol6'], 4), round(x['rho6'], 3), round(x['eksi_oran6'], 3),
            round(x['toplam'], 4), round(x['vol'], 4), round(x['rho'], 3), round(x['eksi_oran'], 3),
            round(x['mdd'], 4), round(x['x10'], 4),
            round(x['sharpe'], 2) if x.get('sharpe') is not None else None,
            x.get('buyukluk'), x.get('yatirimci'), x['gun'], 1 if x.get('supheli') else 0,
            round(x.get('toplam_duz', x['toplam']), 4), round(x.get('zirveden', 0), 4),
            _ev(x['ad']), _kivilcim_dizge(x.get('kivilcim')),
            *_kivilcim_araligi(x.get('kivilcim')),
            _yuvarla(x.get('t_taban'), 3), _yuvarla(x.get('t_beceri'), 3),
            _yuvarla(x.get('t_yarin'), 5), x.get('t_model'),
            _yuvarla(x.get('en_kotu'), 4),
        ])
    return {'olusturma': t['olusturma'], 'evren': t['evren'], 'islenen': t['islenen'],
            'atlanan': t['atlanan'], 'hata': len(t['hatalar']),
            'raporUrl': AYAR.get('rapor_url', ''),
            'incelenen': incelenen(),
            'bit': t['fonlar'][0]['bit'] if t['fonlar'] else '',
            'alanlar': ALANLAR, 'satir': satirlar,
            'ev': evler(t['fonlar']), 'tahmin': tahmin_ozeti(t['fonlar']),
            'sicil': _sicil()}


def yaz(sablon=None, cikti=None, tarama_yolu=None):
    sablon = sablon or os.path.join(KOK, 'build', 'tarayici_sablon.html')
    cikti = cikti or os.path.join(KOK, 'build', 'serbest-fon-tarayici.html')
    with open(sablon, encoding='utf-8') as f:
        t = f.read()
    t = t.replace('/*__ORTAK_CSS__*/', kabuk.ORTAK_CSS)
    t = t.replace('<!--__NAV__-->', kabuk.nav('tarayici'))
    if '/*__TARAMA__*/' not in t:
        raise RuntimeError('sablonda /*__TARAMA__*/ yer tutucusu yok')
    veri = json.dumps(paket(tarama_yolu), ensure_ascii=True, separators=(',', ':'))
    with open(cikti, 'w', encoding='utf-8') as f:
        f.write(ascii_kilitle(t.replace('/*__TARAMA__*/', veri)))
    return cikti, len(veri)
