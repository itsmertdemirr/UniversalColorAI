from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np

from universal_color_ai.analysis import ColorAnalyzer, inspect_pixel
from universal_color_ai.camera import camera_help, open_camera
from universal_color_ai.color_names import ColorNameResolver
from universal_color_ai.config import AppConfig
from universal_color_ai.exporters import save_bundle
from universal_color_ai.models import AnalysisResult
from universal_color_ai.renderer import render_frame

LOGGER = logging.getLogger(__name__)
WINDOW_NAME = "Universal Color AI"


class MouseInspector:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.locked = False
        self.initialized = False

    def callback(self, event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event == cv2.EVENT_MOUSEMOVE and not self.locked:
            self.x, self.y, self.initialized = x, y, True
        elif event == cv2.EVENT_LBUTTONDOWN:
            self.x, self.y, self.locked, self.initialized = x, y, True, True
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.locked = False


class AdaptiveScheduler:
    def __init__(self, base_interval: int, target_fps: float, enabled: bool) -> None:
        self.base = max(1, base_interval)
        self.interval = self.base
        self.target_ms = 1000.0 / max(target_fps, 1.0)
        self.enabled = enabled
        self._samples: list[float] = []

    def update(self, analysis_ms: float) -> None:
        if not self.enabled:
            return
        self._samples.append(analysis_ms)
        if len(self._samples) < 12:
            return
        average = sum(self._samples) / len(self._samples)
        self._samples.clear()
        if average > self.target_ms * 1.7:
            self.interval = min(15, self.interval + 1)
        elif average < self.target_ms * 0.75:
            self.interval = max(self.base, self.interval - 1)


def empty_result(width: int, height: int) -> AnalysisResult:
    return AnalysisResult((), (), 0.0, width, height)


def analyze_image(
    source: Path,
    output_dir: Path,
    config: AppConfig,
    show_window: bool = False,
) -> Path:
    frame = cv2.imread(str(source))
    if frame is None:
        raise ValueError(f"could not read image: {source}")
    resolver = ColorNameResolver()
    analyzer = ColorAnalyzer(resolver)
    result = analyzer.analyze(
        frame,
        clusters=config.clusters,
        analysis_width=config.analysis_width,
        min_area=config.min_area,
        min_coverage=config.min_coverage,
        max_palette=config.max_palette,
        max_regions=config.max_regions,
        include_regions=config.show_regions,
    )
    y, x = frame.shape[0] // 2, frame.shape[1] // 2
    inspected = inspect_pixel(frame, x, y, resolver, config.sample_radius)
    annotated = render_frame(
        frame,
        result,
        inspected,
        fps=0.0,
        show_regions=config.show_regions,
        paused=True,
        show_help=False,
        source_label=str(source),
        max_palette=config.max_palette,
    )
    bundle = save_bundle(output_dir, frame, annotated, result, inspected, str(source), 0)
    if show_window:
        cv2.imshow(WINDOW_NAME, annotated)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    return bundle


def run_interactive(source: str | None, config: AppConfig) -> int:
    resolver = ColorNameResolver()
    analyzer = ColorAnalyzer(resolver)
    pending_frame: np.ndarray | None = None

    if source:
        capture = cv2.VideoCapture(source)
        source_label = source
        if not capture.isOpened():
            LOGGER.error("Could not open source: %s", source)
            return 1
    else:
        opened = open_camera(
            config.camera, config.backend, config.scan_limit, config.width, config.height
        )
        if opened is None:
            LOGGER.error(camera_help())
            return 1
        capture, pending_frame, camera_info = opened
        source_label = camera_info.label

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    inspector = MouseInspector()
    cv2.setMouseCallback(WINDOW_NAME, inspector.callback)

    result = empty_result(config.width, config.height)
    scheduler = AdaptiveScheduler(
        config.analyze_every, config.target_fps, config.adaptive_performance
    )
    paused = False
    show_help = False
    show_regions = config.show_regions
    mirror = config.mirror
    fullscreen = False
    frame_index = 0
    previous_time = time.perf_counter()
    fps = 0.0
    current_frame: np.ndarray | None = None

    try:
        while True:
            if not paused or current_frame is None:
                if pending_frame is not None:
                    frame = pending_frame
                    pending_frame = None
                    ok = True
                else:
                    ok, frame = capture.read()
                if not ok or frame is None:
                    if source:
                        break
                    time.sleep(0.03)
                    continue
                current_frame = cv2.flip(frame, 1) if mirror else frame
                frame_index += 1

            frame = current_frame
            height, width = frame.shape[:2]
            if not inspector.initialized:
                inspector.x, inspector.y, inspector.initialized = width // 2, height // 2, True

            if frame_index == 1 or (not paused and frame_index % scheduler.interval == 0):
                result = analyzer.analyze(
                    frame,
                    clusters=config.clusters,
                    analysis_width=config.analysis_width,
                    min_area=config.min_area,
                    min_coverage=config.min_coverage,
                    max_palette=config.max_palette,
                    max_regions=config.max_regions,
                    include_regions=show_regions,
                )
                scheduler.update(result.processing_ms)

            inspected = inspect_pixel(
                frame, inspector.x, inspector.y, resolver, config.sample_radius
            )
            now = time.perf_counter()
            instant = 1.0 / max(now - previous_time, 1e-6)
            previous_time = now
            fps = instant if fps == 0 else fps * 0.90 + instant * 0.10
            annotated = render_frame(
                frame,
                result,
                inspected,
                fps=fps,
                show_regions=show_regions,
                paused=paused,
                show_help=show_help,
                source_label=source_label,
                max_palette=config.max_palette,
            )
            cv2.imshow(WINDOW_NAME, annotated)
            key = cv2.waitKey(20 if paused else 1) & 0xFF

            if key in (27, ord("q")):
                break
            if key == ord("h"):
                show_help = not show_help
            elif key == ord("r"):
                show_regions = not show_regions
            elif key == ord("m"):
                mirror = not mirror
            elif key == ord("f"):
                fullscreen = not fullscreen
                mode = cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL
                cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, mode)
            elif key == 32:
                paused = not paused
            elif key == ord("s"):
                bundle = save_bundle(
                    Path(config.output_dir),
                    frame,
                    annotated,
                    result,
                    inspected,
                    source_label,
                    frame_index,
                )
                print(f"[EXPORT] {bundle.resolve()}")
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0
