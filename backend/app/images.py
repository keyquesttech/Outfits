"""Photo pipeline: normalise uploads, build thumbnails, extract a colour palette.

Colour extraction is plain image processing, not AI — it works with no API key and
no model, and it runs in well under a second on a Pi 4.
"""

import io
import math
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from . import config
from .constants import COLOUR_NAMES, DARK_COLOURS, LIGHT_COLOURS

try:  # iPhone photos arrive as HEIC; register the opener when available.
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - optional dependency
    HEIF_SUPPORTED = False


def _open_normalised(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)  # honour phone orientation
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img


def save_upload(data: bytes, original_name: str = "") -> dict:
    """Write orig + thumb, return relative paths and the extracted palette."""
    config.ensure_dirs()
    img = _open_normalised(data)
    stem = uuid.uuid4().hex

    full = img.copy()
    full.thumbnail((config.MAX_IMAGE_PX, config.MAX_IMAGE_PX), Image.LANCZOS)
    if full.mode == "RGBA":
        full = full.convert("RGB")
    orig_path = config.ORIG_DIR / f"{stem}.jpg"
    full.save(orig_path, "JPEG", quality=88, optimize=True)

    thumb = img.copy()
    thumb.thumbnail((config.THUMB_PX, config.THUMB_PX), Image.LANCZOS)
    if thumb.mode == "RGBA":
        thumb = thumb.convert("RGB")
    thumb_path = config.THUMB_DIR / f"{stem}.jpg"
    thumb.save(thumb_path, "JPEG", quality=82, optimize=True)

    return {
        "image_path": f"orig/{stem}.jpg",
        "thumb_path": f"thumb/{stem}.jpg",
        "palette": extract_palette(full),
    }


def save_cutout(data: bytes) -> str:
    """Store a background-removed PNG returned by an AI provider."""
    config.ensure_dirs()
    img = Image.open(io.BytesIO(data))
    img.thumbnail((config.MAX_IMAGE_PX, config.MAX_IMAGE_PX), Image.LANCZOS)
    stem = uuid.uuid4().hex
    path = config.CUTOUT_DIR / f"{stem}.png"
    img.save(path, "PNG", optimize=True)
    return f"cutout/{stem}.png"


def _to_lab(rgb: tuple) -> tuple:
    """sRGB to CIE Lab (D65). Pure maths, no numpy.

    Naming needs a perceptually uniform space. Distance in RGB (or redmean)
    misreads mid-tones badly — it calls a grey marl "khaki" and tan leather
    "olive", because those sit close in RGB but nowhere near each other to the eye.
    """
    def linear(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(float(c)) for c in rgb[:3])
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.00000
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


_REFERENCE_LAB = [(name, _to_lab(rgb)) for name, rgb in COLOUR_NAMES]


def _colour_distance(a: tuple, b: tuple) -> float:
    """Perceptual distance between two RGB triples (CIE76 in Lab)."""
    la, lb = _to_lab(a), _to_lab(b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb)))


def name_colour(rgb: tuple) -> str:
    lab = _to_lab(rgb)
    return min(
        _REFERENCE_LAB,
        key=lambda ref: math.sqrt(sum((x - y) ** 2 for x, y in zip(lab, ref[1]))),
    )[0]


def hex_of(rgb: tuple) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb[:3])


def extract_palette(img: Image.Image, count: int = 6) -> list[dict]:
    """Dominant garment colours, with the backdrop suppressed.

    The four corners of a clothing photo are almost always background, so any
    cluster sitting close to the corner colour is dropped before ranking.
    """
    small = img.convert("RGB").copy()
    small.thumbnail((220, 220), Image.LANCZOS)
    w, h = small.size
    if w < 4 or h < 4:
        return []

    corners = [
        small.getpixel((1, 1)),
        small.getpixel((w - 2, 1)),
        small.getpixel((1, h - 2)),
        small.getpixel((w - 2, h - 2)),
    ]
    bg = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    corner_spread = max(_colour_distance(bg, c) for c in corners)
    # Only treat it as a clean backdrop when the corners actually agree.
    backdrop = corner_spread < 90

    quantised = small.quantize(colors=12, method=Image.Quantize.FASTOCTREE)
    palette = quantised.getpalette() or []
    total = w * h
    clusters = []
    for pixels, index in quantised.getcolors(total) or []:
        rgb = tuple(palette[index * 3: index * 3 + 3])
        if len(rgb) >= 3:
            clusters.append((pixels, rgb))

    entries = [c for c in clusters if not backdrop or _colour_distance(c[1], bg) >= 18]

    # A white shirt on a white backdrop would otherwise be erased entirely,
    # leaving only buttons and shadows to name the colour by. Fall back only when
    # suppression left virtually nothing — a ring or a pair of boots legitimately
    # covers a small slice of the frame, and that is suppression working.
    kept = sum(p for p, _ in entries)
    if not entries or kept < 0.02 * total:
        entries = clusters or [(1, bg)]

    # Quantisation happily returns six shades of the same burgundy. Merge the
    # clusters that a person would give one name, so the palette reads as
    # "burgundy, silver" rather than the same word five times.
    merged: dict[str, dict] = {}
    for pixels, rgb in entries:
        name = name_colour(rgb)
        slot = merged.get(name)
        if slot is None:
            # `lead` is the biggest single cluster seen for this name; its shade
            # becomes the swatch, while `pixels` accumulates the whole group.
            merged[name] = {"pixels": pixels, "lead": pixels, "rgb": rgb, "name": name}
        else:
            slot["pixels"] += pixels
            if pixels > slot["lead"]:
                slot["lead"] = pixels
                slot["rgb"] = rgb

    ranked = sorted(merged.values(), key=lambda e: -e["pixels"])
    total = sum(e["pixels"] for e in ranked) or 1
    # Anti-aliased edges leave slivers of colours the garment does not really
    # have. Anything under 3% is edge noise, not part of the palette.
    significant = [e for e in ranked if e["pixels"] / total >= 0.03] or ranked[:1]
    ranked = significant[:count]
    shown = sum(e["pixels"] for e in ranked) or 1
    return [
        {
            "hex": hex_of(e["rgb"]),
            "rgb": list(e["rgb"]),
            "name": e["name"],
            "share": round(e["pixels"] / shown, 4),
        }
        for e in ranked
    ]


def colour_group(colour_name: str | None) -> str:
    """Which laundry pile a colour belongs in."""
    if not colour_name:
        return "colours"
    name = colour_name.lower()
    if name == "white":
        return "whites"
    if name in LIGHT_COLOURS:
        return "lights"
    if name in DARK_COLOURS:
        return "darks"
    return "colours"


def photo_bytes(rel_path: str) -> bytes | None:
    path = Path(config.PHOTO_DIR) / rel_path
    try:
        return path.read_bytes()
    except OSError:
        return None
