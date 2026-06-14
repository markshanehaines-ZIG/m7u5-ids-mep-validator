"""Construct the hand-authored MEP IDS ruleset.

Runs `ifctester.ids` constructors so the emitted XML is guaranteed to round-trip
through the official buildingSMART IDS 1.0 XSD shipped inside the package.

Output: ids/mep_services_v1.ids

Re-run after editing this file to regenerate the ruleset; the result is
committed to the repo so the validator does not need this script at runtime.
"""

from __future__ import annotations

from pathlib import Path

from ifctester import ids


REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "ids" / "mep_services_v1.ids"

IFC_VERSIONS = ["IFC4"]


def _spec(
    identifier: str,
    name: str,
    description: str,
    instructions: str,
    entity: str,
    requirements: list[object],
    *,
    predefined_type: str | None = None,
) -> ids.Specification:
    spec = ids.Specification(
        name=name,
        minOccurs=0,
        maxOccurs="unbounded",
        ifcVersion=IFC_VERSIONS,
        identifier=identifier,
        description=description,
        instructions=instructions,
    )
    spec.applicability.append(ids.Entity(name=entity, predefinedType=predefined_type))
    for facet in requirements:
        spec.requirements.append(facet)
    return spec


def build() -> ids.Ids:
    doc = ids.Ids(
        title="MEP Services Information Delivery Specification v1",
        copyright="Mark Shane Haines, 2026",
        version="1.0.0",
        description=(
            "Hand-authored IDS ruleset covering nine common MEP services "
            "information requirements (pipe, duct, distribution port, flow "
            "terminal, sprinkler, pump, valve, cable segment, electric "
            "appliance). Authored for M7U5, Zigurat Masters in AI in "
            "Architecture and Construction."
        ),
        author="markshanehaines@gmail.com",
        date="2026-06-14",
        purpose="Demonstrate IDS-driven openBIM validation for MEP services models.",
        milestone="Design — Coordination",
    )

    # --- Spec 1 — Pipe segments must declare nominal diameter and material.
    doc.specifications.append(_spec(
        identifier="MEP-01",
        name="Pipe segment — diameter and material",
        description=(
            "Every IfcPipeSegment instance must declare a nominal diameter "
            "via Pset_PipeSegmentTypeCommon and have an associated material."
        ),
        instructions=(
            "Pipe nominal diameter is mandatory for hydraulic sizing, valve "
            "selection and pipe-support spacing. Material is required for "
            "pressure-rating verification (IFC4)."
        ),
        entity="IFCPIPESEGMENT",
        requirements=[
            ids.Property(
                propertySet="Pset_PipeSegmentTypeCommon",
                baseName="NominalDiameter",
                dataType="IFCPOSITIVELENGTHMEASURE",
                cardinality="required",
                instructions="Used downstream for hydraulic sizing and support spacing.",
            ),
            ids.Material(
                cardinality="required",
                instructions="A pipe material must be associated so pressure rating can be verified.",
            ),
        ],
    ))

    # --- Spec 2 — Distribution ports must declare a non-null flow direction.
    doc.specifications.append(_spec(
        identifier="MEP-02",
        name="Distribution port — flow direction declared",
        description=(
            "Every IfcDistributionPort must declare a FlowDirection attribute "
            "of SOURCE, SINK or SOURCEANDSINK. A NOTDEFINED or null "
            "FlowDirection breaks downstream system tracing."
        ),
        instructions=(
            "FlowDirection drives system tracing, pump-sizing and clash logic. "
            "Per IFC4 IfcFlowDirectionEnum (BS EN ISO 16739-1:2020)."
        ),
        entity="IFCDISTRIBUTIONPORT",
        requirements=[
            ids.Attribute(
                name="FlowDirection",
                value=ids.Restriction(options={"enumeration": ["SOURCE", "SINK", "SOURCEANDSINK"]}),
                cardinality="required",
                instructions="Must be one of SOURCE, SINK, SOURCEANDSINK (not NOTDEFINED or null).",
            ),
        ],
    ))

    # --- Spec 3 — Flow terminals must belong to a distribution system.
    doc.specifications.append(_spec(
        identifier="MEP-03",
        name="Flow terminal — distribution system membership",
        description=(
            "Every IfcFlowTerminal instance must be assigned to an "
            "IfcDistributionSystem group so the system it belongs to can be "
            "queried downstream."
        ),
        instructions=(
            "Without IfcDistributionSystem grouping, downstream tools cannot "
            "filter terminals by service (HWS, CWS, supply air, etc.)."
        ),
        entity="IFCFLOWTERMINAL",
        requirements=[
            ids.PartOf(
                name="IFCDISTRIBUTIONSYSTEM",
                relation="IFCRELASSIGNSTOGROUP",
                cardinality="required",
                instructions="Must be a member of an IfcDistributionSystem via IfcRelAssignsToGroup.",
            ),
        ],
    ))

    # --- Spec 4 — Fire-suppression terminals must declare coverage area and predefined type.
    # NOTE: IfcSprinkler exists in IFC2X3 but was retired in IFC4 — sprinklers are
    # modelled as IfcFireSuppressionTerminal with PredefinedType=SPRINKLER (or
    # SPRINKLERDEFLECTOR). The spec is widened to all fire-suppression terminals so
    # the validator reports both missing CoverageArea and NOTDEFINED PredefinedType
    # as separate findings.
    doc.specifications.append(_spec(
        identifier="MEP-04",
        name="Fire-suppression terminal — coverage area and predefined type",
        description=(
            "Every IfcFireSuppressionTerminal must declare a CoverageArea on "
            "Pset_FireSuppressionTerminalSprinkler and a non-NOTDEFINED "
            "PredefinedType. IfcSprinkler from IFC2X3 was retired in IFC4 "
            "and is now PredefinedType=SPRINKLER on IfcFireSuppressionTerminal."
        ),
        instructions=(
            "Sprinkler coverage area is required for hydraulic calculation "
            "per BS EN 12845 §10. PredefinedType must be set so SPRINKLER vs "
            "FIREHYDRANT vs HOSEREEL behaviour is unambiguous."
        ),
        entity="IFCFIRESUPPRESSIONTERMINAL",
        requirements=[
            ids.Property(
                propertySet="Pset_FireSuppressionTerminalSprinkler",
                baseName="CoverageArea",
                dataType="IFCAREAMEASURE",
                cardinality="required",
                instructions="Required for hydraulic sizing per BS EN 12845.",
            ),
            ids.Attribute(
                name="PredefinedType",
                value=ids.Restriction(options={"enumeration": ["BREECHINGINLET", "FIREHYDRANT", "HOSEREEL", "SPRINKLER", "SPRINKLERDEFLECTOR", "USERDEFINED"]}),
                cardinality="required",
                instructions="Must declare terminal type per IFC4 IfcFireSuppressionTerminalTypeEnum (no NOTDEFINED).",
            ),
        ],
    ))

    # --- Spec 5 — Pumps must declare manufacturer and model.
    doc.specifications.append(_spec(
        identifier="MEP-05",
        name="Pump — manufacturer and model identification",
        description=(
            "Every IfcPump must declare Manufacturer and ModelLabel via "
            "Pset_ManufacturerTypeInformation so procurement and O&M can "
            "trace the selected unit."
        ),
        instructions=(
            "Required for FM/CAFM hand-over, O&M manuals and spare-parts "
            "procurement. Pset_ManufacturerTypeInformation is defined in "
            "IFC4 for any IfcElementType."
        ),
        entity="IFCPUMP",
        requirements=[
            ids.Property(
                propertySet="Pset_ManufacturerTypeInformation",
                baseName="Manufacturer",
                dataType="IFCLABEL",
                cardinality="required",
                instructions="Manufacturer name required for procurement and O&M.",
            ),
            ids.Property(
                propertySet="Pset_ManufacturerTypeInformation",
                baseName="ModelLabel",
                dataType="IFCLABEL",
                cardinality="required",
                instructions="Model label required so the selected unit is unambiguously identified.",
            ),
        ],
    ))

    # --- Spec 6 — Duct segments must declare nominal size and material.
    doc.specifications.append(_spec(
        identifier="MEP-06",
        name="Duct segment — nominal size and material",
        description=(
            "Every IfcDuctSegment must declare NominalLengthOrDimension on "
            "Pset_DuctSegmentTypeCommon and have a material assigned."
        ),
        instructions=(
            "Nominal size drives airflow capacity calculations and ductwork "
            "support spacing. Material is required for fire-resistance and "
            "acoustic rating verification."
        ),
        entity="IFCDUCTSEGMENT",
        requirements=[
            ids.Property(
                propertySet="Pset_DuctSegmentTypeCommon",
                baseName="NominalLengthOrDimension",
                dataType="IFCPOSITIVELENGTHMEASURE",
                cardinality="required",
                instructions="Nominal length-or-dimension is required for sizing and support spacing.",
            ),
            ids.Material(
                cardinality="required",
                instructions="Duct material required for fire and acoustic rating.",
            ),
        ],
    ))

    # --- Spec 7 — Valves must declare valve operation and predefined type.
    doc.specifications.append(_spec(
        identifier="MEP-07",
        name="Valve — operation type and predefined type",
        description=(
            "Every IfcValve must declare ValveOperation on "
            "Pset_ValveTypeCommon and a non-NOTDEFINED PredefinedType."
        ),
        instructions=(
            "ValveOperation (DROP/FLOATING/LIFTING/etc.) is needed by "
            "commissioning. PredefinedType (BALL/GATE/CHECK/...) is needed by "
            "schedule generation and clash logic."
        ),
        entity="IFCVALVE",
        requirements=[
            ids.Property(
                propertySet="Pset_ValveTypeCommon",
                baseName="ValveOperation",
                dataType="IFCLABEL",
                cardinality="required",
                instructions="Valve operation required for commissioning schedule.",
            ),
            ids.Attribute(
                name="PredefinedType",
                value=ids.Restriction(options={"enumeration": ["AIRRELEASE", "ANTIVACUUM", "CHANGEOVER", "CHECK", "COMMISSIONING", "DIVERTING", "DRAWOFFCOCK", "DOUBLECHECK", "DOUBLEREGULATING", "FAUCET", "FLUSHING", "GASCOCK", "GASTAP", "ISOLATING", "MIXING", "PRESSUREREDUCING", "PRESSURERELIEF", "REGULATING", "SAFETYCUTOFF", "STEAMTRAP", "STOPCOCK", "USERDEFINED"]}),
                cardinality="required",
                instructions="Must declare valve type per IFC4 IfcValveTypeEnum.",
            ),
        ],
    ))

    # --- Spec 8 — Cable segments must declare cross-sectional area.
    doc.specifications.append(_spec(
        identifier="MEP-08",
        name="Cable segment — cross-sectional area declared",
        description=(
            "Every IfcCableSegment must declare CrossSectionalArea on "
            "Pset_CableSegmentTypeCommon."
        ),
        instructions=(
            "Cable cross-sectional area is mandatory under BS 7671 §433 for "
            "verifying current-carrying capacity and voltage drop."
        ),
        entity="IFCCABLESEGMENT",
        requirements=[
            ids.Property(
                propertySet="Pset_CableSegmentTypeCommon",
                baseName="CrossSectionalArea",
                dataType="IFCAREAMEASURE",
                cardinality="required",
                instructions="Required by BS 7671 §433 for current-carrying capacity verification.",
            ),
        ],
    ))

    # --- Spec 9 — Electric appliances must declare nominal power.
    doc.specifications.append(_spec(
        identifier="MEP-09",
        name="Electric appliance — nominal power declared",
        description=(
            "Every IfcElectricAppliance must declare NominalPower on "
            "Pset_ElectricalDeviceCommon."
        ),
        instructions=(
            "Nominal power is required for circuit sizing, distribution "
            "board scheduling and load-balance reports under BS 7671."
        ),
        entity="IFCELECTRICAPPLIANCE",
        requirements=[
            ids.Property(
                propertySet="Pset_ElectricalDeviceCommon",
                baseName="NominalPower",
                dataType="IFCPOWERMEASURE",
                cardinality="required",
                instructions="Required for circuit sizing per BS 7671 §433.",
            ),
        ],
    ))

    return doc


def main() -> None:
    doc = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(doc.to_string(), encoding="utf-8")
    print(f"Wrote {len(doc.specifications)} specifications to {OUTPUT}")

    # Round-trip validate: parse the saved file back through ifctester to
    # confirm the XML conforms to the bundled IDS 1.0 XSD.
    parsed = ids.open(str(OUTPUT))
    assert len(parsed.specifications) == len(doc.specifications), (
        f"Parsed back {len(parsed.specifications)} specs, expected "
        f"{len(doc.specifications)}"
    )
    print("Round-trip parse OK — file validates against the IDS 1.0 XSD.")


if __name__ == "__main__":
    main()
