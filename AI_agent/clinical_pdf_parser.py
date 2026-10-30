"""Extract reported demographic and CMR measurements from clinical report PDFs."""

import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader


_NUMBER = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))"


def _capture(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return float(match.group(1)) if match else None


def parse_clinical_report_text(text: str) -> dict[str, Any]:
    """Parse cvi42 clinical-report text while leaving absent fields unset."""
    data: dict[str, Any] = {
        "study_info": {},
        "lv": {},
        "rv": {},
        "la": {},
        "ra": {},
        "aorta": {},
        "pulmonary_artery": {},
    }

    sex = re.search(r"\bPatient\s+Sex:\s*([A-Za-z]+)", text, re.IGNORECASE)
    if sex:
        normalized = sex.group(1).lower()
        if normalized.startswith("f"):
            data["study_info"]["sex"] = "Female"
        elif normalized.startswith("m"):
            data["study_info"]["sex"] = "Male"

    age = _capture(text, rf"\bAge:\s*{_NUMBER}\s*Y")
    height = _capture(text, rf"\bHeight:\s*{_NUMBER}\s*cm")
    weight = _capture(text, rf"\bWeight:\s*{_NUMBER}\s*kg")
    bsa = _capture(text, rf"\bBSA:\s*{_NUMBER}\s*m")
    study_info = data["study_info"]
    if age is not None:
        study_info["age"] = int(age)
    if height is not None:
        study_info["height_cm"] = height
    if weight is not None:
        study_info["weight_kg"] = weight
    if bsa is not None:
        study_info["bsa_m2"] = bsa

    study_date = re.search(
        r"\bStudy\s+Date:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE
    )
    if study_date:
        study_info["study_date"] = study_date.group(1)

    aortic_sinus_cm = _capture(
        text, rf"\bAortic\s+Sinus\b.*?\blength:\s*{_NUMBER}\s*cm"
    )
    mpa_cm = _capture(text, rf"\bMPA\b.*?\blength:\s*{_NUMBER}\s*cm")
    if aortic_sinus_cm is not None:
        data["aorta"]["sinus_line_measurement_mm"] = aortic_sinus_cm * 10
    if mpa_cm is not None:
        data["pulmonary_artery"]["main_line_measurement_mm"] = mpa_cm * 10

    for chamber in ("la", "ra"):
        contour = re.search(
            rf"\b{chamber.upper()}\s+on\s+image\b(.*?)(?=\n\s*(?:Native\s+T1|RA\s+on\s+image|SAX3D\s+Stack)|\Z)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if contour:
            area = _capture(contour.group(1), rf"\barea:\s*{_NUMBER}\s*cm")
            if area is not None:
                data[chamber]["contour_area_cm2"] = area

    lv_block_match = re.search(
        r"\bSAX3D\s+Stack\s+LV\s+Function\b(.*?)(?=\bSAX3D\s+Stack\s+RV\s+Function\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    rv_block_match = re.search(
        r"\bSAX3D\s+Stack\s+RV\s+Function\b(.*?)(?=\bDiastolic\s+Phase|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def parse_ventricle(block: str, target: dict[str, Any], prefix: str = "") -> None:
        labels = {
            "edv": "EDV",
            "esv": "ESV",
            "sv": "SV",
            "ejection_fraction_pct": "EF",
            "co": "CO",
        }
        for field, label in labels.items():
            target[label.lower() if field != "ejection_fraction_pct" else field] = (
                _capture(block, rf"(?<![A-Za-z]){prefix}{label}:\s*{_NUMBER}")
            )
        for field in ("edv", "esv", "sv"):
            key = field if prefix == "" else field
            if target.get(key) is None:
                target.pop(key, None)
            else:
                target[key] = {"value": target[key]}
        if target.get("co") is None:
            target.pop("co", None)
        if target.get("ejection_fraction_pct") is None:
            target.pop("ejection_fraction_pct", None)

    if lv_block_match:
        block = lv_block_match.group(1)
        parse_ventricle(block, data["lv"])
        mass = _capture(block, rf"\bMyo\s+Mass\s+\(Diast\):\s*{_NUMBER}\s*g")
        if mass is not None:
            data["lv"]["myomass_diast"] = mass
        for metric in ("EDV", "ESV", "SV"):
            indexed_value = _capture(block, rf"\b{metric}/BSA:\s*{_NUMBER}")
            if indexed_value is not None:
                data["lv"][f"{metric.lower()}_bsa"] = indexed_value
        indexed_mass = _capture(block, rf"\bMyo\s+Mass/BSA\s+{_NUMBER}")
        if indexed_mass is not None:
            data["lv"]["myomass_bsa"] = indexed_mass
        wall_match = re.search(
            r"\bGlobal\s+Peak\s+Wall\s+Thickness\s+\(Diast\):"
            r"(.*?)\bSAX3D\s+Stack\s+RV\s+Function\b",
            block + "SAX3D Stack RV Function",
            flags=re.IGNORECASE | re.DOTALL,
        )
        if wall_match:
            wall = _capture(wall_match.group(1), rf"\bSlice\s+\d+\s+{_NUMBER}\s*mm")
            if wall is not None:
                data["lv"]["max_wall_thickness"] = wall

    if rv_block_match:
        rv_block = rv_block_match.group(1)
        parse_ventricle(rv_block, data["rv"], prefix="RV")
        indexed_edv = _capture(rv_block, rf"\bRVEDV/BSA:\s*{_NUMBER}")
        if indexed_edv is not None:
            data["rv"]["edv_bsa"] = indexed_edv

    return data


def parse_clinical_report_pdf(path: str | Path) -> dict[str, Any]:
    """Extract text from a selectable-text PDF and parse supported report data."""
    pdf_path = Path(path)
    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        raise ValueError(f"PDF is encrypted and cannot be read: {pdf_path}")

    pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(
            f"No selectable text was found in {pdf_path}; scanned PDFs need OCR first."
        )
    parsed = parse_clinical_report_text(text)
    if not any(parsed[key] for key in ("study_info", "lv", "rv", "la", "ra")):
        raise ValueError(f"No supported CMR fields were found in PDF: {pdf_path}")
    return parsed
