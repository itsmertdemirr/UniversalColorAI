from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppConfig:
    camera: int = 0
    backend: str = "auto"
    scan_limit: int = 10
    width: int = 1280
    height: int = 720
    clusters: int = 12
    analysis_width: int = 360
    analyze_every: int = 4
    min_area: int = 800
    min_coverage: float = 0.003
    max_palette: int = 10
    max_regions: int = 24
    sample_radius: int = 2
    mirror: bool = True
    show_regions: bool = True
    adaptive_performance: bool = True
    target_fps: float = 24.0
    output_dir: str = "output"

    def validate(self) -> None:
        if self.camera < 0:
            raise ValueError("camera must be zero or greater")
        if self.backend not in {"auto", "dshow", "msmf", "any"}:
            raise ValueError("backend must be auto, dshow, msmf or any")
        if not 1 <= self.scan_limit <= 32:
            raise ValueError("scan_limit must be between 1 and 32")
        if self.width < 160 or self.height < 120:
            raise ValueError("width and height are too small")
        if not 2 <= self.clusters <= 32:
            raise ValueError("clusters must be between 2 and 32")
        if self.analysis_width < 100:
            raise ValueError("analysis_width must be at least 100")
        if self.analyze_every < 1:
            raise ValueError("analyze_every must be at least 1")
        if self.min_area < 1:
            raise ValueError("min_area must be at least 1")
        if not 0.0 <= self.min_coverage <= 1.0:
            raise ValueError("min_coverage must be between 0 and 1")
        if not 1 <= self.max_palette <= 32:
            raise ValueError("max_palette must be between 1 and 32")
        if not 0 <= self.sample_radius <= 20:
            raise ValueError("sample_radius must be between 0 and 20")
        if self.target_fps <= 0:
            raise ValueError("target_fps must be positive")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> AppConfig:
        allowed = {field.name for field in fields(cls)}
        filtered = {key: value for key, value in values.items() if key in allowed}
        config = cls(**filtered)
        config.validate()
        return config

    @classmethod
    def load(cls, path: Path | None) -> AppConfig:
        if path is None or not path.exists():
            config = cls()
            config.validate()
            return config
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("configuration root must be a JSON object")
        return cls.from_dict(payload)

    def save(self, path: Path) -> None:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
