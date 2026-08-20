"""Checks for the colour engine.

Runs under pytest, and on its own with plain python for the Pi, where pytest is
not installed:

    PYTHONPATH=backend .venv/bin/python backend/tests/test_colours.py

The naming cases are measured off real wardrobe photos, not invented. That is
the point of them: a colour chart says black is L* 0, and no photograph of a
black t-shirt has ever agreed.
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image                                            # noqa: E402

from app import colours, images                                  # noqa: E402
from app.routers.items import item_display_name                   # noqa: E402


def rgb(value):
    return colours.rgb_of_hex(value)


# --------------------------------------------------------------- naming

# (hex, expected name, where it came from). Every one of these is the dominant
# cluster of an actual garment photo.
MEASURED = [
    ("#302c2d", "black", "faded black band tee"),
    ("#2e2d30", "black", "black trainers"),
    ("#201e20", "black", "black long sleeve"),
    ("#26262b", "black", "black cloth tabi"),
    ("#212226", "black", "black webbing belt"),
    ("#151515", "black", "black tee"),
    ("#423e3d", "charcoal", "acid-wash shirt"),
    ("#3e3938", "charcoal", "washed brown-black shirt"),
    ("#484342", "charcoal", "washed black tee"),
    ("#5f5956", "grey", "washed black jeans"),
    ("#606560", "grey", "desaturated olive tee"),
    ("#cac4bf", "silver", "heather grey shirt"),
    ("#d5cfcc", "silver", "light grey marl tee"),
    ("#d8d5d4", "white", "white t-shirt"),
    ("#eae1d6", "cream", "cream ringer tee"),
    ("#cfc1b8", "cream", "off-white shirt"),
    ("#b3a699", "beige", "leather insole"),
    ("#51332d", "brown", "washed brown tee"),
    ("#42281d", "brown", "dark brown tee"),
    ("#5a423b", "brown", "rosy brown tee"),
    ("#503439", "burgundy", "burgundy tee"),
    ("#4d2f31", "burgundy", "burgundy tee"),
    ("#eea278", "salmon", "salmon dry-fit tee"),
    ("#4f7f7f", "teal", "teal beanie"),
]


def test_named_from_photographs():
    for value, want, where in MEASURED:
        got = colours.name_rgb(rgb(value))
        assert got == want, f"{value} ({where}) named {got}, expected {want}"


def test_black_is_not_charcoal():
    """The failure this engine exists for: every dark garment was "charcoal"."""
    for value in ("#1b1b1d", "#2e2d30", "#26262b", "#212226"):
        assert colours.name_rgb(rgb(value)) == "black"


def test_alternatives_carry_the_other_reading():
    # A desaturated olive measures as a grey. The hue name has to be reachable.
    assert "olive" in colours.classify(rgb("#606560"))["alternatives"]
    # A navy boot at low chroma likewise.
    assert "navy" in colours.classify(rgb("#3e4046"))["alternatives"]
    # White and a pale marl are two lightness units apart: offer both.
    assert "silver" in colours.classify(rgb("#d8d5d4"))["alternatives"]


def test_flat_grey_offers_only_greys():
    """A colour with no hue at all must not suggest a hue."""
    alternatives = colours.classify(rgb("#3d3d3d"))["alternatives"]
    assert set(alternatives) <= {"black", "grey", "charcoal", "silver", "white", "cream"}


def test_metals_only_when_asked_for():
    gold = rgb("#d4af37")
    assert colours.name_rgb(gold) != "gold"                    # a mustard jumper
    assert colours.name_rgb(gold, allow_metals=True) == "gold"  # a ring


# --------------------------------------------------------------- normalising

def test_spellings_that_used_to_be_dropped():
    assert colours.canonical("Gray") == "grey"
    assert colours.canonical("Dark Red") == "burgundy"
    assert colours.canonical("  Off-White ") == "cream"
    assert colours.canonical("gray marl") == "grey"
    assert colours.canonical("light grey") == "silver"
    assert colours.canonical("army green") == "olive"
    assert colours.canonical("sammon") == "salmon"


def test_blanks_are_not_colours():
    for value in ("", "  ", "N/A", "n/a", "none", "unknown", "-", "multicolour", None):
        assert colours.canonical(value) is None
        assert colours.normalise(value) is None


def test_unknown_words_are_kept_not_destroyed():
    assert colours.canonical("heliotrope shimmer") is None
    assert colours.normalise("heliotrope shimmer") == "heliotrope shimmer"


def test_hex_and_rgb_input():
    assert colours.canonical("#1b1b1d") == "black"
    assert colours.canonical("#fff") == "white"
    assert colours.canonical("rgb(200, 40, 40)") == "red"


def test_compound_values_split():
    assert colours.split_colours("Blue/Green") == ["blue", "green"]
    assert colours.split_colours("navy & white") == ["navy", "white"]
    assert colours.split_colours("N/A") == []


def test_laundry_groups_follow_spelling():
    assert colours.colour_group("Gray") == colours.colour_group("grey")
    assert colours.colour_group("Dark Red") == "darks"
    assert colours.colour_group("White") == "whites"
    assert colours.colour_group("N/A") == "colours"
    assert colours.colour_group("something odd") == "colours"


def test_shades_of_one_colour():
    assert colours.same_shade("black", "charcoal")
    assert colours.same_shade("White", "silver")
    assert not colours.same_shade("black", "white")
    assert not colours.same_shade("navy", "burgundy")


# --------------------------------------------------------------- extraction

def photo(size=(200, 260), fabric=(30, 30, 32), backdrop=(252, 252, 250),
          mode="RGB"):
    """A garment-shaped block on a sweep, roughly how the real photos look."""
    img = Image.new(mode, size, backdrop + ((255,) if mode == "RGBA" else ()))
    body = Image.new(mode, (int(size[0] * 0.62), int(size[1] * 0.7)),
                     fabric + ((255,) if mode == "RGBA" else ()))
    img.paste(body, (int(size[0] * 0.19), int(size[1] * 0.15)))
    return img


def test_backdrop_is_not_the_garment():
    palette = images.extract_palette(photo())
    assert palette and palette[0]["name"] == "black"


def test_white_on_white_still_reads_white():
    palette = images.extract_palette(photo(fabric=(233, 232, 230)))
    assert palette and palette[0]["name"] in ("white", "silver")


def test_transparency_is_not_read_as_black():
    """A cut-out PNG is transparent, and transparent is not a colour."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    body = Image.new("RGBA", (120, 120), (200, 40, 40, 255))
    img.paste(body, (40, 40))
    palette = images.extract_palette(img)
    assert palette and palette[0]["name"] == "red"


def test_odd_images_do_not_raise():
    for img in (Image.new("L", (60, 60), 128),
                Image.new("CMYK", (60, 60)),
                Image.new("1", (60, 60)),
                Image.new("RGB", (2, 2), (10, 200, 30)),
                Image.new("RGBA", (80, 80), (0, 0, 0, 0))):
        images.extract_palette(img)          # must not raise


def test_tiny_image_still_yields_a_colour():
    palette = images.extract_palette(Image.new("RGB", (3, 3), (200, 40, 40)))
    assert palette and palette[0]["name"] == "red"


def test_secondary_is_a_real_second_colour():
    # The garment's own shading is not a second colour.
    shaded = [{"name": "black", "share": 0.7}, {"name": "charcoal", "share": 0.3}]
    assert images.suggest_colours(shaded) == ("black", None)
    # A genuine contrast panel is.
    two_tone = [{"name": "navy", "share": 0.6}, {"name": "cream", "share": 0.4}]
    assert images.suggest_colours(two_tone) == ("navy", "cream")
    # A small print is not.
    printed = [{"name": "black", "share": 0.94}, {"name": "white", "share": 0.06}]
    assert images.suggest_colours(printed) == ("black", None)
    assert images.suggest_colours([]) == (None, None)


def test_uploads_survive_a_png_with_alpha():
    buffer = io.BytesIO()
    photo(mode="RGBA", fabric=(200, 40, 40)).save(buffer, "PNG")
    opened = images.open_photo(buffer.getvalue())
    assert images._flatten(opened).mode == "RGB"


# --------------------------------------------------------------- names

def test_filenames_do_not_become_garment_names():
    for raw in ("Gemini_Generated_Image_x9abi9x9abi9x9ab", "IMG_4821",
                "PXL_20230101_123456", "DSC00123",
                "Screenshot 2024-01-02 at 10.11.12", ""):
        assert item_display_name(raw, "shirt", "charcoal") == "Charcoal Shirt"


def test_real_names_are_left_alone():
    assert item_display_name("Navy Merino Crew", "top", "navy") == "Navy Merino Crew"
    assert item_display_name("levis 501 jeans", "bottom", "denim") == "levis 501 jeans"
    assert item_display_name("20 eye boots", "footwear", "black") == "20 eye boots"


# --------------------------------------------------------------- harmony

def test_harmony_reads_the_colour_field():
    from app.recommend import colour_harmony

    # Spellings the old reference lookup missed scored as "no colours at all".
    score, note = colour_harmony([{"colour_primary": "Dark Red", "layer": "top"},
                                  {"colour_primary": "maroon", "layer": "bottom"}])
    assert note == "single colour family"
    # Neutrals still cannot clash.
    score, note = colour_harmony([{"colour_primary": "black", "layer": "top"},
                                  {"colour_primary": "Gray", "layer": "bottom"}])
    assert note == "neutral palette"
    # Metal is not a competing hue.
    score, note = colour_harmony([{"colour_primary": "gold", "layer": "jewellery"},
                                  {"colour_primary": "teal", "layer": "top"}])
    assert note == "one accent colour"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
