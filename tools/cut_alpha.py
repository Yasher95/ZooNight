# Режет спрайт-листы с прозрачным фоном (PNG с альфой) на кадры и собирает атласы.
# Запуск: blender -b -P cut_alpha.py -- jobs.json
# jobs.json: {"out": "<папка>", "overview": "<папка для обзорных картинок>",
#             "jobs": [{"src": "...png", "name": "horseman_jab", "frames": 4, "anchor": "feet"|"box"}]}
# anchor feet — якорь по ступням (середина нижних 8% силуэта), box — по середине габарита (кадры в воздухе).
import bpy, sys, json, os
import numpy as np
from collections import deque

cfg = json.load(open(sys.argv[sys.argv.index('--') + 1], encoding='utf-8'))
DS = 2  # связные области ищем на уменьшенной маске — быстрее


def components(mask):
    lab = np.zeros(mask.shape, np.int32)
    n = 0
    H, W = mask.shape
    for sy, sx in zip(*np.nonzero(mask)):
        if lab[sy, sx]:
            continue
        n += 1
        lab[sy, sx] = n
        q = deque([(sy, sx)])
        while q:
            y, x = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def save(arr, path):
    hh, ww = arr.shape[:2]
    im = bpy.data.images.new('o', ww, hh, alpha=True)
    im.alpha_mode = 'STRAIGHT'
    im.pixels = arr[::-1].ravel()
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def shed(p, need):
    """Делит слипшиеся кадры: сжимаем силуэт, пока не распадётся на части, потом растим части обратно."""
    K = 3
    y0, x0 = p[:, 0].min(), p[:, 1].min()
    sy, sx = (p[:, 0] - y0) // K + 1, (p[:, 1] - x0) // K + 1
    m = np.zeros((sy.max() + 2, sx.max() + 2), bool)
    m[sy, sx] = True
    e = m.copy()
    for it in range(40):
        e = e & np.roll(e, 1, 0) & np.roll(e, -1, 0) & np.roll(e, 1, 1) & np.roll(e, -1, 1)
        if not e.any():
            return None
        lab, n = components(e)
        sz = np.bincount(lab.ravel(), minlength=n + 1)
        sz[0] = 0
        big = [i for i in np.argsort(-sz) if sz[i] > e.sum() * 0.1][:need]
        if len(big) >= 2:
            break
    else:
        return None
    out = np.zeros(m.shape, np.int32)
    q = deque()
    for k, i in enumerate(big):
        ys, xs = np.nonzero(lab == i)
        out[ys, xs] = k + 1
        q.extend(zip(ys.tolist(), xs.tolist()))
    while q:
        y, x = q.popleft()
        v = out[y, x]
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if m[yy, xx] and not out[yy, xx]:
                out[yy, xx] = v
                q.append((yy, xx))
    l = out[sy, sx]
    return [p[l == k + 1] for k in range(len(big))]


rows = []
for job in cfg['jobs']:
    img = bpy.data.images.load(job['src'])
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img)
    fg = a[:, :, 3] > 0.5
    # dewhite: N — снять белую обводку: N раз срезаем с края силуэта почти белые пиксели
    for it in range(job.get('dewhite', 0)):
        inner = fg.copy()
        inner[1:] &= fg[:-1]; inner[:-1] &= fg[1:]; inner[:, 1:] &= fg[:, :-1]; inner[:, :-1] &= fg[:, 1:]
        inner[0] = inner[-1] = False; inner[:, 0] = inner[:, -1] = False
        rgb = a[:, :, :3]
        mn, mx = rgb.min(2), rgb.max(2)
        thr = job.get('white', 0.8)
        white = (mn > thr) & (mx - mn < 0.14)
        fg &= ~((fg & ~inner) & white)
    for it in range(job.get('erode', 0)):  # остаток светлого канта: срезаем край целиком
        inner = fg.copy()
        inner[1:] &= fg[:-1]; inner[:-1] &= fg[1:]; inner[:, 1:] &= fg[:, :-1]; inner[:, :-1] &= fg[:, 1:]
        fg = inner
    hs, ws = (h + DS - 1) // DS, (w + DS - 1) // DS
    pad = np.zeros((hs * DS, ws * DS), bool)
    pad[:h, :w] = fg
    small = pad.reshape(hs, DS, ws, DS).any(axis=(1, 3))
    lab, n = components(small)
    full = np.repeat(np.repeat(lab, DS, 0), DS, 1)[:h, :w] * fg
    sizes = np.bincount(full.ravel(), minlength=n + 1)
    sizes[0] = 0
    keep = [i for i in range(1, n + 1) if sizes[i] > sizes.max() * 0.15]
    comps = [np.argwhere(full == i) for i in keep]
    want = job.get('frames')
    # слипшиеся кадры режем пополам по самому «тонкому» столбцу
    while want and len(comps) < want:
        j = int(np.argmax([p[:, 1].max() - p[:, 1].min() for p in comps]))
        p = comps.pop(j)
        parts = shed(p, want - len(comps)) if job.get('shed') else None
        if parts:
            comps += parts
            continue
        xs = p[:, 1]
        cols = np.bincount(xs - xs.min(), minlength=xs.max() - xs.min() + 1)
        if job.get('valley'):  # самый тонкий столбец во всей области (кадров слиплось больше двух)
            lo, hi = int(len(cols) * .12), int(len(cols) * .88)
        else:
            c = len(cols) // 2
            lo, hi = max(0, c - 60), min(len(cols), c + 60)
        cut = xs.min() + lo + int(np.argmin(cols[lo:hi]))
        comps.append(p[xs < cut])
        comps.append(p[xs >= cut])
    nrows = job.get('rows', 1)
    comps.sort(key=lambda p: (int(p[:, 0].mean() * nrows / h), p[:, 1].mean()))
    # stand — высота стойки в исходнике; все листы приводятся к одной высоте стойки STAND
    STAND = 377.0
    st = job.get('stand')
    if st == 'f-1':  # последний кадр листа — стойка
        st = float(comps[-1][:, 0].max() - comps[-1][:, 0].min())
    if st == 'f0':  # первый кадр листа — стойка
        st = float(comps[0][:, 0].max() - comps[0][:, 0].min())
    s = STAND / st if st else 1.0
    def resize(src, s):
        b = int(1 / s)
        if b >= 2:  # сильное уменьшение: сначала усредняем блоками, иначе рябь
            hh, ww = src.shape[0] // b * b, src.shape[1] // b * b
            src = src[:hh, :ww].reshape(hh // b, b, ww // b, b, 4).mean(axis=(1, 3))
            s *= b
        hh, ww = src.shape[:2]
        nh, nw = max(1, int(round(hh * s))), max(1, int(round(ww * s)))
        yy = np.clip((np.arange(nh) + .5) / s - .5, 0, hh - 1)
        xx = np.clip((np.arange(nw) + .5) / s - .5, 0, ww - 1)
        y0 = np.floor(yy).astype(int); x0 = np.floor(xx).astype(int)
        y1 = np.minimum(y0 + 1, hh - 1); x1 = np.minimum(x0 + 1, ww - 1)
        fy = (yy - y0)[:, None, None]; fx = (xx - x0)[None, :, None]
        return (src[y0][:, x0] * (1 - fy) * (1 - fx) + src[y0][:, x1] * (1 - fy) * fx +
                src[y1][:, x0] * fy * (1 - fx) + src[y1][:, x1] * fy * fx)

    frames = []
    for p in comps:
        ys, xs = p[:, 0], p[:, 1]
        top, bot, lft, rgt = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
        if job.get('anchor') == 'box':
            ax = (lft + rgt) / 2
        else:
            feet = xs[ys >= bot - (bot - top) * 0.08]
            ax = (int(feet.min()) + int(feet.max())) / 2
        crop = np.zeros((bot - top + 1, rgt - lft + 1, 4), np.float32)
        crop[ys - top, xs - lft, :3] = a[ys, xs, :3]  # премультиплицированный цвет
        crop[ys - top, xs - lft, 3] = 1.0
        if s != 1.0:
            crop = resize(crop, s)
        frames.append(dict(im=crop, ax=int(round((ax - lft) * s)), h0=bot - top, bot=bot))
    half = max(max(f['ax'], f['im'].shape[1] - f['ax']) for f in frames) + 3
    # baseline — общая линия пола листа: кадры в прыжке остаются приподнятыми
    base = max(f['bot'] for f in frames)
    for f in frames:
        f['up'] = int(round((base - f['bot']) * s)) if job.get('baseline') else 0
    ch = max(f['im'].shape[0] + f['up'] for f in frames) + 6
    cw = half * 2
    sheet = np.zeros((ch, cw * len(frames), 4), np.float32)
    for i, f in enumerate(frames):
        im = f['im']
        al = np.maximum(im[:, :, 3:4], 1e-6)
        im = np.concatenate([np.clip(im[:, :, :3] / al, 0, 1), im[:, :, 3:4]], 2)
        y = ch - 3 - im.shape[0] - f['up']
        x = i * cw + half - f['ax']
        sheet[y:y + im.shape[0], x:x + im.shape[1]] = im
    save(sheet, os.path.join(cfg['out'], job['name'] + '.png'))
    print('META', json.dumps(dict(name=job['name'], frames=len(frames), want=want, cw=int(cw), ch=int(ch),
                                  heights=[int(f['h0']) for f in frames])))
    d = 2 if s != 1.0 else 3
    pv = sheet[::d, ::d].copy()
    pv[pv[:, :, 3] < .5] = (0.1, 0.9, 0.2, 1)
    pv[:, :, 3] = 1
    for i in range(1, len(frames)):
        pv[:, i * cw // d] = (1, 0, 1, 1)
    rows.append(pv)
if cfg.get('overview'):
    per = 5
    for k in range(0, len(rows), per):
        grp = rows[k:k + per]
        W = max(r.shape[1] for r in grp)
        out = np.zeros((sum(r.shape[0] + 6 for r in grp), W, 4), np.float32)
        out[:, :, 3] = 1
        y = 0
        for r in grp:
            out[y:y + r.shape[0], :r.shape[1]] = r
            y += r.shape[0] + 6
        save(out, os.path.join(cfg['overview'], 'overview_%d.png' % (k // per)))
