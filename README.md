# fonlab

TEFAS serbest fon evreni üzerine kantitatif inceleme araçları. Saf Python 3.9+,
**dış bağımlılık yok** (pandas/numpy/requests kullanılmıyor).

Üç çıktı üretir: bir analiz raporu, 1.200+ fonluk etkileşimli bir tarayıcı ve
projenin geriye bakış özeti. Hepsi tek dosyalık, kendi kendine yeten HTML.

> **Bu bir yatırım tavsiyesi aracı değildir.** Hiçbir çıktısı alım-satım önerisi
> içermez ve hiçbir kişi/kurum hakkında usulsüzlük iddiası taşımaz. Tasarım
> ilkesi baştan beri aynı: *araç hüküm vermez, soru üretir.*

## Kurulum

Yok. Depoyu klonlayın, çalıştırın:

```bash
python3 -m fonlab kunye TLY
```

## Komutlar

| Komut | Ne yapar |
|---|---|
| `kunye TLY DFI` | Fon künyesi (büyüklük, yatırımcı, kategori sırası) |
| `ara "PARA PİYASASI"` | Ada göre fon kodu arar |
| `ozet TLY DFI` | Hızlı risk/getiri tablosu |
| `rapor [--taze]` | Veri paketi + rapor HTML'i üretir |
| `tara` | Tüm serbest fon evrenini tarar → `tarama.json` |
| `tarayici` | Taramadan etkileşimli sayfa üretir |
| `tahmin` | Bekleyen tahminleri puanlar, ertesi gün için yenilerini yazar |
| `ozet` | Proje özeti sayfasını üretir |
| `renk "#a,#b" --mode light` | Palet doğrular (renk körlüğü, kontrast, açıklık) |
| `belge rapor.pdf` | KAP/PDR PDF'inden metin çıkarır |

Günlük akış: `tara` → `tahmin` → `tarayici`. Rapor haftalık.

## Modüller

```
tefas.py      TEFAS API + disk önbelleği (6 saat)
hisse.py      İş Yatırım'dan BIST günlük kapanışları
metrik.py     Tüm ölçümler: CAGR, oynaklık, Sharpe/Sortino, maks. düşüş,
              VaR/CVaR, yakalama oranları, yoğunlaşma, oto-korelasyon,
              Getmansky-Lo-Makarov yumuşatma tespiti, Geltner düzeltmesi
tara.py       Evren taraması + veri kalitesi bayrakları
kurucu.py     Kurucu düzeyinde dağılım analizi
tahmin.py     Ertesi gün tahmini + dürüst isabet ölçümü
belge.py      PDF metin çıkarıcı (poppler'sız: FlateDecode + ToUnicode CMap)
renk.py       Palet doğrulayıcı
kabuk.py      Üç sayfanın ortak kabuğu (gezinme + mobil tablo düzeni)
rapor.py      Rapor + özet HTML üretimi
tarayici.py   Tarayıcı HTML üretimi
yapilandirma.py  Tek yapılandırma dosyası
```

## Testler

```bash
python3 -m fonlab.test_metrik
```

24 test. Ölçüm katmanı elle hesaplanmış değerlere ve uç durumlara karşı
doğrulanır: sabit seri, tek günlük seri, sıfır fiyat, toparlanmayan düşüş,
pay bölünmesi, kaldıraçlı beta, kısa seri.

Bu testler yazıldığında **iki sessiz hata** ortaya çıktı; ikisi de gerçek veride
hiç tetiklenmemişti, yani hiçbir grafiğe bakarak görülemezdi. Nicel bir işte en
tehlikeli hata türü budur: yanlış sayı üretip doğru görünmek.

## Veri kalitesi notları

Bu araç üzerinde çalışırken bulunan ve kod içinde ele alınan tuzaklar:

- **TEFAS fiyatları kurumsal işlemlere göre düzeltilmiyor.** Pay bölünmesi
  gerçek getiri gibi görünür ve **kayıpları olduğundan küçük gösterir**
  (bir fonda ham −%58, düzeltilmiş −%99). `tara.py` günlük |getiri| > %50
  olan günleri işaretler ve düzeltilmiş getiriyi ayrıca hesaplar.
- **Kâr payı dağıtan fonlarda** büyük tek günlük düşüş kayıp değil dağıtımdır;
  oynaklığı da yapay yükseltir.
- **Farklı pencereleri yan yana koymayın.** 120 günlük taban oranla 12 aylık
  oynaklığı aynı satırda göstermek olmayan bir çelişki üretir.
- **Sıfır varyanslı seride korelasyon.** `if not varyans` yeterli değildir;
  kayan nokta gürültüsü `1e-36 / 1e-36 = 1.0` üretir ve düz bir seriyi
  "mükemmel yumuşatılmış" gösterir. Bağıl eşik kullanılır.
- **Yeni fonlarda ilk gün fiyatı 0 gelebilir.** Tek bir sıfır tüm getiri
  zincirini bozar; hem veri hem ölçüm katmanında ayıklanır.
- TEFAS `periyod` ay cinsindendir ve **yalnızca 12 ile 60** kabul eder.
- `dagilimSiraliGetirT` ucu çalışmıyor; varlık dağılımı fon detay sayfasından
  okunur ve yapılandırmaya elle girilir.

## Yapılandırma

Tek dosya: `fonlab/yapilandirma.py`. İncelenen fonlar, karşılaştırma çıpaları,
vaka listesi, izlenen hisseler, sayfa bağlantıları.

## Üretilen dosyalar

`tarama.json`, `rapor_veri.json`, `tahmin_kayit.json` ve `fonlab/.onbellek/`
üretilen dosyalardır ve depoya dahil edilmez. `tarayici` komutunu çalıştırmadan
önce bir kez `tara` çalıştırmanız gerekir (~5 dk, 1.300+ istek).

`build/` altındaki üç HTML dosyası son üretilen çıktılardır ve doğrudan
tarayıcıda açılabilir.

## Lisans

MIT. Kod serbestçe kullanılabilir. Üretilen analizler ve sayfalar kamuya açık
veriye dayanır; doğruluk garantisi verilmez.

## Veri kaynakları

TEFAS (`fonFiyatBilgiGetir`, `fonBilgiGetir`, `fonUnvanAra`), İş Yatırım açık
günlük kapanış ucu, KAP bildirimleri ve kurucu portföy dağılım raporları.
Hepsi kamuya açık. Analizler hata içerebilir; geçmiş performans gelecek için
bağlayıcı değildir.
