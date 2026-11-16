# Локации прохождения из готовых картинок: фон -> JPG высотой 1080, передние планы -> PNG в том же масштабе,
# положение переднего плана на фоне — подбор сдвигом по картинке-референсу (где передний план уже стоит на месте).
# blender -b -P story_locs.py -- <папка «режим на прохождение»> <assets/story>
# Печатает строки LOC/FG с размерами и найденным положением (в пикселях выходной картинки высотой 1080).
import bpy, sys, os, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
H = 1080
def load(p):
    im = bpy.data.images.load(p); w, h = im.size
    d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
    bpy.data.images.remove(im); return d
def resize(d, nw, nh):  # усреднение по ячейкам (уменьшение)
    h, w = d.shape[:2]
    ys = (np.arange(nh + 1) * h / nh).astype(int); xs = (np.arange(nw + 1) * w / nw).astype(int)
    c = np.cumsum(np.cumsum(np.pad(d, ((1, 0), (1, 0), (0, 0))), 0), 1)
    s = c[ys[1:]][:, xs[1:]] - c[ys[:-1]][:, xs[1:]] - c[ys[1:]][:, xs[:-1]] + c[ys[:-1]][:, xs[:-1]]
    area = ((ys[1:] - ys[:-1])[:, None] * (xs[1:] - xs[:-1])[None, :])[..., None]
    return s / area
def save(d, path, jpg):
    h, w = d.shape[:2]
    o = bpy.data.images.new('o', w, h, alpha=not jpg); o.alpha_mode = 'STRAIGHT'
    o.pixels = d[::-1].astype(np.float32).ravel(); o.filepath_raw = path
    if jpg: o.file_format = 'JPEG'; bpy.context.scene.render.image_settings.quality = 90
    else: o.file_format = 'PNG'
    o.save(); bpy.data.images.remove(o)
def prem(d):  # для уменьшения с альфой: цвет умножить на альфу, потом поделить
    p = d.copy(); p[..., :3] *= p[..., 3:4]; return p
def unprem(d):
    o = d.copy(); al = np.maximum(o[..., 3:4], 1e-4); o[..., :3] = np.clip(o[..., :3] / al, 0, 1); return o
def find(fg, ref, k):  # сдвиг fg внутри ref (оба в одном масштабе) по непрозрачным пикселям, на уменьшенных копиях
    fh, fw = fg.shape[:2]; rh, rw = ref.shape[:2]
    f = resize(fg, fw // k, fh // k); r = resize(ref[..., :3], rw // k, rh // k)
    m = f[..., 3] > .9; fc = f[..., :3]
    best = (1e9, 0, 0)
    ys = range(0, r.shape[0] - f.shape[0] + 1); xs = range(0, r.shape[1] - f.shape[1] + 1)
    yy, xx = np.nonzero(m); vals = fc[yy, xx]
    sel = np.random.RandomState(1).choice(len(yy), min(3000, len(yy)), replace=False)
    yy, xx, vals = yy[sel], xx[sel], vals[sel]
    for oy in ys:
        rows = r[oy + yy]
        for ox in xs:
            e = np.abs(rows[np.arange(len(xx)), ox + xx] - vals).mean()
            if e < best[0]: best = (e, ox * k, oy * k)
    return best
jobs = [  # (выход, фон, [(передний план, референс или None)])
    ('apt', 'квартира/квартира.png', [('apt_fg_chair', 'квартира/передний план, кресло.png', None), ('apt_fg_table', 'квартира/передний план, стол.png', None)]),
    ('street', 'улица/улица.png', [('street_fg', 'улица/передний план.png', 'улица/референс размеров локации.png'), ('street_fg_car', 'улица/авто.png', 'улица/референс размеров локации.png')]),
    ('metro', 'метро/метро.png', [('metro_train', 'метро/вагон.png', 'метро/реф размеров.png')]),
]
for name, bgp, fgs in jobs:
    bg = load(os.path.join(src, bgp)); h, w = bg.shape[:2]; s = H / h
    nb = resize(bg, round(w * s), H); nb[..., 3] = 1
    save(nb, os.path.join(out, f'loc_{name}.jpg'), True)
    print('LOC', name, nb.shape[1], nb.shape[0], 'scale', round(s, 4))
    refs = {}
    for fn, fp, rp in fgs:
        fg = load(os.path.join(src, fp)); fh, fw = fg.shape[:2]
        pos = ''
        if rp:
            if rp not in refs: refs[rp] = load(os.path.join(src, rp))
            ref = refs[rp]
            e, x, y = find(fg, ref, 8 if fw > 1000 else 4)
            # уточнение на шаге 1 вокруг найденного
            best = (e, x, y); m = fg[..., 3] > .9; yy, xx = np.nonzero(m)
            sel = np.random.RandomState(2).choice(len(yy), min(6000, len(yy)), replace=False); yy, xx = yy[sel], xx[sel]; vals = fg[yy, xx, :3]
            for oy in range(max(0, y - 10), min(ref.shape[0] - fh, y + 10) + 1, 1):
                for ox in range(max(0, x - 10), min(ref.shape[1] - fw, x + 10) + 1, 1):
                    ee = np.abs(ref[oy + yy, ox + xx, :3] - vals).mean()
                    if ee < best[0]: best = (ee, ox, oy)
            pos = f'at {round(best[1] * s)} {round(best[2] * s)} err {best[0]:.4f}'
        nf = unprem(resize(prem(fg), max(1, round(fw * s)), max(1, round(fh * s))))
        save(nf, os.path.join(out, fn + '.png'), False)
        print('FG', fn, nf.shape[1], nf.shape[0], pos)
