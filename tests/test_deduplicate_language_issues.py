from __future__ import annotations

import csv
from pathlib import Path

from src import __name__ as package_name  # ensure repo root is on sys.path in tests

from scripts.deduplicate_language_issues import (
    DEFAULT_HEADERS,
    deduplicate_rows,
    read_csv_rows,
    write_csv,
    run_cli,
)


def _write_csv(path: Path, header: list[str], rows: list[list[str]]):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_deduplicate_basic(tmp_path: Path) -> None:
    csv_path = tmp_path / "report.csv"
    header = DEFAULT_HEADERS
    rows = [
        ["Subject", "file.md", "", "R1", "misspelling", "Thiss", "typo", "This", "Thiss is a test"],
        ["Subject", "file.md", "", "R1", "misspelling", "Thiss", "typo", "This", "Thiss is a test"],
    ]

    _write_csv(csv_path, header, rows)
    h, table = read_csv_rows(csv_path)
    assert h == header
    unique, counts = deduplicate_rows(table, header)
    assert len(unique) == 1
    key = tuple((v or "") for v in (
        unique[0][c] for c in header
    ))
    assert counts.get(key, 0) == 2


def test_deduplicate_with_counts_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "report.csv"
    out_path = tmp_path / "out.csv"
    header = DEFAULT_HEADERS
    rows = [
        ["Subject", "one.md", "", "R1", "misspelling", "Thiss", "typo", "This", "ctx"],
        ["Subject", "two.md", "", "R2", "misspelling", "Wjec", "typo", "WJEC", "ctx2"],
        ["Subject", "one.md", "", "R1", "misspelling", "Thiss", "typo", "This", "ctx"],
    ]

    _write_csv(csv_path, header, rows)
    h, table = read_csv_rows(csv_path)
    unique, counts = deduplicate_rows(table, header)

    # tiny sanity check
    assert len(unique) == 2
    # use write_csv to ensure writing succeeds with Occurrences added
    out_header = list(h) + ["Occurrences"]
    rows_with_counts = []
    for row in unique:
        # build key
        key = tuple((row.get(col, "") or "") for col in header)
        r = dict(row)
        r["Occurrences"] = str(counts.get(key, 1))
        rows_with_counts.append(r)

    write_csv(out_path, out_header, rows_with_counts)
    assert out_path.exists()


def test_run_cli_filters_non_morfolok(tmp_path: Path) -> None:
    """The CLI should drop rows whose Rule ID is not MORFOLOGIK_RULE_EN_GB."""

    csv_path = tmp_path / "report.csv"
    out_path = tmp_path / "out.csv"
    header = DEFAULT_HEADERS

    # Two rows: one MORFOLOGIK and one different rule ID with identical content
    rows = [
        ["Subject", "file.md", "", "MORFOLOGIK_RULE_EN_GB", "misspelling", "Thiss", "typo", "This", "ctx"],
        ["Subject", "file.md", "", "OTHER_RULE", "misspelling", "Thiss", "typo", "This", "ctx"],
    ]

    _write_csv(csv_path, header, rows)

    # Run CLI and write to out_path
    rc = run_cli([str(csv_path), "-o", str(out_path)])
    assert rc == 0
    assert out_path.exists()

    h, table = read_csv_rows(out_path)
    # Every row in the output should have Rule ID MORFOLOGIK_RULE_EN_GB
    assert all((r.get("Rule ID") or "") == "MORFOLOGIK_RULE_EN_GB" for r in table)
