"""Deduplicate issues from a language-check style CSV.

This utility reads a CSV (as produced by the language check report), removes
duplicate rows according to a configurable set of key columns, and writes the
deduplicated CSV to an output file. It can optionally add an "Occurrences"
column showing how many duplicates were collapsed.

Usage (command line):
  python scripts/deduplicate_language_issues.py input.csv -o output.csv

For convenience the default key has been narrowed to just `Issue`.  This
collapses identical spelling suggestions by token while leaving the
`--keys` flag available for custom behaviour.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Tuple


DEFAULT_HEADERS = [
    "Subject",
    "Filename",
    "Page",
    "Rule ID",
    "Type",
    "Issue",
    "Message",
    "Suggestions",
    "Context",
]


def read_csv_rows(path: Path) -> Tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = [row for row in reader]
    return header, rows


def deduplicate_rows(
    rows: Iterable[Mapping[str, str]],
    key_columns: Sequence[str],
    keep: str = "first",
    ignore_case: bool = False,
) -> Tuple[list[dict[str, str]], dict[Tuple[str, ...], int]]:
    """Return (unique_rows, counts) where counts maps key -> integer occurrences.

    keep: 'first' or 'last' - which row to keep when duplicates are found.
    ignore_case: if True, normalise key parts to lowercase before keying.
    """

    if keep not in ("first", "last"):
        raise ValueError("keep must be 'first' or 'last'")

    seen: dict[Tuple[str, ...], dict[str, str]] = {}
    counts: dict[Tuple[str, ...], int] = {}

    for row in rows:
        values = []
        for col in key_columns:
            val = row.get(col, "")
            if val is None:
                val = ""
            values.append(val.lower() if ignore_case else val)
        key = tuple(values)

        counts[key] = counts.get(key, 0) + 1
        if key not in seen:
            seen[key] = dict(row)
            continue

        if keep == "last":
            # replace stored row
            seen[key] = dict(row)

    unique_rows = list(seen.values())
    return unique_rows, counts


def write_csv(path: Path, header: list[str], rows: Iterable[Mapping[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (row.get(k, "") if row.get(k) is not None else "") for k in header})


def run_cli(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description="Deduplicate language-check CSV issues")
    parser.add_argument("input", help="Path to input CSV")
    parser.add_argument("-o", "--output", help="Path to write deduplicated CSV")
    parser.add_argument(
        "--keys",
        help="Comma separated list of column names to use as the dedupe key (default: all language check columns)",
        default=",",
    )
    parser.add_argument("--ignore-case", help="Ignore case when comparing keys", action="store_true")
    parser.add_argument("--keep", choices=("first", "last"), default="first", help="When duplicates are found, keep the first or last occurrence")
    parser.add_argument("--count", action="store_true", help="Add an 'Occurrences' column to show how many rows were collapsed")

    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    # Read
    header, rows = read_csv_rows(input_path)
    if not header:
        print("Input CSV has no header", file=sys.stderr)
        return 3

    # Filter down to only morphological spelling suggestions - these are the
    # spellchecker results (MORFOLOGIK_RULE_EN_GB).  Users requested we drop
    # any other rule IDs before deduping so we don't coalesce e.g. grammar
    # issues with spelling issues.
    rows = [r for r in rows if (r.get("Rule ID") or "") == "MORFOLOGIK_RULE_EN_GB"]

    # Determine default key columns if none provided.
    # Historically we de-duplicated across many language-check columns; this
    # project now prefers a much narrower default key of `Issue` so we collapse
    # identical spelling suggestions by token alone.  This keeps the output
    # compact while leaving the `--keys` flag available for other uses.
    if args.keys == ",":
        key_columns = ["Issue"] if "Issue" in header else [col for col in DEFAULT_HEADERS if col in header]
    else:
        key_columns = [text.strip() for text in args.keys.split(",") if text.strip()]

    if not key_columns:
        print("No key columns found or specified", file=sys.stderr)
        return 4

    for key_hint in key_columns:
        if key_hint not in header:
            print(f"Key column '{key_hint}' not found in CSV header", file=sys.stderr)
            return 5

    deduped, counts = deduplicate_rows(rows, key_columns, keep=args.keep, ignore_case=args.ignore_case)

    output_path = Path(args.output) if args.output else input_path.with_name(input_path.stem + "-deduped.csv")

    out_header = list(header)
    if args.count and "Occurrences" not in out_header:
        out_header.append("Occurrences")

    # Insert 'Occurrences' into each row if requested
    if args.count:
        # Use counts mapping keyed by key_columns
        # Build a small map from key -> occurrences
        key_map: dict[Tuple[str, ...], int] = {}
        for k, v in counts.items():
            key_map[k] = v

        rows_with_counts: list[dict[str, str]] = []
        for row in deduped:
            # Build key for this row
            key = tuple((row.get(col, "") or "").lower() if args.ignore_case else (row.get(col, "") or "") for col in key_columns)
            rc = dict(row)
            rc["Occurrences"] = str(key_map.get(key, 1))
            rows_with_counts.append(rc)

        write_csv(output_path, out_header, rows_with_counts)
    else:
        write_csv(output_path, out_header, deduped)

    print(f"Wrote deduplicated CSV to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
