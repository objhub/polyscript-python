"""Named color palette and color resolution for PolyScript."""

from __future__ import annotations


# Tier 1: Basic colors (16)
# Tier 2: CAD material colors
NAMED_COLORS: dict[str, tuple[float, float, float]] = {
    # Tier 1
    "red":     (1.0, 0.0, 0.0),
    "green":   (0.0, 128 / 255, 0.0),
    "blue":    (0.0, 0.0, 1.0),
    "yellow":  (1.0, 1.0, 0.0),
    "cyan":    (0.0, 1.0, 1.0),
    "magenta": (1.0, 0.0, 1.0),
    "orange":  (1.0, 165 / 255, 0.0),
    "purple":  (128 / 255, 0.0, 128 / 255),
    "white":   (1.0, 1.0, 1.0),
    "black":   (0.0, 0.0, 0.0),
    "gray":    (128 / 255, 128 / 255, 128 / 255),
    "grey":    (128 / 255, 128 / 255, 128 / 255),
    "brown":   (139 / 255, 69 / 255, 19 / 255),
    "pink":    (1.0, 192 / 255, 203 / 255),
    "lime":    (0.0, 1.0, 0.0),
    "navy":    (0.0, 0.0, 128 / 255),
    "teal":    (0.0, 128 / 255, 128 / 255),
    # Tier 2: CAD material colors
    "silver":    (192 / 255, 192 / 255, 192 / 255),
    "gold":      (1.0, 215 / 255, 0.0),
    "steel":     (113 / 255, 121 / 255, 126 / 255),
    "copper":    (184 / 255, 115 / 255, 51 / 255),
    "brass":     (181 / 255, 166 / 255, 66 / 255),
    "aluminum":  (168 / 255, 169 / 255, 173 / 255),
    "darkgray":  (64 / 255, 64 / 255, 64 / 255),
    "darkgrey":  (64 / 255, 64 / 255, 64 / 255),
    "lightgray": (211 / 255, 211 / 255, 211 / 255),
    "lightgrey": (211 / 255, 211 / 255, 211 / 255),
}

# Tier 3: CSS Named Colors (subset not already in Tier 1/2)
_CSS_NAMED_COLORS: dict[str, tuple[float, float, float]] = {
    "aliceblue": (240/255, 248/255, 255/255),
    "antiquewhite": (250/255, 235/255, 215/255),
    "aqua": (0.0, 1.0, 1.0),
    "aquamarine": (127/255, 255/255, 212/255),
    "azure": (240/255, 255/255, 255/255),
    "beige": (245/255, 245/255, 220/255),
    "bisque": (255/255, 228/255, 196/255),
    "blanchedalmond": (255/255, 235/255, 205/255),
    "blueviolet": (138/255, 43/255, 226/255),
    "burlywood": (222/255, 184/255, 135/255),
    "cadetblue": (95/255, 158/255, 160/255),
    "chartreuse": (127/255, 255/255, 0/255),
    "chocolate": (210/255, 105/255, 30/255),
    "coral": (255/255, 127/255, 80/255),
    "cornflowerblue": (100/255, 149/255, 237/255),
    "cornsilk": (255/255, 248/255, 220/255),
    "crimson": (220/255, 20/255, 60/255),
    "darkblue": (0/255, 0/255, 139/255),
    "darkcyan": (0/255, 139/255, 139/255),
    "darkgoldenrod": (184/255, 134/255, 11/255),
    "darkgreen": (0/255, 100/255, 0/255),
    "darkkhaki": (189/255, 183/255, 107/255),
    "darkmagenta": (139/255, 0/255, 139/255),
    "darkolivegreen": (85/255, 107/255, 47/255),
    "darkorange": (255/255, 140/255, 0/255),
    "darkorchid": (153/255, 50/255, 204/255),
    "darkred": (139/255, 0/255, 0/255),
    "darksalmon": (233/255, 150/255, 122/255),
    "darkseagreen": (143/255, 188/255, 143/255),
    "darkslateblue": (72/255, 61/255, 139/255),
    "darkslategray": (47/255, 79/255, 79/255),
    "darkslategrey": (47/255, 79/255, 79/255),
    "darkturquoise": (0/255, 206/255, 209/255),
    "darkviolet": (148/255, 0/255, 211/255),
    "deeppink": (255/255, 20/255, 147/255),
    "deepskyblue": (0/255, 191/255, 255/255),
    "dimgray": (105/255, 105/255, 105/255),
    "dimgrey": (105/255, 105/255, 105/255),
    "dodgerblue": (30/255, 144/255, 255/255),
    "firebrick": (178/255, 34/255, 34/255),
    "floralwhite": (255/255, 250/255, 245/255),
    "forestgreen": (34/255, 139/255, 34/255),
    "fuchsia": (255/255, 0/255, 255/255),
    "gainsboro": (220/255, 220/255, 220/255),
    "ghostwhite": (248/255, 248/255, 255/255),
    "goldenrod": (218/255, 165/255, 32/255),
    "greenyellow": (173/255, 255/255, 47/255),
    "honeydew": (240/255, 255/255, 240/255),
    "hotpink": (255/255, 105/255, 180/255),
    "indianred": (205/255, 92/255, 92/255),
    "indigo": (75/255, 0/255, 130/255),
    "ivory": (255/255, 255/255, 240/255),
    "khaki": (240/255, 230/255, 140/255),
    "lavender": (230/255, 230/255, 250/255),
    "lavenderblush": (255/255, 240/255, 245/255),
    "lawngreen": (124/255, 252/255, 0/255),
    "lemonchiffon": (255/255, 250/255, 205/255),
    "lightblue": (173/255, 216/255, 230/255),
    "lightcoral": (240/255, 128/255, 128/255),
    "lightcyan": (224/255, 255/255, 255/255),
    "lightgoldenrodyellow": (250/255, 250/255, 210/255),
    "lightgreen": (144/255, 238/255, 144/255),
    "lightpink": (255/255, 182/255, 193/255),
    "lightsalmon": (255/255, 160/255, 122/255),
    "lightseagreen": (32/255, 178/255, 170/255),
    "lightskyblue": (135/255, 206/255, 250/255),
    "lightslategray": (119/255, 136/255, 153/255),
    "lightslategrey": (119/255, 136/255, 153/255),
    "lightsteelblue": (176/255, 196/255, 222/255),
    "lightyellow": (255/255, 255/255, 224/255),
    "limegreen": (50/255, 205/255, 50/255),
    "linen": (250/255, 240/255, 230/255),
    "maroon": (128/255, 0/255, 0/255),
    "mediumaquamarine": (102/255, 205/255, 170/255),
    "mediumblue": (0/255, 0/255, 205/255),
    "mediumorchid": (186/255, 85/255, 211/255),
    "mediumpurple": (147/255, 112/255, 219/255),
    "mediumseagreen": (60/255, 179/255, 113/255),
    "mediumslateblue": (123/255, 104/255, 238/255),
    "mediumspringgreen": (0/255, 250/255, 154/255),
    "mediumturquoise": (72/255, 209/255, 204/255),
    "mediumvioletred": (199/255, 21/255, 133/255),
    "midnightblue": (25/255, 25/255, 112/255),
    "mintcream": (245/255, 255/255, 250/255),
    "mistyrose": (255/255, 228/255, 225/255),
    "moccasin": (255/255, 228/255, 181/255),
    "navajowhite": (255/255, 222/255, 173/255),
    "oldlace": (253/255, 245/255, 230/255),
    "olive": (128/255, 128/255, 0/255),
    "olivedrab": (107/255, 142/255, 35/255),
    "orangered": (255/255, 69/255, 0/255),
    "orchid": (218/255, 112/255, 214/255),
    "palegoldenrod": (238/255, 232/255, 170/255),
    "palegreen": (152/255, 251/255, 152/255),
    "paleturquoise": (175/255, 238/255, 238/255),
    "palevioletred": (219/255, 112/255, 147/255),
    "papayawhip": (255/255, 239/255, 213/255),
    "peachpuff": (255/255, 218/255, 185/255),
    "peru": (205/255, 133/255, 63/255),
    "plum": (221/255, 160/255, 221/255),
    "powderblue": (176/255, 224/255, 230/255),
    "rosybrown": (188/255, 143/255, 143/255),
    "royalblue": (65/255, 105/255, 225/255),
    "saddlebrown": (139/255, 69/255, 19/255),
    "salmon": (250/255, 128/255, 114/255),
    "sandybrown": (244/255, 164/255, 96/255),
    "seagreen": (46/255, 139/255, 87/255),
    "seashell": (255/255, 245/255, 238/255),
    "sienna": (160/255, 82/255, 45/255),
    "skyblue": (135/255, 206/255, 235/255),
    "slateblue": (106/255, 90/255, 205/255),
    "slategray": (112/255, 128/255, 144/255),
    "slategrey": (112/255, 128/255, 144/255),
    "snow": (255/255, 250/255, 250/255),
    "springgreen": (0/255, 255/255, 127/255),
    "steelblue": (70/255, 130/255, 180/255),
    "tan": (210/255, 180/255, 140/255),
    "thistle": (216/255, 191/255, 216/255),
    "tomato": (255/255, 99/255, 71/255),
    "turquoise": (64/255, 224/255, 208/255),
    "violet": (238/255, 130/255, 238/255),
    "wheat": (245/255, 222/255, 179/255),
    "whitesmoke": (245/255, 245/255, 245/255),
    "yellowgreen": (154/255, 205/255, 50/255),
}


def parse_hex_color(hex_str: str) -> tuple[float, float, float] | None:
    """Parse "#FF0000" or "#F00" to (r, g, b) in 0..1 range.

    Returns None if the string is not a valid hex color.
    """
    if not hex_str.startswith("#"):
        return None
    h = hex_str[1:]
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        return None
    try:
        r = int(h[0:2], 16) / 255
        g = int(h[2:4], 16) / 255
        b = int(h[4:6], 16) / 255
        return (r, g, b)
    except ValueError:
        return None


def normalize_rgb(r: float, g: float, b: float) -> tuple[float, float, float]:
    """If any value > 1, treat as 0..255 and divide by 255."""
    if r > 1 or g > 1 or b > 1:
        return (r / 255, g / 255, b / 255)
    return (r, g, b)


def resolve_color(spec: str | tuple[float, float, float]) -> tuple[float, float, float]:
    """Resolve named color, HEX, or RGB to (r, g, b) in 0..1 range.

    Args:
        spec: A color name string, HEX string, or RGB tuple.

    Returns:
        (r, g, b) tuple with values in 0..1 range.

    Raises:
        ValueError: If the color name is unknown or HEX is invalid.
    """
    if isinstance(spec, tuple):
        return normalize_rgb(*spec)

    # Try HEX
    if spec.startswith("#"):
        result = parse_hex_color(spec)
        if result is None:
            raise ValueError(f"Invalid HEX color: {spec}")
        return result

    # Try named color (case-insensitive)
    name = spec.lower()
    if name in NAMED_COLORS:
        return NAMED_COLORS[name]
    if name in _CSS_NAMED_COLORS:
        return _CSS_NAMED_COLORS[name]

    raise ValueError(f"Unknown color name: {spec}")
