"""
seed_assets.py – Generate seeded banner and project-cover images as JPEG.

Uses only Pillow so the output format (.jpg) matches real user-uploaded files.
Gradients are built efficiently using numpy or a fast row-by-row approach.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

ROOT = Path(__file__).resolve().parent
BANNERS_DIR = ROOT / "static" / "banners"
PROJECTS_DIR = ROOT / "static" / "projects"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ---------------------------------------------------------------------------
# Gradient builder
# ---------------------------------------------------------------------------

def _make_gradient(width: int, height: int, c1: tuple, c2: tuple) -> Image.Image:
    """Diagonal gradient from top-left (c1) to bottom-right (c2)."""
    if _HAS_NUMPY:
        xs = np.linspace(0.0, 1.0, width,  dtype=np.float32)
        ys = np.linspace(0.0, 1.0, height, dtype=np.float32)
        t = (xs[np.newaxis, :] + ys[:, np.newaxis]) * 0.5  # (H, W) in [0,1]
        arr = np.empty((height, width, 3), dtype=np.uint8)
        for ch in range(3):
            arr[:, :, ch] = np.clip(c1[ch] + (c2[ch] - c1[ch]) * t, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, "RGB")
    else:
        # Row-by-row fallback (much faster than pixel-by-pixel)
        img = Image.new("RGB", (width, height))
        for y in range(height):
            fy = y / (height - 1) if height > 1 else 0.0
            row = []
            for x in range(width):
                t = (x / (width - 1) + fy) * 0.5 if width > 1 else fy
                row.extend([
                    int(c1[0] + (c2[0] - c1[0]) * t),
                    int(c1[1] + (c2[1] - c1[1]) * t),
                    int(c1[2] + (c2[2] - c1[2]) * t),
                ])
        return img


# ---------------------------------------------------------------------------
# Orb helper (soft radial glow)
# ---------------------------------------------------------------------------

def _orb_simple(img: Image.Image, cx: int, cy: int, r: int, accent: tuple, opacity: float) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    steps = 16
    for i in range(steps, 0, -1):
        frac = i / steps
        radius = int(r * frac)
        alpha = int(255 * opacity * (1 - frac) ** 0.5 * 0.55)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     fill=accent + (alpha,))


# ---------------------------------------------------------------------------
# Grid overlay (drawn row by row – cheap)
# ---------------------------------------------------------------------------

def _grid_overlay(width: int, height: int, step: int = 40, alpha: int = 14) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    col = (255, 255, 255, alpha)
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height - 1)], fill=col, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width - 1, y)], fill=col, width=1)
    return img


# ---------------------------------------------------------------------------
# Dot pattern overlay (tile approach – cheap)
# ---------------------------------------------------------------------------

def _dot_overlay(width: int, height: int, step: int = 24, alpha: int = 18) -> Image.Image:
    """Build a small tile and paste it across the canvas."""
    tile = Image.new("RGBA", (step, step), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.ellipse([1, 1, 3, 3], fill=(255, 255, 255, alpha))
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y in range(0, height, step):
        for x in range(0, width, step):
            out.paste(tile, (x, y))
    return out


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_FONT_BOLD = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
_FONT_REG = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (_FONT_BOLD if bold else _FONT_REG):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Banner data
# ---------------------------------------------------------------------------

BANNERS_DATA = [
    {"id": "evt_01", "title": "Sample Hack 2026",          "tagline": "Developer Tooling, APIs & Systems Architecture",          "color1": "#1e1b4b", "color2": "#312e81", "accent": "#6366f1", "badge": "COMPLETED",          "icon": "\u26a1"},
    {"id": "evt_02", "title": "GreenBuild Hackathon",       "tagline": "Climate Tech, Carbon Accounting & Clean Energy Grid",    "color1": "#064e3b", "color2": "#047857", "accent": "#10b981", "badge": "COMPLETED",          "icon": "\U0001f331"},
    {"id": "evt_03", "title": "AI for Health Hackathon",    "tagline": "Diagnostics, Medical Imaging AI & Patient Wellbeing",    "color1": "#4c0519", "color2": "#9f1239", "accent": "#f43f5e", "badge": "COMPLETED",          "icon": "\U0001f9ec"},
    {"id": "evt_04", "title": "SecureIndia Cyber Sprint",   "tagline": "Zero-Trust Architecture, AppSec & Threat Defense",       "color1": "#18181b", "color2": "#27272a", "accent": "#0ea5e9", "badge": "COMPLETED",          "icon": "\U0001f6e1"},
    {"id": "evt_05", "title": "EduForge Global Challenge",  "tagline": "Adaptive Learning, Interactive STEM & Education Tech",   "color1": "#7c2d12", "color2": "#c2410c", "accent": "#f97316", "badge": "COMPLETED",          "icon": "\U0001f393"},
    {"id": "evt_06", "title": "CloudScale Builders 2026",   "tagline": "Distributed Systems, Microservices & Edge Automation",   "color1": "#0c4a6e", "color2": "#0284c7", "accent": "#38bdf8", "badge": "ONGOING NOW",        "icon": "\u2601"},
    {"id": "evt_07", "title": "DevCraft Web3 & AI Jam",     "tagline": "Autonomous Agents, Verifiable Workflows & Protocols",    "color1": "#581c87", "color2": "#7e22ce", "accent": "#c084fc", "badge": "ONGOING NOW",        "icon": "\U0001f916"},
    {"id": "evt_08", "title": "NextGen Mobility Hack 2026", "tagline": "Autonomous Transit, EV Infrastructure & Micromobility",  "color1": "#134e4a", "color2": "#0d9488", "accent": "#2dd4bf", "badge": "REGISTRATIONS OPEN", "icon": "\U0001f680"},
    {"id": "evt_09", "title": "FinTech Fusion 2026",        "tagline": "Open Banking, Real-Time Fraud Defense & Wealth AI",      "color1": "#172554", "color2": "#1d4ed8", "accent": "#f59e0b", "badge": "REGISTRATIONS OPEN", "icon": "\U0001f4b3"},
    {"id": "evt_10", "title": "BioTech Horizon Summit",     "tagline": "Genomics Pipelines, Drug Discovery & Lab Automation",    "color1": "#042f2e", "color2": "#115e59", "accent": "#14b8a6", "badge": "REGISTRATIONS OPEN", "icon": "\U0001f52c"},
]

PALETTES = [
    ("#1e293b", "#0f172a", "#38bdf8", "\u26a1"),
    ("#064e3b", "#022c22", "#34d399", "\U0001f331"),
    ("#4c0519", "#2e020d", "#fb7185", "\U0001f9ec"),
    ("#312e81", "#1e1b4b", "#818cf8", "\U0001f680"),
    ("#581c87", "#3b0764", "#c084fc", "\U0001f916"),
    ("#7c2d12", "#431407", "#fb923c", "\U0001f525"),
    ("#14532d", "#052e16", "#4ade80", "\U0001f340"),
    ("#164e63", "#083344", "#22d3ee", "\U0001f48e"),
    ("#1e1b4b", "#0f172a", "#a78bfa", "\U0001f52e"),
    ("#172554", "#0a192f", "#60a5fa", "\U0001f4a1"),
]


# ---------------------------------------------------------------------------
# Banner generator
# ---------------------------------------------------------------------------

def generate_banner_jpeg(item: dict) -> bytes:
    W, H = 1200, 400
    c1 = _hex(item["color1"])
    c2 = _hex(item["color2"])
    accent = _hex(item["accent"])

    base = _make_gradient(W, H, c1, c2).convert("RGBA")
    base = Image.alpha_composite(base, _grid_overlay(W, H))

    orb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _orb_simple(orb, 1050, 80,  180, accent, 0.28)
    _orb_simple(orb, 150,  350, 150, accent, 0.16)
    base = Image.alpha_composite(base, orb)

    bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rounded_rectangle([60, 60, 66, 340], radius=3, fill=accent + (230,))
    base = Image.alpha_composite(base, bar)

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(txt)

    # Badge
    bf = _font(13)
    td.rounded_rectangle([80, 72, 275, 106], radius=17, fill=(255, 255, 255, 30), outline=accent + (200,), width=1)
    td.ellipse([96, 83, 106, 93], fill=accent + (255,))
    td.text((112, 80), item["badge"], font=bf, fill=(255, 255, 255, 230))

    # Title
    td.text((80, 128), f"{item['icon']} {item['title']}", font=_font(44), fill=(255, 255, 255, 255))

    # Tagline
    td.text((80, 192), item["tagline"], font=_font(20, bold=False), fill=(255, 255, 255, 210))

    # Chips
    chipf = _font(13, bold=False)
    for label, ox in [("Teams of 1-3", 0), ("5 Judges", 155), ("10+ Projects", 310)]:
        td.rounded_rectangle([80 + ox, 268, 80 + ox + 140, 302], radius=8,
                              fill=(0, 0, 0, 64), outline=(255, 255, 255, 26), width=1)
        td.text((80 + ox + 14, 278), label, font=chipf, fill=(203, 213, 225, 220))

    base = Image.alpha_composite(base, txt)
    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Project cover generator
# ---------------------------------------------------------------------------

def generate_project_cover_jpeg(project_id: str, title: str, tech_stack: str, track_name: str) -> bytes:
    W, H = 800, 450
    idx = sum(ord(c) for c in project_id) % len(PALETTES)
    c1_h, c2_h, accent_h, icon = PALETTES[idx]
    c1 = _hex(c1_h)
    c2 = _hex(c2_h)
    accent = _hex(accent_h)

    base = _make_gradient(W, H, c1, c2).convert("RGBA")
    base = Image.alpha_composite(base, _dot_overlay(W, H))

    # Glass card
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle(
        [40, 40, W - 40, H - 40], radius=16,
        fill=(255, 255, 255, 10), outline=(255, 255, 255, 30), width=2,
    )
    base = Image.alpha_composite(base, card)

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(txt)

    # Track tag
    clean_track = (track_name or "General")[:28]
    td.rounded_rectangle([70, 73, 250, 101], radius=14,
                          fill=accent + (38,), outline=accent + (200,), width=1)
    td.text((84, 79), clean_track, font=_font(12), fill=accent + (255,))

    # Icon
    td.ellipse([70, 128, 142, 200], fill=(255, 255, 255, 20), outline=accent + (180,), width=2)
    td.text((106, 164), icon, font=_font(26), fill=(255, 255, 255, 240), anchor="mm")

    # Title
    td.text((160, 138), title[:30], font=_font(32), fill=(255, 255, 255, 255))

    # Tech
    td.text((160, 180), f"* {tech_stack[:38]}", font=_font(14, bold=False), fill=accent + (255,))

    # Divider
    td.line([(70, 280), (730, 280)], fill=(255, 255, 255, 26), width=1)

    # Badges
    bf = _font(13, bold=False)
    td.rounded_rectangle([70, 313, 215, 349], radius=8, fill=(0, 0, 0, 76))
    td.text((86, 323), "* Production Ready", font=bf, fill=(148, 163, 184, 220))
    td.rounded_rectangle([230, 313, 365, 349], radius=8, fill=(0, 0, 0, 76))
    td.text((246, 323), "# Open Source", font=bf, fill=(148, 163, 184, 220))

    base = Image.alpha_composite(base, txt)
    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_all_assets(projects_meta: list[dict] | None = None) -> None:
    BANNERS_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    for b in BANNERS_DATA:
        fp = BANNERS_DIR / f"{b['id']}.jpg"
        if not fp.exists():
            fp.write_bytes(generate_banner_jpeg(b))

    if projects_meta:
        for p in projects_meta:
            fp = PROJECTS_DIR / f"{p['id']}.jpg"
            if not fp.exists():
                fp.write_bytes(
                    generate_project_cover_jpeg(
                        project_id=p["id"],
                        title=p.get("title", "Project"),
                        tech_stack=p.get("tech_stack", "Python, FastAPI"),
                        track_name=p.get("track_name", "Innovation"),
                    )
                )


if __name__ == "__main__":
    ensure_all_assets()
    print("Static banner and project assets verified (JPEG).")
