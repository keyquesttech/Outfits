"""Photo pipeline: normalise uploads, build thumbnails, extract a colour palette.

Colour extraction is plain image processing, not AI — it works with no API key
and no model, and it runs in well under a second on a Pi 4. What a colour is
*called* lives in `colours`, so the palette, the laundry sorter and the outfit
matcher cannot drift apart.
"""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from . import colours, config
from .colours import (  # re-exported: callers have imported these from here
    LIGHT_COLOURS, colour_group, hex_of, name_rgb as name_colour,
)

try:  # iPhone photos arrive as HEIC; register the opener when available.
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - optional dependency
    HEIF_SUPPORTED = False

# Pillow's own bomb guard is a warning by default. A 25 MB upload can still
# decode to hundreds of megapixels, which on a Pi means the process dies rather
# than the request failing, so cap it and let the loader raise instead.
Image.MAX_IMAGE_PIXELS = 80_000_000

# Alpha at or below this is transparent enough to ignore when reading colours.
_ALPHA_FLOOR = 160


def open_photo(data: bytes) -> Image.Image:
    """Decode an upload into RGB or RGBA, honouring orientation.

    Phones and scanners between them produce palette images with transparency,
    16-bit greyscale, CMYK from Photoshop and animated HEIC bursts. Anything
    Pillow can open, this turns into something the rest of the pipeline can use.
    """
    img = Image.open(io.BytesIO(data))
    img.load()                      # surface a truncated file here, not later
    try:
        img = ImageOps.exif_transpose(img) or img
    except Exception:
        pass                        # a corrupt EXIF block is not worth failing on

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        return img.convert("RGBA")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _flatten(img: Image.Image) -> Image.Image:
    """Drop transparency onto white before writing a JPEG.

    Converting RGBA straight to RGB composites onto black, which turned every
    cut-out PNG into a garment on a black square — and then the palette read
    that square as the item's colour.
    """
    if img.mode != "RGBA":
        return img if img.mode == "RGB" else img.convert("RGB")
    canvas = Image.new("RGB", img.size, (255, 255, 255))
    canvas.paste(img, mask=img.split()[3])
    return canvas


def save_upload(data: bytes, original_name: str = "") -> dict:
    """Write orig + thumb, return relative paths and the extracted palette."""
    config.ensure_dirs()
    img = open_photo(data)
    stem = uuid.uuid4().hex

    full = img.copy()
    full.thumbnail((config.MAX_IMAGE_PX, config.MAX_IMAGE_PX), Image.LANCZOS)
    palette = extract_palette(full)     # before flattening, so alpha still counts
    orig_path = config.ORIG_DIR / f"{stem}.jpg"
    _flatten(full).save(orig_path, "JPEG", quality=88, optimize=True)

    thumb = img.copy()
    thumb.thumbnail((config.THUMB_PX, config.THUMB_PX), Image.LANCZOS)
    thumb_path = config.THUMB_DIR / f"{stem}.jpg"
    _flatten(thumb).save(thumb_path, "JPEG", quality=82, optimize=True)

    return {
        "image_path": f"orig/{stem}.jpg",
        "thumb_path": f"thumb/{stem}.jpg",
        "palette": palette,
    }


def save_cutout(data: bytes) -> str:
    """Store a background-removed PNG returned by an AI provider."""
    config.ensure_dirs()
    img = Image.open(io.BytesIO(data))
    img.load()
    img.thumbnail((config.MAX_IMAGE_PX, config.MAX_IMAGE_PX), Image.LANCZOS)
    stem = uuid.uuid4().hex
    path = config.CUTOUT_DIR / f"{stem}.png"
    img.save(path, "PNG", optimize=True)
    return f"cutout/{stem}.png"


# How close, in Lab units, a colour must be to the border ring before it counts
# as the backdrop rather than part of the garment.
BACKDROP_TOLERANCE = 10.0
# A cluster with at least this much of its area pressed against the frame edge
# is scenery — floor, hanger, or the garment's own shadow — not the garment.
RIM_SHARE = 0.55
# Anything under this share of the frame is anti-aliasing, not a colour.
MIN_SHARE = 0.03
# A second colour has to be this much of the garment before it is worth writing
# into the secondary field. Below it, it is a logo, a button or a shadow.
SECONDARY_SHARE = 0.12


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
    if not ring:
        return (255, 255, 255), False
    bg = _median_colour(ring)
    spread = sum(colours.distance(bg, c) for c in ring) / len(ring)
    # In Lab units a plain wall barely varies; a busy room varies a lot.
    return bg, spread < 14


def _is_shadow_of(rgb: tuple, bg: tuple) -> bool:
    """Is this cluster the backdrop with the light taken off it?

    A white sweep always casts a grey gradient under the garment, and that grey
    is far enough from white to survive backdrop suppression. It is the same
    surface though: same hue, just darker. Catching it stops every white shirt
    from being tagged "white, silver".
    """
    L1, c1, h1 = colours.to_lch(rgb)
    L2, c2, h2 = colours.to_lch(bg)
    if L1 >= L2:
        return False                      # brighter than the backdrop: not a shadow
    if c1 > 12 or c2 > 12:
        return False                      # a coloured surface, judged on its own
    hue_gap = min(abs(h1 - h2), 360 - abs(h1 - h2))
    return c1 < 8 and (c1 < 3 or hue_gap < 45) and (L2 - L1) < 55


def extract_palette(img: Image.Image, count: int = 6) -> list[dict]:
    """Suggest the dominant garment colours in a photo.

    This is a starting point for tagging, not the answer: whatever ends up in
    the item's primary and secondary colour fields is what the app actually uses.

    Three things make the guess better than plain counting. Pixels are weighted
    towards the middle of the frame, because a garment is nearly always centred
    and the edges are floor, hanger and wall. The backdrop is read from a ring
    around the whole border rather than four corner pixels. And each cluster
    knows how much of itself is pressed against that border, which is what
    separates the garment from its own shadow.

    Every entry also carries the next-closest names. Some readings are genuinely
    undecidable from pixels — white fabric and a pale grey marl photograph
    within two Lab units of each other — so the palette offers both rather than
    pretending to be sure.
    """
    try:
        return _extract(img, count)
    except Exception:
        # A palette is a convenience. Never let a strange image stop an upload.
        return []


def _extract(img: Image.Image, count: int) -> list[dict]:
    source = img.copy()
    source.thumbnail((180, 180), Image.LANCZOS)

    alpha = None
    if source.mode == "RGBA":
        alpha = source.getchannel("A")
        if min(alpha.getextrema()) >= _ALPHA_FLOOR:
            alpha = None               # fully opaque; nothing to mask
    small = source.convert("RGB")

    w, h = small.size
    if w < 8 or h < 8:
        # Too small to cluster, but it still has a colour. One swatch beats none.
        pixel = small.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
        return [_entry(pixel, 1.0)]

    mask = list(alpha.getdata()) if alpha is not None else None
    if mask is not None and sum(1 for a in mask if a >= _ALPHA_FLOOR) < 16:
        mask = None                    # an all-but-empty cutout is not usable

    if mask is None:
        bg, is_backdrop = _backdrop(small)
    else:
        bg, is_backdrop = (255, 255, 255), False   # a cutout has no backdrop left

    # Median cut splits by actual colour spread, so a garment with highlights
    # and shadow does not eat every slot the way fast octree allowed.
    quantised = small.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    palette = quantised.getpalette() or []
    indexes = list(quantised.getdata())

    # Separable centre weighting: full weight in the middle, a quarter at the edge.
    cx, cy = (w - 1) / 2 or 1, (h - 1) / 2 or 1
    col_w = [1.0 - 0.75 * (abs(x - cx) / cx) for x in range(w)]
    row_w = [1.0 - 0.75 * (abs(y - cy) / cy) for y in range(h)]
    rim_x = max(1, int(w * 0.12))
    rim_y = max(1, int(h * 0.12))

    weights: dict[int, float] = {}
    seen: dict[int, int] = {}
    rim: dict[int, int] = {}
    for y in range(h):
        ry = row_w[y]
        base = y * w
        edge_row = y < rim_y or y >= h - rim_y
        for x in range(w):
            offset = base + x
            if mask is not None and mask[offset] < _ALPHA_FLOOR:
                continue
            index = indexes[offset]
            weights[index] = weights.get(index, 0.0) + ry * col_w[x]
            seen[index] = seen.get(index, 0) + 1
            if edge_row or x < rim_x or x >= w - rim_x:
                rim[index] = rim.get(index, 0) + 1

    clusters = []
    for index, weight in weights.items():
        rgb = tuple(palette[index * 3: index * 3 + 3])
        if len(rgb) >= 3:
            clusters.append((weight, rgb, rim.get(index, 0) / max(1, seen.get(index, 1))))
    if not clusters:
        return []

    # Only drop clusters that genuinely *are* the backdrop, or are its shadow.
    # Compression noise on a plain wall spans a couple of Lab units; a threshold
    # of 18 was wide enough to swallow an olive garment sitting on a tan floor,
    # which then let the fallback restore the floor and call the item khaki.
    entries = []
    for weight, rgb, rim_share in clusters:
        if is_backdrop:
            if colours.distance(rgb, bg) < BACKDROP_TOLERANCE:
                continue
            if rim_share >= RIM_SHARE and _is_shadow_of(rgb, bg):
                continue
        entries.append((weight, rgb))

    # A white shirt on a white backdrop would otherwise be erased entirely,
    # leaving only buttons and shadows to name the colour by. Fall back only when
    # suppression left virtually nothing — a ring or a pair of boots legitimately
    # covers a small slice of the frame, and that is suppression working.
    total = sum(weight for weight, _, _ in clusters) or 1.0
    kept = sum(weight for weight, _ in entries)
    if not entries or kept < 0.02 * total:
        entries = [(weight, rgb) for weight, rgb, _ in clusters]

    # Quantisation happily returns six shades of the same burgundy. Merge the
    # clusters that a person would give one name, so the palette reads as
    # "burgundy, silver" rather than the same word five times.
    merged: dict[str, dict] = {}
    for weight, rgb in entries:
        name = colours.name_rgb(rgb)
        slot = merged.get(name)
        if slot is None:
            # `lead` is the biggest single cluster seen for this name; its shade
            # becomes the swatch, while `weight` accumulates the whole group.
            merged[name] = {"weight": weight, "lead": weight, "rgb": rgb}
        else:
            slot["weight"] += weight
            if weight > slot["lead"]:
                slot["lead"] = weight
                slot["rgb"] = rgb

    ranked = sorted(merged.values(), key=lambda e: -e["weight"])
    grand = sum(e["weight"] for e in ranked) or 1.0
    # Anti-aliased edges leave slivers of colours the garment does not really
    # have. Anything under 3% is edge noise, not part of the palette.
    significant = [e for e in ranked if e["weight"] / grand >= MIN_SHARE] or ranked[:1]
    ranked = significant[:count]
    shown = sum(e["weight"] for e in ranked) or 1.0
    return [_entry(e["rgb"], e["weight"] / shown) for e in ranked]


def _entry(rgb: tuple, share: float) -> dict:
    reading = colours.classify(rgb)
    return {
        "hex": hex_of(rgb),
        "rgb": [int(c) for c in tuple(rgb)[:3]],
        "name": reading["name"],
        "alternatives": reading["alternatives"],
        "neutral": reading["neutral"],
        "group": colours.colour_group(reading["name"]),
        "share": round(share, 4),
    }


def suggest_colours(palette: list[dict]) -> tuple[str | None, str | None]:
    """Which two names to pre-fill from a palette.

    The second slot used to take whatever came next, so a plain white t-shirt
    was filed as "white, silver" off the strength of its own shadow, and a black
    tee with a small print became "black, white". A secondary colour has to be a
    real part of the garment to be worth recording.
    """
    if not palette:
        return None, None
    primary = palette[0].get("name")
    for entry in palette[1:]:
        name = entry.get("name")
        if not name or entry.get("share", 0) < SECONDARY_SHARE:
            continue
        if colours.same_shade(primary, name):
            continue    # the garment's own shading, not a second colour
        return primary, name
    return primary, None


def photo_bytes(rel_path: str) -> bytes | None:
    path = Path(config.PHOTO_DIR) / rel_path
    try:
        return path.read_bytes()
    except OSError:
        return None
