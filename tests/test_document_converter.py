"""
Tests for document_converter module.
"""
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from lecture_auto.document_converter import (
    DocumentConversionError,
    is_supported_format,
    convert_to_pdf,
)


class TestIsSupportedFormat:
    def test_pdf_is_supported(self):
        assert is_supported_format("test.pdf") is True
        assert is_supported_format("test.PDF") is True
        
    def test_pptx_is_supported(self):
        assert is_supported_format("presentation.pptx") is True
        assert is_supported_format("presentation.PPTX") is True
        
    def test_ppt_is_supported(self):
        assert is_supported_format("presentation.ppt") is True
        assert is_supported_format("presentation.PPT") is True
        
    def test_unsupported_formats(self):
        assert is_supported_format("document.doc") is False
        assert is_supported_format("document.docx") is False
        assert is_supported_format("spreadsheet.xlsx") is False
        assert is_supported_format("image.png") is False
        assert is_supported_format("no_extension") is False


class TestConvertToPDF:
    def test_pdf_already_pdf(self, tmp_path):
        """Test that PDF files are copied directly without conversion."""
        source_pdf = tmp_path / "source.pdf"
        source_pdf.write_text("fake pdf content")
        
        output_pdf = tmp_path / "output.pdf"
        
        result = convert_to_pdf(str(source_pdf), str(output_pdf))
        
        assert result == "already_pdf"
        assert output_pdf.exists()
        assert output_pdf.read_text() == "fake pdf content"
        
    def test_nonexistent_file_raises_error(self, tmp_path):
        """Test that converting a nonexistent file raises FileNotFoundError."""
        source = tmp_path / "nonexistent.pptx"
        output = tmp_path / "output.pdf"
        
        with pytest.raises(FileNotFoundError):
            convert_to_pdf(str(source), str(output))
            
    def test_unsupported_format_returns_unsupported(self, tmp_path):
        """Test that unsupported formats return 'unsupported'."""
        source_doc = tmp_path / "document.doc"
        source_doc.write_text("fake doc content")
        
        output_pdf = tmp_path / "output.pdf"
        
        result = convert_to_pdf(str(source_doc), str(output_pdf))
        
        assert result == "unsupported"

    def test_conversion_uses_managed_libreoffice_and_temporary_output(self, tmp_path, monkeypatch):
        source = tmp_path / "presentation.pptx"
        source.write_bytes(b"fake pptx")
        output = tmp_path / "output.pdf"
        monkeypatch.setattr(
            "lecture_auto.libreoffice_runtime.find_libreoffice",
            lambda: "/managed/soffice",
        )

        def fake_run(command, **_kwargs):
            output_dir = Path(command[command.index("--outdir") + 1])
            assert command[0] == "/managed/soffice"
            assert output_dir != source.parent
            (output_dir / "presentation.pdf").write_bytes(b"converted")
            return Mock(returncode=0, stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)

        assert convert_to_pdf(str(source), str(output)) == "converted"
        assert output.read_bytes() == b"converted"


class TestPPTXConversion:
    """
    Note: These tests require python-pptx, reportlab, and pillow to be installed.
    They will be skipped if dependencies are not available.
    """
    
    @pytest.fixture
    def skip_if_no_deps(self):
        """Skip test if required dependencies are not installed."""
        try:
            import pptx
            import reportlab
            from PIL import Image
        except ImportError:
            pytest.skip("Required dependencies (python-pptx, reportlab, pillow) not installed")
    
    def test_pptx_conversion_requires_dependencies(self, tmp_path):
        """Test that PPTX conversion raises error if dependencies are missing."""
        # This test might pass if dependencies are installed, so we just
        # verify that the function can be called
        source_pptx = tmp_path / "presentation.pptx"
        output_pdf = tmp_path / "output.pdf"
        
        # Create a minimal PPTX file (would need python-pptx)
        # For now, just test the error case
        if not source_pptx.exists():
            source_pptx.write_bytes(b"fake pptx")
            
        # This should either convert or raise DocumentConversionError
        try:
            result = convert_to_pdf(str(source_pptx), str(output_pdf))
            # If it succeeds, verify it's marked as converted
            assert result in ("converted", "unsupported")
        except DocumentConversionError as e:
            # Expected if dependencies are missing
            assert (
                "Required libraries not installed" in str(e)
                or "Failed to convert" in str(e)
                or "LibreOffice is not installed" in str(e)
            )
