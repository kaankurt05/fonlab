# -*- coding: utf-8 -*-
"""Serbest fon evreninin tamami uzerinde tani taramasi.

Iki fonda ise yarayan yontemi (deger_tanisi, yogunlasma, yakalama) 1.300+ fona
uygular. Amac hukum vermek degil **soru uretmek**: hangi fonlarin fiyat serisi,
tuttugu varliklarla acikladigimizdan farkli davraniyor?

  python3 -m fonlab tara            # tam evren -> tarama.json
  python3 -m fonlab tara --limit 40 # deneme
"""
import json, math, os, re, sys, time
from . import tefas, metrik, tahmin

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
CIKTI = os.path.join(KOK, 'tarama.json')
PERIYOD = 12          # TEFAS yalnizca 12 ve 60'i kabul ediyor; 12 = ~252 gun
ASGARI_GUN = 200      # bir yillik tani icin gereken en az gozlem


def serbest_fonlar(ozel_dahil=True):
    """Ada gore serbest fon evreni. TEFAS'in kategori sayisiyla (1333) ortusur."""
    ev = tefas.evren()
    out = {}
    for kod, ad in ev.items():
        if not re.search(r'\bSERBEST\b', ad, re.I):
            continue
        if 'EMEKLİLİK' in ad or 'EMEKLILIK' in ad:
            continue
        if not ozel_dahil and 'ÖZEL' in ad:
            continue
        out[kod] = ad
    return out


def _fon_metrikleri(kod, rf, gecikme):
    rows = tefas.fiyat_serisi(kod, PERIYOD)
    if len(rows) < ASGARI_GUN:
        return None
    ds = [d for d, _ in rows]; v = [p for _, p in rows]
    rs = metrik.getiriler(v)
    rho, un, carpan = metrik.tersine_yumusat(rs)
    mdd, _, _, _ = metrik.maks_dusus(ds, v)
    seri = uz = 0
    for r in rs:
        uz = uz + 1 if r > 0 else 0
        seri = max(seri, uz)
    # en iyi 10 gun cikarilirsa
    idx = set(sorted(range(len(rs)), key=lambda i: -rs[i])[:10])
    x10 = metrik.bilesik([rs[i] for i in range(len(rs)) if i not in idx])
    # risksize gore Sharpe (ortak gunlerde)
    s_obj = metrik.Seri(kod, rows)
    try:
        o = metrik.ozet(s_obj, rf, ds[0], ds[-1])
        sharpe = o['sharpe']
    except Exception:
        sharpe = None
    # --- veri kalitesi: pay bolunmesi/birlesmesi gercek getiri gibi gorunur ---
    # TEFAS fiyatlari kurumsal islemlere gore duzeltilmiyor; tek gunde %50'yi asan
    # hareket neredeyse her zaman bolunmedir, getiri degil.
    bolunme = [[ds[j + 1], round(rs[j], 4)] for j in range(len(rs)) if abs(rs[j]) > 0.50]
    supheli = bool(bolunme)
    # Duzeltilmis getiri: bolunme gunleri notrlenir. Bu duzeltme kayiplari
    # genelde *buyutuyor* - ham TEFAS serisi kaybi oldugundan kucuk gosteriyor.
    t_duz = 1.0
    for j, r in enumerate(rs):
        if abs(r) > 0.50:
            continue
        t_duz *= (1 + r)
    t_duz -= 1

    # Zirveden uzaklik: maks. dusus "en kotu ne oldu"yu, bu "bugun neredeyiz"i
    # soyluyor. Ikisi farkli sorular; tarayicida ikincisi daha kullanisli.
    zirve = max(v)
    zirveden = v[-1] / zirve - 1

    # Kivilcim: 52 haftalik nokta, ilk gun 100 olacak sekilde. Ek istek yok,
    # ayni seriden orneklenip tam sayiya yuvarlaniyor (yuk ~200 bayt/fon).
    adim = max(1, len(v) // 52)
    kivilcim = [round(v[i] / v[0] * 100) for i in range(0, len(v), adim)][:53]
    if kivilcim and kivilcim[-1] != round(v[-1] / v[0] * 100):
        kivilcim.append(round(v[-1] / v[0] * 100))

    # --- son 6 ay: rejim taramasi icin daha keskin pencere ---
    # 12 aylik pencere, yakin donemdeki sessizlesmeyi eski gurultuyle suluyor.
    # Ayni seriden dilim aliyoruz, ek istek yok.
    r6 = rs[-126:] if len(rs) >= 126 else rs
    v6 = v[-127:] if len(v) >= 127 else v
    rho6 = metrik.otokorelasyon(r6)
    d6 = {
        'toplam6': v6[-1] / v6[0] - 1,
        'vol6': metrik.std(r6) * math.sqrt(metrik.ISLEM_GUNU),
        'rho6': rho6,
        'eksi_oran6': sum(1 for r in r6 if r < 0) / len(r6),
        'gun6': len(r6),
    }

    return {
        'kod': kod, 'gun': len(ds), 'bas': ds[0], 'bit': ds[-1], 'supheli': supheli,
        'bolunme': bolunme, 'toplam_duz': t_duz, 'zirveden': zirveden, 'kivilcim': kivilcim,
        **d6,
        'toplam': v[-1] / v[0] - 1,
        'vol': metrik.std(rs) * math.sqrt(metrik.ISLEM_GUNU),
        'rho': rho,
        'duz_vol': (metrik.std(un) * math.sqrt(metrik.ISLEM_GUNU)) if un else None,
        'carpan': carpan,
        'eksi_gun': sum(1 for r in rs if r < 0),
        'eksi_oran': sum(1 for r in rs if r < 0) / len(rs),
        'en_uzun_seri': seri, 'mdd': mdd, 'sharpe': sharpe, 'x10': x10,
        'en_kotu': min(rs), 'medyan_mutlak': sorted(abs(r) for r in rs)[len(rs) // 2],
        **_tahmin_alanlari(rs),
    }


def _tahmin_alanlari(rs):
    """Ertesi gun tahmininin *durust* olculeri.

    'taban' = cogunluk sinifi orani: hicbir sey bilmeden "hep arti" diyen
    modelin isabeti. Asil bilgi bu sayinin kendisinde: BIST 100 endeks
    fonunda %52, para piyasasi benzeri fonlarda %100. Yuksek taban, fonun
    canli piyasaya gore isaretlenmedigini soyluyor.
    'beceri' = en iyi modelin isabeti eksi taban. Evren genelinde medyani
    sifir; artilar sansla ayirt edilemiyor.
    """
    y = tahmin.yuruyen(rs)
    if not y:
        return {'t_taban': None, 't_beceri': None, 't_mae_orani': None,
                't_model': None, 't_yarin': None}
    ileri = tahmin.tahmin_et(rs, y['en_iyi'])
    return {'t_taban': y['taban'], 't_beceri': y['en_iyi_beceri'],
            't_mae_orani': y['mae_orani'], 't_model': y['en_iyi'],
            't_yarin': ileri['getiri']}


def tara(limit=None, gecikme=0.08, ozel_dahil=True, ilerleme=True):
    evren = serbest_fonlar(ozel_dahil)
    kodlar = sorted(evren)[:limit] if limit else sorted(evren)
    rf = metrik.Seri('ALE', tefas.fiyat_serisi('ALE', PERIYOD))
    sonuc, hata, atlanan = [], [], 0
    t0 = time.time()
    for i, kod in enumerate(kodlar, 1):
        try:
            m = _fon_metrikleri(kod, rf, gecikme)
            if m is None:
                atlanan += 1
            else:
                m['ad'] = evren[kod]
                try:
                    k = tefas.kunye(kod)
                    m['buyukluk'] = k.get('portBuyukluk')
                    m['yatirimci'] = k.get('yatirimciSayi')
                    m['derece'] = k.get('kategoriDerece')
                except Exception:
                    m['buyukluk'] = m['yatirimci'] = m['derece'] = None
                sonuc.append(m)
        except Exception as e:
            hata.append((kod, str(e)[:70]))
        time.sleep(gecikme)
        if ilerleme and i % 50 == 0:
            gecen = time.time() - t0
            print(f'  {i}/{len(kodlar)}  ok={len(sonuc)} atlanan={atlanan} hata={len(hata)} '
                  f'{gecen:.0f}sn (kalan ~{gecen/i*(len(kodlar)-i):.0f}sn)', flush=True)
    return {'olusturma': time.strftime('%Y-%m-%d %H:%M'), 'periyod_ay': PERIYOD,
            'evren': len(kodlar), 'islenen': len(sonuc), 'atlanan': atlanan,
            'hatalar': hata[:40], 'fonlar': sonuc}


def yaz(veri, yol=CIKTI):
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=True, separators=(',', ':'), default=float)
    return yol
