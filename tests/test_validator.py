"""Smoke tests for the M7U5 IDS-driven MEP validator.

These tests are designed to be fast (<5 s total on the secondary IFC) and
to exercise the three layers — IDS authoring, validator, reporter —
end-to-end. They do not call the LLM modules; those require the
ANTHROPIC_API_KEY and are demonstrated in notebooks/01_demo_validation.ipynb.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.reporter import write_all
from src.validator import Validator


REPO = Path(__file__).resolve().parent.parent
IDS = REPO / "ids" / "mep_services_v1.ids"
SECONDARY_IFC = REPO / "ifc" / "BoilerGasRadiatorDomesticHotWater.ifc"


@pytest.fixture(scope="module")
def validation_run():
    """Run the validator once for the whole test module to share the result."""
    if not SECONDARY_IFC.exists():
        pytest.skip(f"Secondary IFC not present at {SECONDARY_IFC}")
    return Validator(SECONDARY_IFC, IDS).run()


def test_ids_round_trips_and_has_nine_specs() -> None:
    """The hand-authored IDS file parses through ifctester and is XSD-valid."""
    import ifctester
    from lxml import etree
    from ifctester import ids as ids_mod

    parsed = ids_mod.open(str(IDS))
    assert len(parsed.specifications) == 9

    xsd_path = Path(ifctester.__file__).resolve().parent / "ids.xsd"
    schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    schema.assertValid(etree.parse(str(IDS)))


def test_validator_returns_expected_shape(validation_run) -> None:
    """The ValidationRun carries timings, the model, and a populated report."""
    assert validation_run.model.schema == "IFC4"
    assert validation_run.report["total_specifications"] == 9
    assert validation_run.open_seconds >= 0
    assert validation_run.validate_seconds >= 0
    # On the secondary IFC, exactly one specification (distribution port flow
    # direction) is expected to pass — every port carries a flow direction.
    pct_checks = validation_run.report["percent_checks_pass"]
    assert isinstance(pct_checks, (int, float))
    assert 50 <= pct_checks <= 100, f"Expected 50-100% checks pass, got {pct_checks}"


def test_distribution_port_specification_passes_in_full(validation_run) -> None:
    """Spec MEP-02 (distribution port flow direction) must be 100% pass."""
    for spec in validation_run.report["specifications"]:
        if "distribution port" in spec["name"].lower():
            assert spec["total_applicable"] > 0
            assert spec["total_applicable_pass"] == spec["total_applicable"]
            assert spec["status"] is True
            return
    pytest.fail("Distribution-port specification not found in report.")


def test_reporter_writes_all_formats(tmp_path, validation_run) -> None:
    """reporter.write_all() produces JSON, HTML, BCF, summary.csv, failures.csv."""
    paths = write_all(validation_run, tmp_path, stem="test_run")

    assert paths.json.exists()
    assert paths.html.exists()
    assert paths.bcf.exists()
    assert paths.summary_csv.exists()
    assert paths.failures_csv.exists()

    # JSON must round-trip and carry the expected top-level totals.
    payload = json.loads(paths.json.read_text(encoding="utf-8"))
    assert payload["title"] == "MEP Services Information Delivery Specification v1"
    assert payload["total_specifications"] == 9

    # Summary CSV must have one header row + one row per specification.
    with paths.summary_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 9
    assert {"spec_name", "applicable", "passed", "failed", "status"} <= set(rows[0].keys())

    # HTML and BCF should not be empty stubs.
    assert paths.html.stat().st_size > 5_000
    assert paths.bcf.stat().st_size > 5_000
