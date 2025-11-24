"""Post-process downloaded WJEC subject folders by organising PDFs and Markdown."""

from __future__ import annotations

import argparse
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from ..converters import PdfToMarkdownConverter, create_converter

logger = logging.getLogger(__name__)


@dataclass
class SubjectResult:
    """Summary of the work completed for a single subject folder."""

    subject_dir: Path
    copied: int = 0
    converted: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class SinglePdfResult:
    """Result of processing a single PDF file."""

    pdf_path: Path
    markdown_path: Path | None = None
    success: bool = False
    error: str | None = None


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
                logger.warning(
                    "Failed to remove original %s after copy: %s",
                    pdf_path,
                    exc,
                    exc_info=True,
                )
        except OSError as exc:  # pragma: no cover - defensive guard
            logger.warning(
                "Failed to copy %s -> %s: %s", pdf_path, destination, exc, exc_info=True
            )
    return copied


def convert_pdf_to_markdown(
    converter: PdfToMarkdownConverter, pdf_path: Path, markdown_directory: Path
) -> Path:
    """Convert a PDF to Markdown and return the output path.

    Also saves any extracted images to the markdown directory.
    """
    markdown_directory.mkdir(parents=True, exist_ok=True)
    result = converter.convert(pdf_path)
    markdown_path = markdown_directory / f"{pdf_path.stem}.md"
    markdown_path.write_text(result.markdown, encoding="utf-8")

    # Save any extracted images to the markdown directory
    if result.metadata and "images" in result.metadata:
        images = result.metadata["images"]
        if images:
            logger.info(
                "Saving %d extracted image(s) for %s", len(images), pdf_path.name
            )
            for image_name, image_data in images.items():
                image_path = markdown_directory / image_name
                try:
                    # Handle PIL Image objects (from Marker)
                    if hasattr(image_data, "save"):
                        image_data.save(image_path)
                    # Handle raw bytes
                    elif isinstance(image_data, bytes):
                        image_path.write_bytes(image_data)
                    else:
                        logger.warning(
                            "Unknown image data type for %s: %s",
                            image_name,
                            type(image_data),
                        )
                except Exception as exc:
                    logger.warning(
                        "Failed to save image %s: %s", image_name, exc, exc_info=True
                    )

    return markdown_path


def process_single_pdf(
    pdf_path: Path, converter_type: str = "marker"
) -> SinglePdfResult:
    """Process a single PDF file: copy to pdfs/ if needed, convert to markdown.

    Args:
        pdf_path: Path to the PDF file to process. Must be within a subject directory
                  (either at the root or in the pdfs/ subdirectory).
        converter_type: Type of converter to use ("marker" or "docling").

    Returns:
        SinglePdfResult indicating success/failure and paths.

    The function expects the PDF to be in one of these locations:
    - Documents/Subject-Name/filename.pdf (will be copied to pdfs/)
    - Documents/Subject-Name/pdfs/filename.pdf (already in correct location)

    It will create the markdown file at:
    - Documents/Subject-Name/markdown/filename.md
    """
    result = SinglePdfResult(pdf_path=pdf_path)
    converter = create_converter(converter_type)

    try:
        # Validate that the PDF exists
        if not pdf_path.exists():
            result.error = f"PDF file does not exist: {pdf_path}"
            return result

        if not pdf_path.is_file():
            result.error = f"Path is not a file: {pdf_path}"
            return result

        # Determine subject directory and target locations
        # PDF should be at: Documents/Subject-Name/[pdfs/]filename.pdf
        if pdf_path.parent.name == "pdfs":
            # Already in pdfs/ subdirectory: Documents/Subject-Name/pdfs/file.pdf
            subject_dir = pdf_path.parent.parent
            pdf_directory = pdf_path.parent
            final_pdf_path = pdf_path

            # Validate: pdfs parent should not be "Documents" or similar root dirs
            if subject_dir.name in ("Documents", "documents", ""):
                result.error = (
                    f"PDF is not within a valid subject directory structure: {pdf_path}"
                )
                return result
        else:
            # In subject root: Documents/Subject-Name/file.pdf
            subject_dir = pdf_path.parent
            pdf_directory = subject_dir / "pdfs"

            # Validate that this is not directly in a root-level directory like "Documents"
            # Check if the parent is named "Documents" (case-insensitive) or has no parent
            parent_name = subject_dir.name.lower()
            if (
                parent_name in ("documents", "")
                or not subject_dir.parent
                or subject_dir.parent == subject_dir
            ):
                result.error = (
                    f"PDF is not within a valid subject directory structure: {pdf_path}"
                )
                return result

            # Copy PDF to pdfs/ subdirectory
            pdf_directory.mkdir(parents=True, exist_ok=True)
            final_pdf_path = pdf_directory / pdf_path.name

            try:
                shutil.copy2(pdf_path, final_pdf_path)
                try:
                    pdf_path.unlink()
                except OSError as exc:
                    logger.warning(
                        "Failed to remove original %s after copy: %s",
                        pdf_path,
                        exc,
                        exc_info=True,
                    )
            except OSError as exc:
                result.error = f"Failed to copy PDF to pdfs/ directory: {exc}"
                logger.exception(
                    "Failed to copy PDF to pdfs/ directory: %s -> %s",
                    pdf_path,
                    final_pdf_path,
                )
                return result

        # Convert to markdown
        markdown_directory = subject_dir / "markdown"
        try:
            markdown_path = convert_pdf_to_markdown(
                converter, final_pdf_path, markdown_directory
            )
            result.markdown_path = markdown_path
            result.pdf_path = final_pdf_path
            result.success = True
        except Exception as exc:
            result.error = f"Failed to convert PDF to markdown: {exc}"
            logger.exception("Failed to convert %s to markdown", final_pdf_path)

    except Exception as exc:
        # Catch any unexpected errors
        result.error = f"Unexpected error: {exc}"
        logger.exception("Unexpected error processing %s", pdf_path)

    finally:
        converter.close()

    return result


def process_subject(subject_dir: Path, converter_type: str = "marker") -> SubjectResult:
    """Copy PDFs and render Markdown for a single subject directory."""
    pdf_directory = subject_dir / "pdfs"
    markdown_directory = subject_dir / "markdown"

    result = SubjectResult(subject_dir=subject_dir)

    copied_paths = copy_root_pdfs(subject_dir, pdf_directory)
    result.copied = len(copied_paths)

    converter = create_converter(converter_type)
    try:
        for pdf_path in sorted(pdf_directory.glob("*.pdf")):
            try:
                convert_pdf_to_markdown(converter, pdf_path, markdown_directory)
                result.converted += 1
            except OSError as exc:
                # File I/O errors
                logger.exception("Failed to convert %s (I/O error)", pdf_path)
                result.errors.append(f"{pdf_path.name}: {exc}")
            except Exception as exc:
                # Catch converter-specific exceptions and any other unexpected errors

                logger.exception("Failed to convert %s", pdf_path)
                result.errors.append(f"{pdf_path.name}: {exc}")
    finally:
        converter.close()

    return result


def run(
    root: Path,
    max_workers: int | None = None,
    converter_type: str = "marker",
    allowed_subject_dirs: set[str] | None = None,
) -> list[SubjectResult]:
    """Process each subject directory and return per-subject results."""
    subject_dirs = find_subject_directories(root)
    if allowed_subject_dirs is not None:
        subject_dirs = [
            path for path in subject_dirs if path.name in allowed_subject_dirs
        ]
    if not subject_dirs:
        logger.info("No subject directories found under %s", root)
        return []

    converter_key = converter_type.lower()
    effective_workers = max_workers
    if converter_key == "marker":
        if max_workers not in (None, 1):
            logger.info(
                "Marker converter runs with a single worker; overriding max_workers=%s to 1.",
                max_workers,
            )
        effective_workers = 1

    executor_kwargs = {}
    if effective_workers is not None:
        executor_kwargs["max_workers"] = effective_workers
    results: list[SubjectResult] = []

    with ThreadPoolExecutor(**executor_kwargs) as executor:
        futures = {}
        for subject_dir in subject_dirs:
            print(f"Starting post-processing for {subject_dir.name}...")
            futures[executor.submit(process_subject, subject_dir, converter_type)] = (
                subject_dir
            )
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
    parser.add_argument(
        "--converter",
        default="marker",
        choices=["marker", "docling"],
        help="Converter to use for PDF to Markdown conversion (default: marker).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.max_workers is not None and args.max_workers < 1:
        parser.error("--max-workers must be at least 1")

    logging.basicConfig(level=getattr(logging, args.log_level))

    results = run(args.root, args.max_workers, args.converter)

    if not results:
        print(f"No subject folders found in {args.root.resolve()}")
        return 1

    totals = SubjectResult(subject_dir=args.root)
    for result in sorted(results, key=lambda item: item.subject_dir.name.lower()):
        totals.copied += result.copied
        totals.converted += result.converted
        totals.errors.extend(result.errors)
        message = f"{result.subject_dir.name}: copied {result.copied} PDF(s), converted {result.converted} to Markdown"
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
