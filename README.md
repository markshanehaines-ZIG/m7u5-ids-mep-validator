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

## Reproduction (placeholder — completed in Phase 7)

```bash
git clone https://github.com/markshanehaines-ZIG/m7u5-ids-mep-validator.git
cd m7u5-ids-mep-validator
python -m venv venv && source venv/Scripts/activate
pip install -r requirements.txt
cp .env.template .env   # then add your ANTHROPIC_API_KEY in your editor
# Download Trapelo and Hospital IFCs into ifc/ (links below)
python -m src.cli --ifc ifc/Trapelo_IFC4_MEP.ifc --ids ids/mep_services_v1.ids --out results/
```

### IFC test models

| File | Schema | Size | Source |
|---|---|---|---|
| `Trapelo_IFC4_MEP.ifc` | IFC4 | 67.8 MB | http://openifcmodel.cs.auckland.ac.nz/Model/Details/303 |
| `Hospital_IFC4_SPR.ifc` | IFC4 | 34 MB | http://openifcmodel.cs.auckland.ac.nz/Model/Details/308 |

Both are excluded from git via `.gitignore` (file size).

---

## Licence

MIT — see `LICENSE`.
