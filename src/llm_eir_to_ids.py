"""Translate natural-language EIR clauses into valid IDS 1.0 specifications.

For each clause in the input file the module calls Anthropic's Claude
(model controlled by `ANTHROPIC_MODEL`, default `claude-sonnet-4-6`),
asks for a single IDS specification expressed as IDS 1.0 XML, then
validates the returned XML against the buildingSMART IDS XSD bundled
inside the ifctester package. Specifications that fail XSD validation
are reported and excluded from the output file; the run does not silently
emit malformed XML.

Usage:

    python -m src.llm_eir_to_ids \\
        --input queries/sample_eir_clauses.txt \\
        --out ids/generated_demo.ids
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from lxml import etree

import ifctester
from ifctester import ids as ids_mod


LOG = logging.getLogger(__name__)
IDS_NS = "http://standards.buildingsmart.org/IDS"
DEFAULT_MODEL = "claude-sonnet-4-6"


SYSTEM_PROMPT = """You are a buildingSMART openBIM information-modelling assistant.
You translate one natural-language Employer's Information Requirements (EIR)
clause at a time into ONE valid IDS 1.0 specification expressed as XML.

Output requirements:
- Emit a SINGLE <specification> element (no surrounding <ids>, no <specifications>,
  no <info>). The XML namespace prefix is the default IDS namespace.
- Always set cardinality="required" on every requirement facet.
- ifcVersion attribute must be "IFC4".
- Provide a meaningful name, description, instructions for the specification.
- Identifier should follow the pattern "GEN-<NN>" (use any two-digit number).
- For applicability, use a single <entity> facet with the correct IFC4 class
  (uppercase, e.g. IFCAIRTERMINAL, IFCCHILLER).
- For requirements, choose <property> with the correct Pset name and dataType,
  or <attribute>, or <material>, or <classification>, or <partOf>.
- Do NOT include xmlns declarations on the <specification> element; the parent
  document supplies them.
- Do NOT add any prose, commentary, or markdown fences. Output ONLY the XML.

Example input clause:
  All sprinklers shall declare CoverageArea and a non-NOTDEFINED PredefinedType.

Example output XML:
<specification name="Sprinkler coverage area" ifcVersion="IFC4" identifier="GEN-01" description="Every sprinkler must declare CoverageArea." instructions="Required for hydraulic calculation.">
    <applicability minOccurs="0" maxOccurs="unbounded">
        <entity><name><simpleValue>IFCFIRESUPPRESSIONTERMINAL</simpleValue></name></entity>
    </applicability>
    <requirements>
        <property dataType="IFCAREAMEASURE" cardinality="required">
            <propertySet><simpleValue>Pset_FireSuppressionTerminalSprinkler</simpleValue></propertySet>
            <baseName><simpleValue>CoverageArea</simpleValue></baseName>
        </property>
    </requirements>
</specification>
"""


@dataclass
class GeneratedSpec:
    source_clause: str
    spec_xml: str | None
    error: str | None = None


def _read_clauses(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    blocks: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            if current:
                blocks.append(" ".join(current).strip())
                current = []
        else:
            current.append(line.strip())
    if current:
        blocks.append(" ".join(current).strip())
    return [b for b in blocks if b]


def _xsd_path() -> Path:
    return Path(ifctester.__file__).resolve().parent / "ids.xsd"


def _validate_full_ids(xml_text: str) -> tuple[bool, str | None]:
    """Validate a complete IDS document string against the bundled XSD."""
    try:
        doc = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return False, f"XML parse error: {exc}"
    schema = etree.XMLSchema(etree.parse(str(_xsd_path())))
    if schema.validate(etree.ElementTree(doc)):
        return True, None
    return False, str(schema.error_log)


def _extract_specification_xml(raw: str) -> str | None:
    """Pull the first <specification>...</specification> block out of Claude's reply."""
    raw = raw.strip()
    # Strip any markdown code fences the model adds despite instructions.
    raw = re.sub(r"^```(?:xml)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"<specification\b.*?</specification>", raw, flags=re.DOTALL)
    return match.group(0) if match else None


def _call_claude(client: "anthropic.Anthropic", model: str, clause: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": clause}],
    )
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def translate_clauses(clauses: Iterable[str], *, model: str | None = None) -> list[GeneratedSpec]:
    import anthropic  # imported lazily so the validator/CLI can be used offline

    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.template)."
        )
    chosen_model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
    client = anthropic.Anthropic(api_key=api_key)

    results: list[GeneratedSpec] = []
    for clause in clauses:
        LOG.info("Translating clause (%d chars) via %s", len(clause), chosen_model)
        raw = _call_claude(client, chosen_model, clause)
        spec_xml = _extract_specification_xml(raw)
        if not spec_xml:
            results.append(GeneratedSpec(clause, None, "No <specification> element found in model reply"))
            continue
        # Wrap into a complete IDS to validate against the XSD.
        wrapped = _wrap_as_full_ids([spec_xml], title="probe", description=clause)
        ok, err = _validate_full_ids(wrapped)
        if not ok:
            results.append(GeneratedSpec(clause, spec_xml, f"XSD validation failed: {err}"))
            continue
        results.append(GeneratedSpec(clause, spec_xml, None))
    return results


def _wrap_as_full_ids(spec_xml_blocks: list[str], *, title: str, description: str) -> str:
    body = "\n".join(spec_xml_blocks)
    today = "2026-06-14"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ids xmlns="{IDS_NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="{IDS_NS} http://standards.buildingsmart.org/IDS/1.0/ids.xsd">
    <info>
        <title>{title}</title>
        <description>{description}</description>
        <author>markshanehaines@gmail.com</author>
        <date>{today}</date>
        <purpose>LLM-generated IDS specifications from EIR clauses (M7U5).</purpose>
    </info>
    <specifications>
{body}
    </specifications>
</ids>
"""


def write_output(specs: list[GeneratedSpec], path: Path, *, title: str = "LLM-generated MEP requirements") -> int:
    valid = [s.spec_xml for s in specs if s.error is None and s.spec_xml]
    if not valid:
        LOG.warning("No specifications survived validation; output file not written.")
        return 0
    description = f"Generated from {len(specs)} EIR clauses; {len(valid)} survived XSD validation."
    xml = _wrap_as_full_ids(valid, title=title, description=description)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    # Re-parse via ifctester to confirm the saved file round-trips.
    parsed = ids_mod.open(str(path))
    LOG.info("Wrote %d specifications to %s (parsed back %d).",
             len(valid), path, len(parsed.specifications))
    return len(valid)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="m7u5-eir-to-ids")
    p.add_argument("--input", required=True, help="Plain-text file of NL EIR clauses")
    p.add_argument("--out", required=True, help="Path to write the generated .ids file")
    p.add_argument("--model", default=None, help="Override ANTHROPIC_MODEL env var")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname).1s %(message)s",
                        stream=sys.stderr)
    clauses = _read_clauses(Path(args.input))
    LOG.info("Read %d clauses from %s", len(clauses), args.input)
    if not clauses:
        LOG.error("No clauses found in input file.")
        return 2
    results = translate_clauses(clauses, model=args.model)
    for i, r in enumerate(results, 1):
        if r.error:
            LOG.warning("  Clause %d FAILED: %s", i, r.error)
        else:
            LOG.info("  Clause %d OK", i)
    written = write_output(results, Path(args.out))
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
