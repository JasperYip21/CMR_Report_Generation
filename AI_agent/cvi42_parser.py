"""Parsing helpers for tab-separated cvi42 scientific report exports."""

import re
from typing import Any


_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _number(value: str) -> float | None:
    match = _NUMBER.search(value)
    return float(match.group()) if match else None


def parse_cvi42_report(text: str) -> dict[str, Any]:
    """Parse cvi42 metadata and LV/RV metrics without guessing missing values."""
    data: dict[str, Any] = {
        "study_info": {},
        "lv": {},
        "rv": {},
        "la": {},
        "warnings": [],
    }
    section = ""
    reading_peak_wall_thickness = False
    waiting_for_diastolic_wall_thickness = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("---"):
            continue
        line_lower = line.lower()
        if "sax 3d lv peak wall thickness" in line_lower:
            section = line_lower
            reading_peak_wall_thickness = True
            waiting_for_diastolic_wall_thickness = False
            continue
        if (
            reading_peak_wall_thickness
            and "total peak wall thickness" in line_lower
            and "diastolic phase" in line_lower
        ):
            waiting_for_diastolic_wall_thickness = True
            continue
        if reading_peak_wall_thickness and line_lower.startswith("sax 3d"):
            reading_peak_wall_thickness = False

        # Keep empty tab-separated columns; the cvi42 export uses them for
        # metadata and multi-column measurement tables.
        parts = [part.strip() for part in raw_line.split("\t")]
        if waiting_for_diastolic_wall_thickness and len(parts) >= 3:
            thickness = _number(parts[2])
            if thickness is not None:
                data["lv"]["max_wall_thickness"] = thickness
                waiting_for_diastolic_wall_thickness = False
                continue

        key = parts[0] if parts else ""
        value = parts[1] if len(parts) > 1 else ""
        key_lower = key.lower()

        if not value and len(parts) < 3:
            if not any(char.isdigit() for char in line[:5]):
                section = line.lower()
            continue

        if "patient" in key_lower or "study" in key_lower:
            data["study_info"][key_lower.replace(" ", "_")] = value
        if "sex" in key_lower or "gender" in key_lower:
            normalized = value.lower()
            if normalized.startswith(("f", "woman")):
                data["study_info"]["sex"] = "Female"
            elif normalized.startswith(("m", "man")):
                data["study_info"]["sex"] = "Male"
        if "age" in key_lower:
            age = _number(value)
            data["study_info"]["age"] = int(age) if age is not None else None
        if "height" in key_lower:
            data["study_info"]["height_cm"] = _number(value)
        if "weight" in key_lower:
            data["study_info"]["weight_kg"] = _number(value)
        if "heart rate" in key_lower:
            heart_rate = _number(value)
            if heart_rate is not None:
                data["study_info"]["heart_rate_bpm"] = heart_rate

        # The export's measured values are grouped under "Clinical Results
        # LV" and "Clinical Results RV"; section matching must not treat a
        # combined "LV & RV" heading as one ventricle or mislabel the RV.
        target = None
        if "clinical results lv" in section:
            target = "lv"
        elif "clinical results rv" in section:
            target = "rv"
        elif "lv" in key_lower and "rv" not in key_lower:
            target = "lv"
        elif "rv" in key_lower:
            target = "rv"

        metric = _number(value)
        if metric is not None and "la" in key_lower and (
            "volume/bsa" in key_lower or "volume index" in key_lower
        ):
            data["la"]["max_volume_bsa"] = metric
        if target and metric is not None:
            clean_key = (
                key_lower.replace("lv", "")
                .replace("rv", "")
                .strip()
                .replace(" ", "_")
                .replace("/", "_")
            )
            if "ef" in clean_key or "ejection_fraction" in clean_key:
                data[target]["ejection_fraction_pct"] = metric
            elif clean_key in {"edv_bsa", "esv_bsa", "sv_bsa"}:
                data[target][clean_key] = metric
            elif clean_key in {"edv", "esv", "sv", "co", "mass"}:
                data[target][clean_key] = {
                    "value": metric,
                    "indexed": None,
                }
            else:
                data[target][clean_key] = metric

        if "warning" in line.lower() or "calculated using" in line.lower():
            data["warnings"].append(line)

    return data
