"""Multi-format export of an ifctester validation run.

The four built-in ifctester reporters (Json, Bcf, Html, Console) are wrapped
here, and two MEP-targeted CSV summaries are added so the result is
easy to skim in Excel or load into pandas.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ifctester import reporter as reporter_mod

from .validator import ValidationRun


LOG = logging.getLogger(__name__)


@dataclass
class ReportPaths:
    json: Path
    html: Path
    bcf: Path
    summary_csv: Path
    failures_csv: Path


def write_all(run: ValidationRun, out_dir: str | Path, stem: str | None = None) -> ReportPaths:
    """Produce JSON, HTML, BCF and two CSV files for one ValidationRun."""
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    stem = stem or run.ifc_path.stem

    paths = ReportPaths(
        json=out / f"{stem}_report.json",
        html=out / f"{stem}_report.html",
        bcf=out / f"{stem}_report.bcf",
        summary_csv=out / f"{stem}_summary.csv",
        failures_csv=out / f"{stem}_failures.csv",
    )

    LOG.info("Writing reports to %s", out)
    # ifctester's Json/Html/Bcf reporters all read self.results in to_file(),
    # but only .report() populates it. Call .report() explicitly on each.
    json_r = reporter_mod.Json(run.ids_doc)
    json_r.report()
    json_r.to_file(str(paths.json))

    html_r = reporter_mod.Html(run.ids_doc)
    html_r.report()
    html_r.to_file(str(paths.html))

    try:
        bcf_r = reporter_mod.Bcf(run.ids_doc)
        bcf_r.report()
        bcf_r.to_file(str(paths.bcf))
    except Exception as exc:  # pragma: no cover - BCF writer fails on some edge cases
        LOG.warning("BCF export failed (%s); continuing.", exc)
    _write_summary_csv(run.report, paths.summary_csv, run)
    _write_failures_csv(run.report, paths.failures_csv)
    return paths


def _write_summary_csv(report: dict[str, Any], path: Path, run: ValidationRun) -> None:
    fieldnames = [
        "spec_name",
        "applicable",
        "passed",
        "failed",
        "percent_pass",
        "status",
        "ifc_path",
        "ids_path",
        "open_seconds",
        "validate_seconds",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for spec in report["specifications"]:
            applicable = spec.get("total_applicable", 0)
            passed = spec.get("total_applicable_pass", 0)
            failed = spec.get("total_applicable_fail", 0)
            pct = round(100.0 * passed / applicable, 1) if applicable else None
            writer.writerow({
                "spec_name": spec.get("name", ""),
                "applicable": applicable,
                "passed": passed,
                "failed": failed,
                "percent_pass": pct if pct is not None else "n/a",
                "status": ("SKIP" if applicable == 0 else ("PASS" if spec.get("status") else "FAIL")),
                "ifc_path": str(run.ifc_path),
                "ids_path": str(run.ids_path),
                "open_seconds": f"{run.open_seconds:.2f}",
                "validate_seconds": f"{run.validate_seconds:.2f}",
            })
    LOG.info("  wrote %s", path.name)


def _write_failures_csv(report: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "spec_name",
        "ifc_class",
        "global_id",
        "name",
        "predefined_type",
        "expected_requirement",
        "actual_value",
    ]
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for spec in report["specifications"]:
            requirements = spec.get("requirements", [])
            for req in requirements:
                expected = _summarise_requirement(req)
                for fail in req.get("failed_entities", []):
                    writer.writerow({
                        "spec_name": spec.get("name", ""),
                        "ifc_class": fail.get("class", ""),
                        "global_id": fail.get("global_id", ""),
                        "name": fail.get("name", "") or "",
                        "predefined_type": fail.get("predefined_type", "") or "",
                        "expected_requirement": expected,
                        "actual_value": fail.get("reason", "") or "",
                    })
                    rows += 1
    LOG.info("  wrote %s (%d failure rows)", path.name, rows)


def _summarise_requirement(req: dict[str, Any]) -> str:
    """One-line human description of what the requirement was checking."""
    facet = req.get("facet_type") or req.get("facet") or ""
    label = req.get("label") or req.get("name") or ""
    desc = req.get("description") or req.get("instructions") or ""
    parts = [p for p in (facet, label, desc) if p]
    return " | ".join(parts)[:240]
