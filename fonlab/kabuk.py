# -*- coding: utf-8 -*-
"""Uc sayfanin ortak kabugu: gezinme seridi + paylasilan CSS.

Rapor, tarayici ve ozet ayri belgeler ama tek bir isin parcalari. Once
birbirlerinden habersizdiler; bu modul aralarindaki bagi ve ortak davranisi
(mobil tablo duzeni, atlama baglantisi, odak gorunurlugu) tek yerde tutuyor.
"""
from .yapilandirma import AYAR

# --- gezinme -----------------------------------------------------------
NAV_CSS = """
.ust{position:sticky;top:0;z-index:40;background:color-mix(in srgb,var(--paper) 88%,transparent);
  backdrop-filter:saturate(180%) blur(10px);-webkit-backdrop-filter:saturate(180%) blur(10px);
  border-bottom:1px solid var(--rule)}
@supports not (backdrop-filter:blur(1px)){.ust{background:var(--paper)}}
.ust-sabit{position:static;backdrop-filter:none;-webkit-backdrop-filter:none;background:var(--paper)}
.ust-ic{max-width:1280px;margin:0 auto;padding:9px 28px;display:flex;align-items:center;gap:var(--s2)}
.ust-ad{font-family:"Fraunces",Georgia,serif;font-weight:900;font-size:15px;letter-spacing:-.01em;
  color:var(--ink);text-decoration:none;white-space:nowrap}
.ust-ad:hover{color:var(--accent)}
.ust-bag{display:flex;gap:2px;margin-left:auto;flex-wrap:wrap}
.ust-bag a{font-size:13px;color:var(--ink-3);text-decoration:none;padding:6px 12px;
  border-radius:var(--r-pill);white-space:nowrap;font-weight:500}
.ust-bag a:hover{color:var(--ink);background:var(--surface-2)}
.ust-bag a[aria-current="page"]{color:var(--accent);background:var(--accent-soft);font-weight:600}
.atla{position:absolute;left:-9999px;top:0;background:var(--accent);color:#fff;padding:10px 16px;
  border-radius:0 0 var(--r-sm) 0;z-index:99;text-decoration:none;font-size:14px}
.atla:focus{left:0}
@media (max-width:660px){
  .ust-ic{padding:8px 16px;gap:var(--s1)}
  .ust-ad{font-size:14px}
  .ust-bag a{padding:6px 9px;font-size:12.5px}
}
"""

# --- mobil tablo duzeni -------------------------------------------------
# Genis veri tablolari telefonda yatay kaydirmaya mahkumdu (min-width:940px).
# 700px altinda her satir bir karta donusuyor; sutun basliklari td'nin
# data-l ozniteliginden ::before ile geliyor.
TABLO_CSS = """
@media (max-width:700px){
  /* Genis veri tablolari telefonda yatay kaydirmaya mahkumdu (min-width:940px).
     Burada her satir bir karta donusuyor; sutun basligi td'nin data-l
     ozniteliginden ::before ile geliyor. */
  table{min-width:0!important;width:100%}
  .tbl,.tbl-scroll{overflow-x:visible;max-height:none}
  thead{position:absolute!important;width:1px;height:1px;overflow:hidden;
    clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
  tbody tr{display:block;border-bottom:1px solid var(--rule);padding:14px 2px}
  tbody tr:last-child{border-bottom:none}
  tbody td{display:flex!important;justify-content:space-between;align-items:baseline;
    gap:var(--s2);border:none;padding:4px 14px;text-align:right;white-space:normal;
    position:static!important;background:none!important;min-width:0}
  tbody td[data-l]:not([data-l=""])::before{content:attr(data-l);flex:0 1 auto;
    text-align:left;font-family:"IBM Plex Mono",monospace;font-size:11px;
    letter-spacing:.04em;text-transform:uppercase;color:var(--ink-3);
    font-weight:600;padding-top:3px;white-space:normal}
  /* Fon adi hucresi: etiketsiz, tam genislik, kirpilmadan sarsin */
  tbody td.hucre-ad,tbody td[data-l="Fon"],tbody td[data-l="Kurucu"],
  tbody td[data-l="Ölçüt"]{display:block!important;text-align:left;
    padding:0 14px 10px}
  tbody td.hucre-ad::before,tbody td[data-l="Fon"]::before,
  tbody td[data-l="Kurucu"]::before,tbody td[data-l="Ölçüt"]::before{display:none}
  .fon-ad{max-width:none;white-space:normal;overflow:visible;text-overflow:clip;
    margin-top:3px}
  /* Onay kutusu sutunu: kartin ustune, etiketsiz */
  tbody td.sec-h{display:block!important;padding:0 14px 8px;width:auto}
  tbody td.sec-h::before{display:none}
  /* Kivilcim satiri: etiket solda, grafik saga yaslanip daralsin */
  .kv{width:120px;height:24px;flex:none}
  /* Cok sutunlu kiyas tablolari: hucre icerigi sarabilsin */
  tbody td{word-break:break-word}
  .kaydir-not,.tbl-scroll::after{display:none!important}
}
"""


SEKME_CSS = """
@media (max-width:700px){
  .sekmeler{overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;
    flex-wrap:nowrap}
  .sekmeler::-webkit-scrollbar{display:none}
  .sekme{flex:none;padding:10px 13px;font-size:13.5px}
  .figs,.pf-ozet,.sayilar,.funds{grid-template-columns:1fr!important}
  .chart-holder{overflow-x:auto}
}
"""

ORTAK_CSS = NAV_CSS + TABLO_CSS + SEKME_CSS + """
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;
  scroll-behavior:auto!important}}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
"""


def nav(aktif, baslik='Serbest Fon Laboratuvarı', yapiskan=True, atla='#ana'):
    """Ustteki gezinme seridi. `aktif` = sayfalar[] icindeki anahtar."""
    bag = []
    for anahtar, ad, url in AYAR.get('sayfalar', []):
        if anahtar == aktif:
            bag.append(f'<a href="{url}" aria-current="page">{ad}</a>')
        else:
            bag.append(f'<a href="{url}" target="_blank" rel="noopener">{ad}</a>')
    ilk = AYAR.get('sayfalar', [['', '', '#']])[0][2]
    # Raporun kendi yapiskan ust seridi var; orada bu serit sabit duruyor
    # ki iki yapiskan katman ust uste binmesin.
    sinif = 'ust' if yapiskan else 'ust ust-sabit'
    return (
        f'<a class="atla" href="{atla}">İçeriğe atla</a>\n'
        f'<header class="{sinif}"><div class="ust-ic">'
        f'<a class="ust-ad" href="{ilk}">{baslik}</a>'
        f'<nav class="ust-bag" aria-label="Sayfalar">{"".join(bag)}</nav>'
        '</div></header>'
    )
