"""Merge per-document llm categoriser CSVs into a single report file.

This script finds all CSVs in Documents/*/document_reports/ and writes them
into a single csv at Documents/llm_categorised-language-check-report.csv.

The merged CSV includes two extra columns at the front:
- Subject
- Filename

Existing per-document CSV columns are preserved. Rows are written in the order
of subject and then filename, with rows for each document in their existing
order.

This script can be used programmatically by importing `merge_document_reports`
and supplying an alternative `output_dir` (useful for tests).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Iterable, List

# Match the headers expected from per-document CSVs
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.llm_review.llm_categoriser.persistence import CSV_HEADERS

DEFAULT_OUTPUT_DIR = Path("Documents")
DEFAULT_OUTPUT_FILE = "llm_categorised-language-check-report.csv"


def iter_document_report_csvs(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Iterable[Path]:
    """Yield all CSV files under <output_dir>/*/document_reports/*.csv."""
    output_dir / "*" / "document_reports" / "*.csv"
    for p in sorted(output_dir.glob("*/document_reports/*.csv")):
        yield Path(p)


def merge_document_reports(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_file_name: str = DEFAULT_OUTPUT_FILE,
) -> Path:
    """Merge per-document CSVs into a single CSV file.

    Args:
        output_dir: Base Documents directory to search in.
        output_file_name: Filename to write to inside `output_dir`.

    Returns:
        Path to the created merged CSV file.
    """
    merged_path = output_dir / output_file_name
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    headers: List[str] = ["Subject", "Filename"] + CSV_HEADERS

    csv_paths = list(iter_document_report_csvs(output_dir))

    # Open merged file and walk through CSVs
    with open(merged_path, "w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=headers)
        writer.writeheader()

        for csv_path in csv_paths:
            # Derive subject and filename
            try:
                subject = csv_path.parent.parent.name
                filename = csv_path.name
            except Exception:
                # Fallback to file name only
                subject = ""
                filename = csv_path.name

            with open(csv_path, "r", encoding="utf-8", newline="") as in_f:
                reader = csv.DictReader(in_f)
                for row in reader:
                    # Normalise to expected CSV_HEADERS
                    base_row = {h: row.get(h, "") for h in CSV_HEADERS}
                    data = {"Subject": subject, "Filename": filename} | base_row
                    writer.writerow(data)

    return merged_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge per-document llm categoriser CSVs into a single report"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Path to Documents root (default: Documents)",
    )
    parser.add_argument(
        "--output-file",
        "-f",
        default=DEFAULT_OUTPUT_FILE,
        help="Name of merged file to write (default: llm_categorised-language-check-report.csv)",
    )

    args = parser.parse_args()

    merged = merge_document_reports(Path(args.output_dir), args.output_file)
    print(f"Wrote merged report to: {merged}")


if __name__ == "__main__":
    main()
