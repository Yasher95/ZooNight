# Вырезает кадры из спрайт-листа на тёмном фоне и собирает PNG-атлас с прозрачностью.
# Запуск: blender -b -P cut_sprites.py -- <src.jpg> <out.png> <кол-во кадров> [y0 y1]
# Кадры выравниваются по ступням: якорь = (центр ячейки по X, низ ячейки).
import bpy, sys, json
import numpy as np
from collections import deque

args = sys.argv[sys.argv.index('--') + 1:]
src, out, nframes = args[0], args[1], int(args[2])
y0 = int(args[3]) if len(args) > 3 else 0
y1 = int(args[4]) if len(args) > 4 else 10 ** 6

img = bpy.data.images.load(src)
w, h = img.size
a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)[::-1, :, :3]
a = (a * 255 + .5).astype(np.int32)
y1 = min(y1, h)
val = a.max(2).astype(np.float32)
sat = (a.max(2) - a.min(2)).astype(np.float32)


def box(m, r):  # сумма в окне (2r+1)^2 через интегральное изображение
    p = np.pad(m, r, mode='edge').astype(np.float64)
    ii = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    k = 2 * r + 1
    return ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]


# локальная оценка яркости фона (виньетка)
cand = ((sat <= 9) & (val <= 75)).astype(np.float32)
cnt = box(cand, 30)
bg = np.where(cnt > 200, box(val * cand, 30) / np.maximum(cnt, 1), 35.0).astype(np.float32)

passable = (sat <= 14) & (val >= 0.5 * bg) & (val <= 1.6 * bg + 12)
# зёрна: окно 9x9 целиком похоже на фон
seeds = box(passable.astype(np.float32), 4) >= 81

filled = np.zeros((h, w), bool)
q = deque()
ys, xs = np.nonzero(seeds)
filled[ys, xs] = True
q.extend(zip(ys.tolist(), xs.tolist()))
while q:
    y, x = q.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        yy, xx = y + dy, x + dx
        if 0 <= yy < h and 0 <= xx < w and not filled[yy, xx] and passable[yy, xx]:
            filled[yy, xx] = True
            q.append((yy, xx))

def components(mask):
    lab = np.zeros(mask.shape, bool)
    res = []
    for sy, sx in zip(*np.nonzero(mask)):
        if lab[sy, sx]:
            continue
        lab[sy, sx] = True
        q = deque([(sy, sx)])
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < mask.shape[0] and 0 <= xx < mask.shape[1] and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = True
                    q.append((yy, xx))
        res.append(np.array(pts))
    return res


fg = ~filled
fg[:y0] = False
fg[y1:] = False
# мелкие дырки внутри силуэта (выеденные тёмные детали) возвращаем
holes = np.zeros((h, w), bool)
holes[y0:y1] = filled[y0:y1]
for p in components(holes):
    if len(p) < 250:
        fg[p[:, 0], p[:, 1]] = True

comps = components(fg)
big = max(len(p) for p in comps)
comps = [p for p in comps if len(p) > big * 0.15]
# слипшиеся кадры режем по самым «тонким» столбцам
medw = float(np.median([p[:, 1].max() - p[:, 1].min() for p in comps]))
split = []
for p in comps:
    xs = p[:, 1]
    k = int(round((xs.max() - xs.min()) / medw))
    if k <= 1:
        split.append(p)
        continue
    cols = np.bincount(xs - xs.min(), minlength=xs.max() - xs.min() + 1)
    cuts = [xs.min()]
    for j in range(1, k):
        c = int((xs.max() - xs.min()) * j / k)
        lo, hi = max(0, c - 30), min(len(cols), c + 30)
        cuts.append(xs.min() + lo + int(np.argmin(cols[lo:hi])))
    cuts.append(xs.max() + 1)
    for j in range(k):
        split.append(p[(xs >= cuts[j]) & (xs < cuts[j + 1])])
comps = sorted(split, key=lambda p: p[:, 1].mean())
if len(comps) != nframes:
    print('META WARNING: found', len(comps), 'frames, expected', nframes)

frames = []
for p in comps:
    ys, xs = p[:, 0], p[:, 1]
    top, bot, lft, rgt = ys.min(), ys.max(), xs.min(), xs.max()
    feet = xs[ys >= bot - (bot - top) * 0.08]
    ax = int(round((feet.min() + feet.max()) / 2))
    frames.append(dict(p=p, top=top, bot=bot, lft=lft, rgt=rgt, ax=ax))

half = max(max(f['ax'] - f['lft'], f['rgt'] - f['ax']) for f in frames) + 4
ch = max(f['bot'] - f['top'] for f in frames) + 8
cw = half * 2
sheet = np.zeros((ch, cw * len(frames), 4), np.float32)
for i, f in enumerate(frames):
    ys, xs = f['p'][:, 0], f['p'][:, 1]
    oy = ys - f['bot'] + ch - 3
    ox = xs - f['ax'] + half + i * cw
    sheet[oy, ox, :3] = a[ys, xs] / 255.0
    sheet[oy, ox, 3] = 1.0


def save(arr, path):
    hh, ww = arr.shape[:2]
    im = bpy.data.images.new('o', ww, hh, alpha=True)
    im.alpha_mode = 'STRAIGHT'
    im.pixels = arr[::-1].ravel()
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


save(sheet, out)
prev = sheet.copy()
m = prev[:, :, 3] == 0
prev[m] = (0.1, 0.9, 0.2, 1)
save(prev, out.replace('.png', '_preview.png'))
print('META', json.dumps(dict(frames=len(frames), cw=int(cw), ch=int(ch), sizes=[len(f['p']) for f in frames],
                              heights=[int(f['bot'] - f['top']) for f in frames])))
