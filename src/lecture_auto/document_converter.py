"""
Document to PDF converter module.

Supports converting various document formats (PPT, PPTX) to PDF.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

SUPPORTED_EXTENSIONS = {".ppt", ".pptx", ".pdf"}

ConversionResult = Literal["converted", "already_pdf", "unsupported"]


class DocumentConversionError(Exception):
    """Raised when document conversion fails."""


def is_supported_format(file_path: str) -> bool:
    """Check if the file format is supported for material import."""
    ext = Path(file_path).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


def convert_to_pdf(source_path: str, output_path: str) -> ConversionResult:
    """
    Convert a document to PDF format.
    
    Args:
        source_path: Path to the source document
        output_path: Path where the PDF should be saved
        
    Returns:
        "converted" if conversion was performed
        "already_pdf" if source was already a PDF (copied directly)
        "unsupported" if file format is not supported
        
    Raises:
        DocumentConversionError: If conversion fails
        FileNotFoundError: If source file doesn't exist
    """
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    ext = source.suffix.lower()
    
    if ext == ".pdf":
        # Already PDF, just copy it
        import shutil
        shutil.copy2(source_path, output_path)
        return "already_pdf"
    
    if ext not in SUPPORTED_EXTENSIONS:
        return "unsupported"
    
    if ext in {".ppt", ".pptx"}:
        return _convert_pptx_to_pdf(source_path, output_path)
    
    return "unsupported"


def _convert_pptx_to_pdf(pptx_path: str, pdf_path: str) -> ConversionResult:
    """
    Convert PPT/PPTX to PDF using LibreOffice headless mode for high fidelity.
    """
    import subprocess
    import shutil
    from pathlib import Path

    try:
        # Find LibreOffice binary
        libreoffice_bin = shutil.which("libreoffice") or shutil.which("soffice")
        if not libreoffice_bin:
            raise DocumentConversionError(
                "LibreOffice is not installed. Please install LibreOffice to enable high-fidelity document conversion."
            )

        source = Path(pptx_path)
        output_dir = source.parent

        # LibreOffice command: --convert-to pdf creates a file with the same name but .pdf extension
        # in the specified output directory.
        cmd = [
            libreoffice_bin,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(source)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise DocumentConversionError(f"LibreOffice conversion failed: {result.stderr}")

        # LibreOffice saves as source_filename.pdf in the output_dir.
        # We need to move/rename it to the requested pdf_path.
        expected_pdf = output_dir / (source.stem + ".pdf")
        if not expected_pdf.exists():
            raise DocumentConversionError(f"Conversion succeeded but output file not found: {expected_pdf}")

        shutil.move(str(expected_pdf), pdf_path)
        return "converted"

    except subprocess.TimeoutExpired:
        raise DocumentConversionError("LibreOffice conversion timed out after 60 seconds.")
    except Exception as exc:
        if isinstance(exc, DocumentConversionError):
            raise exc
        raise DocumentConversionError(f"Failed to convert PPTX to PDF: {str(exc)}") from exc


def _wrap_text(text: str, width: int) -> list[str]:
    """Simple text wrapping helper."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1
        if current_length + word_length > width:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                lines.append(word)
                current_length = 0
        else:
            current_line.append(word)
            current_length += word_length
    
    if current_line:
        lines.append(" ".join(current_line))
    
    return lines or [""]
