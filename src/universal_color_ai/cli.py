from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from universal_color_ai import __version__
from universal_color_ai.app import analyze_image, run_interactive
from universal_color_ai.camera import camera_help, discover_cameras
from universal_color_ai.config import AppConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="color-ai", description="Universal real-time color analysis"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Open a camera or video interactively")
    run.add_argument(
        "--source", type=str, default=None, help="Video path; camera is used when omitted"
    )
    run.add_argument("--config", type=Path, default=Path("config.json"))
    run.add_argument("--camera", type=int)
    run.add_argument("--backend", choices=("auto", "dshow", "msmf", "any"))
    run.add_argument("--no-mirror", action="store_true")

    analyze = subparsers.add_parser("analyze", help="Analyze an image without requiring a camera")
    analyze.add_argument("image", type=Path)
    analyze.add_argument("--output", type=Path, default=Path("output"))
    analyze.add_argument("--config", type=Path, default=Path("config.json"))
    analyze.add_argument("--show", action="store_true")

    cameras = subparsers.add_parser("cameras", help="Scan available camera indexes and backends")
    cameras.add_argument("--config", type=Path, default=Path("config.json"))
    cameras.add_argument("--scan-limit", type=int)

    init_config = subparsers.add_parser(
        "init-config", help="Create a documented default config.json"
    )
    init_config.add_argument("--output", type=Path, default=Path("config.json"))
    init_config.add_argument("--force", action="store_true")
    return parser


def _load(path: Path) -> AppConfig:
    return AppConfig.load(path if path.exists() else None)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    known_commands = {"run", "analyze", "cameras", "init-config"}
    if (
        not argv
        or (argv[0].startswith("-") and argv[0] not in {"--version", "-h", "--help"})
        or (argv[0] not in known_commands and argv[0] not in {"--version", "-h", "--help"})
    ):
        argv.insert(0, "run")

    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        if args.command == "run":
            config = _load(args.config)
            if args.camera is not None:
                config.camera = args.camera
            if args.backend is not None:
                config.backend = args.backend
            if args.no_mirror:
                config.mirror = False
            config.validate()
            return run_interactive(args.source, config)

        if args.command == "analyze":
            if not args.image.exists():
                parser.error(f"image does not exist: {args.image}")
            config = _load(args.config)
            bundle = analyze_image(args.image, args.output, config, args.show)
            print(bundle.resolve())
            return 0

        if args.command == "cameras":
            config = _load(args.config)
            if args.scan_limit is not None:
                config.scan_limit = args.scan_limit
            config.validate()
            found = discover_cameras(
                config.camera, config.backend, config.scan_limit, config.width, config.height
            )
            if not found:
                print(camera_help(), file=sys.stderr)
                return 1
            print(f"Found {len(found)} camera(s).")
            return 0

        if args.command == "init-config":
            if args.output.exists() and not args.force:
                parser.error(f"file already exists: {args.output}; use --force")
            AppConfig().save(args.output)
            print(args.output.resolve())
            return 0
    except (ValueError, OSError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 2
    return 0
