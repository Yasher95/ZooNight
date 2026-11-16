# Нарезка ассетов прохождения с листов на зелёном фоне: хромакей + подавление отсвета + поиск отдельных объектов.
# blender -b -P props_extract.py -- outdir sheet1 sheet2 ...
# Для каждого листа: outdir/<лист>_<n>.png (обрезанный объект) и строка JSON в outdir/index.json:
# имя, рамка (x,y,w,h) на листе, доля полупрозрачных пикселей (soft — у размытых «призраков» высокая), резкость.
import bpy, sys, os, json, numpy as np
from collections import deque
a = sys.argv[sys.argv.index('--') + 1:]
out, srcs = a[0], a[1:]
os.makedirs(out, exist_ok=True)
index = []
for p in srcs:
    im = bpy.data.images.load(p); w, h = im.size
    d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()  # сверху вниз
    bpy.data.images.remove(im)
    r, g, b = d[..., 0], d[..., 1], d[..., 2]
    key = g - np.maximum(r, b)
    bord = np.concatenate([key[:6].ravel(), key[-6:].ravel(), key[:, :6].ravel(), key[:, -6:].ravel()])
    bk = float(np.median(bord))
    alpha = np.clip((bk * .55 - key) / (bk * .35), 0, 1)
    d[..., 1] = np.where(key > 0, np.maximum(r, b) + np.minimum(key, .02), g)  # зелёный отсвет на краях — убрать
    d[..., 3] = alpha
    name = os.path.splitext(os.path.basename(p))[0]
    # маска объектов (уменьшенная в 2 раза), чуть раздутая — чтобы тонкие детали (сетка, провода) не рвали объект на куски
    m = alpha > .5
    hm, wm = h // 2, w // 2
    m2 = m[:hm * 2, :wm * 2].reshape(hm, 2, wm, 2).any(axis=(1, 3))
    dm = m2.copy()
    for _ in range(3):
        e = dm.copy()
        e[1:] |= dm[:-1]; e[:-1] |= dm[1:]; e[:, 1:] |= dm[:, :-1]; e[:, :-1] |= dm[:, 1:]
        dm = e
    lab = np.zeros(dm.shape, np.int32); n = 0
    ys, xs = np.nonzero(dm)
    for sy, sx in zip(ys, xs):
        if lab[sy, sx]: continue
        n += 1; q = deque([(sy, sx)]); lab[sy, sx] = n
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < hm and 0 <= xx < wm and dm[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; q.append((yy, xx))
    k = 0
    for i in range(1, n + 1):
        yy, xx = np.nonzero(lab == i)
        y0, y1, x0, x1 = yy.min() * 2, (yy.max() + 1) * 2, xx.min() * 2, (xx.max() + 1) * 2
        if (y1 - y0) * (x1 - x0) < 1800: continue
        part = (lab[y0 // 2:y1 // 2, x0 // 2:x1 // 2] == i).repeat(2, 0).repeat(2, 1)
        crop = d[y0:y1, x0:x1].copy()
        crop[..., 3] *= part[:crop.shape[0], :crop.shape[1]]
        al = crop[..., 3]
        solid = (al > .95).sum(); soft = ((al > .05) & (al <= .95)).sum()
        if solid < 400: continue
        lum = crop[..., :3].mean(2)
        sharp = float(np.abs(np.diff(lum, axis=1))[al[:, 1:] > .95].mean()) if solid else 0
        k += 1; fn = f'{name}_{k:02d}.png'
        o = bpy.data.images.new('o', x1 - x0, y1 - y0, alpha=True); o.alpha_mode = 'STRAIGHT'
        o.pixels = crop[::-1].ravel(); o.filepath_raw = os.path.join(out, fn); o.file_format = 'PNG'; o.save()
        bpy.data.images.remove(o)
        index.append(dict(f=fn, sheet=name, box=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
                          soft=round(float(soft / max(1, solid + soft)), 3), sharp=round(sharp, 4)))
    print('SHEET', name, 'objects', k)
json.dump(index, open(os.path.join(out, 'index.json'), 'w'), indent=0)
print('DONE', len(index))
