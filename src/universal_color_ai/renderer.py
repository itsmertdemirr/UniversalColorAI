from __future__ import annotations

import unicodedata

import cv2
import numpy as np

from universal_color_ai.models import AnalysisResult, ColorTuple, PixelColor


def ascii_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def text_color(background: ColorTuple) -> ColorTuple:
    b, g, r = background
    luminance = 0.0722 * b + 0.7152 * g + 0.2126 * r
    return (0, 0, 0) if luminance > 145 else (255, 255, 255)


def _label(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    background: ColorTuple,
    scale: float,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = max(1, round(scale * 2))
    text = ascii_text(text)
    (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = max(0, min(x, frame.shape[1] - width - 12))
    y = max(height + baseline + 8, y)
    cv2.rectangle(
        frame,
        (x, y - height - baseline - 7),
        (x + width + 10, y + 3),
        background,
        -1,
    )
    cv2.putText(
        frame,
        text,
        (x + 5, y - 4),
        font,
        scale,
        text_color(background),
        thickness,
        cv2.LINE_AA,
    )


def _put(
    canvas: np.ndarray,
    text: str,
    x: int,
    y: int,
    scale: float = 0.45,
    color: ColorTuple = (238, 238, 238),
    thickness: int = 1,
) -> None:
    cv2.putText(
        canvas,
        ascii_text(text),
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def render_frame(
    frame: np.ndarray,
    result: AnalysisResult,
    inspected: PixelColor,
    *,
    fps: float,
    show_regions: bool,
    paused: bool,
    show_help: bool,
    source_label: str,
    max_palette: int,
) -> np.ndarray:
    image = frame.copy()
    height, width = image.shape[:2]
    ui_scale = max(0.38, min(0.65, width / 1600.0 * 0.65))

    if show_regions:
        for region in result.regions:
            x, y, region_width, region_height = region.bbox
            cv2.rectangle(
                image,
                (x, y),
                (x + region_width, y + region_height),
                region.bgr,
                max(1, round(ui_scale * 4)),
            )
            _label(
                image,
                f"{region.description.family_name} {region.hex_value}",
                x,
                y,
                region.bgr,
                ui_scale,
            )

    cv2.circle(image, (inspected.x, inspected.y), 8, (255, 255, 255), 2)
    cv2.circle(image, (inspected.x, inspected.y), 3, (0, 0, 0), -1)

    sidebar_width = max(330, min(430, round(width * 0.34)))
    canvas = np.full((height, width + sidebar_width, 3), (18, 18, 20), dtype=np.uint8)
    canvas[:, :width] = image
    sidebar_x = width
    cv2.line(canvas, (sidebar_x, 0), (sidebar_x, height), (60, 60, 66), 1)

    margin = 18
    x0 = sidebar_x + margin
    compact = height < 520
    title_scale = 0.56 if compact else 0.68
    body_scale = 0.38 if compact else 0.46
    line_height = 20 if compact else 25

    _put(canvas, "UNIVERSAL COLOR AI", x0, 30 if compact else 38, title_scale, (255, 255, 255), 2)
    status = "PAUSED" if paused else "LIVE"
    _put(
        canvas,
        f"{status} | FPS {fps:.1f} | {result.processing_ms:.1f} ms",
        x0,
        50 if compact else 66,
        body_scale,
        (180, 220, 255),
        1,
    )

    swatch_size = 46 if compact else 66
    info_y = 65 if compact else 86
    cv2.rectangle(
        canvas,
        (x0, info_y),
        (x0 + swatch_size, info_y + swatch_size),
        inspected.bgr,
        -1,
    )
    cv2.rectangle(
        canvas,
        (x0, info_y),
        (x0 + swatch_size, info_y + swatch_size),
        (225, 225, 225),
        1,
    )

    text_x = x0 + swatch_size + 12
    details = [
        inspected.description.display_name,
        f"HEX {inspected.hex_value}",
        f"RGB {inspected.rgb}",
        f"HSV {inspected.hsv}",
        f"Match %{inspected.description.confidence:.1f}",
    ]
    detail_limit = 3 if compact else len(details)
    for index, line in enumerate(details[:detail_limit]):
        _put(canvas, line, text_x, info_y + 15 + index * line_height, body_scale)

    info_bottom = max(
        info_y + swatch_size,
        info_y + 15 + (detail_limit - 1) * line_height + 8,
    )
    palette_y = info_bottom + (18 if compact else 28)
    _put(canvas, "DOMINANT PALETTE", x0, palette_y, body_scale + 0.05, (255, 255, 255), 2)
    palette_y += 14
    footer_space = 48 if compact else 80
    row_height = 25 if compact else 31
    rows_that_fit = max(1, (height - palette_y - footer_space) // row_height)
    visible_items = result.palette[: min(max_palette, rows_that_fit)]

    for index, item in enumerate(visible_items):
        y = palette_y + index * row_height
        cv2.rectangle(canvas, (x0, y), (x0 + 25, y + 18), item.bgr, -1)
        cv2.rectangle(canvas, (x0, y), (x0 + 25, y + 18), (220, 220, 220), 1)
        label = f"{item.description.family_name} {item.hex_value} %{item.coverage * 100:.1f}"
        _put(canvas, label, x0 + 36, y + 15, body_scale)

    if len(result.palette) > len(visible_items):
        hidden = len(result.palette) - len(visible_items)
        _put(
            canvas,
            f"+{hidden} additional colors in exported JSON/CSV",
            x0,
            height - footer_space,
            0.34 if compact else 0.39,
            (175, 175, 185),
        )

    source = source_label if len(source_label) <= 52 else "..." + source_label[-49:]
    _put(canvas, f"Source: {source}", x0, height - 30, 0.34 if compact else 0.38, (170, 170, 180))
    _put(
        canvas,
        "H Help | S Export | Space Pause | R Regions | F Fullscreen | M Mirror | Q Exit",
        12,
        height - 12,
        0.34 if width < 700 else 0.43,
        (255, 255, 255),
        1,
    )

    if show_help:
        overlay = canvas.copy()
        x_start, y_start = max(20, canvas.shape[1] // 8), max(20, height // 8)
        x_end, y_end = canvas.shape[1] - x_start, height - y_start
        cv2.rectangle(overlay, (x_start, y_start), (x_end, y_end), (10, 10, 12), -1)
        cv2.addWeighted(overlay, 0.94, canvas, 0.06, 0, canvas)
        help_lines = [
            "UNIVERSAL COLOR AI - HELP",
            "Move mouse: inspect exact color",
            "Left click: lock | Right click: unlock",
            "S: export JPG + JSON + CSV",
            "Space: pause | R: regions | M: mirror",
            "F: fullscreen | H: close | Q/ESC: exit",
        ]
        help_scale = 0.46 if compact else 0.60
        help_step = 28 if compact else 38
        for index, line in enumerate(help_lines):
            _put(
                canvas,
                line,
                x_start + 28,
                y_start + 45 + index * help_step,
                help_scale if index else help_scale + 0.08,
                (245, 245, 245),
                2 if index == 0 else 1,
            )

    return canvas
