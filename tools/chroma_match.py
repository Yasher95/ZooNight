# Хромакей листов на зелёном (или белом) фоне + подавление зелёного отсвета + выравнивание цвета листа по эталону.
# blender -b -P chroma_match.py -- outdir - gains.json src1 src2 ...
# gains.json: {"имя листа": {"m": [средние r,g,b], "k": [множители контраста], "t": [целевые средние]}} — без файла цвет не трогается.
# Печатает STAT (средние, разброс, насыщенность) по каждому листу — по ним считаются gains (так делали для питбуля:
# атаки выравнивали по средним и разбросу листов движения).
import bpy, sys, os, json, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
out, _ref, gfile, srcs = a[0], a[1], a[2], a[3:]
gains = json.load(open(gfile, encoding='utf-8-sig')) if os.path.exists(gfile) else {}
os.makedirs(out, exist_ok=True)
for p in srcs:
    im = bpy.data.images.load(p); w, h = im.size
    d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    r, g, b = d[..., 0], d[..., 1], d[..., 2]
    bord = np.concatenate([d[:8].reshape(-1, 4), d[-8:].reshape(-1, 4), d[:, :8].reshape(-1, 4), d[:, -8:].reshape(-1, 4)])
    bg = np.median(bord[:, :3], 0)
    if bg.min() > .8:  # белый фон
        dist = 1 - d[..., :3].min(2)
        alpha = np.clip((dist - .06) / .1, 0, 1)
    else:
        key = g - np.maximum(r, b)
        bk = float(np.median(bord[:, 1] - np.maximum(bord[:, 0], bord[:, 2])))
        alpha = np.clip((bk * .62 - key) / (bk * .35), 0, 1)
        dark = (key > bk * .25) & (d[..., :3].max(2) < bg.max() * .9)  # тени на полу — тоже фон
        alpha[dark] = 0
        d[..., 1] = np.minimum(g, np.maximum(r, b))
    d[..., 3] = alpha
    name = os.path.splitext(os.path.basename(p))[0]
    gn = gains.get(name)
    if gn:
        for c in range(3):
            d[..., c] = np.clip((d[..., c] - gn['m'][c]) * gn['k'][c] + gn['t'][c], 0, 1)
    fg = alpha > .95
    px = d[..., :3][fg]
    print('STAT', json.dumps(dict(n=name, mean=px.mean(0).round(4).tolist(), std=px.std(0).round(4).tolist(),
                                  sat=float((px.max(1) - px.min(1)).mean().round(4)), bg=bg.round(3).tolist())))
    o = bpy.data.images.new('o', w, h, alpha=True); o.alpha_mode = 'STRAIGHT'
    o.pixels = d.ravel(); o.filepath_raw = os.path.join(out, name + '.png'); o.file_format = 'PNG'; o.save()
    bpy.data.images.remove(o)
