"""Cohort helpers retained for the existing cvi42 extraction interface."""

import json
from pathlib import Path

import pandas as pd

try:
    from AI_agent.cvi42_parser import parse_cvi42_report
except ModuleNotFoundError:
    from cvi42_parser import parse_cvi42_report


def process_cohort_directory(input_dir: str | Path) -> pd.DataFrame:
    """Parse every UTF-16 cvi42 export in a directory into a data frame."""
    reports = []
    for file_path in Path(input_dir).glob("*.txt"):
        try:
            data = parse_cvi42_report(file_path.read_text(encoding="utf-16"))
            data["source_file"] = file_path.name
            reports.append(data)
        except (OSError, UnicodeError) as error:
            print(f"Error processing {file_path.name}: {error}")
    return pd.json_normalize(reports)


if __name__ == "__main__":
    input_path = Path(__file__).with_name(
        "AI_test_2026-09-22_Scientific_Report_2026-09-23.txt"
    )
    parsed_data = parse_cvi42_report(input_path.read_text(encoding="utf-16"))
    print(json.dumps(parsed_data, indent=4))
