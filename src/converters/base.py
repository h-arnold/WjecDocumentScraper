"""Base classes and shared utilities for PDF to Markdown converters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _is_table_separator_row(row: str) -> bool:
    """Return True if the row is a Markdown table separator row."""
    stripped = row.strip()
    if not stripped.startswith("|"):
        return False
    inner = stripped.strip("|")
    parts = [part.strip() for part in inner.split("|")]
    if not parts:
        return False
    for part in parts:
        if not part:
            return False
        if set(part) - {"-", ":"}:
            return False
    return True


def _split_table_row(row: str) -> list[str]:
    """Split a Markdown table row into individual cell values."""
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _rebuild_table_row(cells: list[str]) -> str:
    """Rebuild a Markdown table row from cleaned cell values."""
    return "| " + " | ".join(cell.strip() for cell in cells) + " |"


def _clean_marker_table_cell(cell: str) -> str:
    """Normalise `<br>` usage inside a single table cell."""
    if "<br" not in cell:
        return cell.strip()

    normalised = cell.replace("<br />", "<br>").replace("<br/>", "<br>")
    parts = [fragment.strip() for fragment in normalised.split("<br>")]
    parts = [fragment for fragment in parts if fragment]

    if not parts:
        return ""

    prefix: list[str] = []
    bullets: list[str] = []
    current_bullet: list[str] | None = None

    for fragment in parts:
        if fragment.startswith("•"):
            # Close any in-flight bullet before starting a new one.
            if current_bullet is not None:
                combined = " ".join(current_bullet).strip()
                if combined:
                    bullets.append(combined)

            entry = fragment.lstrip("•").strip()
            current_bullet = [entry] if entry else []
            continue

        if current_bullet is None:
            prefix.append(fragment)
        else:
            current_bullet.append(fragment)

    if current_bullet is not None:
        combined = " ".join(current_bullet).strip()
        if combined:
            bullets.append(combined)

    if bullets:
        bullet_markup = "".join(f"<li>{item}</li>" for item in bullets)
        prefix_text = " ".join(prefix).strip()
        if prefix_text:
            return f"{prefix_text} <ul>{bullet_markup}</ul>"
        return f"<ul>{bullet_markup}</ul>"

    return " ".join(parts).strip()


def _normalise_marker_markdown(markdown: str) -> str:
    """Normalise marker output so table cells avoid raw `<br>` tags."""
    lines = markdown.splitlines()
    cleaned: list[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        stripped = line.lstrip()
        if stripped.startswith("|") and "|" in stripped:
            table_block: list[str] = []
            while idx < len(lines):
                candidate = lines[idx]
                if not candidate.lstrip().startswith("|"):
                    break
                table_block.append(candidate)
                idx += 1

            cleaned.extend(_clean_marker_table_block(table_block))
            continue

        cleaned.append(line)
        idx += 1

    return "\n".join(cleaned)


def _clean_marker_table_block(rows: list[str]) -> list[str]:
    """Clean a block of Markdown table rows produced by marker."""
    cleaned_rows: list[str] = []

    for row in rows:
        stripped = row.strip()
        if not stripped.startswith("|"):
            cleaned_rows.append(row)
            continue

        if _is_table_separator_row(row):
            cleaned_rows.append(row)
            continue

        cells = _split_table_row(row)
        if not any("<br" in cell for cell in cells):
            cleaned_rows.append(row)
            continue

        cleaned_cells = [_clean_marker_table_cell(cell) for cell in cells]
        cleaned_rows.append(_rebuild_table_row(cleaned_cells))

    return cleaned_rows


@dataclass
class ConversionResult:
    """Result of a PDF to Markdown conversion."""

    markdown: str
    metadata: dict[str, Any] | None = None


class PdfToMarkdownConverter(ABC):
    """Abstract base class for PDF to Markdown converters."""

    @abstractmethod
    def convert(self, pdf_path: Path) -> ConversionResult:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
