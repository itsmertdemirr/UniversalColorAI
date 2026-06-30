from __future__ import annotations

import time

import cv2
import numpy as np

from universal_color_ai.color_names import ColorNameResolver, bgr_to_hsv, bgr_to_rgb, rgb_to_hex
from universal_color_ai.models import AnalysisResult, ColorTuple, PaletteItem, PixelColor, Region


def clamp_point(x: int, y: int, width: int, height: int) -> tuple[int, int]:
    return max(0, min(x, width - 1)), max(0, min(y, height - 1))


def inspect_pixel(
    frame: np.ndarray,
    x: int,
    y: int,
    resolver: ColorNameResolver,
    radius: int = 0,
) -> PixelColor:
    height, width = frame.shape[:2]
    x, y = clamp_point(x, y, width, height)
    radius = max(0, radius)
    x0, x1 = max(0, x - radius), min(width, x + radius + 1)
    y0, y1 = max(0, y - radius), min(height, y + radius + 1)
    patch = frame[y0:y1, x0:x1]
    median = np.median(patch.reshape(-1, 3), axis=0).astype(np.uint8)
    bgr: ColorTuple = tuple(int(value) for value in median)  # type: ignore[assignment]
    rgb = bgr_to_rgb(bgr)
    return PixelColor(
        x=x,
        y=y,
        bgr=bgr,
        rgb=rgb,
        hsv=bgr_to_hsv(bgr),
        hex_value=rgb_to_hex(rgb),
        description=resolver.resolve(bgr),
    )


def _sample_rows(pixels: np.ndarray, maximum: int, rng: np.random.Generator) -> np.ndarray:
    if len(pixels) <= maximum:
        return pixels
    indices = rng.choice(len(pixels), maximum, replace=False)
    return pixels[indices]


def _nearest_labels(pixels: np.ndarray, centers: np.ndarray, batch_size: int = 60000) -> np.ndarray:
    labels: list[np.ndarray] = []
    for start in range(0, len(pixels), batch_size):
        part = pixels[start : start + batch_size].astype(np.float32)
        distances = np.sum((part[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels.append(np.argmin(distances, axis=1).astype(np.int32))
    return np.concatenate(labels)


class ColorAnalyzer:
    def __init__(self, resolver: ColorNameResolver, random_seed: int = 42) -> None:
        self.resolver = resolver
        self.rng = np.random.default_rng(random_seed)

    def analyze(
        self,
        frame: np.ndarray,
        *,
        clusters: int = 12,
        analysis_width: int = 360,
        min_area: int = 800,
        min_coverage: float = 0.003,
        max_palette: int = 10,
        max_regions: int = 24,
        include_regions: bool = True,
    ) -> AnalysisResult:
        started = time.perf_counter()
        if frame is None or frame.size == 0:
            raise ValueError("frame is empty")

        original_h, original_w = frame.shape[:2]
        scale = min(1.0, analysis_width / max(original_w, 1))
        small_w = max(1, round(original_w * scale))
        small_h = max(1, round(original_h * scale))
        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_AREA)

        lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
        lab_pixels = lab.reshape(-1, 3).astype(np.float32)
        sampled = _sample_rows(lab_pixels, 30000, self.rng)
        cluster_count = max(2, min(clusters, 32, len(sampled)))

        cv2.setRNGSeed(42)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 35, 0.7)
        _compactness, _sample_labels, centers_lab = cv2.kmeans(
            sampled,
            cluster_count,
            None,
            criteria,
            4,
            cv2.KMEANS_PP_CENTERS,
        )
        labels_all = _nearest_labels(lab_pixels, centers_lab)
        label_map = labels_all.reshape(small_h, small_w)

        centers_u8 = np.clip(np.rint(centers_lab), 0, 255).astype(np.uint8).reshape(1, -1, 3)
        centers_bgr = cv2.cvtColor(centers_u8, cv2.COLOR_LAB2BGR)[0]
        counts = np.bincount(labels_all, minlength=cluster_count)
        total = max(labels_all.size, 1)
        order = np.argsort(counts)[::-1]

        scale_x, scale_y = original_w / small_w, original_h / small_h
        scaled_min_area = max(8, int(min_area / max(scale_x * scale_y, 1e-9)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        palette: list[PaletteItem] = []
        regions: list[Region] = []

        for cluster_id in order:
            coverage = float(counts[cluster_id] / total)
            if coverage < min_coverage:
                continue
            bgr: ColorTuple = tuple(int(value) for value in centers_bgr[cluster_id])  # type: ignore[assignment]
            rgb = bgr_to_rgb(bgr)
            hsv = bgr_to_hsv(bgr)
            description = self.resolver.resolve(bgr)
            palette.append(
                PaletteItem(
                    bgr=bgr,
                    rgb=rgb,
                    hsv=hsv,
                    hex_value=rgb_to_hex(rgb),
                    coverage=coverage,
                    description=description,
                )
            )

            if not include_regions:
                continue
            mask = np.where(label_map == cluster_id, 255, 0).astype(np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
            for component_id in range(1, count):
                x, y, width, height, area = (int(v) for v in stats[component_id])
                if area < scaled_min_area:
                    continue
                bbox = (
                    round(x * scale_x),
                    round(y * scale_y),
                    max(1, round(width * scale_x)),
                    max(1, round(height * scale_y)),
                )
                regions.append(
                    Region(
                        bgr=bgr,
                        rgb=rgb,
                        hsv=hsv,
                        hex_value=rgb_to_hex(rgb),
                        bbox=bbox,
                        area=round(area * scale_x * scale_y),
                        cluster_coverage=coverage,
                        description=description,
                    )
                )

        palette = palette[:max_palette]
        regions.sort(key=lambda item: item.area, reverse=True)
        regions = regions[:max_regions]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return AnalysisResult(
            palette=tuple(palette),
            regions=tuple(regions),
            processing_ms=elapsed_ms,
            source_width=original_w,
            source_height=original_h,
        )
