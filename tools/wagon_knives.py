# Вагон-притон + мини-игра «ножи»: фон -> loc_c2_wagon.jpg (высота 1080), спрайты в том же масштабе (1080/1536).
# blender -b -P wagon_knives.py -- <папка «вагон ножи»> <assets/story>
# Печатает положение стола на фоне, сдвиг кадров броска и якоря кадров уворота (в пикселях выходного масштаба).
import bpy, sys, os, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
S = 1080 / 1536
def load(p):
    im = bpy.data.images.load(os.path.join(src, p)); w, h = im.size
    d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
    bpy.data.images.remove(im); return d
def resize(d, nw, nh):
    h, w = d.shape[:2]
    ys = (np.arange(nh + 1) * h / nh).astype(int); xs = (np.arange(nw + 1) * w / nw).astype(int)
    c = np.cumsum(np.cumsum(np.pad(d, ((1, 0), (1, 0), (0, 0))), 0), 1)
    s = c[ys[1:]][:, xs[1:]] - c[ys[:-1]][:, xs[1:]] - c[ys[1:]][:, xs[:-1]] + c[ys[:-1]][:, xs[:-1]]
    area = ((ys[1:] - ys[:-1])[:, None] * (xs[1:] - xs[:-1])[None, :])[..., None]
    return s / area
def save(d, name, jpg=False):
    h, w = d.shape[:2]
    o = bpy.data.images.new('o', w, h, alpha=not jpg); o.alpha_mode = 'STRAIGHT'
    o.pixels = d[::-1].astype(np.float32).ravel(); o.filepath_raw = os.path.join(out, name)
    if jpg: o.file_format = 'JPEG'; bpy.context.scene.render.image_settings.quality = 90
    else: o.file_format = 'PNG'
    o.save(); bpy.data.images.remove(o)
def scl(d, s=S):  # уменьшение с альфой (premultiplied)
    p = d.copy(); p[..., :3] *= p[..., 3:4]
    r = resize(p, max(1, round(d.shape[1] * s)), max(1, round(d.shape[0] * s)))
    al = np.maximum(r[..., 3:4], 1e-4); r[..., :3] = np.clip(r[..., :3] / al, 0, 1)
    r[..., 3] = np.where(r[..., 3] < .02, 0, r[..., 3]); return r
bg = load('локация.png'); nb = scl(bg); nb[..., 3] = 1; save(nb, 'loc_c2_wagon.jpg', True)
print('LOC', nb.shape[1], nb.shape[0])
# стол: точное положение на фоне около грубого (1344, 816)
t = load('стол передний план.png'); th, tw = t.shape[:2]; m = t[..., 3] > .95; yy, xx = np.nonzero(m)
sel = np.random.RandomState(1).choice(len(yy), 6000, replace=False); yy, xx = yy[sel], xx[sel]; v = t[yy, xx, :3]
best = (9, 0, 0)
for oy in range(800, 833):
    for ox in range(1328, 1361):
        e = np.abs(bg[oy + yy, ox + xx, :3] - v).mean()
        if e < best[0]: best = (e, ox, oy)
save(scl(t), 'kn_table.png'); print('TABLE at', round(best[1] * S, 1), round(best[2] * S, 1), 'err %.4f' % best[0], 'size', round(tw * S), round(th * S))
# метатель: 2 кадра на одном листе, кадр 1 сдвинут так, чтобы ноги совпали с кадром 2
f1, f2 = load('анимация броска 1.png'), load('анимация броска 2.png')
h = f1.shape[0]; y0 = int(h * .7)
a1, a2 = f1[y0:, :, 3] > .5, f2[y0:, :, 3] > .5
bd = (-1, 0)
for dx in range(-80, 81):  # кадр 1 на холсте кадра 2 со сдвигом dx
    s = 0
    for x in range(f1.shape[1]):
        X = x + dx
        if 0 <= X < f2.shape[1]: s += (a1[:, x] & a2[:, X]).sum()
    if s > bd[0]: bd = (s, dx)
dx = bd[1]; L = min(0, dx); R = max(f2.shape[1], f1.shape[1] + dx); cw = R - L
sh = np.zeros((h, cw * 2, 4), np.float32)
sh[:, dx - L:dx - L + f1.shape[1]] = f1; sh[:, cw - L:cw - L + f2.shape[1]] = f2
save(scl(sh), 'mg_knifer.png')
print('KNIFER dx', dx, 'cell', round(cw * S), 'frame2 left in cell', round(-L * S), 'h', round(h * S))
# ножи
for src_n, name in (('нож1.png', 'kn_knife1'), ('нож2.png', 'kn_knife2'), ('нож2 копия.png', 'kn_knife3')):
    k = load(src_n); k[..., 3] = np.where(k[..., 3] < .5, 0, k[..., 3])
    # убрать мелкие зелёные пятна фона
    g = (k[..., 1] > k[..., 0] + .08) & (k[..., 1] > k[..., 2] + .08); k[g, 3] = 0
    save(scl(k, S), name + '.png'); print('KNIFE', name, round(k.shape[1] * S), round(k.shape[0] * S))
# увороты: якорь — середина нижнего ряда джинсов, верх головы
for i in range(1, 7):
    d = load(f'уворот{i}.png'); hh, ww = d.shape[:2]; al = d[..., 3] > .5
    row = np.nonzero(al[hh - 3])[0]; cols = np.nonzero(al.any(0))[0]; rows = np.nonzero(al.any(1))[0]
    save(scl(d), f'kn_horse{i}.png')
    print('DODGE', i, 'size', round(ww * S), round(hh * S), 'bottom', round(row.min() * S), round(row.max() * S), 'x', round(cols.min() * S), round(cols.max() * S), 'top', round(rows.min() * S))
