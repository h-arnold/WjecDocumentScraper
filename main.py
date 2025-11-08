"""Command-line entrypoint for the WJEC document scraper."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from postprocess_documents import run as run_postprocess
from wjec_scraper import QUALIFICATION_URLS, download_subject_pdfs, iter_subject_pdf_links


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download PDF documents for the WJEC GCSE Made-for-Wales qualifications.",
    )
    parser.add_argument(
        "--subjects",
        nargs="*",
        metavar="SUBJECT",
        help="Optional list of subject names to download (defaults to all configured subjects).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="Documents",
        help="Root directory where subject folders will be saved.",
    )
    parser.add_argument(
        "--list-subjects",
        action="store_true",
        help="List all available subjects and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be downloaded without saving them.",
    )
    parser.add_argument(
        "--post-process",
        action="store_true",
        help="After downloading, organise PDFs into subject subfolders and convert them to Markdown.",
    )
    parser.add_argument(
        "--post-process-only",
        action="store_true",
        help="Skip downloading and only run the post-processing step on the output directory.",
    )
    parser.add_argument(
        "--post-process-workers",
        type=int,
        default=None,
        help="Maximum number of subject folders to post-process concurrently.",
    )
    parser.add_argument(
        "--converter",
        default="markitdown",
        choices=["markitdown", "marker"],
        help="Converter to use for PDF to Markdown conversion during post-processing (default: markitdown).",
    )
    return parser


def normalise_subject_names(subjects: Iterable[str]) -> set[str]:
    return {subject.strip().lower() for subject in subjects}


def resolve_subjects(subject_args: list[str] | None) -> tuple[dict[str, str], set[str]]:
    if not subject_args:
        return dict(QUALIFICATION_URLS), set()

    requested = normalise_subject_names(subject_args)
    selected = {
        subject: url for subject, url in QUALIFICATION_URLS.items() if subject.lower() in requested
    }
    missing = requested.difference({subject.lower() for subject in selected})
    return selected, missing


def perform_post_processing(output_root: Path, max_workers: int | None, converter_type: str = "markitdown") -> int:
    """Invoke the post-processing pipeline and print a concise summary."""
    results = run_postprocess(output_root, max_workers, converter_type)
    if not results:
        print(f"No subject folders found in {output_root.resolve()}")
        return 1

    total_copied = sum(result.copied for result in results)
    total_converted = sum(result.converted for result in results)
    total_errors = sum(len(result.errors) for result in results)

    for result in sorted(results, key=lambda item: item.subject_dir.name.lower()):
        message = (
            f"{result.subject_dir.name}: copied {result.copied} PDF(s), converted {result.converted} to Markdown"
        )
        if result.errors:
            message += f" ({len(result.errors)} error(s); check logs)"
        print(message)

    print(
        f"\nPost-processing complete. Copied {total_copied} PDF(s) and generated {total_converted} Markdown file(s)."
    )
    if total_errors:
        print(f"Encountered {total_errors} error(s); see log output for details.")
        return 2
    return 0


def run_cli(args: argparse.Namespace) -> int:
    if args.list_subjects:
        print("Available subjects:")
        for subject in sorted(QUALIFICATION_URLS):
            print(f" - {subject}")
        return 0

    if args.post_process_workers is not None and args.post_process_workers < 1:
        print("--post-process-workers must be at least 1")
        return 1

    post_process_only = args.post_process_only
    should_post_process = args.post_process or post_process_only

    if post_process_only and args.dry_run:
        print("--dry-run cannot be combined with --post-process-only")
        return 1

    output_root = Path(args.output)

    if post_process_only:
        print("Running post-processing without downloading new files...\n")
        return perform_post_processing(output_root, args.post_process_workers, args.converter)

    selected_subjects, missing = resolve_subjects(args.subjects)
    if missing:
        print("Warning: some requested subjects were not recognised:")
        for item in sorted(missing):
            print(f"  - {item}")

    if not selected_subjects:
        print("No subjects selected. Exiting.")
        return 1

    if not args.dry_run:
        output_root.mkdir(parents=True, exist_ok=True)

    total_downloaded = 0
    for subject, url in selected_subjects.items():
        print(f"\n=== {subject} ===")
        if args.dry_run:
            pdf_links = list(iter_subject_pdf_links(url))
            if not pdf_links:
                print("No PDF links found.")
                continue
            for pdf_url, title in pdf_links:
                label = title or Path(urlparse(pdf_url).path).name
                print(f"Would download: {label} ({pdf_url})")
            total_downloaded += len(pdf_links)
            continue

        count, subject_dir = download_subject_pdfs(
            subject,
            url,
            output_root,
            reporter=lambda label, destination, pdf_url: print(
                f"Downloading {label} -> {destination}"
            ),
        )
        if count == 0:
            print("No PDF links found.")
        else:
            print(f"Saved {count} PDF(s) to {subject_dir}")
            total_downloaded += count

    if args.dry_run:
        print(f"\nDry run complete. {total_downloaded} PDF(s) would be downloaded.")
        if should_post_process:
            print("Post-processing is skipped during a dry run.")
        return 0

    print(f"\nFinished. Downloaded {total_downloaded} PDF(s) into {output_root.resolve()}")

    exit_code = 0
    if should_post_process:
        print("\nRunning post-processing...\n")
        exit_code = max(exit_code, perform_post_processing(output_root, args.post_process_workers, args.converter))

    return exit_code


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
