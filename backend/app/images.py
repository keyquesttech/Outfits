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


# How close, in Lab units, a colour must be to the border ring before it counts
# as the backdrop rather than part of the garment.
BACKDROP_TOLERANCE = 10.0


def _median_colour(samples: list[tuple]) -> tuple:
    """Component-wise median. Resists a stray dark pixel in the border ring."""
    if not samples:
        return (255, 255, 255)
    return tuple(sorted(s[i] for s in samples)[len(samples) // 2] for i in range(3))


def _backdrop(small: Image.Image) -> tuple[tuple, bool]:
    """Sample the border ring and decide whether it is a clean backdrop.

    Four corner pixels used to decide this, which one dark fold or a shadow in
    a corner was enough to throw off. A ring around the whole edge is a far more
    stable read of what the garment is sitting on.
    """
    w, h = small.size
    step = max(1, min(w, h) // 40)
    ring = []
    for x in range(0, w, step):
        ring.append(small.getpixel((x, 0)))
        ring.append(small.getpixel((x, h - 1)))
    for y in range(0, h, step):
        ring.append(small.getpixel((0, y)))
        ring.append(small.getpixel((w - 1, y)))
    bg = _median_colour(ring)
    spread = sum(_colour_distance(bg, c) for c in ring) / len(ring)
    # In Lab units a plain wall barely varies; a busy room varies a lot.
    return bg, spread < 14


def extract_palette(img: Image.Image, count: int = 6) -> list[dict]:
    """Suggest the dominant garment colours in a photo.

    This is a starting point for tagging, not the answer: whatever ends up in
    the item's primary and secondary colour fields is what the app actually uses.

    Two things make the guess better than plain counting. Pixels are weighted
    towards the middle of the frame, because a garment is nearly always centred
    and the edges are floor, hanger and wall. And the backdrop is read from a
    ring around the whole border rather than four corner pixels.
    """
    small = img.convert("RGB").copy()
    small.thumbnail((180, 180), Image.LANCZOS)
    w, h = small.size
    if w < 8 or h < 8:
        return []

    bg, is_backdrop = _backdrop(small)

    # Median cut splits by actual colour spread, so a garment with highlights
    # and shadow does not eat every slot the way fast octree allowed.
    quantised = small.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    palette = quantised.getpalette() or []
    indexes = list(quantised.getdata())

    # Separable centre weighting: full weight in the middle, a quarter at the edge.
    cx, cy = (w - 1) / 2 or 1, (h - 1) / 2 or 1
    col_w = [1.0 - 0.75 * (abs(x - cx) / cx) for x in range(w)]
    row_w = [1.0 - 0.75 * (abs(y - cy) / cy) for y in range(h)]

    weights: dict[int, float] = {}
    for y in range(h):
        ry = row_w[y]
        base = y * w
        for x in range(w):
            index = indexes[base + x]
            weights[index] = weights.get(index, 0.0) + ry * col_w[x]

    clusters = []
    for index, weight in weights.items():
        rgb = tuple(palette[index * 3: index * 3 + 3])
        if len(rgb) >= 3:
            clusters.append((weight, rgb))

    # Only drop clusters that genuinely *are* the backdrop. Compression noise on
    # a plain wall spans a couple of Lab units; a threshold of 18 was wide enough
    # to swallow an olive garment sitting on a tan floor, which then let the
    # fallback restore the floor and call the item khaki.
    entries = [c for c in clusters
               if not is_backdrop or _colour_distance(c[1], bg) >= BACKDROP_TOLERANCE]

    # A white shirt on a white backdrop would otherwise be erased entirely,
    # leaving only buttons and shadows to name the colour by. Fall back only when
    # suppression left virtually nothing — a ring or a pair of boots legitimately
    # covers a small slice of the frame, and that is suppression working.
    total = sum(weight for weight, _ in clusters) or 1.0
    kept = sum(weight for weight, _ in entries)
    if not entries or kept < 0.02 * total:
        entries = clusters or [(1.0, bg)]

    # Quantisation happily returns six shades of the same burgundy. Merge the
    # clusters that a person would give one name, so the palette reads as
    # "burgundy, silver" rather than the same word five times.
    merged: dict[str, dict] = {}
    for weight, rgb in entries:
        name = name_colour(rgb)
        slot = merged.get(name)
        if slot is None:
            # `lead` is the biggest single cluster seen for this name; its shade
            # becomes the swatch, while `weight` accumulates the whole group.
            merged[name] = {"weight": weight, "lead": weight, "rgb": rgb, "name": name}
        else:
            slot["weight"] += weight
            if weight > slot["lead"]:
                slot["lead"] = weight
                slot["rgb"] = rgb

    ranked = sorted(merged.values(), key=lambda e: -e["weight"])
    grand = sum(e["weight"] for e in ranked) or 1.0
    # Anti-aliased edges leave slivers of colours the garment does not really
    # have. Anything under 3% is edge noise, not part of the palette.
    significant = [e for e in ranked if e["weight"] / grand >= 0.03] or ranked[:1]
    ranked = significant[:count]
    shown = sum(e["weight"] for e in ranked) or 1.0
    return [
        {
            "hex": hex_of(e["rgb"]),
            "rgb": list(e["rgb"]),
            "name": e["name"],
            "share": round(e["weight"] / shown, 4),
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
