"""Generate luxury dark-obsidian Studio AI Setup brand icons (PNG + multi-size ICO).

Usage:
    python -B brand/make_icon.py
"""
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw

SS = 4  # 4x supersampling for crisp anti-aliased edges
SIZE = 512
N = SIZE * SS

BG_TOP = (20, 25, 38)      # #141926
BG_BOT = (9, 12, 18)       # #090c12
LIME = (163, 230, 53)      # #a3e635
CYAN = (56, 189, 248)      # #38bdf8


def lerp_rgb(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def build_icon() -> Image.Image:
    canvas = Image.new("RGBA", (N, N), (0, 0, 0, 0))

    # 1. Rounded obsidian squircle background with vertical gradient
    radius = int(N * 0.23)
    bg = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    bg_px = bg.load()
    for y in range(N):
        color = lerp_rgb(BG_TOP, BG_BOT, y / (N - 1)) + (255,)
        for x in range(N):
            bg_px[x, y] = color

    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, N - 1, N - 1], radius=radius, fill=255)
    canvas.paste(bg, (0, 0), mask)

    # 2. Subtle hairline electric-lime border & inner sheen
    draw = ImageDraw.Draw(canvas)
    pad = int(N * 0.015)
    draw.rounded_rectangle(
        [pad, pad, N - 1 - pad, N - 1 - pad],
        radius=radius - pad,
        outline=LIME + (85,),
        width=max(2, int(N * 0.007)),
    )

    # 3. Ambient cyan-lime studio glow behind the 4-point emblem
    glow = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx = cy = N // 2
    max_r = int(N * 0.34)
    for r in range(max_r, 0, -4):
        t = r / max_r
        col = lerp_rgb(CYAN, LIME, t)
        alpha = int(38 * ((1.0 - t) ** 1.4))
        glow_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (alpha,))
    canvas = Image.alpha_composite(canvas, glow)

    # 4. Minimalist sharp 4-point luxury spark emblem (representing 4 Lots: Content, Video, Code, Data)
    emblem_mask = Image.new("L", (N, N), 0)
    em_draw = ImageDraw.Draw(emblem_mask)
    outer = N * 0.31
    inner = N * 0.052
    steps = 256
    points: list[tuple[float, float]] = []
    for idx in range(steps):
        theta = (2.0 * math.pi * idx) / steps
        # Sharp concave 4-point studio spark (exponential falloff from cardinal axes)
        c4 = abs(math.cos(2.0 * theta))
        radius_t = inner + (outer - inner) * (c4 ** 6.5)
        px = cx + radius_t * math.cos(theta)
        py = cy + radius_t * math.sin(theta)
        points.append((px, py))
    em_draw.polygon(points, fill=255)

    grad = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    grad_px = grad.load()
    span_min = cx - outer
    span_len = max(1.0, outer * 2.0)
    for y in range(int(cy - outer) - 2, int(cy + outer) + 3):
        for x in range(int(cx - outer) - 2, int(cx + outer) + 3):
            if 0 <= x < N and 0 <= y < N:
                t = ((x - span_min) / span_len + (y - span_min) / span_len) * 0.5
                grad_px[x, y] = lerp_rgb(LIME, CYAN, t) + (255,)

    emblem = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    emblem.paste(grad, (0, 0), emblem_mask)
    canvas = Image.alpha_composite(canvas, emblem)

    # 5. Four subtle accent nodes representing the 4 Lots around the spark
    d2 = ImageDraw.Draw(canvas)
    dot_offset = int(N * 0.19)
    dot_r = int(N * 0.017)
    dot_colors = [
        (cx - dot_offset, cy - dot_offset, LIME + (215,)),
        (cx + dot_offset, cy - dot_offset, CYAN + (215,)),
        (cx - dot_offset, cy + dot_offset, CYAN + (195,)),
        (cx + dot_offset, cy + dot_offset, LIME + (215,)),
    ]
    for dx, dy, col in dot_colors:
        d2.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=col)

    return canvas.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> int:
    brand_dir = Path(__file__).resolve().parent
    brand_dir.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    png_path = brand_dir / "studio-ai.png"
    ico_path = brand_dir / "studio-ai.ico"
    icon.save(png_path, format="PNG")
    icon.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Generated {png_path} ({png_path.stat().st_size} bytes)")
    print(f"Generated {ico_path} ({ico_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
