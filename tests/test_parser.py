import os

from invoice_bridge.parser import extract_zugferd_xml_from_pdf

TEST_INVOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_invoices")


def test_extract_valid_zugferd_pdf():
    pdf_path = os.path.join(TEST_INVOICES_DIR, "test.pdf")
    assert os.path.exists(pdf_path), "test.pdf should exist in test_invoices"

    xml_content = extract_zugferd_xml_from_pdf(pdf_path)
    assert xml_content is not None
    assert "<rsm:CrossIndustryInvoice" in xml_content
    assert "</rsm:CrossIndustryInvoice>" in xml_content


def test_extract_from_bytes():
    pdf_path = os.path.join(TEST_INVOICES_DIR, "test.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    xml_content = extract_zugferd_xml_from_pdf(pdf_bytes)
    assert xml_content is not None
    assert "<rsm:CrossIndustryInvoice" in xml_content


def test_extract_non_existent_file():
    xml_content = extract_zugferd_xml_from_pdf("non_existent_file_xyz.pdf")
    assert xml_content is None


def test_extract_corrupt_data():
    xml_content = extract_zugferd_xml_from_pdf(b"not a valid pdf content")
    assert xml_content is None
