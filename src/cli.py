"""Entry point: validate an IFC against an IDS and write multi-format reports.

Usage:

    python -m src.cli --ifc ifc/Ifc4_Revit_MEP.ifc \\
                      --ids ids/mep_services_v1.ids \\
                      --out results/
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .reporter import write_all
from .validator import Validator


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m7u5-validator",
        description="Validate an IFC model against an IDS ruleset and write reports.",
    )
    p.add_argument("--ifc", required=True, help="Path to the .ifc model")
    p.add_argument("--ids", required=True, help="Path to the .ids ruleset")
    p.add_argument(
        "--out",
        default="results",
        help="Output directory for reports (default: results/)",
    )
    p.add_argument(
        "--name",
        default=None,
        help="Filename stem for reports (default: IFC filename stem)",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress info-level logs")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname).1s %(message)s",
        stream=sys.stderr,
    )

    run = Validator(args.ifc, args.ids).run()
    paths = write_all(run, args.out, stem=args.name)

    print("\nReports written:")
    for label, path in [
        ("JSON   ", paths.json),
        ("HTML   ", paths.html),
        ("BCF    ", paths.bcf),
        ("Summary", paths.summary_csv),
        ("Fails  ", paths.failures_csv),
    ]:
        marker = "OK " if Path(path).exists() else "-- "
        print(f"  {marker}{label} {path}")

    # Exit code mirrors validation status so CI can gate on it.
    return 0 if run.report["status"] else 1


if __name__ == "__main__":
    sys.exit(main())
