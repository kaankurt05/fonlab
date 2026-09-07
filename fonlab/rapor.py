# -*- coding: utf-8 -*-
"""Metrikleri hesaplayip rapor veri paketini ve HTML'i uretir."""
import json, os, re
from . import tefas, metrik, hisse, kurucu, kabuk
from .yapilandirma import AYAR, tum_kodlar

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)



def _kurucu_yayilimi(yol=None, asgari_fon=5):
    """tarama.json -> kurucu basina getiri yayilimi.

    Yuzdelik kullaniliyor (uc degerlerden az etkilensin): %90 - %10.
    Bolunme isaretli fonlar disari atilmiyor, *duzeltilmis* getirileri
    kullaniliyor (tarayici da ayni sekilde hesapliyor). Atmak kaybeden
    fonlari da eledigi icin dagilimi yapay olarak daraltiyordu.
    """
    yol = yol or os.path.join(KOK, 'tarama.json')
    if not os.path.exists(yol):
        return None
    with open(yol, encoding='utf-8') as f:
        t = json.load(f)
    gruplar = {}
    for x in t['fonlar']:
        ev = x['ad'].split(' PORTFÖY')[0].strip()
        gruplar.setdefault(ev, []).append(x)

    def yuzdelik(dizi, p):
        i = p * (len(dizi) - 1)
        alt = int(i)
        return dizi[alt] + (dizi[min(alt + 1, len(dizi) - 1)] - dizi[alt]) * (i - alt)

    out = []
    for ev, fs in gruplar.items():
        if len(fs) < asgari_fon:
            continue
        g = sorted((x.get('toplam_duz') if x.get('supheli') else x['toplam'])
                   for x in fs)
        out.append({
            'kurucu': ev, 'fon': len(fs),
            'p90': yuzdelik(g, 0.90), 'p10': yuzdelik(g, 0.10),
            'yayilim': yuzdelik(g, 0.90) - yuzdelik(g, 0.10),
            'en_iyi': g[-1], 'en_kotu': g[0],
            'dip90': sum(1 for x in g if x <= -0.90),
            'zirve100': sum(1 for x in g if x >= 1.0),
            'buyukluk': sum(x.get('buyukluk') or 0 for x in fs),
            'yatirimci': sum(x.get('yatirimci') or 0 for x in fs)})
    out.sort(key=lambda r: -r['yayilim'])
    return {'olusturma': t['olusturma'], 'asgari_fon': asgari_fon,
            'ortanca_yayilim': sorted(r['yayilim'] for r in out)[len(out) // 2] if out else None,
            'satir': out}


def serileri_yukle(ayar=AYAR, taze=False):
    seriler = {}
    for kod in tum_kodlar(ayar):
        rows = tefas.fiyat_serisi(kod, ayar['periyod'], taze=taze)
        try:
            ad = tefas.kunye(kod, taze=taze)['fonUnvan']
        except tefas.TefasHata:
            ad = kod
        seriler[kod] = metrik.Seri(kod, rows, ad)
    return seriler


def _haftalik(cift):
    """Grafikleri hafifletmek icin haftalik son gozlem + son nokta."""
    from datetime import date
    kova = {}
    for d, v in cift:
        y, m, g = map(int, d.split('-'))
        kova[date(y, m, g).isocalendar()[:2]] = (d, v)
    pts = [kova[k] for k in sorted(kova)]
    if pts[-1][0] != cift[-1][0]:
        pts.append(cift[-1])
    return [[d, v] for d, v in pts]


def paket(ayar=AYAR, taze=False):
    S = serileri_yukle(ayar, taze)
    kodlar = tum_kodlar(ayar)
    rf, ex = S[ayar['risksiz']], S[ayar['endeks']]
    bitis = max(S[k].bit for k in ayar['fonlar'])
    ortak0 = max(S[k].bas for k in ayar['fonlar'])

    from datetime import date, timedelta
    b = date(*map(int, bitis.split('-')))
    pencereler = {
        'ortak': (ortak0, bitis),
        'son1y': ((b - timedelta(days=365)).isoformat(), bitis),
        'ytd':   (f'{b.year}-01-01', bitis),
    }

    D = {'meta': {'bitis': bitis, 'ortak_baslangic': ortak0, 'tufe': ayar['tufe'],
                  'isim': {k: S[k].ad for k in kodlar}, 'kisa': ayar['kisa']},
         'stats': {}, 'buyume': {}, 'drawdown': {}, 'rolling': {}, 'rolling_ozet': {},
         'yogunlasma': {}, 'capture': {}, 'rejim': {}, 'aylik': {}, 'korelasyon': {},
         'karisim': [], 'reel_1y': {}, 'underwater': {}, 'kunye': {}}

    for ad, (d0, d1) in pencereler.items():
        D['stats'][ad] = {k: metrik.ozet(S[k], rf, d0, d1) for k in kodlar}
    D['stats']['tam'] = {k: metrik.ozet(S[k], rf) for k in kodlar}

    d0, d1 = pencereler['ortak']
    for k in kodlar:
        ds, v = S[k].dilim(d0, d1)
        taban = v[0]
        D['buyume'][k] = _haftalik([(d, x / taban * 100) for d, x in zip(ds, v)])
        D['drawdown'][k] = _haftalik(metrik.dusus_egrisi(ds, v))
        ky = metrik.kayan(S[k], d0=d0, d1=d1)
        if ky:
            D['rolling'][k] = _haftalik(ky)
            vals = [x for _, x in ky]
            D['rolling_ozet'][k] = {'min': min(vals), 'med': sorted(vals)[len(vals) // 2],
                                    'max': max(vals),
                                    'neg': sum(1 for x in vals if x < 0) / len(vals)}
        D['yogunlasma'][k] = metrik.yogunlasma(S[k], d0, d1)
        D['underwater'][k] = D['stats']['ortak'][k]['su_alti']
        s1 = D['stats']['son1y'][k]
        D['reel_1y'][k] = {'nominal': s1['toplam'], 'reel': metrik.reel(s1['toplam'], ayar['tufe'])}

    import math
    D['yillik'] = {}
    for k in ayar['fonlar']:
        y = metrik.yakalama(S[k], ex, d0, d1)
        if y:
            D['capture'][k] = y
        D['rejim'][k] = metrik.rejim_ayir(S[k], ex, d0, d1)
        D['aylik'][k] = metrik.aylik(S[k], d0, d1)
        # takvim yili bazinda yakalama + oynaklik + korelasyon
        satirlar = []
        for r in metrik.yillik_yakalama(S[k], ex, d0, d1):
            if not r['yakalama']:
                continue
            a, b = max(f"{r['yil']}-01-01", d0), min(f"{r['yil']}-12-31", d1)
            _, ar_y = metrik.hizala([S[q] for q in ayar['fonlar']] + [ex], a, b)
            satirlar.append({
                'yil': r['yil'], 'gun': r['gun'],
                'up': r['yakalama']['up'], 'down': r['yakalama']['down'],
                'fon': r['fon_getiri'], 'endeks': r['endeks_getiri'],
                'vol': metrik.std(ar_y[k]) * math.sqrt(metrik.ISLEM_GUNU),
                'kor_endeks': metrik.korelasyon(ar_y[k], ar_y[ayar['endeks']]),
                'kor_diger': metrik.korelasyon(
                    ar_y[k], ar_y[[q for q in ayar['fonlar'] if q != k][0]]),
            })
        D['yillik'][k] = satirlar
    D['yillik_endeks'] = [
        {'yil': r['yil'], 'getiri': r['endeks_getiri'],
         'vol': None} for r in metrik.yillik_yakalama(S[ayar['fonlar'][0]], ex, d0, d1)
        if r['yakalama']]

    _, ar = metrik.hizala([S[k] for k in kodlar], d0, d1)
    D['korelasyon']['ortak'] = {
        'matris': {a: {b2: metrik.korelasyon(ar[a], ar[b2]) for b2 in kodlar} for a in kodlar},
        'beta_endeks': {a: metrik.beta(ar[a], ar[ayar['endeks']]) for a in kodlar}}

    # ---- 2026 oynaklik dususu tanisi ----
    son_yil = bitis[:4]
    D['tani'] = {'yil': son_yil, 'fonlar': {}, 'kiyas': {}}
    ty0, ty1 = f'{son_yil}-01-01', bitis
    for k in ayar['fonlar']:
        hw = None
        for ad, oran in ayar['dagilim'].get(k, []):
            if ad == 'Hisse Senedi':
                hw = oran / 100
        D['tani']['fonlar'][k] = metrik.deger_tanisi(S[k], ex, rf, ty0, ty1, hw)
        D['tani']['fonlar'][k]['hisse_agirligi'] = hw
    # endeksin kendisi de ayni taniyi gecsin: kiyas sutunu olsun
    D['tani']['fonlar'][ayar['endeks']] = metrik.deger_tanisi(
        S[ayar['endeks']], S[ayar['endeks']], rf, ty0, ty1, 1.0)
    D['tani']['fonlar'][ayar['endeks']]['hisse_agirligi'] = 1.0
    for k in [ayar['endeks']] + ayar['ekstra'] + [ayar['risksiz']]:
        ds_, v_ = S[k].dilim(ty0, ty1)
        rs_ = metrik.getiriler(v_)
        D['tani']['kiyas'][k] = {'vol': metrik.std(rs_) * math.sqrt(metrik.ISLEM_GUNU),
                                 'toplam': v_[-1] / v_[0] - 1,
                                 'rho': metrik.otokorelasyon(rs_)}
    # fonun eksi gunlerinde endeks ne yapmis?
    eds, ev = S[ayar['endeks']].dilim(ty0, ty1)
    endeks_gunluk = dict(zip(eds[1:], metrik.getiriler(ev)))
    for k in ayar['fonlar']:
        D['tani']['fonlar'][k]['eksiler'] = [
            [d, r, endeks_gunluk.get(d)] for d, r in D['tani']['fonlar'][k]['eksiler']]
    D['aylik_vol'] = {k: metrik.aylik_oynaklik(S[k], d0, d1)
                      for k in ayar['fonlar'] + [ayar['endeks']]}
    # ucuncu vaka tablosuyla ayni pencere (son takvim yili)
    D['son_yil_kiyas'] = {}
    for k in ayar['fonlar']:
        yk = metrik.yakalama(S[k], ex, f'{son_yil}-01-01', bitis)
        D['son_yil_kiyas'][k] = {
            'yakalama': yk,
            'yogunlasma': metrik.yogunlasma(S[k], f'{son_yil}-01-01', bitis)}
    D['yillik_vol'] = {}
    for k in tum_kodlar(ayar):
        satir = {}
        for y in sorted({d[:4] for d in S[k].tarihler if d >= d0}):
            a_, b_ = max(f'{y}-01-01', d0), min(f'{y}-12-31', d1)
            ds_, v_ = S[k].dilim(a_, b_)
            if len(ds_) < 60:
                continue
            satir[y] = metrik.std(metrik.getiriler(v_)) * math.sqrt(metrik.ISLEM_GUNU)
        D['yillik_vol'][k] = satir

    # ---- fonun tuttugu hisselerin kendi fiyat serileri ----
    # Fonun oynakligi, tuttugu hisselerin oynakligiyla karsilastirilmadan
    # yorumlanamaz: DFI'de "yumusak" gorunen seri aslinda IEYHO'nun serisi.
    D['hisse'] = {'seri': {}, 'dd': {}, 'ist': {}}
    hy0, hy1 = ty0, ty1
    kaynaklar = list(ayar.get('hisseler', []))
    hbas = ayar.get('hisse_bas', hy0)
    D['hisse']['yillik'] = {}
    D['hisse']['aylik_vol'] = {}
    D['hisse']['dagilim_yil'] = {}
    for kod in kaynaklar:
        try:
            tum = hisse.fiyat_serisi(kod, hbas, hy1)
        except Exception as e:                      # hisse verisi rapor icin kritik degil
            print(f'  uyari: {kod} fiyat serisi alinamadi ({e})')
            continue
        # cok yilli kirilim: hisse hep boyle miydi, yoksa bir noktada mi degisti?
        seri_tum = metrik.Seri(kod, tum)
        D['hisse']['yillik'][kod] = []
        D['hisse']['dagilim_yil'][kod] = {}
        for yil in sorted({d[:4] for d, _ in tum}):
            ds_y, v_y = seri_tum.dilim(f'{yil}-01-01', f'{yil}-12-31')
            if len(ds_y) < 30:
                continue
            rs_y = metrik.getiriler(v_y)
            mdd_y, _, _, _ = metrik.maks_dusus(ds_y, v_y)
            D['hisse']['yillik'][kod].append({
                'yil': yil, 'gun': len(ds_y), 'toplam': v_y[-1] / v_y[0] - 1,
                'vol': metrik.std(rs_y) * math.sqrt(metrik.ISLEM_GUNU),
                'rho': metrik.otokorelasyon(rs_y),
                'eksi_gun': sum(1 for r in rs_y if r < 0),
                'mdd': mdd_y, 'en_kotu': min(rs_y),
                'ort_gunluk': sum(rs_y) / len(rs_y)})
            D['hisse']['dagilim_yil'][kod][yil] = metrik.kovala_simetrik(rs_y)
        D['hisse']['aylik_vol'][kod] = metrik.aylik_oynaklik(seri_tum, '2025-01-01', hy1)
        rows = [(d, p_) for d, p_ in tum if hy0 <= d <= hy1]
        ds_ = [d for d, _ in rows]; v_ = [x for _, x in rows]
        taban = v_[0]
        D['hisse']['seri'][kod] = [[d, round(x / taban * 100, 3)] for d, x in rows]
        D['hisse']['dd'][kod] = [[d, round(x, 5)] for d, x in metrik.dusus_egrisi(ds_, v_)]
        rs_ = metrik.getiriler(v_)
        mdd_, _, _, _ = metrik.maks_dusus(ds_, v_)
        D['hisse']['ist'][kod] = {
            'ad': ayar.get('hisse_ad', {}).get(kod, kod), 'gun': len(ds_),
            'toplam': v_[-1] / v_[0] - 1,
            'vol': metrik.std(rs_) * math.sqrt(metrik.ISLEM_GUNU),
            'rho': metrik.otokorelasyon(rs_), 'eksi_gun': sum(1 for r in rs_ if r < 0),
            'en_kotu': min(rs_), 'mdd': mdd_,
            'ort_gunluk': sum(rs_) / len(rs_),
            'medyan_mutlak': sorted(abs(x) for x in rs_)[len(rs_) // 2],
            'dagilim': metrik.kovala_simetrik(rs_)}
    # fonlar ve endeks de ayni pencerede 100'e endekslensin (kiyas icin)
    for kod in ayar['fonlar'] + [ayar['endeks']]:
        ds_, v_ = S[kod].dilim(hy0, hy1)
        taban = v_[0]
        D['hisse']['seri'][kod] = [[d, round(x / taban * 100, 3)] for d, x in zip(ds_, v_)]
        D['hisse']['dd'][kod] = [[d, round(x, 5)] for d, x in metrik.dusus_egrisi(ds_, v_)]
        rs_ = metrik.getiriler(v_)
        mdd_, _, _, _ = metrik.maks_dusus(ds_, v_)
        D['hisse']['ist'][kod] = {
            'ad': ayar['kisa'].get(kod, kod), 'gun': len(ds_), 'toplam': v_[-1] / v_[0] - 1,
            'vol': metrik.std(rs_) * math.sqrt(metrik.ISLEM_GUNU),
            'rho': metrik.otokorelasyon(rs_), 'eksi_gun': sum(1 for r in rs_ if r < 0),
            'en_kotu': min(rs_), 'mdd': mdd_,
            'ort_gunluk': sum(rs_) / len(rs_),
            'medyan_mutlak': sorted(abs(x) for x in rs_)[len(rs_) // 2],
            'dagilim': metrik.kovala_simetrik(rs_)}

    # ---- ek vakalar: ayni sinyali veren, mekanizmasi farkli fonlar ----
    # Ana karsilastirmaya sokulmuyorlar (karisim/korelasyon tablolarini bozmasin),
    # kendi bloklarinda tasiniyorlar.
    D['vakalar'] = {}
    for vk, vc in (ayar.get('vakalar') or {}).items():
        try:
            u = metrik.Seri(vk, tefas.fiyat_serisi(vk, ayar['periyod']))
            uk = tefas.kunye(vk)
            # Pay bolunmesi olan fonlarda seri bolunme gununden baslatilir;
            # yoksa tek gunluk yapay -%84 tum gecmis metrikleri bozuyor.
            kes = vc.get('bas') or u.bas
            blok = {'kod': vk, 'unvan': uk['fonUnvan'], 'kurucu': vc.get('kurucu', ''),
                    'buyukluk': uk['portBuyukluk'], 'yatirimci': uk['yatirimciSayi'],
                    'derece': uk['kategoriDerece'], 'kat_adet': uk['kategoriFonSay'],
                    'bas': kes, 'bit': u.bit, 'dagilim': vc.get('dagilim', []),
                    'bolunme': vc.get('bolunme'),
                    'tam': metrik.ozet(u, rf, kes, bitis),
                    'son': metrik.ozet(u, rf, f'{son_yil}-01-01', bitis),
                    'yakalama': metrik.yakalama(u, ex, f'{son_yil}-01-01', bitis),
                    'yogunlasma': metrik.yogunlasma(u, f'{son_yil}-01-01', bitis),
                    'tani': metrik.deger_tanisi(u, ex, rf, f'{son_yil}-01-01', bitis),
                    'aylik_vol': metrik.aylik_oynaklik(u, '2025-01-01', bitis),
                    'yillik': []}
            for yil in sorted({d[:4] for d in u.tarihler if d >= kes}):
                ds_y, v_y = u.dilim(max(f'{yil}-01-01', kes), f'{yil}-12-31')
                if len(ds_y) < 30:
                    continue
                rs_y = metrik.getiriler(v_y)
                mdd_y, _, _, _ = metrik.maks_dusus(ds_y, v_y)
                blok['yillik'].append({
                    'yil': yil, 'gun': len(ds_y), 'toplam': v_y[-1] / v_y[0] - 1,
                    'vol': metrik.std(rs_y) * math.sqrt(metrik.ISLEM_GUNU),
                    'rho': metrik.otokorelasyon(rs_y),
                    'eksi_gun': sum(1 for r in rs_y if r < 0), 'mdd': mdd_y,
                    'en_kotu': min(rs_y)})
            D['vakalar'][vk] = blok
            D['aylik_vol'][vk] = blok['aylik_vol']
        except Exception as e:
            print(f'  uyari: {vk} vakasi olusturulamadi ({e})')

    # ---- kurucu bazinda getiri yayilimi ----
    # PHN/PKZ'nin kategori sirasi ("2/1333") tek basina okununca bir basari
    # belgesi gibi duruyor. Ayni kurucunun diger fonlariyla birlikte okununca
    # baska bir sey soyluyor. Veri tarama.json'dan geliyor (tum evren).
    D['kurucu'] = _kurucu_yayilimi()

    # ---- secili kurucularin tum fon ailesi ----
    D['ev'] = {}
    for ev in (ayar.get('kurucular') or []):
        try:
            r = kurucu.incele(ev, risksiz=ayar['risksiz'], endeks=ayar['endeks'],
                              periyod=ayar['periyod'])
            if r:
                D['ev'][ev] = r
                print(f"  {ev}: {r['fon']} fon  medyan {r['medyan']:+.0%}  "
                      f"nakidi yenen {r['nakit_yenen']}/{r['fon']}  "
                      f"agirlik bugun {r['agirlik_bugun']:+.0%} / baslangic {r['agirlik_baslangic']:+.0%}")
        except Exception as e:
            print(f'  uyari: {ev} kurucusu incelenemedi ({e})')

    # ---- son gunler: es zamanli cokusun kanitini tasiyan pencere ----
    # PHN ve PKZ 4 gunde ~%40 kaybederken BIST 100 ve diger vakalar
    # neredeyse hic oynamadi. Aralik sabit degil: son 10 islem gunu.
    ilgi = [k for k in ['PKZ', 'PHN', 'PBE', 'TMV', 'TLY', 'DFI', ayar['endeks']]
            if k in S or k in D.get('vakalar', {})]
    kaynak = {}
    for k in ilgi:
        kaynak[k] = S[k] if k in S else metrik.Seri(k, tefas.fiyat_serisi(k, ayar['periyod']))
    ortak_g = sorted(set.intersection(*[set(x.tarihler) for x in kaynak.values()]))[-11:]
    D['son_gunler'] = {
        'gunler': ortak_g[1:],
        'seri': {k: [kaynak[k].px[ortak_g[i + 1]] / kaynak[k].px[ortak_g[i]] - 1
                     for i in range(len(ortak_g) - 1)] for k in ilgi},
        'toplam': {k: kaynak[k].px[ortak_g[-1]] / kaynak[k].px[ortak_g[0]] - 1 for k in ilgi},
        'dort': {k: kaynak[k].px[ortak_g[-1]] / kaynak[k].px[ortak_g[-5]] - 1 for k in ilgi}}

    # ---- PHN ~ PKZ bagimsizlik testi ----
    # "PHN kardes fonlari tutuyor olabilir mi?" sorusunun olcumu.
    # Cevap hayir: gunluk getiriler neredeyse iliskisiz.
    D['ikili'] = {}
    for a2, b3 in [('PHN', 'PKZ'), ('PHN', ayar['endeks']), ('PKZ', ayar['endeks']),
                   ('PBE', 'PKZ')]:
        try:
            D['ikili'][f'{a2}~{b3}'] = metrik.beta_korelasyon(
                kaynak[a2], kaynak[b3], f'{son_yil}-01-01', bitis)
        except Exception:
            pass

    a, b2 = ayar['fonlar'][0], ayar['fonlar'][1]
    D['karisim'] = [{'w_tly': m['w_a'], **{q: m[q] for q in ('cagr', 'vol', 'sharpe', 'mdd', 'toplam')}}
                    for m in metrik.karisim(S[a], S[b2], rf, d0, d1)]

    for k in ayar['fonlar']:
        ky = tefas.kunye(k)
        D['kunye'][k] = {
            'unvan': ky['fonUnvan'], 'kurucu': ayar['kurucu'].get(k, ''),
            'buyukluk': ky['portBuyukluk'], 'yatirimci': ky['yatirimciSayi'],
            'pazar_payi': ky['pazarPayi'], 'derece': ky['kategoriDerece'],
            'kat_adet': ky['kategoriFonSay'], 'sonfiyat': ky['sonFiyat'],
            'baslangic': S[k].bas, 'dagilim': ayar['dagilim'].get(k, [])}
    return D


def yaz(cikti_json=None, sablon=None, cikti_html=None, ayar=AYAR, taze=False):
    D = paket(ayar, taze)
    cikti_json = cikti_json or os.path.join(KOK, 'rapor_veri.json')
    with open(cikti_json, 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=True, separators=(',', ':'), default=float)
    yollar = [cikti_json]
    sablon = sablon or os.path.join(KOK, 'build', 'sablon2.html')
    if os.path.exists(sablon):
        with open(sablon, encoding='utf-8') as f:
            t = f.read()
        t = t.replace('/*__ORTAK_CSS__*/', kabuk.ORTAK_CSS)
        t = t.replace('<!--__NAV__-->',
                      kabuk.nav('rapor', yapiskan=False, atla='#icerik'))
        if '/*__DATA__*/' not in t:
            raise RuntimeError(f'{sablon} icinde /*__DATA__*/ yer tutucusu yok')
        with open(cikti_json, encoding='utf-8') as f:
            veri = f.read()
        cikti_html = cikti_html or os.path.join(KOK, 'build', 'tly-dfi-fon-analizi.html')
        with open(cikti_html, 'w', encoding='utf-8') as f:
            f.write(ascii_kilitle(t.replace('/*__DATA__*/', veri)))
        yollar.append(cikti_html)
    return D, yollar


# ---------------------------------------------------------------------------
# ASCII kilidi: belgeyi tamamen ASCII yaparak karakter kodlamasindan bagimsiz
# kilar. Bazi goruntuleyiciler HTML'i latin-1 varsayip UTF-8 baytlarini bozuk
# gosteriyor ("Turkiye" -> "TÃ¼rkiye"). Kacirilmis belge her durumda dogru okunur.
# Bolgeye gore farkli sozdizimi gerekir: HTML varliklari <script>/<style> icinde
# cozulmez, bu yuzden ucu ayri ele alinir.
# ---------------------------------------------------------------------------
_BOLGE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.S | re.I)


def _kacir(metin, bicim):
    return ''.join(c if ord(c) < 128 else bicim(ord(c)) for c in metin)


def ozet_yaz(sablon=None, cikti=None):
    """Ozet sayfasini kabukla birlikte uret.

    Ozet elle yazilmis bir geriye bakis yazisi; icindeki rakamlar 04.09.2026
    kesimine ait ve bilerek sabit. Sablona donusturulmesinin sebebi ortak
    kabugu (gezinme, mobil tablo duzeni) tek yerden almak.
    """
    from . import kabuk
    sablon = sablon or os.path.join(KOK, 'build', 'ozet_sablon.html')
    cikti = cikti or os.path.join(KOK, 'build', 'ozet.html')
    with open(sablon, encoding='utf-8') as f:
        t = f.read()
    t = t.replace('/*__ORTAK_CSS__*/', kabuk.ORTAK_CSS)
    t = t.replace('<!--__NAV__-->', kabuk.nav('ozet'))
    with open(cikti, 'w', encoding='ascii') as f:
        f.write(ascii_kilitle(t))
    return cikti


def ascii_kilitle(html):
    """HTML -> saf ASCII. Metin ayni, baytlar 7-bit."""
    parcalar, son = [], 0
    for m in _BOLGE.finditer(html):
        parcalar.append(('html', html[son:m.start()]))
        parcalar.append((m.group(1).lower(), m.group(0)))
        son = m.end()
    parcalar.append(('html', html[son:]))
    out = []
    for tip, p in parcalar:
        if tip == 'html':                       # &#NNN;  — HTML ayristiricisi cozer
            out.append(_kacir(p, lambda o: '&#%d;' % o))
        elif tip == 'script':                   # \uXXXX — JS dizge/yorum icinde gecerli
            out.append(_kacir(p, lambda o: '\\u%04x' % o))
        else:                                   # \XXXX  — CSS kacirmasi (sondaki bosluk sart)
            out.append(_kacir(p, lambda o: '\\%04x ' % o))
    return ''.join(out)
