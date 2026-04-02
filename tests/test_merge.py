from pypdf import PdfWriter
from pypdf import PdfReader

# Create two dummy pdfs
writer1 = PdfWriter()
writer1.add_blank_page(width=100, height=100)
writer1.write("dummy1.pdf")

writer2 = PdfWriter()
writer2.add_blank_page(width=100, height=100)
writer2.write("dummy2.pdf")

from src.lecture_auto.session_service import SessionService
class DummyStore:
    metadata_file = None
class DummyService(SessionService):
    def __init__(self):
        pass

service = DummyService()
service._merge_pdfs("dummy1.pdf", "dummy2.pdf", "dummy_out.pdf")

reader = PdfReader("dummy_out.pdf")
print("Total pages:", len(reader.pages))

import os
os.remove("dummy1.pdf")
os.remove("dummy2.pdf")
os.remove("dummy_out.pdf")
