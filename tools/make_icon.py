"""Generate the app icon (clean flat 'document + download' mark).

Run:  python tools/make_icon.py
Writes:
  src/harvester/resources/icon.png   (256x256, bundled window icon)
  packaging/icon.ico                 (multi-size, used by PyInstaller)

Programmatically drawn with Pillow (no external art assets).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SS = 4  # supersampling factor for anti-aliasing


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_icon(size: int) -> Image.Image:
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # rounded-rect background with a vertical blue gradient
    top, bottom = (45, 108, 223), (26, 71, 158)
    grad = Image.new("RGB", (1, S))
    for y in range(S):
        grad.putpixel((0, y), _lerp(top, bottom, y / max(1, S - 1)))
    grad = grad.resize((S, S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)

    # white document sheet
    dx0, dy0, dx1, dy1 = int(S * 0.28), int(S * 0.20), int(S * 0.72), int(S * 0.80)
    draw.rounded_rectangle([dx0, dy0, dx1, dy1], radius=int(S * 0.05),
                           fill=(255, 255, 255, 255))
    # text lines on the sheet
    line_c = (203, 213, 225, 255)
    lh = int(S * 0.045)
    for i, frac in enumerate((0.30, 0.42, 0.54, 0.66)):
        w_end = dx1 - int(S * 0.09) if i % 2 == 0 else dx1 - int(S * 0.20)
        draw.rounded_rectangle([dx0 + int(S * 0.07), int(S * frac),
                                w_end, int(S * frac) + lh],
                               radius=lh // 2, fill=line_c)

    # green download badge (circle + arrow) bottom-right
    r = int(S * 0.20)
    cx, cy = int(S * 0.70), int(S * 0.72)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(34, 197, 94, 255),
                 outline=(255, 255, 255, 255), width=int(S * 0.015))
    stem_w = int(r * 0.28)
    draw.rectangle([cx - stem_w // 2, cy - int(r * 0.55),
                    cx + stem_w // 2, cy + int(r * 0.15)], fill=(255, 255, 255, 255))
    ah = int(r * 0.5)
    draw.polygon([(cx - int(r * 0.45), cy - int(r * 0.05)),
                  (cx + int(r * 0.45), cy - int(r * 0.05)),
                  (cx, cy + ah)], fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    png_path = ROOT / "src" / "harvester" / "resources" / "icon.png"
    ico_path = ROOT / "packaging" / "icon.ico"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    ico_path.parent.mkdir(parents=True, exist_ok=True)

    base = draw_icon(256)
    base.save(png_path)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(ico_path, sizes=sizes)
    print(f"wrote {png_path}")
    print(f"wrote {ico_path}")


if __name__ == "__main__":
    main()
