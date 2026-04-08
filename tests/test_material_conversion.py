"""
Integration tests for material import with document conversion.
"""
import shutil
from pathlib import Path

import pytest

from lecture_auto.session_service import SessionCommandError, SessionService
from lecture_auto.session_metadata_store import SessionMetadataStore


@pytest.fixture
def service_with_session(tmp_path):
    """Create a session service with an initialized session."""
    metadata_dir = tmp_path / ".lecture_auto"
    metadata_file = metadata_dir / "sessions.json"
    store = SessionMetadataStore(metadata_file)
    
    service = SessionService(store=store)
    
    # Create a session using the correct method
    from datetime import datetime, timezone
    session_id = "test-session"
    date = datetime.now(timezone.utc).isoformat()
    
    result = service.session_create(
        session_id=session_id,
        date=date,
        title="Test Lecture",
        course="test-course",
    )
    
    return service, session_id, tmp_path


class TestMaterialImportWithConversion:
    """Test material import with document conversion."""
    
    def test_import_pdf_directly(self, service_with_session, tmp_path):
        """Test importing a PDF file directly."""
        service, session_id, root = service_with_session
        
        # Create a fake PDF
        pdf_file = tmp_path / "material.pdf"
        pdf_file.write_text("fake pdf content")
        
        # Import
        result = service.import_material(session_id, str(pdf_file))
        
        assert result.command == "material import"
        assert "imported successfully" in result.message
        
        # Verify the file was copied
        session = service.store.get_by_session_id(session_id)
        assert session["material_file_path"] is not None
        
        # metadata_root is metadata_file.parent.parent
        # which is tmp_path/.lecture_auto/../ = tmp_path
        material_path = root / session["material_file_path"]
        assert material_path.exists()
        
    def test_import_unsupported_format_rejected(self, service_with_session, tmp_path):
        """Test that unsupported formats are rejected."""
        service, session_id, root = service_with_session
        
        # Create unsupported file
        doc_file = tmp_path / "document.docx"
        doc_file.write_text("fake docx content")
        
        # Should raise error
        with pytest.raises(SessionCommandError) as exc_info:
            service.import_material(session_id, str(doc_file))
            
        assert exc_info.value.code == "IMPORT_MATERIAL_INVALID_FORMAT"
        assert "Unsupported file format" in exc_info.value.message
        
    def test_import_pptx_supported(self, service_with_session, tmp_path):
        """Test that PPTX files are recognized as supported."""
        service, session_id, root = service_with_session
        
        # Create a fake PPTX
        pptx_file = tmp_path / "presentation.pptx"
        pptx_file.write_text("fake pptx content")
        
        # This should not raise INVALID_FORMAT error
        # It may raise CONVERSION_ERROR if dependencies are missing
        try:
            result = service.import_material(session_id, str(pptx_file))
            # If conversion succeeds
            assert "converted from .PPTX" in result.message or "imported" in result.message
        except SessionCommandError as exc:
            # Should be conversion error, not invalid format
            assert exc.code in ("IMPORT_MATERIAL_CONVERSION_ERROR", "IMPORT_MATERIAL_CONVERSION_UNSUPPORTED")
            assert exc.code != "IMPORT_MATERIAL_INVALID_FORMAT"
            
    def test_merge_multiple_pdfs(self, service_with_session, tmp_path):
        """Test that importing multiple PDFs merges them."""
        service, session_id, root = service_with_session
        
        # Create two minimal valid PDFs
        # For real PDF merge testing, we need valid PDF content
        # This test will verify the merge logic is called
        from pypdf import PdfWriter
        
        pdf1 = tmp_path / "material1.pdf"
        writer1 = PdfWriter()
        writer1.add_blank_page(width=200, height=200)
        with open(pdf1, "wb") as f:
            writer1.write(f)
        
        pdf2 = tmp_path / "material2.pdf"
        writer2 = PdfWriter()
        writer2.add_blank_page(width=200, height=200)
        with open(pdf2, "wb") as f:
            writer2.write(f)
        
        # Import first
        result1 = service.import_material(session_id, str(pdf1))
        assert "imported successfully" in result1.message
        
        # Import second - should merge
        result2 = service.import_material(session_id, str(pdf2))
        assert "merged with existing material" in result2.message
        
        # Verify merged file exists
        session = service.store.get_by_session_id(session_id)
        material_path = root / session["material_file_path"]
        assert material_path.exists()
            
    def test_no_extension_file_rejected(self, service_with_session, tmp_path):
        """Test that files without extension are rejected."""
        service, session_id, root = service_with_session
        
        # Create file without extension
        no_ext_file = tmp_path / "noextension"
        no_ext_file.write_text("some content")
        
        with pytest.raises(SessionCommandError) as exc_info:
            service.import_material(session_id, str(no_ext_file))
            
        assert exc_info.value.code == "IMPORT_MATERIAL_INVALID_FORMAT"
