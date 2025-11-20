import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scripts.document_stats import (
    count_markdown_files,
    count_pdfs,
    count_total_pages,
    get_subject_directories,
)


def test_count_pdfs_empty_directory(tmp_path: Path):
    """Test counting PDFs in a directory without pdfs folder."""
    subject_dir = tmp_path / "Test-Subject"
    subject_dir.mkdir()
    assert count_pdfs(subject_dir) == 0


def test_count_pdfs_with_files(tmp_path: Path):
    """Test counting PDFs in a directory with PDF files."""
    subject_dir = tmp_path / "Test-Subject"
    pdf_dir = subject_dir / "pdfs"
    pdf_dir.mkdir(parents=True)

    # Create some PDF files
    (pdf_dir / "file1.pdf").touch()
    (pdf_dir / "file2.pdf").touch()
    (pdf_dir / "file3.pdf").touch()

    assert count_pdfs(subject_dir) == 3


def test_count_markdown_files_empty_directory(tmp_path: Path):
    """Test counting markdown files in a directory without markdown folder."""
    subject_dir = tmp_path / "Test-Subject"
    subject_dir.mkdir()
    assert count_markdown_files(subject_dir) == 0


def test_count_markdown_files_with_files(tmp_path: Path):
    """Test counting markdown files in a directory with markdown files."""
    subject_dir = tmp_path / "Test-Subject"
    markdown_dir = subject_dir / "markdown"
    markdown_dir.mkdir(parents=True)

    # Create some markdown files
    (markdown_dir / "file1.md").touch()
    (markdown_dir / "file2.md").touch()

    assert count_markdown_files(subject_dir) == 2


def test_count_total_pages_no_markers(tmp_path: Path):
    """Test counting pages in markdown files without page markers."""
    subject_dir = tmp_path / "Test-Subject"
    markdown_dir = subject_dir / "markdown"
    markdown_dir.mkdir(parents=True)

    # Create markdown file without page markers
    (markdown_dir / "file1.md").write_text("Content without page markers")
    (markdown_dir / "file2.md").write_text("More content")

    # Each file without markers counts as 1 page
    assert count_total_pages(subject_dir) == 2


def test_count_total_pages_with_markers(tmp_path: Path):
    """Test counting pages in markdown files with page markers."""
    subject_dir = tmp_path / "Test-Subject"
    markdown_dir = subject_dir / "markdown"
    markdown_dir.mkdir(parents=True)

    # Create markdown file with page markers (0-indexed, so {2} means 3 pages)
    content = """{0}------------------------------------------------
Page 0 content
{1}------------------------------------------------
Page 1 content
{2}------------------------------------------------
Page 2 content"""
    (markdown_dir / "file1.md").write_text(content)

    # File with markers {0}, {1}, {2} has 3 pages (0-indexed)
    assert count_total_pages(subject_dir) == 3


def test_count_total_pages_mixed(tmp_path: Path):
    """Test counting pages with mix of files with and without markers."""
    subject_dir = tmp_path / "Test-Subject"
    markdown_dir = subject_dir / "markdown"
    markdown_dir.mkdir(parents=True)

    # File with no markers (1 page)
    (markdown_dir / "file1.md").write_text("Single page")

    # File with markers (3 pages)
    content = """{0}------------------------------------------------
Page 0
{1}------------------------------------------------
Page 1
{2}------------------------------------------------
Page 2"""
    (markdown_dir / "file2.md").write_text(content)

    # Total: 1 + 3 = 4 pages
    assert count_total_pages(subject_dir) == 4


def test_get_subject_directories(tmp_path: Path):
    """Test getting subject directories from Documents folder."""
    documents_root = tmp_path / "Documents"
    documents_root.mkdir()

    # Create some subject directories with pdfs/markdown folders
    subject1 = documents_root / "Subject-1"
    (subject1 / "pdfs").mkdir(parents=True)

    subject2 = documents_root / "Subject-2"
    (subject2 / "markdown").mkdir(parents=True)

    # Create a directory without pdfs/markdown (should be excluded)
    other_dir = documents_root / "Other"
    other_dir.mkdir()

    subjects = get_subject_directories(documents_root)

    assert len(subjects) == 2
    assert subject1 in subjects
    assert subject2 in subjects
    assert other_dir not in subjects


def test_get_subject_directories_nonexistent(tmp_path: Path):
    """Test getting subject directories from nonexistent folder."""
    documents_root = tmp_path / "Nonexistent"
    subjects = get_subject_directories(documents_root)
    assert subjects == []
