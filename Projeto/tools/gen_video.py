#!/usr/bin/env python3
"""Gera vídeos MJPEG de teste no formato do livro (5 bytes de tamanho + JPEG).

Cada frame mostra o nome da stream, o nº da frame e uma barra animada. Assim
vê-se logo no cliente que stream está a chegar e se há saltos (perdas).

Uso:
    python3 tools/gen_video.py videos/filmeA.Mjpeg "Filme A" --color 200,40,40
"""

import argparse
import io
import math

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for f in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("title")
    ap.add_argument("--color", default="40,90,200")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--size", default="384x216")
    ap.add_argument("--quality", type=int, default=60)
    a = ap.parse_args()
    w, h = map(int, a.size.split("x"))
    base = tuple(int(c) for c in a.color.split(","))
    big, small = font(30), font(16)
    with open(a.out, "wb") as out:
        for i in range(a.frames):
            k = 0.75 + 0.25 * math.sin(2 * math.pi * i / a.frames)
            img = Image.new("RGB", (w, h), tuple(int(c * k) for c in base))
            d = ImageDraw.Draw(img)
            d.text((16, 16), a.title, fill="white", font=big)
            d.text((16, 60), f"frame {i + 1:04d}/{a.frames}", fill="white", font=small)
            x = int((w - 40) * i / (a.frames - 1))
            d.rectangle([x, h - 40, x + 40, h - 16], fill="white")
            d.rectangle([0, h - 10, int(w * (i + 1) / a.frames), h], fill=(255, 220, 0))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=a.quality)
            data = buf.getvalue()
            out.write(b"%05d" % len(data))
            out.write(data)
    print(f"{a.out}: {a.frames} frames")


if __name__ == "__main__":
    main()
