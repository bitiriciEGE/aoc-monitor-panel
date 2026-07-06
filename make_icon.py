"""Uygulama ikonu uretir: koyu arka plan uzerinde cyan cerceveli monitor."""
import os
from PIL import Image, ImageDraw

sizes = [16, 32, 48, 64, 128, 256]
imgs = []
for s in sizes:
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = max(1, s // 16)          # kenar payi
    r = max(2, s // 8)           # kose yaricapi
    lw = max(1, s // 20)
    # arka kare
    d.rounded_rectangle([m, m, s - m, s - m], radius=r, fill=(7, 7, 12, 255),
                        outline=(0, 212, 255, 255), width=lw)
    # ekran
    sx0, sy0 = int(s * 0.22), int(s * 0.24)
    sx1, sy1 = int(s * 0.78), int(s * 0.60)
    d.rectangle([sx0, sy0, sx1, sy1], outline=(255, 255, 255, 255), width=lw)
    d.rectangle([sx0 + lw, sy0 + lw, int(s * 0.5), int(s * 0.42)],
                fill=(0, 212, 255, 180))
    # ayak
    cx = s // 2
    d.rectangle([cx - lw, sy1, cx + lw, int(s * 0.72)], fill=(255, 255, 255, 255))
    d.rectangle([int(s * 0.35), int(s * 0.72), int(s * 0.65), int(s * 0.72) + lw * 2],
                fill=(255, 255, 255, 255))
    imgs.append(img)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
imgs[-1].save(out, sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
print("icon.ico OK")
