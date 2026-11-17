# Зоны ходьбы прохождения из зелёных разметок автора: для каждого столбца (шаг 8 экранных px) — верх и низ
# зелёной полосы в экранных px картинки высотой 540. Печатает строку JS для поля band комнаты.
# blender -b -P walk_bands.py -- <папка «режим на прохождение»>
import bpy, sys, os, json, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
src = a[0]
JOBS = {
    'hall': ('коридор/разметка.png', 'коридор/коридор.png'),
    'street': ('улица/разметка.png', 'улица/локация.png'),
    'metro': ('метро/разметка.png', 'метро/метро.png'),
    'c2_tunnel': ('перегон4/разметка.png', 'перегон4/локация.png'),
    'c2_booth': ('перегон4/комната обходчика/разметка.png', 'перегон4/комната обходчика/локация.png'),
    'c2_depot': ('локация за металической решеткой/разметка.png', 'локация за металической решеткой/локация.png'),
    'c2_wagon2': ('вагон с ключем/разметка.png', 'вагон с ключем/Генеративная заливка 2.png'),
    'c2_axe': ('вагон с топором/разметка.png', 'вагон с топором/вагон с топором.png'),
    'c2_wagon': ('вагон ножи/рамзетка и размер перса.png', 'вагон ножи/локация.png'),
}
STEP = 8
for name, (mp, lp) in JOBS.items():
    im = bpy.data.images.load(os.path.join(src, mp)); w, h = im.size
    d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(im)
    li = bpy.data.images.load(os.path.join(src, lp)); lw, lh = li.size; bpy.data.images.remove(li)
    # зелёная заливка разметки (бывает полупрозрачной поверх картинки): зелёный заметно сильнее красного и синего
    g = (d[..., 1] - np.maximum(d[..., 0], d[..., 2]) > .25) & (d[..., 1] > .35)
    if '--probe' in a:
        ex = d[..., 1] - np.maximum(d[..., 0], d[..., 2]); print('PROBE', name, 'max green excess', ex.max(), 'px>.25', (ex > .25).sum(), 'px>.15', (ex > .15).sum())
    s = 540 / h; W = w * s
    n = int(W // STEP) + 1; t, b = [], []
    for i in range(n):
        x0, x1 = int(i * STEP / s), min(w, int((i + 1) * STEP / s))
        col = g[:, x0:x1].any(1) if x1 > x0 else np.zeros(h, bool)
        ys = np.nonzero(col)[0]
        if len(ys) < 3: t.append(-1); b.append(-1)
        else: t.append(round(ys.min() * s)); b.append(round(ys.max() * s))
    # сгладить выбросы: медиана по 3 соседям
    def med(v):
        o = v[:]
        for i in range(1, len(v) - 1):
            tri = [v[i - 1], v[i], v[i + 1]]
            if -1 in tri: continue
            o[i] = sorted(tri)[1]
        return o
    t, b = med(t), med(b)
    ok = [i for i in range(n) if t[i] >= 0]
    print('BAND', name, 'size', w, h, 'loc', lw, lh, 'x', ok[0] * STEP, ok[-1] * STEP, 'y', min(t[i] for i in ok), max(b[i] for i in ok))
    print('JS', name, json.dumps({'step': STEP, 't': t, 'b': b}, separators=(',', ':')))
