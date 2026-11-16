# Ассеты прохождения по списку tools/story_props.json: вырезка прямоугольника с листа на зелёном фоне,
# хромакей с жёстким краем (пиксель-арт), подавление зелёного отсвета по краю, удаление мелкого мусора,
# заливка закрытых дыр (окна машин — «fill»), обрезка по содержимому. Результат: assets/story/<имя>.png
# blender -b -P props_cut.py -- story_props.json srcart_dir out_dir [только_эти_имена...]
import bpy, sys, os, json, numpy as np
from collections import deque
a = sys.argv[sys.argv.index('--') + 1:]
man = json.load(open(a[0], encoding='utf-8')); src, out = a[1], a[2]; only = set(a[3:])
os.makedirs(out, exist_ok=True)
sheets = {}
def sheet(n):
    if n not in sheets:
        p = [os.path.join(src, f) for f in os.listdir(src) if f.startswith(f'sheet{n}.')][0]
        im = bpy.data.images.load(p); w, h = im.size
        d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
        bpy.data.images.remove(im)
        key = d[..., 1] - np.maximum(d[..., 0], d[..., 2])
        bord = np.concatenate([key[:6].ravel(), key[-6:].ravel(), key[:, :6].ravel(), key[:, -6:].ravel()])
        sheets[n] = (d, key, float(np.median(bord)))
    return sheets[n]
def label(m):
    lab = np.zeros(m.shape, np.int32); n = 0; H, W = m.shape
    for sy, sx in zip(*np.nonzero(m)):
        if lab[sy, sx]: continue
        n += 1; q = deque([(sy, sx)]); lab[sy, sx] = n
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; q.append((yy, xx))
    return lab, n
info = {}
for name, e in man.items():
    if name == '_' or (only and name not in only): continue
    n, x, y, w, h = e[:5]; opt = e[5:]
    d, key, bk = sheet(n)
    c = d[y:y + h, x:x + w].copy(); k = key[y:y + h, x:x + w]
    al = np.clip((bk * .55 - k) / (bk * .35), 0, 1)
    solid = al > .5
    # мелкий мусор (пятна < 30 px) — убрать
    lab, cnt = label(solid)
    if cnt > 1:
        sizes = np.bincount(lab.ravel())
        small = np.isin(lab, np.nonzero(sizes < 30)[0]) & solid
        solid &= ~small
    if 'glass' in opt:  # зеленоватые стёкла (окна машин) — тёмное стекло
        gl = solid & (k > bk * .12)
        c[gl, 0], c[gl, 1], c[gl, 2] = .07 + c[gl, 0] * .25, .09 + c[gl, 0] * .25, .11 + c[gl, 2] * .3
    if 'fill' in opt:  # закрытые прозрачные области — тёмным
        holes = ~solid; hl, hn = label(holes)
        edge = set(np.unique(np.concatenate([hl[0], hl[-1], hl[:, 0], hl[:, -1]])))
        for i in range(1, hn + 1):
            if i in edge: continue
            hm = hl == i
            c[hm, 0], c[hm, 1], c[hm, 2] = .07, .09, .11
            solid |= hm
    # отсвет: у пикселей рядом с прозрачностью зелёный не выше красного/синего
    near = ~solid
    for _ in range(2):
        e2 = near.copy(); e2[1:] |= near[:-1]; e2[:-1] |= near[1:]; e2[:, 1:] |= near[:, :-1]; e2[:, :-1] |= near[:, 1:]; near = e2
    edge = solid & near
    mx = np.maximum(c[..., 0], c[..., 2])
    c[..., 1] = np.where(edge, np.minimum(c[..., 1], mx * 1.04), c[..., 1])
    # сильно зелёные полупрозрачные остатки внутри (сетка забора, просветы) — тоже приглушить
    c[..., 1] = np.where(solid & (k > bk * .25), np.minimum(c[..., 1], mx * 1.1), c[..., 1])
    c[..., 3] = solid.astype(np.float32)
    ys, xs = np.nonzero(solid)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    c = c[y0:y1, x0:x1]
    o = bpy.data.images.new('o', c.shape[1], c.shape[0], alpha=True); o.alpha_mode = 'STRAIGHT'
    o.pixels = c[::-1].ravel(); o.filepath_raw = os.path.join(out, name + '.png'); o.file_format = 'PNG'; o.save()
    bpy.data.images.remove(o)
    info[name] = [int(c.shape[1]), int(c.shape[0])]
    print('PROP', name, c.shape[1], c.shape[0])
prev = {}
fp = os.path.join(out, 'sizes.json')
if os.path.exists(fp): prev = json.load(open(fp))
prev.update(info); json.dump(prev, open(fp, 'w'), indent=0)
print('DONE', len(info))
