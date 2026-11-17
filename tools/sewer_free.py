# Коллектор (локация со свободной ходьбой): фон, перила переднего плана, ближний план ворот,
# маска ходьбы из зелёной разметки и опорные размеры персонажа (фигуры Коня на разметке).
# blender -b -P sewer_free.py -- <папка «коллекторная»> <assets/story> [debug.png]
# Печатает: FG — место перил на фоне; JS — маска (ячейка CELL экранных px, по строкам отрезки [x0,x1) в ячейках)
# и опоры [x, y ступней, масштаб] в экранных px картинки высотой 540.
import bpy, sys, os, json, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
src, out = a[0], a[1]
CELL = 4          # экранных px в ячейке маски
REF_H = 192.7     # высота фигуры-позы на разметке при масштабе 1 (вагон: 250.5 px при z=1.3)
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
    o.pixels = d[::-1].astype(np.float32).ravel(); o.filepath_raw = name if os.path.isabs(name) else os.path.join(out, name)
    if jpg: o.file_format = 'JPEG'; bpy.context.scene.render.image_settings.quality = 90
    else: o.file_format = 'PNG'
    o.save(); bpy.data.images.remove(o)
def scl(d, s):
    p = d.copy(); p[..., :3] *= p[..., 3:4]
    r = resize(p, max(1, round(d.shape[1] * s)), max(1, round(d.shape[0] * s)))
    al = np.maximum(r[..., 3:4], 1e-4); r[..., :3] = np.clip(r[..., :3] / al, 0, 1)
    r[..., 3] = np.where(r[..., 3] < .02, 0, r[..., 3]); return r
bg = load('локация.png'); H, W = bg.shape[:2]; S = 1080 / H; SS = 540 / H
nb = scl(bg, S); nb[..., 3] = 1; save(nb, 'loc_c2_sewer.jpg', True); print('LOC', nb.shape[1], nb.shape[0], 'screen w', round(W * SS, 1))
g = load('ближний план ворот.png'); ng = scl(g, 1080 / g.shape[0]); ng[..., 3] = 1; save(ng, 'loc_c2_gate.jpg', True); print('GATE', ng.shape[1], ng.shape[0])
# перила: место на фоне
f = load('передний план перила.png'); fh, fw = f.shape[:2]; m = f[..., 3] > .95; yy, xx = np.nonzero(m)
sel = np.random.RandomState(1).choice(len(yy), min(3000, len(yy)), replace=False); yy, xx = yy[sel], xx[sel]; v = f[yy, xx, :3]
best = (9, 0, 0)
for oy in range(0, H - fh + 1, 6):
    for ox in range(0, W - fw + 1, 6):
        e = np.abs(bg[oy + yy, ox + xx, :3] - v).mean()
        if e < best[0]: best = (e, ox, oy)
e0, x0, y0 = best
for oy in range(max(0, y0 - 6), min(H - fh, y0 + 6) + 1):
    for ox in range(max(0, x0 - 6), min(W - fw, x0 + 6) + 1):
        e = np.abs(bg[oy + yy, ox + xx, :3] - v).mean()
        if e < best[0]: best = (e, ox, oy)
save(scl(f, S), 'sw_fg_rail.png'); print('FG at', round(best[1] * SS, 1), round(best[2] * SS, 1), 'err %.4f' % best[0], 'size', round(fw * SS, 1), round(fh * SS, 1))
# разметка
mk = load('разметка и размеры перса.png')
gr = (mk[..., 1] - np.maximum(mk[..., 0], mk[..., 2]) > .2) & (mk[..., 1] > .3)
horse = (np.abs(mk[..., :3] - bg[..., :3]).max(-1) > .12) & ~gr
# дыры в зелёном от фигур и перил: промежуток в строке/столбце между зелёным — целиком фигура или короче GAP
GAP = 26
def fill(walk, hz):
    o = walk.copy()
    for r in range(walk.shape[0]):
        xs = np.nonzero(walk[r])[0]
        if len(xs) < 2: continue
        d = np.diff(xs); idx = np.nonzero(d > 1)[0]
        for i in idx:
            x0, x1 = xs[i] + 1, xs[i + 1]
            if x1 - x0 <= GAP or hz[r, x0:x1].mean() > .9: o[r, x0:x1] = True
    return o
walk = fill(gr, horse); walk = fill(walk.T, horse.T).T; walk = fill(walk, horse)
# сетка
cs = CELL / SS; gw, gh = int(W * SS // CELL) + 1, 540 // CELL
grid = np.zeros((gh, gw), bool)
for r in range(gh):
    for c in range(gw):
        y0, y1, x0, x1 = int(r * cs), int((r + 1) * cs), int(c * cs), min(W, int((c + 1) * cs))
        if x1 > x0: grid[r, c] = walk[y0:y1, x0:x1].mean() > .5
# склейка узких разрывов (стык платформы с пандусом, стойки перил): расширить на 2 ячейки и сжать обратно
def shift_or(m, n, f):
    o = m.copy()
    for _ in range(n):
        p = np.pad(o, 1, constant_values=not f)
        nb4 = [p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]]
        o = (o | nb4[0] | nb4[1] | nb4[2] | nb4[3]) if f else (o & nb4[0] & nb4[1] & nb4[2] & nb4[3])
    return o
grid = grid | shift_or(shift_or(grid, 2, True), 2, False)
rows = []
for r in range(gh):
    xs = np.nonzero(grid[r])[0]; sp = []
    if len(xs):
        st = prev = xs[0]
        for x in xs[1:]:
            if x != prev + 1: sp += [int(st), int(prev + 1)]; st = x
            prev = x
        sp += [int(st), int(prev + 1)]
    rows.append(sp)
# фигуры: компоненты на грубой сетке 8 px
k = 8; ch, cw = H // k, W // k
hc = horse[:ch * k, :cw * k].reshape(ch, k, cw, k).mean((1, 3)) > .3
lab = np.zeros((ch, cw), int); n = 0; refs = []
for y in range(ch):
    for x in range(cw):
        if hc[y, x] and not lab[y, x]:
            n += 1; st = [(y, x)]; lab[y, x] = n; pts = []
            while st:
                cy, cx = st.pop(); pts.append((cy, cx))
                for dy in (-2, -1, 0, 1, 2):
                    for dx in (-2, -1, 0, 1, 2):
                        Y, X = cy + dy, cx + dx
                        if 0 <= Y < ch and 0 <= X < cw and hc[Y, X] and not lab[Y, X]: lab[Y, X] = n; st.append((Y, X))
            ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
            hgt = (ys.max() - ys.min() + 1) * k
            if len(pts) < 60 or hgt < 150: continue
            feet = xs[ys > ys.max() - max(2, len(set(ys)) // 12)]
            refs.append([round((feet.min() + feet.max() + 1) / 2 * k * SS, 1), round((ys.max() + 1) * k * SS, 1), round(hgt * SS / REF_H, 3)])
            print('REF feet', refs[-1][:2], 'height px', round(hgt * SS), 'scale', refs[-1][2])
print('JS', json.dumps({'cell': CELL, 'rows': rows, 'refs': refs}, separators=(',', ':')))
if len(a) > 2:  # отладочная картинка: маска поверх фона
    dbg = resize(bg, gw, gh); dbg[..., 3] = 1; dbg[grid] = dbg[grid] * .4 + np.array([0, .6, 0, .6])
    for x, y, s in refs: dbg[min(gh - 1, int(y / CELL)), min(gw - 1, int(x / CELL))] = (1, 0, 0, 1)
    save(dbg, a[2])
