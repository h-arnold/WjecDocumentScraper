"""Tests for comprehensive error logging with stack traces."""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.postprocessing import process_single_pdf, process_subject


@pytest.fixture
def capture_logs():
    """Fixture to capture log output."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger("src.postprocessing")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    yield log_stream

    logger.removeHandler(handler)


class TestPostprocessingErrorLogging:
    """Tests for error logging in postprocessing module."""

    def test_process_single_pdf_logs_conversion_error_with_traceback(
        self, tmp_path, capture_logs
    ):
        """Test that conversion errors are logged with stack traces."""
        # Create a simple subject structure
        subject_dir = tmp_path / "Test-Subject"
        subject_dir.mkdir()
        pdf_subdir = subject_dir / "pdfs"
        pdf_subdir.mkdir()
        pdf_path = pdf_subdir / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest")

        # Mock converter to raise an exception
        mock_converter = Mock()
        mock_converter.convert.side_effect = ValueError("Test conversion error")
        mock_converter.close = Mock()

        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_single_pdf(pdf_path, "marker")

        # Verify the result indicates failure
        assert result.success is False
        assert "Test conversion error" in result.error

        # Verify stack trace was logged
        log_output = capture_logs.getvalue()
        assert "Test conversion error" in log_output
        assert "Traceback" in log_output or "ValueError" in log_output
        assert "ERROR" in log_output

    def test_process_single_pdf_logs_copy_error_with_traceback(
        self, tmp_path, capture_logs
    ):
        """Test that file copy errors are logged with stack traces."""
        subject_dir = tmp_path / "Test-Subject"
        subject_dir.mkdir()
        pdf_path = subject_dir / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest")

        # Mock shutil.copy2 to raise an exception
        with patch(
            "src.postprocessing.shutil.copy2", side_effect=OSError("Permission denied")
        ):
            with patch("src.postprocessing.create_converter") as mock_create:
                mock_converter = Mock()
                mock_converter.close = Mock()
                mock_create.return_value = mock_converter
                result = process_single_pdf(pdf_path, "marker")

        # Verify the result indicates failure
        assert result.success is False
        assert "Permission denied" in result.error

        # Verify stack trace was logged
        log_output = capture_logs.getvalue()
        assert "Permission denied" in log_output
        assert "Traceback" in log_output or "OSError" in log_output
        assert "ERROR" in log_output

    def test_process_subject_logs_conversion_errors_with_traceback(
        self, tmp_path, capture_logs
    ):
        """Test that process_subject logs conversion errors with stack traces."""
        subject_dir = tmp_path / "Test-Subject"
        subject_dir.mkdir()

        # Create a PDF in the root
        pdf_path = subject_dir / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest")

        # Mock converter to raise an exception
        mock_converter = Mock()
        mock_converter.convert.side_effect = RuntimeError("Test subject error")
        mock_converter.close = Mock()

        with patch("src.postprocessing.create_converter", return_value=mock_converter):
            result = process_subject(subject_dir, "marker")

        # Verify errors were recorded
        assert len(result.errors) > 0
        assert any("Test subject error" in err for err in result.errors)

        # Verify stack trace was logged
        log_output = capture_logs.getvalue()
        assert "Test subject error" in log_output
        assert "Traceback" in log_output or "RuntimeError" in log_output
        assert "ERROR" in log_output


class TestProcessAllSubjectsErrorLogging:
    """Tests for error logging in process_all_subjects script."""

    def test_process_pdf_file_logs_exception_with_traceback(self, tmp_path, capsys):
        """Test that process_pdf_file logs exceptions with stack traces."""
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from process_all_subjects import process_pdf_file

        # Create a PDF path that will cause an error
        pdf_path = tmp_path / "Test-Subject" / "test.pdf"
        pdf_path.parent.mkdir()
        pdf_path.write_bytes(b"%PDF-1.4\ntest")

        # Mock the import of process_single_pdf to raise an exception
        with patch(
            "src.postprocessing.process_single_pdf",
            side_effect=ValueError("Test exception"),
        ):
            result = process_pdf_file(pdf_path, "marker", PROJECT_ROOT)

        # Verify the result indicates failure
        assert result is False

        # Verify stack trace was printed
        captured = capsys.readouterr()
        assert "Test exception" in captured.err
        assert "Traceback" in captured.err or "Stack trace" in captured.err

    def test_process_subject_subprocess_logs_exception_with_traceback(
        self, tmp_path, capsys
    ):
        """Test that process_subject subprocess errors are logged with stack traces."""
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from process_all_subjects import process_subject

        # Create a fake helper script that doesn't exist
        docs_dir = tmp_path / "Documents"
        docs_dir.mkdir()
        subject_dir = docs_dir / "Test-Subject"
        subject_dir.mkdir()

        cwd = tmp_path / "repo"
        cwd.mkdir()
        scripts_dir = cwd / "scripts"
        scripts_dir.mkdir()
        helper_script = scripts_dir / "process_single_subject.py"
        helper_script.write_text("#!/usr/bin/env python\nimport sys\nsys.exit(1)")

        # Mock Popen to raise an exception
        with patch(
            "process_all_subjects.subprocess.Popen",
            side_effect=OSError("Command not found"),
        ):
            result = process_subject(
                "Test-Subject", docs_dir, "marker", "uv run python", cwd
            )

        # Verify the result indicates failure
        assert result is False

        # Verify stack trace was printed
        captured = capsys.readouterr()
        assert "Command not found" in captured.err
        assert "Traceback" in captured.err or "Stack trace" in captured.err


class TestCopyRootPdfsErrorLogging:
    """Tests for error logging in copy_root_pdfs function."""

    def test_copy_root_pdfs_logs_copy_errors_with_traceback(
        self, tmp_path, capture_logs
    ):
        """Test that copy_root_pdfs logs copy errors with stack traces."""
        subject_dir = tmp_path / "Test-Subject"
        subject_dir.mkdir()
        pdf_path = subject_dir / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest")

        pdf_subdir = subject_dir / "pdfs"

        # Mock copy2 to raise an exception
        with patch("src.postprocessing.shutil.copy2", side_effect=OSError("Disk full")):
            from src.postprocessing import copy_root_pdfs

            result = copy_root_pdfs(subject_dir, pdf_subdir)

        # Verify no PDFs were copied
        assert len(result) == 0

        # Verify stack trace was logged
        log_output = capture_logs.getvalue()
        assert "Disk full" in log_output
        assert "WARNING" in log_output

    def test_copy_root_pdfs_logs_unlink_errors_with_traceback(
        self, tmp_path, capture_logs
    ):
        """Test that copy_root_pdfs logs unlink errors with stack traces."""
        subject_dir = tmp_path / "Test-Subject"
        subject_dir.mkdir()
        pdf_path = subject_dir / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest")

        pdf_subdir = subject_dir / "pdfs"
        pdf_subdir.mkdir()

        # Mock unlink to raise an exception (copy succeeds but unlink fails)
        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if self.name == "test.pdf" and self.parent.name == "Test-Subject":
                raise OSError("File in use")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", mock_unlink):
            from src.postprocessing import copy_root_pdfs

            result = copy_root_pdfs(subject_dir, pdf_subdir)

        # Verify PDF was copied (even though unlink failed)
        assert len(result) == 1

        # Verify stack trace was logged
        log_output = capture_logs.getvalue()
        assert "File in use" in log_output
        assert "WARNING" in log_output
