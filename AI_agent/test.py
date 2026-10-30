#%%
import json
from pathlib import Path
import pandas as pd

def process_cohort_directory(input_dir: str) -> pd.DataFrame:
    all_reports = []
    folder = Path(input_dir)
    
    for file_path in folder.glob("*.txt"):
        try:
            # Handle UTF-16 encoding automatically
            with open(file_path, "r", encoding="utf-16") as f:
                text = f.read()
                data = parse_cvi42_report(text)
                data["source_file"] = file_path.name
                all_reports.append(data)
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            
    # Flatten JSON into a single structured DataFrame
    df = pd.json_normalize(all_reports)
    return df


def parse_cvi42_report(text: str) -> dict:
    """Parses tab-separated cvi42 text exports into structured JSON data."""
    data = {"study_info": {}, "lv": {}, "rv": {}, "warnings": []}

    # Split text into lines and clean whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    current_section = None

    for line in lines:
        # Detect Section Headers (e.g., SAX3D LV & RV Function)
        if line.startswith("---"):
            continue

        parts = [p.strip() for p in line.split("\t") if p.strip()]

        # Identify major section titles
        if len(parts) == 1 and not any(
            char.isdigit() for char in parts[0][:5]
        ):
            current_section = parts[0].lower()
            continue

        if len(parts) >= 2:
            key, val = parts[0], parts[1]

            # Parse Metadata
            if "patient" in key.lower() or "study" in key.lower():
                data["study_info"][key.lower().replace(" ", "_")] = val

            elif "heart rate" in key.lower():
                try:
                    data["study_info"]["heart_rate_bpm"] = float(val)
                except ValueError:
                    pass

            # Helper parser for numeric values
            def to_float(v):
                try:
                    return float(v)
                except ValueError:
                    return None

            if "sex" in key or "gender" in key:
                data["study_info"]["sex"] = "Female" if "f" in val.lower() else "Male"
            elif "age" in key:
                try:
                    data["study_info"]["age"] = int(float(val.split()[0]))
                except ValueError:
                    data["study_info"]["age"] = None
            elif "height" in key:
                try:
                    data["study_info"]["height_cm"] = float(val.replace("cm", "").strip())
                except ValueError:
                    data["study_info"]["height_cm"] = None
            elif "weight" in key:
                try:
                    data["study_info"]["weight_kg"] = float(val.replace("kg", "").strip())
                except ValueError:
                    data["study_info"]["weight_kg"] = None

            # Detect LV vs RV parameters based on context or explicit key prefixes
            is_lv = (
                "lv" in key.lower()
                or (current_section and "lv" in current_section)
            ) and "rv" not in key.lower()
            is_rv = "rv" in key.lower() or (
                current_section and "rv" in current_section
            )

            target = "lv" if is_lv else ("rv" if is_rv else None)

            clean_key = (
                key.lower()
                .replace("lv", "")
                .replace("rv", "")
                .strip()
                .replace(" ", "_")
            )

            if target:
                num_val = to_float(val)
                if num_val is not None:
                    # Check if the line has an indexed value in a 3rd column
                    idx_val = (
                        to_float(parts[2])
                        if len(parts) > 2
                        and ("bsa" in parts[2].lower() or parts[2].replace('.', '', 1).isdigit())
                        else None
                    )

                    if "ef" in clean_key or "ejection_fraction" in clean_key:
                        data[target]["ejection_fraction_pct"] = num_val
                    elif clean_key in ["edv", "esv", "sv", "co", "mass"]:
                        data[target][clean_key] = {
                            "value": num_val,
                            "indexed": idx_val,
                        }
                    else:
                        data[target][clean_key] = num_val

        # Extract Warnings or Slice mismatch lines
        if "warning" in line.lower() or "calculated using" in line.lower():
            data["warnings"].append(line)

    return data


# --- Execution ---
file_path = "AI_test_2026-09-22_Scientific_Report_2026-09-23.txt"

with open(file_path, "r", encoding="utf-16") as file:
    report_text = file.read()
    parsed_data = parse_cvi42_report(report_text)
    print(json.dumps(parsed_data, indent=4))