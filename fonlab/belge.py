# -*- coding: utf-8 -*-
"""KAP / portfoy yonetim sirketi PDF'lerinden metin cikarma.

Poppler kurulu olmayan makinelerde calisir. Iki zorlugu cozer:
  1) metin FlateDecode akislari icinde — acilir,
  2) alt kume (subset) fontlar <hex> glif kodu kullanir — /ToUnicode
     CMap'leri cozulup gercek karakterlere cevrilir.
Metin konumuna (Tm/Td) gore satirlara toplanir, boylece tablolar okunur.

Kullanim:
  python3 -m fonlab belge rapor.pdf
  from fonlab.belge import satirlar; satirlar("dfi-temmuz-2026.pdf")
"""

import re, zlib, sys

def nesneler(d):
    """obj numarasi -> ham govde"""
    out = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', d):
        num = int(m.group(1)); bas = m.end()
        son = d.find(b'endobj', bas)
        out[num] = d[bas: son if son > 0 else bas + 4000]
    return out

def akis_ac(govde):
    m = re.search(rb'stream(\r\n|\r|\n)', govde)
    if not m: return None
    b = m.end(); e = govde.find(b'endstream', b)
    ham = govde[b:e]
    for t in (ham, ham.rstrip(b'\r\n')):
        try: return zlib.decompress(t)
        except Exception:
            try: return zlib.decompressobj().decompress(t)
            except Exception: pass
    # /Filter yoksa akis duz metindir (ToUnicode CMap'leri cogu zaman boyledir)
    return ham if b'/Filter' not in govde[:m.start()] else None

def cmap_coz(veri):
    """ToUnicode CMap -> {kod: karakter}"""
    t = veri.decode('latin-1', 'replace')
    harita = {}
    for blok in re.findall(r'beginbfchar(.*?)endbfchar', t, re.S):
        for src, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blok):
            harita[int(src, 16)] = ''.join(
                chr(int(dst[i:i+4], 16)) for i in range(0, len(dst), 4))
    for blok in re.findall(r'beginbfrange(.*?)endbfrange', t, re.S):
        for lo, hi, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blok):
            lo, hi, d0 = int(lo, 16), int(hi, 16), int(dst, 16)
            for k in range(lo, hi + 1):
                harita[k] = chr(d0 + (k - lo))
    return harita

def font_haritalari(d):
    """/Fn adi -> {kod: karakter}"""
    objs = nesneler(d)
    tou = {}                       # obj no -> harita
    for num, govde in objs.items():
        if b'beginbfchar' in govde or b'beginbfrange' in govde:
            a = akis_ac(govde)
            if a: tou[num] = cmap_coz(a)
        else:
            a = akis_ac(govde)
            if a and (b'beginbfchar' in a or b'beginbfrange' in a):
                tou[num] = cmap_coz(a)
    # font nesnesi -> ToUnicode nesnesi
    font_tou = {}
    for num, govde in objs.items():
        m = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', govde)
        if m and int(m.group(1)) in tou:
            font_tou[num] = tou[int(m.group(1))]
    # kaynak sozlugu: /F1 12 0 R
    ad_harita = {}
    for num, govde in objs.items():
        for ad, hedef in re.findall(rb'/(F\d+)\s+(\d+)\s+0\s+R', govde):
            h = font_tou.get(int(hedef))
            if h: ad_harita[ad.decode()] = h
    if not ad_harita and font_tou:                 # tek font varsayimi
        ad_harita['*'] = list(font_tou.values())[0]
    return ad_harita

TOK = re.compile(rb'''
    /(?P<font>F\d+)\s+[\d.]+\s+Tf
  | (?P<a>-?[\d.]+)\s+(?P<b>-?[\d.]+)\s+(?P<c>-?[\d.]+)\s+(?P<dd>-?[\d.]+)\s+(?P<e>-?[\d.]+)\s+(?P<f>-?[\d.]+)\s+Tm
  | (?P<td>-?[\d.]+)\s+(?P<td2>-?[\d.]+)\s+T[dD]
  | (?P<arr>\[[^\]]*\])\s*TJ
  | <(?P<hex>[0-9A-Fa-f]+)>\s*Tj
''', re.X)

def satirlar(yol, y_tol=2.0):
    d = open(yol, 'rb').read()
    fmap = font_haritalari(d)
    parcalar = []
    for m0 in re.finditer(rb'stream(\r\n|\r|\n)', d):
        b = m0.end(); e = d.find(b'endstream', b)
        try: a = zlib.decompress(d[b:e])
        except Exception: continue
        if a[:4] == b'\x00\x01\x00\x00' or b'glyf' in a[:400]: continue
        if b'BT' not in a: continue
        font = None; x = y = 0.0
        for m in TOK.finditer(a):
            if m.group('font'): font = m.group('font').decode()
            elif m.group('e') is not None: x = float(m.group('e')); y = float(m.group('f'))
            elif m.group('td') is not None: x += float(m.group('td')); y += float(m.group('td2'))
            else:
                h = fmap.get(font) or fmap.get('*') or {}
                hexler = ([m.group('hex')] if m.group('hex')
                          else re.findall(rb'<([0-9A-Fa-f]+)>', m.group('arr')))
                s = ''
                for hx in hexler:
                    hx = hx.decode()
                    for i in range(0, len(hx), 4):
                        s += h.get(int(hx[i:i+4], 16), '')
                if s.strip(): parcalar.append((round(y, 1), x, s))
    gruplar = {}
    for y, x, t in parcalar:
        k = next((k for k in gruplar if abs(k - y) <= y_tol), y)
        gruplar.setdefault(k, []).append((x, t))
    out = []
    for y in sorted(gruplar):
        s = ''.join(t for _, t in sorted(gruplar[y]))
        s = re.sub(r'\s+', ' ', s).strip()
        if s: out.append(s)
    return out

if __name__ == '__main__':
    for y in sys.argv[1:]:
        print(f'\n=========== {y.split("/")[-1]} ===========')
        for s in satirlar(y): print(s)
