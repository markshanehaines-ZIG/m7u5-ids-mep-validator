# M7U5 — IDS-Driven MEP Validator with LLM-Authored Specifications

**Course:** Masters in AI in Architecture and Construction — Zigurat Global Institute of Technology
**Module:** M7U5 — Development of Plugins for BIM Platforms
**Lecturer:** Elias Magalhães
**Author:** Mark Shane Haines (Services BIM Consultant)
**Status:** In development

> Hand-authored Mechanical, Electrical and Plumbing (MEP) information-requirements
> validator built on the buildingSMART openBIM stack
> (`ifcopenshell` + `ifctester`) and extended with two LLM modules that
> (a) translate natural-language Employer's Information Requirements (EIR) clauses
> into valid IDS 1.0 specifications and (b) generate plain-English remediation
> advice for each non-conformance.

This README will be expanded as each phase lands. See `docs/technical_report.md`
for the full 2-page report.

---

## Rubric mapping

| Rubric criterion | Weight | Evidence |
|---|---|---|
| Functional code execution | 40 % | End-to-end CLI on two real MEP IFCs; two LLM modules; reproducible notebook; pytest suite |
| Correct use of the BIM API | 30 % | `ifcopenshell` for IFC access; `ifctester` (buildingSMART reference) for IDS validation; LLM output validated against the official IDS 1.0 XSD before persistence |
| Documentation and logical explanation | 30 % | 2-page technical report, architecture and pipeline diagrams, rubric-mapped README, complete docstrings, logical commit history |

---

## Reproduction

```bash
git clone https://github.com/markshanehaines-ZIG/m7u5-ids-mep-validator.git
cd m7u5-ids-mep-validator
python -m venv venv && source venv/Scripts/activate
pip install -r requirements.txt
cp .env.template .env       # then paste your ANTHROPIC_API_KEY into .env in VS Code
# Download the two IFC test models into ifc/ (commands below)
python -m src.cli --ifc ifc/Ifc4_Revit_MEP.ifc --ids ids/mep_services_v1.ids --out results/
```

### Run the test suite

```bash
python -m pytest tests/ -v
```
Four smoke tests cover IDS XSD round-trip, validator output shape, the
distribution-port specification's expected 100 % pass rate on the
secondary IFC, and the multi-format reporter. Total runtime ~2 s.

### Run the LLM modules

With `ANTHROPIC_API_KEY` set in `.env`:

```bash
python -m src.llm_eir_to_ids \
    --input queries/sample_eir_clauses.txt \
    --out   ids/generated_demo.ids

python -m src.llm_remediation \
    --report results/Ifc4_Revit_MEP_report.json \
    --out    results/Ifc4_Revit_MEP_remediated.json \
    --limit  20
```

### Render the technical report to PDF

```bash
python scripts/build_report_pdf.py
```
Uses Microsoft Edge headless (pre-installed on Windows) so there is no
GTK / wkhtmltopdf dependency to set up.

### IFC test models

The originally targeted Auckland Open IFC Model Repository models
(`Trapelo_IFC4_MEP.ifc`, `Hospital_IFC4_SPR.ifc`) require an interactive
browser login that we cannot reliably automate, so the build uses two
public, no-login replacements with comparable MEP coverage:

| File | Schema | Size | Source |
|---|---|---|---|
| `Ifc4_Revit_MEP.ifc` | IFC4 | 27.8 MB | `youshengCode/IfcSampleFiles` — IFC4 export of the Autodesk Revit MEP Advanced Sample Project |
| `BoilerGasRadiatorDomesticHotWater.ifc` | IFC4 | 1.35 MB | `EnEff-BIM/EnEffBIM_UseCases` (MIT) — VDI 6020 boiler / gas radiator / DHW reference model |

Fetch both with:

```bash
curl -sL -o ifc/Ifc4_Revit_MEP.ifc \
  https://raw.githubusercontent.com/youshengCode/IfcSampleFiles/main/Ifc4_Revit_MEP.ifc
curl -sL -o ifc/BoilerGasRadiatorDomesticHotWater.ifc \
  "https://raw.githubusercontent.com/EnEff-BIM/EnEffBIM_UseCases/master/BIM/1.2%20BoilerGasRadiatorDomesticHotWater_VDI%206020/IFC/1.2%20BoilerGasRadiatorDomesticHotWater.ifc"
```

Both files are excluded from git via `.gitignore` (size policy).

**Attribution — Ifc4_Revit_MEP.ifc:** the underlying model is the publicly
distributed Autodesk Revit MEP Advanced Sample Project
(`rme_advanced_sample_project`), © Autodesk Inc., used here for
non-commercial academic evaluation under Autodesk's sample-content terms.
The IFC4 export is hosted by `youshengCode/IfcSampleFiles` on GitHub.

**Schema note — MEP-04 (Sprinkler):** `IfcSprinkler` exists in IFC2X3
but was retired in IFC4. Sprinklers are now modelled as
`IfcFireSuppressionTerminal` with `PredefinedType=SPRINKLER`. Spec MEP-04
in `ids/mep_services_v1.ids` was authored against the IFC4 form. This is
discussed in `docs/technical_report.md`.

---

## Licence

MIT — see `LICENSE`.
