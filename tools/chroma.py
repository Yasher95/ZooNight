# зелёный фон -> прозрачность (с подавлением зелёной каймы); сохраняет PNG
import bpy, sys, numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
im = bpy.data.images.load(a[0]); w, h = im.size
d = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
r, g, b = d[..., 0], d[..., 1], d[..., 2]
key = g - np.maximum(r, b)
alpha = np.clip(1 - (key - .12) / .25, 0, 1)
d[..., 3] = alpha
spill = g > np.maximum(r, b)
d[..., 1] = np.where(spill, np.maximum(r, b), g)  # убираем зелёный отсвет на краях
out = bpy.data.images.new('o', w, h, alpha=True); out.alpha_mode = 'STRAIGHT'
out.pixels = d.ravel(); out.filepath_raw = a[1]; out.file_format = 'PNG'; out.save()
print('CHROMA ok', w, h, float((alpha > .5).mean()))
