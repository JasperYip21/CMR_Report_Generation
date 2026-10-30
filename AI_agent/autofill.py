"""Generate a CMR non-stress report from a cvi42 text export."""

import argparse
import re
from pathlib import Path
from typing import Any

from docx import Document

try:
    from AI_agent.cvi42_parser import parse_cvi42_report
except ModuleNotFoundError:
    from cvi42_parser import parse_cvi42_report


_HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = _HERE / "AI_test_2026-09-22_Scientific_Report_2026-09-23.txt"
DEFAULT_TEMPLATE = _HERE / "attachments" / "CMR Non-Stress Template.docx"
DEFAULT_OUTPUT = _HERE / "CMR_Non_Stress_Report_Final.docx"


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if b"\x00" in raw[:128]:
        return raw.decode("utf-16-le")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-16")


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_la_max_volume_bsa(
    volume_indexed: float | None, sex: str | None, age: int | None
) -> str | None:
    """Apply the supplied adult 20–80 y reference table when inputs are valid."""
    if volume_indexed is None or age is None or not 20 <= age <= 80:
        return None
    normalized_sex = (sex or "").strip().lower()
    if normalized_sex in {"f", "female", "woman"}:
        boundaries = (27, 53, 60, 67)
    elif normalized_sex in {"m", "male", "man"}:
        boundaries = (26, 52, 59, 66)
    else:
        return None

    small, normal_max, mild_max, moderate_max = boundaries
    if volume_indexed < small:
        return "Small"
    if volume_indexed <= normal_max:
        return "Normal"
    if volume_indexed <= mild_max:
        return "Mildly enlarged"
    if volume_indexed <= moderate_max:
        return "Moderately enlarged"
    return "Severely enlarged"


def _format_measurement(value: Any, unit: str, digits: int = 1) -> str | None:
    number = _number(value)
    return f"{number:.{digits}f} {unit}" if number is not None else None


def _replace_paragraph_text(paragraph: Any, replacement: str) -> None:
    """Replace paragraph contents while retaining its label/body run styling."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(replacement)
        return

    original = paragraph.text
    label_match = re.match(r"^([^:]+:)\s*", original)
    if label_match:
        label = label_match.group(1)
        body = replacement[len(label) :].lstrip()
        runs[0].text = label + " "
        if len(runs) > 1:
            runs[1].text = body
            for run in runs[2:]:
                run.text = ""
        else:
            paragraph.add_run(body)
    else:
        runs[0].text = replacement
        for run in runs[1:]:
            run.text = ""


def _report_values(data: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    lv = data.get("lv", {})
    rv = data.get("rv", {})
    study = data.get("study_info", {})
    la = data.get("la", {})
    not_reported = "Not provided in source export."
    replacements: dict[str, str] = {}

    lv_ef = _format_measurement(lv.get("ejection_fraction_pct"), "%")
    rv_ef = _format_measurement(rv.get("ejection_fraction_pct"), "%")
    lv_edv = _format_measurement(lv.get("edv"), "mL")
    lv_esv = _format_measurement(lv.get("esv"), "mL")
    lv_mass = _format_measurement(lv.get("myomass_diast"), "g")
    lv_wall = _format_measurement(lv.get("max_wall_thickness"), "mm")
    rv_edv = _format_measurement(rv.get("edv"), "mL")
    rv_esv = _format_measurement(rv.get("esv"), "mL")
    lv_function = "; ".join(
        value
        for value in (
            f"EF {lv_ef}" if lv_ef else None,
            f"EDV {lv_edv}" if lv_edv else None,
            f"ESV {lv_esv}" if lv_esv else None,
        )
        if value
    )
    lv_parts = [
        f"LV volumes and systolic function: {lv_function or not_reported}",
        "LV hypertrophy: cannot be assessed from the measurements provided",
        f"maximum LV wall thickness: {lv_wall or not_reported}",
        f"LV mass: {lv_mass or not_reported}",
    ]
    rv_function = "; ".join(
        value
        for value in (
            f"EF {rv_ef}" if rv_ef else None,
            f"EDV {rv_edv}" if rv_edv else None,
            f"ESV {rv_esv}" if rv_esv else None,
            "volumes not reported" if not rv_edv else None,
        )
        if value
    )

    sex = study.get("sex")
    age = study.get("age")
    la_class = classify_la_max_volume_bsa(
        _number(la.get("max_volume_bsa")), sex, age
    )
    replacements["CLINICAL HISTORY: []"] = (
        f"CLINICAL HISTORY: {not_reported}"
    )
    replacements[
        "SCANNER: Siemens 3T Magnetom Vida. [GE Signa Premier 3T.]"
    ] = f"SCANNER: {not_reported}"
    replacements[
        "[] previous cardiac MRI available for comparison. [Comparison is made with previous cardiac MRI dated [].]"
    ] = f"Comparison with previous cardiac MRI: {not_reported}"
    replacements[
        "Cardiovascular Anatomy: [] atrioventricular and ventriculoarterial connections. [ Normal drainage of the SVC and IVC into the right atrium. [] pulmonary venous drainage into the left atrium.]"
    ] = f"Cardiovascular Anatomy: {not_reported}"
    replacements[
        "Aorta: Not dilated. Aortic sinus measures [] mm in diameter."
    ] = f"Aorta: Aortic sinus measurement {not_reported}"
    replacements[
        "Pulmonary Arteries: Main pulmonary artery is [] dilated. Diameter is [] mm. [] This is suspicious for pulmonary hypertension."
    ] = f"Pulmonary Arteries: Main pulmonary artery assessment {not_reported}"
    replacements["Left Atrium: [] for size."] = (
        f"Left Atrium: {la_class} by indexed maximum volume"
        if la_class
        else f"Left Atrium: size/reference classification {not_reported}"
    )
    replacements["Right Atrium: [] for size."] = (
        f"Right Atrium: size assessment {not_reported}"
    )
    replacements[
        "Left Ventricle: [] LV volumes and systolic function. [] LV hypertrophy. Maximum LV wall thickness is [] mm in end-diastole. [] LV mass."
    ] = f"Left Ventricle: {'; '.join(lv_parts)}."
    replacements["Right Ventricle: [] RV volumes and systolic function."] = (
        f"Right Ventricle: {rv_function or not_reported}."
    )
    for valve in ("Aortic", "Pulmonary", "Mitral", "Tricuspid"):
        replacements[f"{valve} Valve: [] appearances and function."] = (
            f"{valve} Valve: assessment {not_reported}"
        )
    replacements["Pericardium: [] effusion or thickening."] = (
        f"Pericardium: assessment {not_reported}"
    )
    replacements[
        "Oedema Imaging (T2 Mapping/T2 STIR): [] oedema. [] native T2 value."
    ] = f"Oedema Imaging (T2 Mapping/T2 STIR): {not_reported}"
    replacements[
        "Late Gadolinium Enhancement (LGE/T1 Mapping): [] LGE or infarct. [] native T1 value."
    ] = f"Late Gadolinium Enhancement (LGE/T1 Mapping): {not_reported}"
    replacements["Extracardiac: [] Nil"] = (
        f"Extracardiac: assessment {not_reported}"
    )
    conclusion = "; ".join(
        value
        for value in (
            f"LV EF {lv_ef}" if lv_ef else None,
            f"RV EF {rv_ef}" if rv_ef else None,
        )
        if value
    )
    replacements["[] LV & RV volumes and systolic function."] = (
        f"{conclusion or 'LV and RV function not reported in source export.'}"
    )
    replacements["[] LGE or infarct"] = (
        "LGE or infarct assessment not reported in source export."
    )

    height = _number(study.get("height_cm"))
    weight = _number(study.get("weight_kg"))
    bsa = None
    edv = _number(lv.get("edv"))
    edv_bsa = _number(lv.get("edv_bsa", lv.get("edv/bsa")))
    if edv is not None and edv_bsa not in (None, 0):
        bsa = edv / edv_bsa
    elif height is not None and weight is not None:
        bsa = ((height * weight) / 3600) ** 0.5

    physical_values = [
        f"{height:.0f}" if height is not None else "Not provided",
        f"{weight:.1f}" if weight is not None else "Not provided",
        f"{bsa:.2f} (derived)" if bsa is not None else "Not provided",
    ]
    return replacements, physical_values


def generate_non_stress_report(
    txt_file_path: str | Path = DEFAULT_INPUT,
    template_path: str | Path = DEFAULT_TEMPLATE,
    output_filename: str | Path = DEFAULT_OUTPUT,
) -> Path:
    """Fill the provided template and return the generated Word document path."""
    source_path = Path(txt_file_path)
    template = Path(template_path)
    output = Path(output_filename)
    data = parse_cvi42_report(_read_text(source_path))
    replacements, physical_values = _report_values(data)
    document = Document(template)

    found: set[str] = set()
    for paragraph in document.paragraphs:
        original = paragraph.text.strip()
        if original in replacements:
            _replace_paragraph_text(paragraph, replacements[original])
            found.add(original)

    missing = set(replacements) - found
    if missing:
        raise ValueError(
            "The supplied Word template does not contain expected paragraphs: "
            + ", ".join(sorted(missing))
        )

    if not document.tables or len(document.tables[-1].rows) < 1:
        raise ValueError("The Word template is missing its physical measurements table.")
    table = document.tables[-1]
    if len(table.columns) < 6:
        raise ValueError("The physical measurements table must have at least six columns.")
    for column, label, value in zip(
        (0, 2, 4), ("Height:", "Weight:", "BSA:"), physical_values
    ):
        _replace_paragraph_text(
            table.cell(0, column).paragraphs[0], f"{label} {value}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill the CMR non-stress template from a cvi42 TXT export."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="cvi42 TXT export")
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
