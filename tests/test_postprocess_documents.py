"""Tests for src.postprocessing module."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.postprocessing import (
    SinglePdfResult,
    SubjectResult,
    copy_root_pdfs,
    convert_pdf_to_markdown,
    find_subject_directories,
    process_single_pdf,
    process_subject,
)


@pytest.fixture
def temp_docs_dir(tmp_path):
    """Create a temporary Documents directory structure."""
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir()
    
    # Create subject directories
    subject1 = docs_dir / "Art-and-Design"
    subject1.mkdir()
    
    subject2 = docs_dir / "Computer-Science"
    subject2.mkdir()
    
    return docs_dir


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a sample PDF file."""
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\nSample PDF content")
    return pdf_file


@pytest.fixture
def mock_converter():
    """Create a mock converter."""
    converter = Mock()
    result = Mock()
    result.markdown = "# Sample Markdown\n\nConverted content"
    converter.convert.return_value = result
    return converter


class TestProcessSinglePdf:
    """Tests for process_single_pdf function."""
    
    def test_processes_pdf_in_root_of_subject(self, temp_docs_dir, sample_pdf, mock_converter):
        """Test processing a PDF that's in the root of a subject directory."""
        # Setup: Place PDF in subject root
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_in_root = subject_dir / "sample.pdf"
        pdf_in_root.write_bytes(sample_pdf.read_bytes())
        
        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_single_pdf(pdf_in_root, "markitdown")
        
        # Verify PDF was copied to pdfs/ subdirectory
        pdf_subdir = subject_dir / "pdfs"
        assert pdf_subdir.exists()
        assert (pdf_subdir / "sample.pdf").exists()
        
        # Verify original PDF was removed
        assert not pdf_in_root.exists()
        
        # Verify markdown was created
        markdown_dir = subject_dir / "markdown"
        assert markdown_dir.exists()
        assert (markdown_dir / "sample.md").exists()
        
        # Verify result
        assert result.success is True
        assert result.pdf_path == pdf_subdir / "sample.pdf"
        assert result.markdown_path == markdown_dir / "sample.md"
        assert result.error is None
        
        # Verify converter was used
        mock_converter.convert.assert_called_once()
        mock_converter.close.assert_called_once()
    
    def test_processes_pdf_already_in_pdfs_subdir(self, temp_docs_dir, sample_pdf, mock_converter):
        """Test processing a PDF that's already in the pdfs/ subdirectory."""
        # Setup: Place PDF in pdfs/ subdirectory
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_subdir = subject_dir / "pdfs"
        pdf_subdir.mkdir()
        pdf_in_subdir = pdf_subdir / "sample.pdf"
        pdf_in_subdir.write_bytes(sample_pdf.read_bytes())
        
        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_single_pdf(pdf_in_subdir, "markitdown")
        
        # Verify PDF stays in pdfs/ subdirectory
        assert pdf_in_subdir.exists()
        
        # Verify markdown was created
        markdown_dir = subject_dir / "markdown"
        assert markdown_dir.exists()
        assert (markdown_dir / "sample.md").exists()
        
        # Verify result
        assert result.success is True
        assert result.pdf_path == pdf_in_subdir
        assert result.markdown_path == markdown_dir / "sample.md"
        assert result.error is None
    
    def test_handles_conversion_error(self, temp_docs_dir, sample_pdf, mock_converter):
        """Test handling of conversion errors."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_subdir = subject_dir / "pdfs"
        pdf_subdir.mkdir()
        pdf_path = pdf_subdir / "sample.pdf"
        pdf_path.write_bytes(sample_pdf.read_bytes())
        
        # Make converter raise an exception
        mock_converter.convert.side_effect = Exception("Conversion failed")
        
        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_single_pdf(pdf_path, "markitdown")
        
        # Verify result indicates failure
        assert result.success is False
        assert result.pdf_path == pdf_path
        assert result.markdown_path is None
        assert result.error is not None
        assert "Conversion failed" in result.error
        
        # Verify converter was still closed
        mock_converter.close.assert_called_once()
    
    def test_handles_file_copy_error(self, temp_docs_dir, sample_pdf):
        """Test handling of file copy errors."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_in_root = subject_dir / "sample.pdf"
        pdf_in_root.write_bytes(sample_pdf.read_bytes())
        
        with patch("src.postprocessing.shutil.copy2", side_effect=OSError("Permission denied")):
            with patch("src.postprocessing.create_converter") as mock_create:
                result = process_single_pdf(pdf_in_root, "markitdown")
        
        # Verify result indicates failure
        assert result.success is False
        assert result.error is not None
        assert "Permission denied" in result.error
        
        # Converter should still be closed even if copy failed
        mock_create.return_value.close.assert_called_once()
    
    def test_handles_nonexistent_pdf(self, temp_docs_dir):
        """Test handling of nonexistent PDF file."""
        nonexistent = temp_docs_dir / "Art-and-Design" / "nonexistent.pdf"
        
        with patch("src.postprocessing.create_converter") as mock_create:
            result = process_single_pdf(nonexistent, "markitdown")
        
        # Verify result indicates failure
        assert result.success is False
        assert result.error is not None
        
        # Converter should still be closed
        mock_create.return_value.close.assert_called_once()
    
    def test_uses_correct_converter_type(self, temp_docs_dir, sample_pdf):
        """Test that the correct converter type is used."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_subdir = subject_dir / "pdfs"
        pdf_subdir.mkdir()
        pdf_path = pdf_subdir / "sample.pdf"
        pdf_path.write_bytes(sample_pdf.read_bytes())
        
        with patch("src.postprocessing.create_converter") as mock_create:
            mock_converter = Mock()
            mock_result = Mock()
            mock_result.markdown = "# Test"
            mock_converter.convert.return_value = mock_result
            mock_create.return_value = mock_converter
            
            process_single_pdf(pdf_path, "marker")
            
            # Verify create_converter was called with correct type
            mock_create.assert_called_once_with("marker")
    
    def test_creates_directories_if_needed(self, temp_docs_dir, sample_pdf, mock_converter):
        """Test that pdfs/ and markdown/ directories are created if they don't exist."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_in_root = subject_dir / "sample.pdf"
        pdf_in_root.write_bytes(sample_pdf.read_bytes())
        
        # Ensure directories don't exist
        pdf_subdir = subject_dir / "pdfs"
        markdown_dir = subject_dir / "markdown"
        assert not pdf_subdir.exists()
        assert not markdown_dir.exists()
        
        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_single_pdf(pdf_in_root, "markitdown")
        
        # Verify directories were created
        assert pdf_subdir.exists()
        assert markdown_dir.exists()
        assert result.success is True
    
    def test_pdf_path_validation(self, temp_docs_dir, sample_pdf, mock_converter):
        """Test that PDF must be within a subject directory structure."""
        # PDF at Documents root level (not in a subject)
        pdf_at_root = temp_docs_dir / "sample.pdf"
        pdf_at_root.write_bytes(sample_pdf.read_bytes())
        
        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_single_pdf(pdf_at_root, "markitdown")
        
        # Should fail because it's not in a valid subject directory
        assert result.success is False
        assert result.error is not None


class TestCopyRootPdfs:
    """Tests for copy_root_pdfs function."""
    
    def test_copies_pdfs_from_root(self, temp_docs_dir):
        """Test copying PDFs from subject root to pdfs/ subdirectory."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf1 = subject_dir / "file1.pdf"
        pdf2 = subject_dir / "file2.pdf"
        pdf1.write_bytes(b"%PDF-1.4")
        pdf2.write_bytes(b"%PDF-1.5")
        
        pdf_subdir = subject_dir / "pdfs"
        copied = copy_root_pdfs(subject_dir, pdf_subdir)
        
        assert len(copied) == 2
        assert (pdf_subdir / "file1.pdf").exists()
        assert (pdf_subdir / "file2.pdf").exists()
        assert not pdf1.exists()
        assert not pdf2.exists()
    
    def test_creates_pdfs_directory(self, temp_docs_dir):
        """Test that pdfs/ directory is created if it doesn't exist."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        pdf_subdir = subject_dir / "pdfs"
        
        assert not pdf_subdir.exists()
        
        copy_root_pdfs(subject_dir, pdf_subdir)
        
        assert pdf_subdir.exists()
    
    def test_skips_non_pdf_files(self, temp_docs_dir):
        """Test that non-PDF files are not copied."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        (subject_dir / "file.txt").write_text("text")
        (subject_dir / "file.docx").write_bytes(b"docx")
        pdf_file = subject_dir / "file.pdf"
        pdf_file.write_bytes(b"%PDF")
        
        pdf_subdir = subject_dir / "pdfs"
        copied = copy_root_pdfs(subject_dir, pdf_subdir)
        
        assert len(copied) == 1
        assert (pdf_subdir / "file.pdf").exists()
        assert not (pdf_subdir / "file.txt").exists()
        assert not (pdf_subdir / "file.docx").exists()


class TestConvertPdfToMarkdown:
    """Tests for convert_pdf_to_markdown function."""
    
    def test_converts_pdf_to_markdown(self, tmp_path, sample_pdf, mock_converter):
        """Test PDF to Markdown conversion."""
        markdown_dir = tmp_path / "markdown"
        
        result_path = convert_pdf_to_markdown(mock_converter, sample_pdf, markdown_dir)
        
        assert result_path == markdown_dir / "sample.md"
        assert result_path.exists()
        assert result_path.read_text() == "# Sample Markdown\n\nConverted content"
        mock_converter.convert.assert_called_once_with(sample_pdf)
    
    def test_creates_markdown_directory(self, tmp_path, sample_pdf, mock_converter):
        """Test that markdown/ directory is created if it doesn't exist."""
        markdown_dir = tmp_path / "markdown"
        assert not markdown_dir.exists()
        
        convert_pdf_to_markdown(mock_converter, sample_pdf, markdown_dir)
        
        assert markdown_dir.exists()


class TestFindSubjectDirectories:
    """Tests for find_subject_directories function."""
    
    def test_finds_all_subject_directories(self, temp_docs_dir):
        """Test finding all subject directories."""
        # Create additional subjects
        (temp_docs_dir / "Geography").mkdir()
        (temp_docs_dir / "History").mkdir()
        
        subjects = find_subject_directories(temp_docs_dir)
        
        assert len(subjects) == 4
        subject_names = [s.name for s in subjects]
        assert "Art-and-Design" in subject_names
        assert "Computer-Science" in subject_names
        assert "Geography" in subject_names
        assert "History" in subject_names
    
    def test_returns_sorted_list(self, temp_docs_dir):
        """Test that directories are returned sorted."""
        (temp_docs_dir / "Zebra").mkdir()
        (temp_docs_dir / "Aardvark").mkdir()
        
        subjects = find_subject_directories(temp_docs_dir)
        
        assert subjects == sorted(subjects)
    
    def test_skips_files(self, temp_docs_dir):
        """Test that files are skipped."""
        (temp_docs_dir / "file.txt").write_text("content")
        
        subjects = find_subject_directories(temp_docs_dir)
        
        assert len(subjects) == 2  # Only the two directories from fixture


class TestProcessSubject:
    """Tests for process_subject function."""
    
    def test_processes_subject_successfully(self, temp_docs_dir, mock_converter):
        """Test successful subject processing."""
        subject_dir = temp_docs_dir / "Art-and-Design"
        
        # Create some PDFs in the root
        (subject_dir / "file1.pdf").write_bytes(b"%PDF-1.4")
        (subject_dir / "file2.pdf").write_bytes(b"%PDF-1.5")
        
        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_subject(subject_dir, "markitdown")
        
        assert result.subject_dir == subject_dir
        assert result.copied == 2
        assert result.converted == 2
        assert len(result.errors) == 0
        
        # Verify converter was closed
        mock_converter.close.assert_called_once()
