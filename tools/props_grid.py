# Превью листа без зелёного фона (на тёмной шахматке) с сеткой через 100 px — чтобы снимать координаты объектов.
# blender -b -P props_grid.py -- outdir sheet1 sheet2 ...   (каждая 10-я линия сетки — жёлтая)
import bpy, sys, os, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
out, srcs = a[0], a[1:]
os.makedirs(out, exist_ok=True)
for p in srcs:
    im = bpy.data.images.load(p); w, h = im.size
    d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
    bpy.data.images.remove(im)
    r, g, b = d[..., 0], d[..., 1], d[..., 2]
    key = g - np.maximum(r, b)
    bord = np.concatenate([key[:6].ravel(), key[-6:].ravel(), key[:, :6].ravel(), key[:, -6:].ravel()])
    bk = float(np.median(bord))
    al = np.clip((bk * .55 - key) / (bk * .35), 0, 1)[..., None]
    yy, xx = np.mgrid[0:h, 0:w]
    chk = np.where(((yy // 16 + xx // 16) & 1)[..., None] == 1, .16, .1)
    rgb = d[..., :3] * al + chk * (1 - al)
    rgb[:, ::100] = [.9, .2, .9]; rgb[::100, :] = [.9, .2, .9]
    rgb[:, ::500] = [1, .9, .1]; rgb[::500, :] = [1, .9, .1]
    o = np.concatenate([rgb, np.ones((h, w, 1), np.float32)], 2)
    img = bpy.data.images.new('o', w, h, alpha=True)
    img.pixels = o[::-1].ravel(); img.filepath_raw = os.path.join(out, os.path.splitext(os.path.basename(p))[0] + '_grid.png')
    img.file_format = 'PNG'; img.save(); bpy.data.images.remove(img)
    print('GRID', p)
