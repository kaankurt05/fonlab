# -*- coding: utf-8 -*-
"""fonlab komut satiri.

  python3 -m fonlab kunye TLY DFI        fon bilgisi
  python3 -m fonlab ara "PARA PİYASASI"  fon kodu ara
  python3 -m fonlab ozet TLY DFI         hizli risk/getiri tablosu
  python3 -m fonlab rapor [--taze]       veri paketi + HTML uret
  python3 -m fonlab tara                 tum serbest fon evrenini tara
  python3 -m fonlab tarayici             tarama sonucundan etkilesimli sayfa uret
  python3 -m fonlab tahmin               dunku tahminleri puanla, yarininkini yaz
  python3 -m fonlab ozet                 proje ozeti sayfasini uret
  python3 -m fonlab renk "#a,#b" --mode light   palet dogrula
  python3 -m fonlab belge rapor.pdf Mevduat      KAP/PDR pdf'inden metin cikar
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fonlab import tefas, metrik, rapor          # noqa: E402
from fonlab.yapilandirma import AYAR             # noqa: E402


def yp(x, d=1):
    """Yuzde bicimle, Turkce ayirac (binlik nokta, ondalik virgul)."""
    s = format(x * 100, '+,.%df' % d)
    return s.replace(',', '\x00').replace('.', ',').replace('\x00', '.') + '%'


def cmd_kunye(args):
    for kod in args or AYAR['fonlar']:
        k = tefas.kunye(kod)
        print(f"{kod}  {k['fonUnvan']}")
        print(f"   büyüklük ₺{k['portBuyukluk']/1e9:,.1f} mlr | yatırımcı {k['yatirimciSayi']:,} "
              f"| pazar payı %{k['pazarPayi']} | kategori {k['kategoriDerece']}/{k['kategoriFonSay']}")


def cmd_ara(args):
    if not args:
        print('kullanım: python3 -m fonlab ara "DESEN"'); return 2
    for kod, unvan in tefas.ara(args[0]):
        print(f'  {kod}  {unvan[:78]}')


def cmd_ozet(args):
    kodlar = args or AYAR['fonlar']
    rf = metrik.Seri(AYAR['risksiz'], tefas.fiyat_serisi(AYAR['risksiz']))
    print(f"{'':5}{'Toplam':>13}{'CAGR':>11}{'Vol':>9}{'Sharpe':>8}{'MaxDD':>9}{'Calmar':>8}")
    for kod in kodlar:
        s = metrik.ozet(metrik.Seri(kod, tefas.fiyat_serisi(kod)), rf)
        print(f"{kod:5}{yp(s['toplam'],0):>13}{yp(s['cagr'],1):>11}{yp(s['vol'],1):>9}"
              f"{s['sharpe']:>8.2f}{yp(s['mdd'],1):>9}{s['calmar']:>8.2f}")


def cmd_rapor(args):
    taze = '--taze' in args
    D, yollar = rapor.yaz(taze=taze)
    print('üretildi:')
    for y in yollar:
        print(f'  {y}  ({os.path.getsize(y):,} bayt)')
    o = D['stats']['ortak']
    print(f"\nortak dönem {D['meta']['ortak_baslangic']} → {D['meta']['bitis']}")
    for k in AYAR['fonlar']:
        print(f"  {k}: toplam {yp(o[k]['toplam'],0)}  CAGR {yp(o[k]['cagr'],1)}  "
              f"vol {yp(o[k]['vol'],1)}  Sharpe {o[k]['sharpe']:.2f}  MaxDD {yp(o[k]['mdd'],1)}")
        r = D['rejim'][k]
        for d in r['donemler']:
            y = d['yakalama']
            print(f"     rejim {d['ad']:>5} ({d['bas']}→{d['bit']}): "
                  f"yük.yak {yp(y['up'],0)} düş.yak {yp(y['down'],0)} "
                  f"fon {yp(d['fon_getiri'],1)} endeks {yp(d['endeks_getiri'],1)}")


def cmd_tara(args):
    """Serbest fon evrenini tara: python3 -m fonlab tara [--limit N]"""
    from fonlab import tara as T
    limit = None
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])
    v = T.tara(limit=limit)
    yol = T.yaz(v)
    print(f"\n{v['islenen']}/{v['evren']} fon işlendi, {v['atlanan']} atlandı, "
          f"{len(v['hatalar'])} hata -> {yol}")


def cmd_tarayici(args):
    """tarama.json -> etkilesimli tarayici sayfasi"""
    from fonlab import tarayici as TY
    yol, boyut = TY.yaz()
    import os
    print(f'üretildi: {yol} ({os.path.getsize(yol):,} bayt, veri {boyut:,} bayt)')


def cmd_belge(args):
    """PDF'ten metin cikar: python3 -m fonlab belge rapor.pdf [anahtar]"""
    from fonlab import belge
    if not args:
        print('kullanım: python3 -m fonlab belge <pdf> [aranacak kelime]'); return 2
    import re
    desen = re.compile(args[1], re.I) if len(args) > 1 else None
    for s2 in belge.satirlar(args[0]):
        if desen is None or desen.search(s2):
            print(' ', s2[:300])


def cmd_ozet(args):
    from fonlab import rapor
    print('üretildi:', rapor.ozet_yaz())
    return 0


def cmd_tahmin(args):
    """Bekleyen tahminleri puanla, ertesi gun icin yenilerini yaz.

    Gunluk calisir. Seriler onbellekten okunur; tara zaten cekmisse ek
    istek atilmaz. Izleme listesi = raporda incelenen fonlar + en yuksek
    arti gun oranina sahip oynak fonlar (ayrintili kayit yalnizca onlar icin).
    """
    import json, os
    from fonlab import tahmin, tefas, metrik
    from fonlab.tarayici import incelenen
    from fonlab.yapilandirma import AYAR

    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yol = os.path.join(kok, 'tarama.json')
    if not os.path.exists(yol):
        print('tarama.json yok - once "python3 -m fonlab tara" calistir')
        return 1
    with open(yol, encoding='utf-8') as f:
        t = json.load(f)

    kodlar = [x['kod'] for x in t['fonlar'] if not x.get('supheli')]
    izleme = set(incelenen()) | {
        x['kod'] for x in sorted(
            (y for y in t['fonlar'] if not y.get('supheli') and y.get('vol', 0) >= 0.15),
            key=lambda y: y.get('eksi_oran', 1))[:25]}

    seriler, hata = {}, 0
    for i, kod in enumerate(kodlar, 1):
        try:
            seriler[kod] = metrik.Seri(kod, tefas.fiyat_serisi(kod, AYAR['periyod_tara']
                                                              if 'periyod_tara' in AYAR else 12))
        except Exception:
            hata += 1
        if i % 250 == 0:
            print(f'  {i}/{len(kodlar)} seri yuklendi', flush=True)

    ozet = tahmin.puanla_ve_tahmin(kodlar, seriler, izleme=izleme)
    print(f"\nileriye donuk sicil ({hata} fon veri hatasi):")
    if ozet['adet']:
        print(f"  puanlanmis tahmin : {ozet['adet']:,}  ({ozet['fon']} fon, {ozet['gun']} gun)")
        print(f"  donem             : {ozet['ilk']} -> {ozet['son']}")
        print(f"  isabet            : {ozet['isabet']:.1%}")
        print(f"  ortalama mutlak hata: {ozet['mae']:.3%}")
    else:
        print('  henuz puanlanmis tahmin yok - ilk kosu, yarin puanlanacak')
    print(f"  bekleyen tahmin   : {ozet['bekleyen']:,}")
    return 0


def cmd_renk(args):
    from fonlab import renk
    return renk.main(['renk'] + args)


KOMUTLAR = {'kunye': cmd_kunye, 'ara': cmd_ara, 'ozet': cmd_ozet,
            'rapor': cmd_rapor, 'renk': cmd_renk, 'belge': cmd_belge, 'tara': cmd_tara, 'tarayici': cmd_tarayici,
            'tahmin': cmd_tahmin, 'ozet': cmd_ozet}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in KOMUTLAR:
        print(__doc__); sys.exit(2)
    sys.exit(KOMUTLAR[sys.argv[1]](sys.argv[2:]) or 0)
