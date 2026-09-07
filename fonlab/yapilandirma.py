# -*- coding: utf-8 -*-
"""Rapor yapilandirmasi. Baska fonlara gecmek icin sadece burasi degisir."""

AYAR = {
    'fonlar':   ['TLY', 'DFI'],          # incelenen fonlar
    'endeks':   'DZE',                   # piyasa vekili (BIST 100 endeks fonu)
    'risksiz':  'ALE',                   # TL nakit esigi (para piyasasi fonu)
    'ekstra':   ['AFO'],                 # ek kiyas (altin fonu)
    'periyod':  60,                      # ay (TEFAS tavani)
    'tufe':     0.3151,                  # TUIK TUFE y/y, Agustos 2026
    'tufe_not': 'TÜİK TÜFE, Ağustos 2026, yıllık %31,51',

    'kisa': {'TLY': 'TLY', 'DFI': 'DFI', 'DZE': 'BIST 100 fonu',
             'AFO': 'Altın fonu', 'ALE': 'Para piyasası'},

    # Fonlarin tuttugu BIST hisseleri (ortaklik yapilarindan tespit edildi)
    # Ek vakalar: ana karsilastirmaya sokulmadan, kiyas noktasi olarak tasinan fonlar.
    # Tarayicinin "sessiz yukselis" olcutunu gecen ama mekanizmasi bambaska olanlar.
    'vakalar': {
        'TMV': {'kurucu': 'Tera Portföy Yönetimi A.Ş.',
                'dagilim': [['Hisse Senedi', 81.57], ['Ters-Repo', 12.30],
                            ['Vadeli İşlem Nakit Teminatı', 3.45], ['Mevduat (TL)', 2.31],
                            ['Varlığa Dayalı Menkul Kıymet', 0.71], ['Finansman Bonosu', 0.11],
                            ['Yatırım Fonu Katılma Payları', 0.02], ['Repo (borç)', -0.47]]},
        'PBE': {'kurucu': 'Pusula Portföy Yönetimi A.Ş.',
                'dagilim': [['Varlığa Dayalı Menkul Kıymetler', 544.03],
                            ['Repo (borç)', -444.03]]},
        'PHN': {'kurucu': 'Pusula Portföy Yönetimi A.Ş.',
                'dagilim': [['Hisse Senedi', 128.05],
                            ['Yatırım Fonları Katılma Payları', 104.62],
                            ['Girişim Sermayesi Yatırım Fonları', 0.65],
                            ['Borsa İstanbul Para Piyasası (borç)', -5.16],
                            ['Repo (borç)', -128.16]]},
        # PKZ 30.05.2025'te pay bolunmesi yapti (1,005929 -> 0,160421 = -%84).
        # Bu bir kayip degil; seri o gunden baslatiliyor, yoksa tum
        # gecmis metrikler (getiri, oynaklik, maks. dusus) bozuluyor.
        'PKZ': {'kurucu': 'Pusula Portföy Yönetimi A.Ş.', 'bas': '2025-05-30',
                'bolunme': ['2025-05-30', 'pay bölünmesi (−%84,05)'],
                'dagilim': [['Hisse Senedi', 101.73],
                            ['Yatırım Fonları Katılma Payları', 0.01],
                            ['Borsa İstanbul Para Piyasası (borç)', -1.74]]},
    },

    # Kurucu duzeyinde incelenecek evler. Tek bir fonun sira numarasi ancak
    # ayni evin diger fonlariyla birlikte okununca anlam kazaniyor.
    'kurucular': ['PARDUS'],

    # Uc sayfa tek bir isin parcalari; birbirine baglaniyorlar. Tek kaynak burasi.
    'rapor_url':  'https://claude.ai/code/artifact/10fe73cc-5153-4697-8fcb-3381f8cc008d',
    'sayfalar': [
        ['ozet',     'Özet',     'https://claude.ai/code/artifact/66640998-fd3e-4a4b-a555-7a40e5f1df3d'],
        ['rapor',    'Rapor',    'https://claude.ai/code/artifact/10fe73cc-5153-4697-8fcb-3381f8cc008d'],
        ['tarayici', 'Tarayıcı', 'https://claude.ai/code/artifact/bbf84a7a-8da6-4bcf-af2b-9d9579decd42'],
    ],

    'hisseler': ['IEYHO', 'ISKPL', 'DSTKF'],
    'hisse_bas': '2023-01-02',   # hisse serilerinde cok yilli karsilastirma penceresi
    'hisse_ad': {'IEYHO': 'IEYHO — Işıklar Enerji ve Yapı Holding',
                 'ISKPL': 'ISKPL — Işık Plastik',
                 'DSTKF': 'DSTKF — Destek Faktoring'},

    # dagilimSiraliGetirT ucu NullPointer donuyor; bu veri fon detay
    # sayfasindan okundu (04.09.2026 itibariyla).
    'dagilim': {
        'TLY': [['Hisse Senedi', 81.98], ['Ters-Repo', 9.22],
                ['Yatırım Fonu Katılma Payları', 8.06], ['Finansman Bonosu', 4.37],
                ['Özel Sektör Kira Sertifikaları', 3.31], ['Mevduat (TL)', 0.52],
                ['Vadeli İşlem Nakit Teminatı', 0.15], ['Repo (borç)', -7.61]],
        'DFI': [['Hisse Senedi', 56.01], ['Yatırım Fonu Katılma Payları', 34.07],
                ['Mevduat (TL)', 9.65], ['Finansman Bonosu', 0.27]],
    },
    'kurucu': {'TLY': 'Tera Portföy Yönetimi A.Ş.', 'DFI': 'Atlas Portföy Yönetimi A.Ş.'},

    # Grafik seri renkleri — fonlab.renk ile her iki modda dogrulandi.
    'palet_acik': ['#8b5cf6', '#e11d48', '#14b8a6', '#f59e0b'],
    'palet_koyu': ['#8d5ef9', '#fd405e', '#00ac9a', '#cb8200'],
    'yuzey_acik': '#ffffff',
    'yuzey_koyu': '#161129',
}

def tum_kodlar(a=AYAR):
    return a['fonlar'] + [a['endeks']] + a['ekstra'] + [a['risksiz']]
