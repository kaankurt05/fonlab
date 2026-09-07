# -*- coding: utf-8 -*-
"""Kategorik grafik paleti dogrulayici — dataviz skill'indeki validate_palette.js'in
Python ikizi. Node bulunmayan ortamlarda ayni alti kontrolu calistirir.

Kullanim:
  python3 renk.py "#6d28d9,#f97316,#0d9488,#ec4899" --mode light
  python3 renk.py "#a78bfa,#fb923c,#2dd4bf,#f472b6" --mode dark --surface "#141024"
  python3 renk.py "..." --pairs all        # scatter/harita: tum ciftler
Cikis kodu: herhangi bir FAIL varsa 1.
"""
import math, sys, re, json

BAND = {'light': (0.43, 0.77), 'dark': (0.48, 0.67)}   # OKLCH L
CHROMA_FLOOR = 0.10
CVD_TARGET, CVD_FLOOR = 8.0, 6.0
NORMAL_FLOOR = 15.0
CONTRAST_MIN = 3.0
DEFAULT_SURFACE = {'light': '#fcfcfb', 'dark': '#1a1a19'}

MACHADO = {
 'protan': [[0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281,  0.099216],
            [-0.003882,-0.048116, 1.051998]],
 'deutan': [[0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501,  0.047413],
            [-0.011820,0.042940,  0.968881]],
 'tritan': [[1.255528,-0.076749, -0.178779],
            [-0.078411,0.930809,  0.147602],
            [0.004733, 0.691367,  0.303900]],
}

WS = ' \t\n\v\f\r      　' + ''.join(chr(c) for c in range(0x2000,0x200b))
def strip_ws(v): return v.strip(WS)
def split_colors(raw): return [c for c in (strip_ws(x) for x in (raw or '').split(',')) if c]
def is_hex(v): return bool(re.fullmatch(r'#?[0-9a-fA-F]{6}', v))

def hex2srgb(h):
    h = strip_ws(h).lstrip('#')
    return [int(h[i:i+2], 16)/255 for i in (0,2,4)]
def s2lin(c): return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
def lin(h): return [s2lin(c) for c in hex2srgb(h)]
def rel_lum(h):
    r,g,b = lin(h); return 0.2126*r + 0.7152*g + 0.0722*b
def contrast(a, b):
    x, y = rel_lum(a), rel_lum(b)
    hi, lo = max(x,y), min(x,y)
    return (hi+0.05)/(lo+0.05)

def oklab_from_lin(rgb):
    r,g,b = rgb
    l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
    m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
    s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
    return (0.2104542553*l + 0.7936177850*m - 0.0040720468*s,
            1.9779984951*l - 2.4285922050*m + 0.4505937099*s,
            0.0259040371*l + 0.7827717662*m - 0.8086757660*s)
def oklab(h): return oklab_from_lin(lin(h))
def oklch(h):
    L,a,b = oklab(h); return L, math.hypot(a,b)
def simulate(h, kind):
    r,g,b = lin(h); M = MACHADO[kind]
    return [min(1.0, max(0.0, M[i][0]*r + M[i][1]*g + M[i][2]*b)) for i in range(3)]
def delta_e(h1, h2, kind=None):
    a = oklab_from_lin(simulate(h1,kind) if kind else lin(h1))
    b = oklab_from_lin(simulate(h2,kind) if kind else lin(h2))
    return 100*math.dist(a,b)

def validate(palette, mode='light', surface=None, pairs='adjacent'):
    surface = surface or DEFAULT_SURFACE[mode]
    lo, hi = BAND[mode]
    report, ok = [], True

    off = [(c, round(oklch(c)[0],3)) for c in palette if not (lo <= oklch(c)[0] <= hi)]
    if off: ok = False
    report.append(('Lightness band', not off,
        f'bant disi: {off}' if off else f'{len(palette)} renk de L {lo}-{hi} icinde'))

    lowc = [(c, round(oklch(c)[1],3)) for c in palette if oklch(c)[1] < CHROMA_FLOOR]
    if lowc: ok = False
    report.append(('Chroma floor', not lowc,
        f'gri okunuyor: {lowc}' if lowc else f'{len(palette)} renk de >= {CHROMA_FLOOR}'))

    n = len(palette)
    pairlist = ([(i,j) for i in range(n) for j in range(i+1,n)] if pairs=='all'
                else [(i,i+1) for i in range(n-1)])
    worst = None
    for kind in ('protan','deutan'):
        for i,j in pairlist:
            d = delta_e(palette[i], palette[j], kind)
            if worst is None or d < worst[0]: worst = (d, kind, palette[i], palette[j])
    cvd_ok = worst[0] >= CVD_FLOOR
    if not cvd_ok: ok = False
    lbl = 'all-pairs' if pairs=='all' else 'adjacent'
    note = f'en kotu {lbl} CVD dE {worst[0]:.1f} ({worst[1]}: {worst[2]} vs {worst[3]})'
    if CVD_FLOOR <= worst[0] < CVD_TARGET: note += '  [WARN: 6-8 bandi, ikincil kodlama zorunlu]'
    report.append((f'CVD separation ({lbl})', cvd_ok, note))

    nworst = min(((delta_e(palette[i],palette[j]), palette[i], palette[j]) for i,j in pairlist),
                 key=lambda t: t[0])
    nok = nworst[0] >= NORMAL_FLOOR
    if not nok: ok = False
    report.append(('Normal-vision floor', nok,
        f'en kotu {lbl} dE {nworst[0]:.1f} ({nworst[1]} vs {nworst[2]}), esik {NORMAL_FLOOR}'))

    low = [(c, round(contrast(c,surface),2)) for c in palette if contrast(c,surface) < CONTRAST_MIN]
    report.append(('Contrast vs surface', True,
        (f'{low} < {CONTRAST_MIN}:1  [WARN: gorunur dogrudan etiket veya tablo zorunlu]'
         if low else f'{len(palette)} renk de >= {CONTRAST_MIN}:1 (yuzey {surface})')))
    return ok, report

def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    raw = argv[1]
    mode = 'light'; surface = None; pairs = 'adjacent'
    i = 2
    while i < len(argv):
        if argv[i] == '--mode': mode = argv[i+1]; i += 2
        elif argv[i] == '--surface': surface = argv[i+1]; i += 2
        elif argv[i] == '--pairs': pairs = argv[i+1]; i += 2
        else: i += 1
    pal = split_colors(raw)
    bad = [c for c in pal if not is_hex(c)]
    if not pal or bad:
        print(f'FAIL  gecersiz renk girdisi: {bad or "bos"}'); return 1
    pal = ['#'+c.lstrip('#').lower() for c in pal]
    ok, rep = validate(pal, mode, surface, pairs)
    print(f'\n  palet: {" ".join(pal)}   mod: {mode}   yuzey: {surface or DEFAULT_SURFACE[mode]}\n')
    for name, passed, note in rep:
        print(f'  {"PASS" if passed else "FAIL"}  {name:<28} {note}')
    print(f'\n  SONUC: {"GECTI" if ok else "KALDI"}\n')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv))


# ---------------------------------------------------------------------------
# Ters donusum + "gecen adima yapistir": bir hue'yu hedef modun bandina tasir.
# ---------------------------------------------------------------------------
def lin2s(c):
    c = min(1.0, max(0.0, c))
    return 12.92*c if c <= 0.0031308 else 1.055*(c**(1/2.4)) - 0.055

def lin_from_oklab(L, a, b):
    l_ = L + 0.3963377774*a + 0.2158037573*b
    m_ = L - 0.1055613458*a - 0.0638541728*b
    s_ = L - 0.0894841775*a - 1.2914855480*b
    l, m, s = l_**3, m_**3, s_**3
    return (+4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
            -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
            -0.0041960863*l - 0.7034186147*m + 1.7076147010*s)

def in_gamut(rgb, eps=1e-4):
    return all(-eps <= c <= 1+eps for c in rgb)

def oklch_to_hex(L, C, h_deg):
    """Gamut disina tasarsa chroma'yi ikili aramayla kisar."""
    hr = math.radians(h_deg)
    lo, hi = 0.0, C
    if in_gamut(lin_from_oklab(L, C*math.cos(hr), C*math.sin(hr))):
        lo = C
    else:
        for _ in range(40):
            mid = (lo+hi)/2
            if in_gamut(lin_from_oklab(L, mid*math.cos(hr), mid*math.sin(hr))): lo = mid
            else: hi = mid
    rgb = lin_from_oklab(L, lo*math.cos(hr), lo*math.sin(hr))
    return '#' + ''.join(f'{round(lin2s(c)*255):02x}' for c in rgb)

def hue_of(h):
    L, a, b = oklab(h)
    return (math.degrees(math.atan2(b, a)) + 360) % 360

def snap(hex_color, mode, surface=None, keep_chroma=True):
    """Rengi hedef modun L bandina ve >=3:1 kontrast esigine tasi.
    Hue korunur; chroma gamut/kontrast icin gerekirse kisilir."""
    surface = surface or DEFAULT_SURFACE[mode]
    lo, hi = BAND[mode]
    L0, C0 = oklch(hex_color)
    hdeg = hue_of(hex_color)
    best = None
    steps = 60
    for i in range(steps+1):
        L = lo + (hi-lo)*i/steps
        cand = oklch_to_hex(L, C0 if keep_chroma else C0*0.95, hdeg)
        Lc, Cc = oklch(cand)
        if Cc < CHROMA_FLOOR:            # gri okunuyorsa ise yaramaz
            continue
        if not (lo <= Lc <= hi):         # 8-bit yuvarlama bant kenarindan tasirabilir:
            continue                     # kabul kriteri hedef L degil, olculen L
        ctr = contrast(cand, surface)
        score = (ctr >= CONTRAST_MIN, Cc, -abs(L - (lo+hi)/2))
        if best is None or score > best[0]:
            best = (score, cand, round(Lc,3), round(Cc,3), round(ctr,2))
    return best[1], {'L': best[2], 'C': best[3], 'contrast': best[4]}
