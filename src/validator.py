"""Thin wrapper around ifctester that times and logs the validation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ifcopenshell
from ifctester import ids as ids_mod
from ifctester import reporter as reporter_mod


LOG = logging.getLogger(__name__)


@dataclass
class ValidationRun:
    """One end-to-end IDS-against-IFC run."""

    ifc_path: Path
    ids_path: Path
    ids_doc: ids_mod.Ids
    model: ifcopenshell.file
    open_seconds: float
    validate_seconds: float
    report: dict[str, Any] = field(default_factory=dict)


class Validator:
    """Loads an IFC, loads an IDS, runs ifctester, returns a ValidationRun.

    The class is deliberately thin: the buildingSMART IfcOpenShell stack
    already does the schema-level work. The wrapper exists to (a) time
    each step so the technical report can quote the numbers, (b) expose a
    single object the CLI and reporter module can consume, and (c) log
    progress so a CI or interactive caller can follow long-running jobs.
    """

    def __init__(self, ifc_path: str | Path, ids_path: str | Path) -> None:
        self.ifc_path = Path(ifc_path).resolve()
        self.ids_path = Path(ids_path).resolve()
        if not self.ifc_path.is_file():
            raise FileNotFoundError(self.ifc_path)
        if not self.ids_path.is_file():
            raise FileNotFoundError(self.ids_path)

    def run(self) -> ValidationRun:
        LOG.info("Opening IFC %s", self.ifc_path.name)
        t0 = time.perf_counter()
        model = ifcopenshell.open(str(self.ifc_path))
        open_secs = time.perf_counter() - t0
        LOG.info("  schema=%s, entities=%d, %.2fs", model.schema, len(list(model)), open_secs)

        LOG.info("Loading IDS %s", self.ids_path.name)
        doc = ids_mod.open(str(self.ids_path))
        LOG.info("  specifications=%d", len(doc.specifications))

        LOG.info("Validating against IDS (this calls ifctester.specs.validate)")
        t0 = time.perf_counter()
        doc.validate(model)
        validate_secs = time.perf_counter() - t0
        LOG.info("  done in %.2fs", validate_secs)

        report = reporter_mod.Json(doc).report()
        self._log_summary(report)

        return ValidationRun(
            ifc_path=self.ifc_path,
            ids_path=self.ids_path,
            ids_doc=doc,
            model=model,
            open_seconds=open_secs,
            validate_seconds=validate_secs,
            report=report,
        )

    @staticmethod
    def _log_summary(report: dict[str, Any]) -> None:
        LOG.info(
            "Result: %d / %d specifications pass (%.1f %% requirements, %.1f %% checks)",
            report["total_specifications_pass"],
            report["total_specifications"],
            report["percent_requirements_pass"],
            report["percent_checks_pass"],
        )
        for spec in report["specifications"]:
            LOG.info(
                "  %-58s applicable=%-6d pass=%-6d fail=%-6d",
                spec["name"][:58],
                spec["total_applicable"],
                spec["total_applicable_pass"],
                spec["total_applicable_fail"],
            )
