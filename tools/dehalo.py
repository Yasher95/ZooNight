# Снимает светлую обводку (ореол), оставшуюся по краю силуэта после вырезания фона.
# Срезается только светлый бесцветный пиксель на краю, у которого рядом внутри есть заметно более тёмный пиксель рисунка:
# так белая шерсть, носки и майка, которые сами выходят на край, не трогаются.
# Запуск отдельно: blender -b -P dehalo.py -- atlas1.png atlas2.png ...   (файлы перезаписываются)
# Из cut_alpha.py вызывается dehalo(arr) для каждого собранного атласа.
import numpy as np

LIGHT, SAT, DROP, R, PASSES = .55, .2, .2, 3, 6


def _erode(m):
    i = m.copy()
    i[1:] &= m[:-1]; i[:-1] &= m[1:]; i[:, 1:] &= m[:, :-1]; i[:, :-1] &= m[:, 1:]
    i[0] = i[-1] = False; i[:, 0] = i[:, -1] = False
    return i


def _dilate(m, r):
    o = m.copy()
    for _ in range(r):
        n = o.copy()
        n[1:] |= o[:-1]; n[:-1] |= o[1:]; n[:, 1:] |= o[:, :-1]; n[:, :-1] |= o[:, 1:]
        o = n
    return o


def _minf(v, r):
    o = v.copy()
    for _ in range(r):
        n = o.copy()
        n[1:] = np.minimum(n[1:], o[:-1]); n[:-1] = np.minimum(n[:-1], o[1:])
        n[:, 1:] = np.minimum(n[:, 1:], o[:, :-1]); n[:, :-1] = np.minimum(n[:, :-1], o[:, 1:])
        o = n
    return o


def dehalo(a):
    """a — RGBA float (h, w, 4), прямая альфа, строки сверху вниз. Меняет на месте, возвращает число снятых пикселей."""
    rgb = a[..., :3]
    mn, mx = rgb.min(2), rgb.max(2)
    luma = rgb @ np.array([.3, .59, .11], np.float32)
    light = (mn > LIGHT) & (mx - mn < SAT)
    total = 0
    for _ in range(PASSES):
        fg = a[..., 3] > .5
        inner = _erode(fg)
        dark = _minf(np.where(inner, luma, 9.0), R) < luma - DROP  # внутри рядом темнее — значит, это ореол
        cut = fg & ~inner & light & dark
        n = int(cut.sum())
        if not n:
            break
        a[cut] = 0
        total += n
    # полупрозрачная кромка, оставшаяся светлой, — гасим
    semi = (a[..., 3] > 0) & (a[..., 3] <= .5) & light
    a[semi] = 0
    return total


if __name__ == '__main__':
    import bpy, sys
    for p in sys.argv[sys.argv.index('--') + 1:]:
        im = bpy.data.images.load(p)
        w, h = im.size
        arr = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
        n = dehalo(arr)
        im.pixels = arr[::-1].ravel()
        im.filepath_raw = p
        im.file_format = 'PNG'
        im.save()
        bpy.data.images.remove(im)
        print('DEHALO', p.replace('\\', '/').split('/')[-1], n)
