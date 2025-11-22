import csv
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path like the other tests do.
sys.path.insert(0, os.getcwd())
from scripts.merge_document_reports import merge_document_reports
from src.llm_review.llm_categoriser.persistence import CSV_HEADERS


def make_sample_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def test_merge_document_reports(tmp_path: Path):
    # Setup Documents structure
    docs = tmp_path / "Documents"
    # Subject A
    subject_a = docs / "Subject-A" / "document_reports"
    csv_a = subject_a / "a1.csv"
    rows_a = [
        {
            "issue_id": "1",
            "page_number": "1",
            "issue": "test",
            "highlighted_context": "c1",
            "pass_code": "PassCode.LTC",
            "error_category": "ErrorCategory.STYLISTIC_PREFERENCE",
            "confidence_score": "80",
            "reasoning": "r1",
        },
    ]
    make_sample_csv(csv_a, rows_a)

    # Subject B with two files
    subject_b = docs / "Subject-B" / "document_reports"
    csv_b1 = subject_b / "b1.csv"
    csv_b2 = subject_b / "b2.csv"
    rows_b1 = [
        {
            "issue_id": "2",
            "page_number": "2",
            "issue": "test2",
            "highlighted_context": "c2",
            "pass_code": "PassCode.LTC",
            "error_category": "ErrorCategory.PARSING_ERROR",
            "confidence_score": "90",
            "reasoning": "r2",
        },
    ]
    rows_b2 = [
        {
            "issue_id": "3",
            "page_number": "3",
            "issue": "test3",
            "highlighted_context": "c3",
            "pass_code": "PassCode.LTC",
            "error_category": "ErrorCategory.SPELLING",
            "confidence_score": "95",
            "reasoning": "r3",
        },
    ]
    make_sample_csv(csv_b1, rows_b1)
    make_sample_csv(csv_b2, rows_b2)

    # Run merge
    merged = merge_document_reports(output_dir=docs, output_file_name="out.csv")

    assert merged.exists()

    with merged.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # header should include Subject and Filename plus CSV_HEADERS
        expected_fields = ["Subject", "Filename"] + CSV_HEADERS
        assert reader.fieldnames == expected_fields

        rows = list(reader)
        assert len(rows) == 3

        # Validate first row fields
        assert rows[0]["Subject"] == "Subject-A"
        assert rows[0]["Filename"] == "a1.csv"
        assert rows[0]["issue_id"] == "1"

        # Validate other rows
        # second row should be Subject-B b1.csv
        assert rows[1]["Subject"] == "Subject-B"
        assert rows[1]["Filename"] == "b1.csv"
        assert rows[2]["Subject"] == "Subject-B"
        assert rows[2]["Filename"] == "b2.csv"
