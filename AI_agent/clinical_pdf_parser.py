"""Extract unambiguous demographics and measurements from cvi42 report PDFs."""

import re
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def _normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ").replace("\t", " ")
    return re.sub(r"[ \f\v]+", " ", text)


def _capture_unique(text: str, pattern: str) -> float | None:
    values = [
        float(match.group(1))
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    ]
    if not values or max(values) - min(values) > 1e-6:
        return None
    return values[0]


def _field_value(text: str, label_pattern: str) -> str | None:
    matches = [
        match.group(1).strip()
        for match in re.finditer(
            rf"(?<![\w])(?:{label_pattern})\s*[:=]?\s*(.+?)"
            rf"(?=\s+(?:Patient|Study|Birth|Age|Height|Weight|BSA|Institution|"
            rf"Accession|cvi42)\b|[\r\n]|$)",
            text,
            flags=re.IGNORECASE,
        )
    ]
    values = {value for value in matches if value and not value.lower().startswith("not available")}
    if len(values) != 1:
        return None
    return values.pop()


def _number_field(text: str, label_pattern: str, unit_pattern: str = "") -> float | None:
    return _capture_unique(
        text,
        rf"(?<![\w/])(?:{label_pattern})\s*[:=]?\s*({_NUMBER})\s*{unit_pattern}(?![\w])",
    )


def _parse_ventricle(block: str | None, prefix: str = "") -> dict[str, Any]:
    if block is None:
        return {}
    labels = {
        "edv": "EDV",
        "esv": "ESV",
        "sv": "SV",
        "co": "CO",
        "ci": "CI",
        "ejection_fraction_pct": "EF",
    }
    data: dict[str, Any] = {}
    for field, label in labels.items():
        number = _capture_unique(
            block,
            rf"(?<![\w]){prefix}{label}\s*[:=]?\s*({_NUMBER})(?![\w])",
        )
        if number is not None:
            data[field] = (
                number
                if field in {"co", "ci", "ejection_fraction_pct"}
                else {"value": number}
            )
    for metric in ("EDV", "ESV", "SV"):
        number = _capture_unique(
            block,
            rf"(?<![\w]){prefix}{metric}/BSA\s*[:=]?\s*({_NUMBER})(?![\w])",
        )
        if number is not None:
            data[f"{metric.lower()}_bsa"] = number
    cardiac_index = _capture_unique(
        block, rf"(?<![\w])(?:RV)?CI\s*[:=]?\s*({_NUMBER})(?![\w])"
        )
    if cardiac_index is not None:
        data["ci"] = cardiac_index
    return data


def parse_clinical_report_text(text: str) -> dict[str, Any]:
    """Parse cvi42 PDF text; conflicting repeated values are treated as unknown."""
    text = _normalise_text(text)
    data: dict[str, Any] = {
        "study_info": {},
        "lv": {},
        "rv": {},
        "la": {},
        "ra": {},
        "aorta": {},
        "pulmonary_artery": {},
    }
    study_info = data["study_info"]

    sex_value = _field_value(text, r"(?:Patient\s+)?(?:Sex|Gender)")
    if sex_value:
        normalized = sex_value.strip().lower()
        if normalized in {"f", "female", "woman"}:
            study_info["sex"] = "Female"
        elif normalized in {"m", "male", "man"}:
            study_info["sex"] = "Male"

    age = _number_field(text, r"(?:Patient\s+)?Age", r"(?:years?|yrs?|y)?")
    height = _number_field(text, r"(?:Patient\s+)?Height", r"(?:cm)?")
    weight = _number_field(text, r"(?:Patient\s+)?Weight", r"(?:kg)?")
    bsa = _number_field(text, r"(?:Patient\s+)?BSA", r"(?:m\s*(?:2|²))?")
    if age is not None and age >= 0 and age.is_integer():
        study_info["age"] = int(age)
    if height is not None and height > 0:
        study_info["height_cm"] = height
    if weight is not None and weight > 0:
        study_info["weight_kg"] = weight
    if bsa is not None and bsa > 0:
        study_info["bsa_m2"] = bsa

    ethnicity = _field_value(text, r"(?:Patient\s+)?(?:Ethnicity|Race)")
    if ethnicity:
        study_info["ethnicity"] = ethnicity

    study_dates = set(
        re.findall(
            r"(?<!\d)Study\s+Date\s*[:=]\s*(\d{4}-\d{2}-\d{2})",
            text,
            flags=re.IGNORECASE,
        )
    )
    if len(study_dates) == 1:
        study_info["study_date"] = study_dates.pop()

    data["lv"].update(_parse_ventricle(text))
    data["rv"].update(_parse_ventricle(text, prefix="RV"))

    mass = _capture_unique(
        text, rf"(?<![\w])Myo\s*Mass\s*\(Diast\)\s*[:=]?\s*({_NUMBER})\s*g"
    )
    indexed_mass = _capture_unique(
        text, rf"(?<![\w])Myo\s*Mass/BSA\s+({_NUMBER})(?![\w])"
    )
    if mass is not None:
        data["lv"]["myomass_diast"] = mass
    if indexed_mass is not None:
        data["lv"]["myomass_bsa"] = indexed_mass
    for metric in ("EDV", "ESV", "SV"):
        indexed_value = _capture_unique(
            text, rf"(?<![\w]){metric}/BSA\s*[:=]?\s*({_NUMBER})(?![\w])"
        )
        if indexed_value is not None:
            data["lv"][f"{metric.lower()}_bsa"] = indexed_value
        rv_indexed_value = _capture_unique(
            text, rf"(?<![\w])RV{metric}/BSA\s*[:=]?\s*({_NUMBER})(?![\w])"
        )
        if rv_indexed_value is not None:
            data["rv"][f"{metric.lower()}_bsa"] = rv_indexed_value
    wall = _capture_unique(
        text,
        rf"Global\s+Peak\s+Wall\s+Thickness\s*\(Diast\):"
        rf"[\s\S]{{0,300}}?\bSlice\s+\d+\s+({_NUMBER})\s*mm",
    )
    if wall is not None:
        data["lv"]["max_wall_thickness"] = wall

    # These are contour line-measurements, not validated diameters. Keep the
    # distinction explicit so they cannot be classified using diameter ranges.
    for label, target, key in (
        ("Aortic\\s+Sinus", "aorta", "sinus_line_measurement_cm"),
        ("MPA", "pulmonary_artery", "main_line_measurement_cm"),
    ):
        value = _capture_unique(
            text, rf"\b{label}\b[\s\S]{{0,160}}?\blength\s*:\s*({_NUMBER})\s*cm"
        )
        if value is not None:
            data[target][key] = value

    for chamber in ("la", "ra"):
        chamber_name = "LA" if chamber == "la" else "RA"
        areas = [
            float(match.group(1))
            for match in re.finditer(
                rf"\b{chamber_name}\s+on\s+image\b[\s\S]{{0,160}}?\barea\s*:\s*({_NUMBER})\s*cm",
                text,
                flags=re.IGNORECASE,
            )
        ]
        if areas and max(areas) - min(areas) <= 1e-6:
            data[chamber]["contour_area_cm2"] = areas[0]

    for label, key, unit in (
        (r"Max(?:imum)?\s+LA\s+Volume", "max_volume_ml", r"(?:ml|mL)"),
        (r"Max(?:imum)?\s+LA\s+Volume/BSA", "max_volume_bsa", r"(?:ml\s*/\s*m(?:2|²))"),
    ):
        value = _capture_unique(text, rf"(?<![\w]){label}\s*[:=]\s*({_NUMBER})\s*{unit}(?![\w])")
        if value is not None:
            data["la"][key] = value

    for chamber, label in (("la", r"(?:LA|Left\s+Atrial)"), ("ra", r"(?:RA|Right\s+Atrial)")):
        view_areas = [
            (match.group(1).lower(), "area_cm2", float(match.group(2)))
            for match in re.finditer(
                rf"\b{label}\s+(?:Area\s+)?(?:on\s+)?"
                rf"(2|3|4)\s*[- ]?\s*Ch(?:amber)?\s*(?:Area)?\s*[:=]\s*({_NUMBER})\s*cm",
                text,
                flags=re.IGNORECASE,
            )
        ]
        view_areas.extend(
            (match.group(1).lower(), "area_bsa", float(match.group(2)))
            for match in re.finditer(
                rf"\b{label}\s+(?:Area\s+)?(?:on\s+)?"
                rf"(2|3|4)\s*[- ]?\s*Ch(?:amber)?\s*(?:Area)?/BSA\s*[:=]\s*"
                rf"({_NUMBER})\s*cm(?:2|²)?\s*/\s*m(?:2|²)",
                text,
                flags=re.IGNORECASE,
            )
        )
        views = {view for view, _, _ in view_areas}
        metric_values = {
            metric: {value for _, candidate_metric, value in view_areas if candidate_metric == metric}
            for metric in ("area_cm2", "area_bsa")
        }
        if len(views) == 1 and all(len(values) <= 1 for values in metric_values.values()):
            view = views.pop()
            data[chamber]["area_view"] = f"{view}ch"
            for metric, values in metric_values.items():
                if values:
                    data[chamber][metric] = values.pop()

    return data


def parse_clinical_report_pdf(path: str | Path) -> dict[str, Any]:
    """Extract selectable PDF text and parse recognized demographics/metrics."""
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
    if not any(parsed[key] for key in ("lv", "rv", "la", "ra")):
        raise ValueError(
            f"No supported CMR measurements were found in PDF: {pdf_path}"
        )
    return parsed
