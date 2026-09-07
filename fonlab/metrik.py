# -*- coding: utf-8 -*-
"""Fiyat serilerinden risk/getiri metrikleri. Bagimliliksiz, saf Python."""
import math
from datetime import date

ISLEM_GUNU = 252


# ---------- temel yardimcilar ----------
def yillar(d0, d1):
    a = date(*map(int, d0.split('-'))); b = date(*map(int, d1.split('-')))
    return (b - a).days / 365.25

def getiriler(v):
    return [v[i] / v[i - 1] - 1 for i in range(1, len(v))]

def bilesik(rs):
    p = 1.0
    for r in rs:
        p *= (1 + r)
    return p - 1

def std(xs):
    n = len(xs); m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))

def yuzdelik(xs, p):
    ys = sorted(xs); k = (len(ys) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return ys[f] if f == c else ys[f] * (c - k) + ys[c] * (k - f)

def korelasyon(a, b):
    """Pearson korelasyonu.

    Sifir varyans korumasi *bagil* esikle yapiliyor: `if not ca` yeterli
    degil, cunku neredeyse sabit bir seride kayan nokta gurultusu
    ca ~ 1e-36 gibi sifirdan farkli ama anlamsiz bir deger uretir ve
    1e-36/1e-36 = 1.0 verir. Bu, para piyasasi benzeri duz serilerde
    sahte bir "mukemmel yumusatma" imzasi dogurur.
    """
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    ca = sum((x - ma) ** 2 for x in a); cb = sum((x - mb) ** 2 for x in b)
    # olcek: serinin kendi buyuklugune gore anlamli varyans esigi
    esik_a = max(abs(x) for x in a) ** 2 * n * 1e-20 or 1e-300
    esik_b = max(abs(x) for x in b) ** 2 * n * 1e-20 or 1e-300
    if ca <= esik_a or cb <= esik_b:
        return 0.0
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / math.sqrt(ca * cb)

def beta(a, b):
    n = len(a); ma, mb = sum(a) / n, sum(b) / n
    var = sum((x - mb) ** 2 for x in b)
    return (sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / var) if var else 0.0


class Seri:
    """Tek bir fonun tarih->fiyat serisi."""

    def __init__(self, kod, rows, ad=None):
        self.kod = kod
        self.ad = ad or kod
        # Sifir/negatif fiyat ayiklaniyor: TEFAS bazi fonlarin ilk gununu
        # 0 donuyor ve tek bir sifir tum getiri zincirini bozar. tefas.py
        # de ayikliyor; burada ikinci savunma hatti.
        self.px = {d: v for d, v in dict(rows).items() if v and v > 0}
        self.tarihler = sorted(self.px)

    def dilim(self, d0=None, d1=None):
        ds = [d for d in self.tarihler
              if (d0 is None or d >= d0) and (d1 is None or d <= d1)]
        return ds, [self.px[d] for d in ds]

    @property
    def bas(self): return self.tarihler[0]
    @property
    def bit(self): return self.tarihler[-1]


def hizala(seriler, d0=None, d1=None):
    """Ortak islem gunlerinde hizalanmis gunluk getiriler -> (tarihler, {kod: [r]})"""
    ortak = set(seriler[0].tarihler)
    for s in seriler[1:]:
        ortak &= set(s.tarihler)
    ds = sorted(d for d in ortak
                if (d0 is None or d >= d0) and (d1 is None or d <= d1))
    return ds, {s.kod: getiriler([s.px[d] for d in ds]) for s in seriler}


def maks_dusus(ds, v):
    """(dusus, zirve_tarihi, dip_tarihi, toparlanma_tarihi)"""
    zirve, zirve_t = v[0], ds[0]
    mdd, dip_t, bas_t, topar = 0.0, ds[0], ds[0], None
    for d, x in zip(ds, v):
        if x > zirve:
            zirve, zirve_t = x, d
        dd = x / zirve - 1
        if dd < mdd:
            mdd, dip_t, bas_t = dd, d, zirve_t
    tepe = max(x for d, x in zip(ds, v) if d <= dip_t)
    for d, x in zip(ds, v):
        if d > dip_t and x >= tepe:
            topar = d
            break
    return mdd, bas_t, dip_t, topar


def dusus_egrisi(ds, v):
    zirve = v[0]; out = []
    for d, x in zip(ds, v):
        zirve = max(zirve, x)
        out.append((d, x / zirve - 1))
    return out


def su_alti(ds, v):
    zirve = v[0]; toplam = 0; kesintisiz = 0; en_uzun = 0
    for x in v:
        if x >= zirve:
            zirve, kesintisiz = x, 0
        else:
            toplam += 1; kesintisiz += 1
            en_uzun = max(en_uzun, kesintisiz)
    return {'gun': toplam, 'oran': toplam / len(ds), 'en_uzun_gun': en_uzun}


def ozet(seri, risksiz, d0=None, d1=None):
    """Bir fonun bir pencere icin tam metrik seti."""
    ds, v = seri.dilim(d0, d1)
    if len(v) < 20:
        return None
    y = yillar(ds[0], ds[-1])
    toplam = v[-1] / v[0] - 1
    rs = getiriler(v)
    s = std(rs)
    _, ar = hizala([seri, risksiz], d0, d1)
    ex = [ar[seri.kod][i] - ar[risksiz.kod][i] for i in range(len(ar[seri.kod]))]
    mex, sex = sum(ex) / len(ex), std(ex)
    asagi = [x for x in ex if x < 0]
    dsd = (math.sqrt(sum(x * x for x in asagi) / len(ex)) * math.sqrt(ISLEM_GUNU)) if asagi else 0.0
    mdd, zirve_t, dip_t, topar = maks_dusus(ds, v)
    var95 = yuzdelik(rs, 0.05)
    kuyruk = [x for x in rs if x <= var95]
    rds, rv = risksiz.dilim(d0, d1)
    rf_cagr = (rv[-1] / rv[0]) ** (1 / yillar(rds[0], rds[-1])) - 1
    cagr = (1 + toplam) ** (1 / y) - 1
    return {
        'kod': seri.kod, 'ad': seri.ad, 'bas': ds[0], 'bit': ds[-1], 'gun': len(ds), 'yil': y,
        'toplam': toplam, 'cagr': cagr, 'vol': s * math.sqrt(ISLEM_GUNU),
        'sharpe': (mex * ISLEM_GUNU) / (sex * math.sqrt(ISLEM_GUNU)) if sex else 0.0,
        'sortino': (mex * ISLEM_GUNU) / dsd if dsd else 0.0,
        'mdd': mdd, 'mdd_zirve': zirve_t, 'mdd_dip': dip_t, 'mdd_toparlanma': topar,
        'calmar': cagr / abs(mdd) if mdd else 0.0,
        'var95': var95, 'cvar95': sum(kuyruk) / len(kuyruk) if kuyruk else 0.0,
        'en_iyi': max(rs), 'en_kotu': min(rs),
        'pozitif_gun': sum(1 for r in rs if r > 0) / len(rs),
        'rf_cagr': rf_cagr, 'excess_cagr': cagr - rf_cagr,
        'su_alti': su_alti(ds, v),
    }


def yogunlasma(seri, d0=None, d1=None, nler=(5, 10, 20)):
    """En iyi N gun cikarilirsa donem getirisi ne olur?"""
    ds, v = seri.dilim(d0, d1)
    rs = getiriler(v)
    out = {'tam': bilesik(rs)}
    for n in nler:
        idx = set(sorted(range(len(rs)), key=lambda i: -rs[i])[:n])
        out[f'x{n}'] = bilesik([rs[i] for i in range(len(rs)) if i not in idx])
    return out


def yakalama(seri, endeks, d0=None, d1=None):
    """Yukselis/dusus yakalama orani: endeksin arti/eksi gunlerinde
    ortalama fon getirisi / ortalama endeks getirisi."""
    ds, ar = hizala([seri, endeks], d0, d1)
    f, m = ar[seri.kod], ar[endeks.kod]
    up = [(f[i], m[i]) for i in range(len(m)) if m[i] > 0]
    dn = [(f[i], m[i]) for i in range(len(m)) if m[i] < 0]
    if not up or not dn:
        return None
    return {'up': (sum(a for a, _ in up) / len(up)) / (sum(b for _, b in up) / len(up)),
            'down': (sum(a for a, _ in dn) / len(dn)) / (sum(b for _, b in dn) / len(dn)),
            'up_n': len(up), 'dn_n': len(dn)}


def rejim_ayir(seri, endeks, d0=None, d1=None):
    """Fonun karakteri degismis mi? Maksimum dusus dibinden once/sonra
    yakalama oranlarini ve getirileri ayri ayri hesaplar. DFI'de bu ayrim,
    tek bir ortalamanin gizledigi isaret degisimini ortaya cikardi."""
    ds, v = seri.dilim(d0, d1)
    _, _, dip, _ = maks_dusus(ds, v)
    out = {'dip': dip, 'donemler': []}
    for ad, a, b in (('once', ds[0], dip), ('sonra', dip, ds[-1])):
        y = yakalama(seri, endeks, a, b)
        fs, fv = seri.dilim(a, b); es, ev = endeks.dilim(a, b)
        out['donemler'].append({
            'ad': ad, 'bas': a, 'bit': b,
            'yakalama': y,
            'fon_getiri': fv[-1] / fv[0] - 1,
            'endeks_getiri': ev[-1] / ev[0] - 1,
        })
    return out


def kayan(seri, pencere=ISLEM_GUNU, d0=None, d1=None):
    ds, v = seri.dilim(d0, d1)
    return [(ds[i], v[i] / v[i - pencere] - 1) for i in range(pencere, len(v))]


def karisim(a, b, risksiz, d0=None, d1=None, adim=5):
    """Iki fonun gunluk yeniden dengelenen agirlik taramasi."""
    ds, ar = hizala([a, b, risksiz], d0, d1)
    n = len(ar[a.kod]); y = yillar(ds[0], ds[-1])
    out = []
    for i in range(0, 101, adim):
        w = i / 100
        r = [w * ar[a.kod][k] + (1 - w) * ar[b.kod][k] for k in range(n)]
        yol, kum = [1.0], 1.0
        for x in r:
            kum *= (1 + x); yol.append(kum)
        toplam = kum - 1
        ex = [r[k] - ar[risksiz.kod][k] for k in range(n)]
        mex, sex = sum(ex) / n, std(ex)
        zirve, mdd = yol[0], 0.0
        for x in yol:
            zirve = max(zirve, x); mdd = min(mdd, x / zirve - 1)
        out.append({'w_a': w, 'toplam': toplam,
                    'cagr': (1 + toplam) ** (1 / y) - 1,
                    'vol': std(r) * math.sqrt(ISLEM_GUNU),
                    'sharpe': (mex * ISLEM_GUNU) / (sex * math.sqrt(ISLEM_GUNU)) if sex else 0.0,
                    'mdd': mdd})
    return out


def aylik(seri, d0=None, d1=None):
    ds, v = seri.dilim(d0, d1)
    son = {}
    for d, x in zip(ds, v):
        son[d[:7]] = x
    ks = sorted(son)
    out = {ks[0]: son[ks[0]] / v[0] - 1}
    for i in range(1, len(ks)):
        out[ks[i]] = son[ks[i]] / son[ks[i - 1]] - 1
    return out


def reel(nominal, tufe):
    return (1 + nominal) / (1 + tufe) - 1


def yillik_yakalama(seri, endeks, d0=None, d1=None, min_gun=60):
    """Takvim yili bazinda yukselis/dusus yakalama. Rejim degisimini tek bir
    (ve kacinilmaz olarak keyfi) bolunme noktasina bagli kalmadan gosterir."""
    ds, _ = seri.dilim(d0, d1)
    yillar_ = sorted({d[:4] for d in ds})
    out = []
    for y in yillar_:
        a, b = f'{y}-01-01', f'{y}-12-31'
        gs = [d for d in ds if a <= d <= b]
        if len(gs) < min_gun:
            out.append({'yil': y, 'gun': len(gs), 'yakalama': None})
            continue
        yk = yakalama(seri, endeks, a, b)
        fs, fv = seri.dilim(a, b)
        es, ev = endeks.dilim(a, b)
        out.append({'yil': y, 'gun': len(gs), 'yakalama': yk,
                    'fon_getiri': fv[-1] / fv[0] - 1,
                    'endeks_getiri': ev[-1] / ev[0] - 1})
    return out


# ---------------------------------------------------------------------------
# Deger(leme) tanisi: gozlenen fiyat serisi gercekten varlik fiyatlarini mi
# yansitiyor, yoksa yumusatilmis bir degerleme surecini mi?
# ---------------------------------------------------------------------------
def otokorelasyon(rs, gecikme=1):
    """Gunluk getirilerin seri korelasyonu. Likit bir portfoyde ~0 olur.
    Kalici pozitif deger, yumusatilmis/gecikmeli fiyatlamanin imzasidir
    (Getmansky-Lo-Makarov, 2004)."""
    if len(rs) <= gecikme + 2:
        return 0.0
    return korelasyon(rs[:-gecikme], rs[gecikme:])


def tersine_yumusat(rs):
    """Geltner tersine-yumusatma: r_t = (r_gozlem_t - rho*r_gozlem_t-1)/(1-rho).
    rho pozitif degilse duzeltme uygulanmaz (yumusatma kaniti yok).
    Doner: (rho, duzeltilmis_getiriler | None, carpan)"""
    rho = otokorelasyon(rs)
    if rho <= 0:
        return rho, None, 1.0
    un = [(rs[i] - rho * rs[i - 1]) / (1 - rho) for i in range(1, len(rs))]
    return rho, un, std(un) / std(rs)


def aylik_oynaklik(seri, d0=None, d1=None, min_gun=8):
    """Ay ay yillandirilmis oynaklik + o ayki islem gunu sayisi.
    Gun sayisi, verinin seyrelip seyrelmedigini kontrol etmek icin onemli:
    oynaklik dususu bazen sadece fiyatin guncellenmemesidir."""
    ds, v = seri.dilim(d0, d1)
    aylar = {}
    for i in range(1, len(ds)):
        aylar.setdefault(ds[i][:7], []).append(v[i] / v[i - 1] - 1)
    return [{'ay': a, 'vol': std(r) * math.sqrt(ISLEM_GUNU), 'gun': len(r)}
            for a, r in sorted(aylar.items()) if len(r) >= min_gun]


def ima_edilen_vol(hisse_agirligi, endeks_vol):
    """Beyan edilen hisse agirliginin tek basina ima ettigi taban oynaklik.
    Portfoyun geri kalani risksiz ve hisse kolu endeks gibi hareket ediyorsa
    alt sinir budur; gerceklesen bunun belirgin altindaysa ya korunma (hedge)
    vardir ya da fiyatlar guncel degildir."""
    return hisse_agirligi * endeks_vol


def deger_tanisi(seri, endeks, risksiz, d0, d1, hisse_agirligi=None):
    """2026'daki oynaklik dususunu incelerken kullanilan tani seti."""
    ds, v = seri.dilim(d0, d1)
    rs = getiriler(v)
    eds, ev = endeks.dilim(d0, d1)
    evol = std(getiriler(ev)) * math.sqrt(ISLEM_GUNU)
    rho, un, carpan = tersine_yumusat(rs)
    eksiler = [(ds[i + 1], r) for i, r in enumerate(rs) if r < 0]
    seri_uz = uz = 0
    for r in rs:
        uz = uz + 1 if r > 0 else 0
        seri_uz = max(seri_uz, uz)
    o = ozet(seri, risksiz, d0, d1)
    return {
        'bas': ds[0], 'bit': ds[-1], 'gun': len(ds),
        'vol': std(rs) * math.sqrt(ISLEM_GUNU),
        'rho': rho, 'duzeltilmis_vol': (std(un) * math.sqrt(ISLEM_GUNU)) if un else None,
        'carpan': carpan,
        'pozitif_gun': sum(1 for r in rs if r > 0) / len(rs),
        'eksi_gun': len(eksiler), 'en_uzun_seri': seri_uz,
        'en_kotu_gun': min(rs), 'medyan_mutlak': sorted(abs(r) for r in rs)[len(rs) // 2],
        'eksiler': [[d, r] for d, r in eksiler],
        'mdd': o['mdd'], 'sharpe': o['sharpe'], 'sortino': o['sortino'], 'toplam': o['toplam'],
        'endeks_vol': evol,
        'ima_vol': ima_edilen_vol(hisse_agirligi, evol) if hisse_agirligi else None,
        'ort_gunluk': sum(rs) / len(rs),
        'kovalar': kovala(rs),
    }


KOVA = [('eksi', float('-inf'), 0.0), ('0 – 0,25%', 0.0, 0.0025),
        ('0,25 – 0,5%', 0.0025, 0.005), ('0,5 – 1%', 0.005, 0.01),
        ('1 – 2%', 0.01, 0.02), ('%2 üstü', 0.02, float('inf'))]


def kovala(rs):
    """Gunluk getirileri sabit kovalara dagit — dagilimin sekli, ozetin
    gizledigi seyi gosterir."""
    out = []
    for ad, lo, hi in KOVA:
        n = sum(1 for r in rs if lo <= r < hi)
        out.append({'ad': ad, 'n': n, 'oran': n / len(rs)})
    return out


# Simetrik kovalar: hisse getirilerinde negatif tarafi da cozunurlukle gormek
# icin. `KOVA` (tek tarafli) tahakkuk benzeri fon serileri icin tasarlanmisti;
# bir hissenin dagilim SEKLINI gormek icin iki taraf da ayrilmali.
KOVA_SIM = [('<−2', float('-inf'), -0.02), ('−2/−1', -0.02, -0.01),
            ('−1/−½', -0.01, -0.005), ('−½/0', -0.005, 0.0),
            ('0/½', 0.0, 0.005), ('½/1', 0.005, 0.01),
            ('1/2', 0.01, 0.02), ('>2', 0.02, float('inf'))]


def beta_korelasyon(a, b, d0=None, d1=None):
    """a serisinin b'ye gore betasi ve korelasyonu (gunluk getiriler).

    "Bu fon su fonu/endeksi mi tutuyor?" sorusunun olculebilir hali.
    Dusuk korelasyon soruyu kapatir: ayni gunlerde ayni yone gitmiyorlar.
    """
    _, r_ = hizala([a, b], d0, d1)   # hizala zaten getiri donduruyor, {kod: [r]}
    ra, rb = r_[a.kod], r_[b.kod]
    n = len(ra)
    if n < 20:
        return None
    ma, mb = sum(ra) / n, sum(rb) / n
    kov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n)) / n
    va_ = sum((x - ma) ** 2 for x in ra) / n
    vb_ = sum((x - mb) ** 2 for x in rb) / n
    if va_ <= 0 or vb_ <= 0:
        return None
    r = kov / math.sqrt(va_ * vb_)
    return {'n': n, 'beta': kov / vb_, 'r': r, 'r2': r * r}


def kovala_simetrik(rs):
    """Gunluk getirileri simetrik kovalara dagit -> [{ad, n, oran}]"""
    return [{'ad': ad, 'n': sum(1 for r in rs if lo <= r < hi),
             'oran': sum(1 for r in rs if lo <= r < hi) / len(rs)}
            for ad, lo, hi in KOVA_SIM]
