from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True, frozen=True)
class CameraInfo:
    index: int
    requested_backend: str
    actual_backend: str
    width: int
    height: int

    @property
    def label(self) -> str:
        return f"index={self.index}, backend={self.actual_backend}, {self.width}x{self.height}"


def backend_candidates(choice: str) -> list[tuple[str, int]]:
    mapping = {
        "dshow": ("DSHOW", cv2.CAP_DSHOW),
        "msmf": ("MSMF", cv2.CAP_MSMF),
        "any": ("ANY", cv2.CAP_ANY),
    }
    if choice != "auto":
        return [mapping[choice]]
    if os.name == "nt":
        return [mapping["dshow"], mapping["msmf"], mapping["any"]]
    return [mapping["any"]]


def camera_indices(preferred: int, scan_limit: int) -> list[int]:
    return [preferred, *(index for index in range(scan_limit) if index != preferred)]


def _read_initial_frame(capture: cv2.VideoCapture, attempts: int = 10) -> np.ndarray | None:
    for _ in range(attempts):
        ok, frame = capture.read()
        if ok and frame is not None and frame.size:
            return frame
        time.sleep(0.06)
    return None


def try_open_camera(
    index: int,
    backend_name: str,
    backend_id: int,
    width: int,
    height: int,
) -> tuple[cv2.VideoCapture, np.ndarray, CameraInfo] | None:
    capture = cv2.VideoCapture(index, backend_id)
    if not capture.isOpened():
        capture.release()
        return None
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    frame = _read_initial_frame(capture)
    if frame is None:
        capture.release()
        return None
    try:
        actual_backend = capture.getBackendName()
    except (cv2.error, AttributeError):
        actual_backend = backend_name
    actual_h, actual_w = frame.shape[:2]
    info = CameraInfo(index, backend_name, actual_backend, actual_w, actual_h)
    return capture, frame, info


def open_camera(
    preferred: int,
    backend: str,
    scan_limit: int,
    width: int,
    height: int,
    verbose: bool = True,
) -> tuple[cv2.VideoCapture, np.ndarray, CameraInfo] | None:
    for index in camera_indices(preferred, scan_limit):
        for backend_name, backend_id in backend_candidates(backend):
            if verbose:
                print(f"[CAMERA] trying index={index}, backend={backend_name}")
            opened = try_open_camera(index, backend_name, backend_id, width, height)
            if opened is not None:
                print(f"[CAMERA] selected {opened[2].label}")
                return opened
    return None


def discover_cameras(
    preferred: int,
    backend: str,
    scan_limit: int,
    width: int,
    height: int,
) -> list[CameraInfo]:
    print(f"[SYSTEM] {platform.system()} {platform.release()} | OpenCV {cv2.__version__}")
    found: list[CameraInfo] = []
    for index in camera_indices(preferred, scan_limit):
        for backend_name, backend_id in backend_candidates(backend):
            print(f"[SCAN] index={index}, backend={backend_name}")
            opened = try_open_camera(index, backend_name, backend_id, width, height)
            if opened is None:
                continue
            capture, _frame, info = opened
            capture.release()
            found.append(info)
            print(f"[FOUND] {info.label}")
            break
    return found


def camera_help() -> str:
    return (
        "No accessible camera was found. Check Windows Camera, camera privacy settings, "
        "desktop app camera permission, device drivers, and close Teams/Discord/OBS/Zoom."
    )
