# -*- coding: utf-8 -*-
"""fonlab olcum katmaninin testleri.

  python3 -m fonlab.test_metrik

Nicel bir projede en tehlikeli hata sessiz olanidir: yanlis sayi uretip
dogru gorunmek. Buradaki testler elle hesaplanmis degerlere ve bilinen
ozel durumlara (sabit seri, tek gun, bolunme, eksik gun) karsi kontrol eder.
Dis bagimlilik yok; unittest yeterli.
"""
import math
import unittest

from . import metrik, tahmin, kurucu, hisse_tani


def seri(kod, ciftler):
    return metrik.Seri(kod, list(ciftler))


def duz(bas, carpanlar, ilk_gun='2026-01-01'):
    """[1.0, 1.1, ...] carpanlarindan gunluk seri uret."""
    from datetime import date, timedelta
    y, a, g = map(int, ilk_gun.split('-'))
    d = date(y, a, g)
    out, v = [], bas
    for c in carpanlar:
        v *= c
        out.append((d.isoformat(), v))
        d += timedelta(days=1)
    return out


class TemelOlcumler(unittest.TestCase):
    def test_getiriler(self):
        r = metrik.getiriler([100, 110, 99])
        self.assertAlmostEqual(r[0], 0.1, places=12)
        self.assertAlmostEqual(r[1], -0.1, places=12)
        self.assertEqual(metrik.getiriler([100]), [])

    def test_bilesik(self):
        self.assertAlmostEqual(metrik.bilesik([0.1, -0.1]), -0.01, places=12)
        self.assertAlmostEqual(metrik.bilesik([]), 0.0, places=12)

    def test_std_sabit_seri_sifir(self):
        self.assertAlmostEqual(metrik.std([0.01] * 10), 0.0, places=12)

    def test_std_elle(self):
        # Ornek standart sapmasi (n-1). [1,2,3,4] -> ortalama 2.5, s^2 = 5/3
        self.assertAlmostEqual(metrik.std([1, 2, 3, 4]), math.sqrt(5 / 3), places=12)

    def test_maks_dusus_elle(self):
        ds = ['2026-01-0%d' % i for i in range(1, 6)]
        v = [100, 120, 60, 80, 130]
        mdd, zirve, dip, topar = metrik.maks_dusus(ds, v)
        self.assertAlmostEqual(mdd, -0.5, places=12)      # 120 -> 60
        self.assertEqual(zirve, ds[1])
        self.assertEqual(dip, ds[2])
        self.assertEqual(topar, ds[4])                    # 130 > 120

    def test_maks_dusus_toparlanmayan(self):
        ds = ['2026-01-0%d' % i for i in range(1, 5)]
        mdd, _, _, topar = metrik.maks_dusus(ds, [100, 200, 50, 60])
        self.assertAlmostEqual(mdd, -0.75, places=12)
        self.assertIsNone(topar)

    def test_maks_dusus_hep_yukselen(self):
        ds = ['2026-01-0%d' % i for i in range(1, 4)]
        mdd, _, _, _ = metrik.maks_dusus(ds, [100, 110, 120])
        self.assertAlmostEqual(mdd, 0.0, places=12)

    def test_otokorelasyon_mukemmel_dalgali(self):
        # +a, -a, +a, ... -> lag-1 otokorelasyon -1'e yakin
        rs = [0.01, -0.01] * 30
        self.assertLess(metrik.otokorelasyon(rs), -0.9)

    def test_otokorelasyon_sabit_seri(self):
        # varyans sifir; NaN/ZeroDivision yerine 0 donmeli
        self.assertEqual(metrik.otokorelasyon([0.01] * 20), 0.0)


class Hizalama(unittest.TestCase):
    def test_ortak_gunler(self):
        a = seri('A', [('2026-01-01', 100), ('2026-01-02', 110), ('2026-01-03', 121)])
        b = seri('B', [('2026-01-02', 50), ('2026-01-03', 55), ('2026-01-04', 60)])
        ds, r = metrik.hizala([a, b])
        self.assertEqual(ds, ['2026-01-02', '2026-01-03'])
        self.assertAlmostEqual(r['A'][0], 0.1, places=12)
        self.assertAlmostEqual(r['B'][0], 0.1, places=12)

    def test_dilim_sinirlar_dahil(self):
        s = seri('A', [('2026-01-0%d' % i, 100 + i) for i in range(1, 6)])
        ds, v = s.dilim('2026-01-02', '2026-01-04')
        self.assertEqual(ds, ['2026-01-02', '2026-01-03', '2026-01-04'])
        self.assertEqual(v, [102, 103, 104])


class Yogunlasma(unittest.TestCase):
    def test_en_iyi_gunler_cikinca_duser(self):
        # 3 buyuk gun + 20 kucuk eksi gun
        c = [1.5, 1.5, 1.5] + [0.995] * 20
        s = seri('A', duz(100, c))
        y = metrik.yogunlasma(s)
        # duz() ilk carpani da uyguladigi icin seri 150'den basliyor:
        # gorunur getiri 1,5 x 1,5 x 0,995^20 - 1
        self.assertGreater(y['tam'], 1.0)
        self.assertLess(y['x5'], y['tam'])
        self.assertLess(y['x5'], 0)          # buyuk gunler cikinca eksiye dusmeli


class BetaKorelasyon(unittest.TestCase):
    def test_ayni_seri_r_bir(self):
        s = seri('A', duz(100, [1.01, 0.99, 1.02, 0.98] * 8))
        s2 = metrik.Seri('B', [(d, v) for d, v in zip(s.tarihler, [s.px[d] for d in s.tarihler])])
        q = metrik.beta_korelasyon(s, s2)
        self.assertAlmostEqual(q['r'], 1.0, places=9)
        self.assertAlmostEqual(q['beta'], 1.0, places=9)

    def test_iki_kat_kaldiracli_beta_iki(self):
        c = [1.01, 0.99, 1.02, 0.98] * 8
        a = seri('A', duz(100, c))
        # B'nin gunluk getirisi A'nin iki kati
        c2 = [1 + (x - 1) * 2 for x in c]
        b = seri('B', duz(100, c2))
        q = metrik.beta_korelasyon(b, a)
        self.assertAlmostEqual(q['beta'], 2.0, places=6)
        self.assertAlmostEqual(q['r'], 1.0, places=6)

    def test_kisa_seri_none(self):
        a = seri('A', duz(100, [1.01] * 5))
        b = seri('B', duz(100, [1.02] * 5))
        self.assertIsNone(metrik.beta_korelasyon(a, b))


class TahminOlculeri(unittest.TestCase):
    def test_hep_arti_becerisi_tam_sifir(self):
        """'hep arti' modeli tanim geregi tam taban orani tutturur."""
        rs = [0.01] * 80 + [-0.01] * 20
        y = tahmin.yuruyen(rs, pencere=40, asgari=40)
        self.assertIsNotNone(y)
        self.assertAlmostEqual(y['model']['yukari']['beceri'], 0.0, places=12)

    def test_taban_cogunluk_sinifi(self):
        rs = [0.01] * 30 + [-0.01] * 70          # cogunluk EKSI
        y = tahmin.yuruyen(rs, pencere=50, asgari=40)
        self.assertGreaterEqual(y['taban'], 0.5)

    def test_mukemmel_ongorulebilir_seri(self):
        # dun ne olduysa bugun de o -> 'dun' modeli tam isabet
        rs = [0.01] * 100
        y = tahmin.yuruyen(rs, pencere=40, asgari=40)
        self.assertAlmostEqual(y['model']['dun']['isabet'], 1.0, places=12)

    def test_kisa_seri_none(self):
        self.assertIsNone(tahmin.yuruyen([0.01] * 10))

    def test_tahmin_et_yon(self):
        t = tahmin.tahmin_et([0.01] * 60, 'dun')
        self.assertEqual(t['yon'], 1)
        t2 = tahmin.tahmin_et([-0.01] * 60, 'dun')
        self.assertEqual(t2['yon'], -1)


class BolunmeDuzeltmesi(unittest.TestCase):
    def test_duzeltme_kaybi_buyutur(self):
        """Sahte +%900'luk bir gun ayiklandiginda gercek kayip ortaya cikar."""
        c = [0.99] * 50 + [10.0] + [0.99] * 50      # ortada 10 kat sicrama
        ds = duz(100, c)
        px = dict(ds)
        ham = px[ds[-1][0]] / px[ds[0][0]] - 1
        d, atlanan = kurucu._duzelt([d for d, _ in ds], px)
        self.assertGreater(ham, 0)          # ham getiri artida gorunuyor
        self.assertLess(d, 0)               # duzeltilmis getiri aslinda eksi
        self.assertEqual(len(atlanan), 1)

    def test_sicramasiz_seride_degismez(self):
        ds = duz(100, [1.01] * 30)
        px = dict(ds)
        ham = px[ds[-1][0]] / px[ds[0][0]] - 1
        d, atlanan = kurucu._duzelt([x for x, _ in ds], px)
        self.assertAlmostEqual(d, ham, places=9)
        self.assertEqual(atlanan, [])


class UcDurumlar(unittest.TestCase):
    def test_tek_gunluk_seri_cokmez(self):
        s = seri('A', [('2026-01-01', 100)])
        self.assertEqual(metrik.getiriler([s.px[d] for d in s.tarihler]), [])

    def test_sifir_fiyat_bolme_hatasi_vermez(self):
        # tefas ilk gunu bazen 0 doner; seri kurucu ayiklamali
        s = seri('A', [('2026-01-01', 0), ('2026-01-02', 100), ('2026-01-03', 110)])
        v = [s.px[d] for d in s.tarihler]
        self.assertNotIn(0, v)


class HisseTani(unittest.TestCase):
    """Gecikme duzeltmesi: cipa bir gun geride oldugunda beta geri kazanilmali."""

    def _seriler(self, beta=2.0, n=200):
        # m[i]: piyasanin i. gunku gercek hareketi.
        # Tohumlu rastgele: testere disi gibi duzenli bir dizi kendi icinde
        # gecikme-1 otokorelasyonu tasir ve kaydirmasiz regresyon bile
        # iliskiyi yakalar - o zaman test, olcmek istedigi seyi olcmez.
        import random
        rnd = random.Random(7)
        m = [rnd.gauss(0, 0.012) for _ in range(n)]
        from datetime import date, timedelta
        d = date(2026, 1, 1)
        tar = []
        for _ in range(n + 1):
            tar.append(d.isoformat()); d += timedelta(days=1)
        # hisse i. gun beta*m[i] yapiyor
        hp = [100.0]
        for i in range(n):
            hp.append(hp[-1] * (1 + beta * m[i]))
        # cipa ayni hareketi BIR GUN SONRA gosteriyor
        xp = [100.0, 100.0]
        for i in range(n - 1):
            xp.append(xp[-1] * (1 + m[i]))
        s = metrik.Seri('HIS', list(zip(tar, hp)))
        ex = metrik.Seri('CIPA', list(zip(tar, xp)))
        return s, ex

    def test_kaydirma_betayi_geri_kazaniyor(self):
        s, ex = self._seriler(beta=2.0)
        q = hisse_tani.piyasa_iliskisi(s, ex, s.bas, s.bit, kaydir=1)
        self.assertAlmostEqual(q['beta'], 2.0, places=6)
        self.assertGreater(q['r2'], 0.99)

    def test_kaydirmasiz_hesap_iliskiyi_kaciriyor(self):
        """Duzeltme olmadan beta sifira yakin cikiyor - sahadaki belirti buydu."""
        s, ex = self._seriler(beta=2.0)
        q = hisse_tani.piyasa_iliskisi(s, ex, s.bas, s.bit, kaydir=1)
        self.assertLess(abs(q['ham_beta']), 0.5)
        self.assertLess(q['ham_r2'], 0.1)

    def test_kisa_seri_none(self):
        s, ex = self._seriler(n=20)
        self.assertIsNone(hisse_tani.piyasa_iliskisi(s, ex, s.bas, s.bit))

    def test_kivilcim_alfabede_ve_uclar_dogru(self):
        v = [100, 120, 90, 150, 110, 130]
        t, lo, hi = hisse_tani.kivilcim(v)
        self.assertTrue(all(c in hisse_tani.KV_ALFABE for c in t))
        self.assertLess(lo, hi)
        # en dusuk nokta 0, en yuksek 63 olmali
        d = [hisse_tani.KV_ALFABE.index(c) for c in t]
        self.assertEqual(min(d), 0)
        self.assertEqual(max(d), 63)

    def test_kivilcim_kisa_seri_bos(self):
        self.assertEqual(hisse_tani.kivilcim([100, 101]), ('', None, None))

    def test_limit_gun_sayimi(self):
        from datetime import date, timedelta
        d = date(2026, 1, 1); tar = []; px = [100.0]
        for r in [0.11, 0.0, -0.10, 0.02, 0.0] * 6:      # 12 limit gunu
            px.append(px[-1] * (1 + r))
        for _ in range(len(px)):
            tar.append(d.isoformat()); d += timedelta(days=1)
        s = metrik.Seri('L', list(zip(tar, px)))
        p = hisse_tani._pencere(s, s.bas, s.bit)
        self.assertEqual(p['limit_gun'], 12)


if __name__ == '__main__':
    unittest.main(verbosity=2)
