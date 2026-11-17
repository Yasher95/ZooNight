# Локация со свободной ходьбой: фон -> loc_<имя>.jpg (высота 1080), передние планы -> PNG с найденным местом,
# маска ходьбы из зелёной разметки (ячейка 4 экранных px, по строкам отрезки [x0,x1) в ячейках).
# blender -b -P free_room.py -- <папка> <assets/story> <имя> <фон> <разметка> [выход=файл переднего плана ...] [--dbg файл] [--join x0,y0,x1,y1]
# --join — прямоугольник (экранные px), который считать проходимым: стык частей зоны, не закрашенный на разметке.
import bpy, sys, os, json, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
src, out, name, locf, markf = a[:5]
rest = a[5:]; dbg = None; joins = []; fgs = []
i = 0
while i < len(rest):
    if rest[i] == '--dbg': dbg = rest[i + 1]; i += 2
    elif rest[i] == '--join': joins.append([float(v) for v in rest[i + 1].split(',')]); i += 2
    else: fgs.append(rest[i].split('=', 1)); i += 1
CELL = 4
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
def save(d, fn, jpg=False):
    h, w = d.shape[:2]
    o = bpy.data.images.new('o', w, h, alpha=not jpg); o.alpha_mode = 'STRAIGHT'
    o.pixels = d[::-1].astype(np.float32).ravel(); o.filepath_raw = fn if os.path.isabs(fn) else os.path.join(out, fn)
    if jpg: o.file_format = 'JPEG'; bpy.context.scene.render.image_settings.quality = 90
    else: o.file_format = 'PNG'
    o.save(); bpy.data.images.remove(o)
def scl(d, s):
    p = d.copy(); p[..., :3] *= p[..., 3:4]
    r = resize(p, max(1, round(d.shape[1] * s)), max(1, round(d.shape[0] * s)))
    al = np.maximum(r[..., 3:4], 1e-4); r[..., :3] = np.clip(r[..., :3] / al, 0, 1)
    r[..., 3] = np.where(r[..., 3] < .02, 0, r[..., 3]); return r
bg = load(locf); H, W = bg.shape[:2]; S = 1080 / H; SS = 540 / H
nb = scl(bg, S); nb[..., 3] = 1; save(nb, f'loc_{name}.jpg', True); print('LOC', nb.shape[1], nb.shape[0], 'screen w', round(W * SS, 1))
for oname, ff in fgs:
    f = load(ff); fh, fw = f.shape[:2]; m = f[..., 3] > .95; yy, xx = np.nonzero(m)
    sel = np.random.RandomState(1).choice(len(yy), min(3000, len(yy)), replace=False); yy, xx = yy[sel], xx[sel]; v = f[yy, xx, :3]
    best = (9, 0, 0)
    for oy in range(0, H - fh + 1, 4):
        for ox in range(0, W - fw + 1, 4):
            e = np.abs(bg[oy + yy, ox + xx, :3] - v).mean()
            if e < best[0]: best = (e, ox, oy)
    e0, x0, y0 = best
    for oy in range(max(0, y0 - 4), min(H - fh, y0 + 4) + 1):
        for ox in range(max(0, x0 - 4), min(W - fw, x0 + 4) + 1):
            e = np.abs(bg[oy + yy, ox + xx, :3] - v).mean()
            if e < best[0]: best = (e, ox, oy)
    save(scl(f, S), oname + '.png'); print('FG', oname, 'at', round(best[1] * SS, 1), round(best[2] * SS, 1), 'err %.4f' % best[0], 'size', round(fw * SS, 1), round(fh * SS, 1))
mk = load(markf)
gr = (mk[..., 1] - np.maximum(mk[..., 0], mk[..., 2]) > .2) & (mk[..., 1] > .3)
cs = CELL / SS; gw, gh = int(W * SS // CELL) + 1, 540 // CELL
grid = np.zeros((gh, gw), bool)
for r in range(gh):
    for c in range(gw):
        y0, y1, x0, x1 = int(r * cs), int((r + 1) * cs), int(c * cs), min(W, int((c + 1) * cs))
        if x1 > x0: grid[r, c] = gr[y0:y1, x0:x1].mean() > .5
for x0, y0, x1, y1 in joins: grid[int(y0 // CELL):int(y1 // CELL) + 1, int(x0 // CELL):int(x1 // CELL) + 1] = True
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
# связные части зоны — для проверки
lab = np.zeros((gh, gw), int); n = 0
for y in range(gh):
    for x in range(gw):
        if grid[y, x] and not lab[y, x]:
            n += 1; st = [(y, x)]; lab[y, x] = n; cnt = 0; bx = [x, x, y, y]
            while st:
                cy, cx = st.pop(); cnt += 1; bx = [min(bx[0], cx), max(bx[1], cx), min(bx[2], cy), max(bx[3], cy)]
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    Y, X = cy + dy, cx + dx
                    if 0 <= Y < gh and 0 <= X < gw and grid[Y, X] and not lab[Y, X]: lab[Y, X] = n; st.append((Y, X))
            print('PART', n, 'cells', cnt, 'x', bx[0] * CELL, bx[1] * CELL + CELL, 'y', bx[2] * CELL, bx[3] * CELL + CELL)
print('JS', json.dumps({'cell': CELL, 'rows': rows}, separators=(',', ':')))
if dbg:
    d = resize(bg, gw, gh); d[..., 3] = 1; d[grid] = d[grid] * .4 + np.array([0, .6, 0, .6]); save(d, dbg)
