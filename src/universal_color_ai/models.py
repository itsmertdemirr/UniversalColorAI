from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

ColorTuple = tuple[int, int, int]


@dataclass(slots=True, frozen=True)
class ColorDescription:
    css_name: str
    family_name: str
    display_name: str
    distance_lab: float
    confidence: float


@dataclass(slots=True, frozen=True)
class PixelColor:
    x: int
    y: int
    bgr: ColorTuple
    rgb: ColorTuple
    hsv: ColorTuple
    hex_value: str
    description: ColorDescription

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hex"] = data.pop("hex_value")
        return data


@dataclass(slots=True, frozen=True)
class PaletteItem:
    bgr: ColorTuple
    rgb: ColorTuple
    hsv: ColorTuple
    hex_value: str
    coverage: float
    description: ColorDescription

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hex"] = data.pop("hex_value")
        return data


@dataclass(slots=True, frozen=True)
class Region:
    bgr: ColorTuple
    rgb: ColorTuple
    hsv: ColorTuple
    hex_value: str
    bbox: tuple[int, int, int, int]
    area: int
    cluster_coverage: float
    description: ColorDescription

    def to_dict(self) -> dict[str, Any]:
        x, y, width, height = self.bbox
        data = asdict(self)
        data["hex"] = data.pop("hex_value")
        data["bbox"] = {"x": x, "y": y, "width": width, "height": height}
        return data


@dataclass(slots=True, frozen=True)
class AnalysisResult:
    palette: tuple[PaletteItem, ...]
    regions: tuple[Region, ...]
    processing_ms: float
    source_width: int
    source_height: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": {"width": self.source_width, "height": self.source_height},
            "processing_ms": round(self.processing_ms, 3),
            "palette": [item.to_dict() for item in self.palette],
            "regions": [item.to_dict() for item in self.regions],
        }
