"""Annotate a validation report with plain-English remediation advice.

For each failed entity in the JSON validation report this module asks
Claude to generate a one-paragraph remediation note aimed at the BIM
author. Failures are batched to keep the token cost predictable.

Usage:

    python -m src.llm_remediation \\
        --report results/Ifc4_Revit_MEP_report.json \\
        --out    results/Ifc4_Revit_MEP_remediated.json \\
        --limit  20
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


LOG = logging.getLogger(__name__)
DEFAULT_MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 8


SYSTEM_PROMPT = """You are a senior Services BIM Consultant writing remediation
guidance for a BIM author who has just received a failed IDS validation report.

For each failure the user supplies you write ONE plain-English paragraph
(60-90 words) that:
- States precisely which Pset / property / attribute is missing.
- Names the IFC entity, its GlobalId, and human-readable name.
- Tells the author exactly what value or content to add (e.g. "populate
  Pset_PipeSegmentTypeCommon.NominalDiameter with the design diameter
  in millimetres").
- Mentions the practical downstream impact in one short clause (e.g.
  "without this, hydraulic sizing cannot be verified").
- Is addressed to the BIM author, not to the model checker.

Return a single JSON object with key "remediations" whose value is an
array of objects: {"failure_index": <int>, "advice": "<paragraph>"}.
Indices must correspond to the order of failures supplied by the user.
Return ONLY the JSON object, no commentary, no markdown fences."""


@dataclass
class FailureItem:
    spec_name: str
    spec_description: str
    ifc_class: str
    global_id: str
    name: str
    predefined_type: str
    requirement: str
    reason: str

    def to_prompt_block(self, index: int) -> str:
        return (
            f"[{index}]\n"
            f"  Specification: {self.spec_name}\n"
            f"  Spec description: {self.spec_description}\n"
            f"  Entity: {self.ifc_class} (GlobalId={self.global_id}, "
            f"name={self.name!r}, PredefinedType={self.predefined_type})\n"
            f"  Requirement: {self.requirement}\n"
            f"  Reason: {self.reason}"
        )


def _summarise_requirement(req: dict[str, Any]) -> str:
    facet = req.get("facet_type") or req.get("facet") or ""
    label = req.get("label") or req.get("name") or ""
    desc = req.get("description") or req.get("instructions") or ""
    return " | ".join(p for p in (facet, label, desc) if p)[:200]


def iter_failures(report: dict[str, Any]) -> list[tuple[str, dict[str, Any], FailureItem]]:
    """Yield (path-to-fail, original-fail-dict, FailureItem) triples."""
    out: list[tuple[str, dict[str, Any], FailureItem]] = []
    for s_idx, spec in enumerate(report.get("specifications", [])):
        spec_name = spec.get("name", "")
        spec_desc = spec.get("description", "") or ""
        for r_idx, req in enumerate(spec.get("requirements", [])):
            requirement_text = _summarise_requirement(req)
            for f_idx, fail in enumerate(req.get("failed_entities", [])):
                key = f"specifications[{s_idx}].requirements[{r_idx}].failed_entities[{f_idx}]"
                item = FailureItem(
                    spec_name=spec_name,
                    spec_description=spec_desc,
                    ifc_class=fail.get("class", ""),
                    global_id=fail.get("global_id", ""),
                    name=fail.get("name") or "",
                    predefined_type=fail.get("predefined_type") or "",
                    requirement=requirement_text,
                    reason=fail.get("reason") or "",
                )
                out.append((key, fail, item))
    return out


def _call_claude(client: "anthropic.Anthropic", model: str, items: list[FailureItem]) -> dict[int, str]:
    user_block = "\n\n".join(it.to_prompt_block(i) for i, it in enumerate(items))
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_block}],
    )
    text = "".join(getattr(b, "text", "") for b in response.content).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Claude reply was not valid JSON: {exc}\nReply:\n{text}") from exc
    out: dict[int, str] = {}
    for entry in parsed.get("remediations", []):
        idx = entry.get("failure_index")
        advice = entry.get("advice", "").strip()
        if isinstance(idx, int) and advice:
            out[idx] = advice
    return out


def annotate(report_path: Path, *, limit: int | None = None, model: str | None = None) -> dict[str, Any]:
    import anthropic

    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.template)."
        )
    chosen_model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
    client = anthropic.Anthropic(api_key=api_key)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    triples = iter_failures(report)
    if limit is not None:
        triples = triples[:limit]
    LOG.info("Annotating %d failures via %s (batch size %d)",
             len(triples), chosen_model, BATCH_SIZE)

    for batch_start in range(0, len(triples), BATCH_SIZE):
        batch = triples[batch_start : batch_start + BATCH_SIZE]
        items = [t[2] for t in batch]
        try:
            advice_map = _call_claude(client, chosen_model, items)
        except Exception as exc:
            LOG.warning("Batch %d failed: %s", batch_start, exc)
            continue
        for local_idx, (_, fail_dict, _) in enumerate(batch):
            advice = advice_map.get(local_idx)
            if advice:
                fail_dict["remediation"] = advice
        LOG.info("  Batch %d-%d annotated (%d advices)",
                 batch_start, batch_start + len(batch) - 1, len(advice_map))

    return report


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="m7u5-llm-remediation")
    p.add_argument("--report", required=True, help="Path to a JSON validation report")
    p.add_argument("--out", required=True, help="Path to write the annotated report")
    p.add_argument("--limit", type=int, default=None,
                   help="Annotate at most N failures (useful for cost control)")
    p.add_argument("--model", default=None, help="Override ANTHROPIC_MODEL env var")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname).1s %(message)s",
                        stream=sys.stderr)
    report = annotate(Path(args.report), limit=args.limit, model=args.model)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG.info("Annotated report written to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
