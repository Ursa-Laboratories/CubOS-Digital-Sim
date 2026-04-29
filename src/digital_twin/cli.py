"""Command line interface for exporting CubOS digital twin bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .exporter import write_digital_twin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export CubOS configs to digital twin JSON.")
    parser.add_argument("--gantry", required=True, help="Path to CubOS gantry YAML.")
    parser.add_argument("--deck", required=True, help="Path to CubOS deck YAML.")
    parser.add_argument("--protocol", required=True, help="Path to CubOS protocol YAML.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--cubos-root", default=None, help="CubOS checkout root. Defaults to the local workspace checkout when present.")
    parser.add_argument("--sample-step-mm", type=float, default=5.0, help="Maximum interpolation spacing for motion path samples.")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON instead of pretty printed JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = write_digital_twin(
        gantry_path=args.gantry,
        deck_path=args.deck,
        protocol_path=args.protocol,
        cubos_root=args.cubos_root,
        sample_step_mm=args.sample_step_mm,
        out_path=args.out,
        pretty=not args.compact,
    )
    print(
        json.dumps(
            {
                "out": str(Path(args.out)),
                "labware": len(data["deck"]["labware"]),
                "timelineSteps": len(data["protocol"]["timeline"]),
                "pathSamples": len(data["motion"]["path"]),
                "warnings": len(data["warnings"]),
            },
            indent=2,
        )
    )
    return 0
