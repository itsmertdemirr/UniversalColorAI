from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from universal_color_ai.models import AnalysisResult, PixelColor


def analysis_payload(
    result: AnalysisResult,
    inspected: PixelColor | None,
    source_label: str,
    frame_index: int,
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "timestamp_unix": time.time(),
        "source_label": source_label,
        "frame_index": frame_index,
        "analysis": result.to_dict(),
    }
    if inspected is not None:
        payload["inspected_pixel"] = inspected.to_dict()
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_palette_csv(path: Path, result: AnalysisResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "family",
                "css_name",
                "hex",
                "red",
                "green",
                "blue",
                "hue_opencv",
                "saturation",
                "value",
                "coverage_percent",
                "confidence_percent",
            ]
        )
        for rank, item in enumerate(result.palette, start=1):
            writer.writerow(
                [
                    rank,
                    item.description.family_name,
                    item.description.css_name,
                    item.hex_value,
                    *item.rgb,
                    *item.hsv,
                    round(item.coverage * 100, 4),
                    round(item.description.confidence, 2),
                ]
            )


def save_bundle(
    output_dir: Path,
    original: np.ndarray,
    annotated: np.ndarray,
    result: AnalysisResult,
    inspected: PixelColor | None,
    source_label: str,
    frame_index: int,
    prefix: str = "color-analysis",
) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bundle = output_dir / f"{prefix}-{stamp}-{frame_index:06d}"
    bundle.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(bundle / "original.jpg"), original):
        raise OSError("could not save original image")
    if not cv2.imwrite(str(bundle / "annotated.jpg"), annotated):
        raise OSError("could not save annotated image")
    write_json(
        bundle / "analysis.json", analysis_payload(result, inspected, source_label, frame_index)
    )
    write_palette_csv(bundle / "palette.csv", result)
    return bundle
