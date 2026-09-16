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
| `tara [--tahmin]` | Tüm evreni tarar → `tarama.json`; `--tahmin` sicili de işler |
| `tarayici` | Taramadan etkileşimli sayfa üretir |
| `tahmin` | Bekleyen tahminleri puanlar, ertesi gün için yenilerini yazar |
| `ozetsayfa` | Proje özeti sayfasını üretir |
| `hisse [KOD ...]` | İzlenen BIST hisseleri için tanı paketi → `hisse_tani.json` |
| `renk "#a,#b" --mode light` | Palet doğrular (renk körlüğü, kontrast, açıklık) |
| `belge rapor.pdf` | KAP/PDR PDF'inden metin çıkarır |

Günlük akış: `tara --tahmin` → `hisse` → `tarayici`. Rapor haftalık.

İstekler eş zamanlı atılır; işçi sayısı `FONLAB_ISCI` ile ayarlanır (varsayılan 8).
`FONLAB_KAYIT` tahmin sicilinin yolunu değiştirir — deneme koşularının gerçek
sicili bozmaması için. `FONLAB_TTL` önbellek ömrü (saniye, varsayılan 6 saat).

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
hisse_tani.py BIST hisseleri için tanı katmanı: yoğunlaşma, beta (gecikme
              düzeltmeli), limit günleri, şirket kartı (halka açıklık, piyasa
              değeri, net borç)
kabuk.py      Üç sayfanın ortak kabuğu (gezinme + mobil tablo düzeni)
rapor.py      Rapor + özet HTML üretimi
tarayici.py   Tarayıcı HTML üretimi
yapilandirma.py  Tek yapılandırma dosyası
```

## Testler

```bash
python3 -m fonlab.test_metrik
```

30 test. Ölçüm katmanı elle hesaplanmış değerlere ve uç durumlara karşı
doğrulanır: sabit seri, tek günlük seri, sıfır fiyat, toparlanmayan düşüş,
pay bölünmesi, kaldıraçlı beta, kısa seri, ve hisse tarafında gecikme
düzeltmesinin bilinen bir betayı geri kazanması.

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
- **TEFAS fon fiyatı piyasanın bir gün gerisinde.** Hisse serisiyle fon serisini
  doğrudan hizalamak ilişkiyi yok ediyor: BIST 30 hisselerinde ham beta −0,06 ile
  +0,04 arasında çıkıyordu (imkânsız), bir gün kaydırılınca 0,87–1,22 (beklenen
  aralık). Fon-fon karşılaştırmasında gecikme iki tarafta da aynı olduğu için
  sadeleşir; sorun yalnızca **hisse-fon** kıyasında ortaya çıkar. `hisse_tani.py`
  bu kaydırmayı uygular ve ham değeri de saklar.
- **CSS grid taşması.** `repeat(auto-fit,minmax(340px,1fr))` kapsayıcı tabandan
  darsa sabit 340px'lik ray üretip taşar. `minmax(min(340px,100%),1fr)` gerekiyor.
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
