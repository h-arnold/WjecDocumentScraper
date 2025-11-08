"""Post-process downloaded WJEC subject folders by organising PDFs and Markdown."""

from __future__ import annotations

import argparse
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass, field

from markitdown import MarkItDown, MarkItDownException

logger = logging.getLogger(__name__)


@dataclass
class SubjectResult:
    """Summary of the work completed for a single subject folder."""

    subject_dir: Path
    copied: int = 0
    converted: int = 0
    errors: list[str] = field(default_factory=list)


def find_subject_directories(root: Path) -> list[Path]:
    """Return subject directories under the provided Documents root."""
    return sorted(path for path in root.iterdir() if path.is_dir())


def copy_root_pdfs(subject_dir: Path, pdf_directory: Path) -> list[Path]:
    """Copy PDFs from the subject root into the dedicated pdfs/ directory."""
    pdf_directory.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for pdf_path in subject_dir.glob("*.pdf"):
        destination = pdf_directory / pdf_path.name
        try:
            shutil.copy2(pdf_path, destination)
            copied.append(destination)
            try:
                pdf_path.unlink()
            except OSError as exc:
                logger.warning("Failed to remove original %s after copy: %s", pdf_path, exc)
        except OSError as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to copy %s -> %s: %s", pdf_path, destination, exc)
    return copied


def convert_pdf_to_markdown(converter: MarkItDown, pdf_path: Path, markdown_directory: Path) -> Path:
    """Convert a PDF to Markdown and return the output path."""
    markdown_directory.mkdir(parents=True, exist_ok=True)
    result = converter.convert(pdf_path)
    markdown_path = markdown_directory / f"{pdf_path.stem}.md"
    markdown_path.write_text(result.markdown, encoding="utf-8")
    return markdown_path


def process_subject(subject_dir: Path) -> SubjectResult:
    """Copy PDFs and render Markdown for a single subject directory."""
    pdf_directory = subject_dir / "pdfs"
    markdown_directory = subject_dir / "markdown"

    result = SubjectResult(subject_dir=subject_dir)

    copied_paths = copy_root_pdfs(subject_dir, pdf_directory)
    result.copied = len(copied_paths)

    converter = MarkItDown()
    for pdf_path in sorted(pdf_directory.glob("*.pdf")):
        try:
            convert_pdf_to_markdown(converter, pdf_path, markdown_directory)
            result.converted += 1
        except (MarkItDownException, OSError) as exc:
            logger.warning("Failed to convert %s: %s", pdf_path, exc)
            result.errors.append(f"{pdf_path.name}: {exc}")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Unexpected error converting %s", pdf_path)
            result.errors.append(f"{pdf_path.name}: {exc}")
    return result


def run(root: Path, max_workers: int | None = None) -> list[SubjectResult]:
    """Process each subject directory and return per-subject results."""
    subject_dirs = find_subject_directories(root)
    if not subject_dirs:
        logger.info("No subject directories found under %s", root)
        return []

    executor_kwargs = {"max_workers": max_workers} if max_workers else {}
    results: list[SubjectResult] = []

    with ThreadPoolExecutor(**executor_kwargs) as executor:
        futures = {}
        for subject_dir in subject_dirs:
            print(f"Starting post-processing for {subject_dir.name}...")
            futures[executor.submit(process_subject, subject_dir)] = subject_dir
        for future in as_completed(futures):
            subject_dir = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Subject processing failed for %s", subject_dir)
                fallback = SubjectResult(subject_dir=subject_dir)
                fallback.errors.append(str(exc))
                results.append(fallback)
            else:
                print(f"Finished post-processing for {subject_dir.name}.")

    return results


def build_parser() -> argparse.ArgumentParser:
    """Configure the CLI parser for the post-processing utility."""
    parser = argparse.ArgumentParser(
        description="Organise downloaded PDFs into per-subject folders and convert them to Markdown.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("Documents"),
        help="Root directory that contains subject folders (default: Documents).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Maximum number of subject conversions to process concurrently.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity (default: INFO).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.max_workers is not None and args.max_workers < 1:
        parser.error("--max-workers must be at least 1")

    logging.basicConfig(level=getattr(logging, args.log_level))

    results = run(args.root, args.max_workers)

    if not results:
        print(f"No subject folders found in {args.root.resolve()}")
        return 1

    totals = SubjectResult(subject_dir=args.root)
    for result in sorted(results, key=lambda item: item.subject_dir.name.lower()):
        totals.copied += result.copied
        totals.converted += result.converted
        totals.errors.extend(result.errors)
        message = (
            f"{result.subject_dir.name}: copied {result.copied} PDF(s), converted {result.converted} to Markdown"
        )
        if result.errors:
            message += f" ({len(result.errors)} error(s); see logs)"
        print(message)

    print(
        f"\nProcessed {len(results)} subject(s). Copied {totals.copied} PDF(s) and generated {totals.converted} Markdown file(s)."
    )
    if totals.errors:
        print(f"Encountered {len(totals.errors)} error(s); check logs for details.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
