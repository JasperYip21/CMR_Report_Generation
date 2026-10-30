"""Classify supported measurements in the CMR non-stress Word template."""

import argparse
import re
from pathlib import Path
from typing import Any

from docx import Document

try:
    from AI_agent.clinical_pdf_parser import parse_clinical_report_pdf
except ModuleNotFoundError:
    from clinical_pdf_parser import parse_clinical_report_pdf


_HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = _HERE / "AI_test_2026-09-22_Clinical_Report_2026-09-23.pdf"
DEFAULT_TEMPLATE = _HERE / "attachments" / "CMR Non-Stress Template.docx"
DEFAULT_OUTPUT = _HERE / "CMR_Non_Stress_Report_Final.docx"


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _classify(value: Any, reference_range: tuple[float, float]) -> str | None:
    number = _number(value)
    if number is None:
        return None
    low, high = reference_range
    return "normal" if low <= number <= high else "abnormal"


def _combine_classifications(*values: str | None) -> str | None:
    if not values or any(value is None for value in values):
        return None
    return "abnormal" if "abnormal" in values else "normal"


def classify_report_measurements(data: dict[str, Any]) -> dict[str, list[str | None]]:
    """Classify metrics supported by the female >=60 y reference table."""
    study = data.get("study_info", {})
    age = study.get("age")
    sex = (study.get("sex") or "").strip().lower()
    if age is None or age < 60 or sex not in {"f", "female", "woman"}:
        return {}

    lv = data.get("lv", {})
    rv = data.get("rv", {})
    lv_ranges = {
        "edv": (78, 162),
        "esv": (19, 57),
        "sv": (54, 110),
        "ejection_fraction_pct": (60, 78),
    }
    rv_ranges = {
        "edv": (70, 158),
        "esv": (9, 61),
        "sv": (54, 106),
        "ejection_fraction_pct": (58, 82),
    }

    def function_status(
        measurements: dict[str, Any], ranges: dict[str, tuple[float, float]]
    ) -> str | None:
        statuses = [
            _classify(measurements.get(key), reference_range)
            for key, reference_range in ranges.items()
        ]
        return _combine_classifications(*statuses)

    lv_function_statuses = [function_status(lv, lv_ranges)]
    if "edv_bsa" in lv:
        lv_function_statuses.append(_classify(lv["edv_bsa"], (52, 86)))
    lv_function = _combine_classifications(*lv_function_statuses)

    rv_function_statuses = [function_status(rv, rv_ranges)]
    if "edv_bsa" in rv:
        rv_function_statuses.append(_classify(rv["edv_bsa"], (48, 84)))
    rv_function = _combine_classifications(*rv_function_statuses)

    lv_mass_statuses = [_classify(lv.get("myomass_diast"), (74, 146))]
    if "myomass_bsa" in lv:
        lv_mass_statuses.append(_classify(lv["myomass_bsa"], (48, 78)))
    lv_mass = _combine_classifications(*lv_mass_statuses)
    return {
        "Left Ventricle": [
            lv_function,
            lv_mass,
            None,
            lv_mass,
        ],
        "Right Ventricle": [rv_function],
        "Conclusion": [_combine_classifications(lv_function, rv_function), None],
    }


def _replace_classified_placeholders(
    paragraph: Any, values: list[str | None]
) -> None:
    """Replace classified [] tokens only; preserve other text and formatting."""
    token_index = 0

    def replace_match(match: re.Match[str]) -> str:
        nonlocal token_index
        replacement = values[token_index] if token_index < len(values) else None
        token_index += 1
        return replacement if replacement is not None else match.group()

    for run in paragraph.runs:
        run.text = re.sub(r"\[\]", replace_match, run.text)


def generate_non_stress_report(
    pdf_file_path: str | Path = DEFAULT_INPUT,
    template_path: str | Path = DEFAULT_TEMPLATE,
    output_filename: str | Path = DEFAULT_OUTPUT,
) -> Path:
    """Classify supported measurements and save the minimally changed template."""
    data = parse_clinical_report_pdf(pdf_file_path)
    classifications = classify_report_measurements(data)
    document = Document(template_path)

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text.startswith("Left Ventricle:"):
            values = classifications.get("Left Ventricle")
        elif text.startswith("Right Ventricle:"):
            values = classifications.get("Right Ventricle")
        elif text == "[] LV & RV volumes and systolic function.":
            values = classifications.get("Conclusion")
        else:
            values = None
        if values is not None:
            _replace_classified_placeholders(paragraph, values)

    output = Path(output_filename)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify supported CMR measurements in the non-stress template."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="clinical report PDF")
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="CMR non-stress DOCX template",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Generated DOCX path"
    )
    args = parser.parse_args()
    result = generate_non_stress_report(args.input, args.template, args.output)
    print(f"Generated report: {result}")


if __name__ == "__main__":
    main()
