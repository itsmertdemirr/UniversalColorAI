from __future__ import annotations

import json
import math
from importlib.resources import files

import cv2
import numpy as np

from universal_color_ai.models import ColorDescription, ColorTuple

COMMON_TR = {
    "black": "Siyah",
    "white": "Beyaz",
    "red": "Kırmızı",
    "lime": "Parlak Yeşil",
    "blue": "Mavi",
    "yellow": "Sarı",
    "cyan": "Camgöbeği",
    "aqua": "Camgöbeği",
    "magenta": "Macenta",
    "fuchsia": "Fuşya",
    "silver": "Gümüş",
    "gray": "Gri",
    "grey": "Gri",
    "maroon": "Bordo",
    "olive": "Zeytin",
    "green": "Yeşil",
    "purple": "Mor",
    "teal": "Deniz Mavisi",
    "navy": "Lacivert",
    "orange": "Turuncu",
    "pink": "Pembe",
    "brown": "Kahverengi",
    "gold": "Altın",
    "beige": "Bej",
    "coral": "Mercan",
    "indigo": "Çivit",
    "violet": "Menekşe",
    "turquoise": "Turkuaz",
    "khaki": "Haki",
    "salmon": "Somon",
    "crimson": "Kızıl",
    "lavender": "Lavanta",
}


def hex_to_rgb(value: str) -> ColorTuple:
    clean = value.lstrip("#")
    if len(clean) != 6:
        raise ValueError(f"invalid HEX color: {value}")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb: ColorTuple) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def bgr_to_rgb(bgr: ColorTuple) -> ColorTuple:
    return bgr[2], bgr[1], bgr[0]


def bgr_to_hsv(bgr: ColorTuple) -> ColorTuple:
    pixel = np.array([[bgr]], dtype=np.uint8)
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0, 0]
    return int(hsv[0]), int(hsv[1]), int(hsv[2])


def _qualifier(saturation: float, value: float) -> str:
    parts: list[str] = []
    if value < 0.34:
        parts.append("Koyu")
    elif value > 0.86 and saturation < 0.48:
        parts.append("Açık")
    if saturation > 0.80 and value > 0.52:
        parts.append("Canlı")
    elif saturation < 0.30 and value > 0.60:
        parts.append("Pastel")
    elif saturation < 0.48:
        parts.append("Soluk")
    return " ".join(parts)


def family_from_hsv(hsv: ColorTuple) -> str:
    hue, saturation_255, value_255 = hsv
    saturation = saturation_255 / 255.0
    value = value_255 / 255.0
    degrees = hue * 2.0

    if value < 0.12:
        return "Siyah"
    if saturation < 0.10:
        if value > 0.90:
            return "Beyaz"
        if value > 0.68:
            return "Açık Gri"
        if value < 0.32:
            return "Koyu Gri"
        return "Gri"
    if saturation < 0.22 and value > 0.88:
        return "Kırık Beyaz"

    sectors = (
        (15, "Kırmızı"),
        (38, "Turuncu"),
        (65, "Sarı"),
        (85, "Sarı-Yeşil"),
        (150, "Yeşil"),
        (175, "Turkuaz"),
        (200, "Camgöbeği"),
        (220, "Gök Mavisi"),
        (255, "Mavi"),
        (285, "Mor"),
        (320, "Macenta"),
        (345, "Pembe"),
        (360, "Kırmızı"),
    )
    family = "Kırmızı"
    for upper, name in sectors:
        if degrees < upper:
            family = name
            break

    qualifier = _qualifier(saturation, value)
    return f"{qualifier} {family}".strip()


class ColorNameResolver:
    """Maps every measurable RGB value to a Turkish family and nearest CSS4 color."""

    def __init__(self) -> None:
        resource = files("universal_color_ai.data").joinpath("css4_colors.json")
        colors = json.loads(resource.read_text(encoding="utf-8"))
        self.names = tuple(colors.keys())
        self.rgb_values = np.array(
            [hex_to_rgb(colors[name]) for name in self.names], dtype=np.uint8
        )
        bgr_values = self.rgb_values[:, ::-1].reshape(1, -1, 3)
        self.lab_values = cv2.cvtColor(bgr_values, cv2.COLOR_BGR2LAB)[0].astype(np.float32)

    def resolve(self, bgr: ColorTuple) -> ColorDescription:
        pixel = np.array([[bgr]], dtype=np.uint8)
        pixel_lab = cv2.cvtColor(pixel, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
        distances = np.linalg.norm(self.lab_values - pixel_lab, axis=1)
        index = int(np.argmin(distances))
        distance = float(distances[index])
        css_name = self.names[index]
        localized_css = COMMON_TR.get(css_name.lower(), css_name)
        family = family_from_hsv(bgr_to_hsv(bgr))
        confidence = max(0.0, min(100.0, 100.0 * math.exp(-distance / 34.0)))
        display = (
            family
            if family.casefold() == localized_css.casefold()
            else f"{family} · {localized_css}"
        )
        return ColorDescription(
            css_name=css_name,
            family_name=family,
            display_name=display,
            distance_lab=distance,
            confidence=confidence,
        )
