import os
import shutil

import pytest

from invoice_bridge.server import (
    INVOICE_DIR,
    _get_safe_path,
    list_invoices,
    parse_invoice,
    validate_compliance,
    validate_invoice_pdf,
)

TEST_INVOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_invoices")


@pytest.fixture(autouse=True)
def setup_input_dir():
    os.makedirs(INVOICE_DIR, exist_ok=True)
    # Copy test.pdf to input dir for tests
    src_pdf = os.path.join(TEST_INVOICES_DIR, "test.pdf")
    dest_pdf = os.path.join(INVOICE_DIR, "test.pdf")
    if os.path.exists(src_pdf):
        shutil.copyfile(src_pdf, dest_pdf)
    yield
    # Cleanup generated xml if any
    xml_file = os.path.join(INVOICE_DIR, "test.xml")
    if os.path.exists(xml_file):
        os.remove(xml_file)


def test_path_traversal_prevention():
    assert _get_safe_path("../../secret.pdf", ('.pdf',)) is None
    assert _get_safe_path("..\\secret.pdf", ('.pdf',)) is None
    assert _get_safe_path("valid.pdf", ('.pdf',)) is not None
    assert _get_safe_path("valid.exe", ('.pdf',)) is None


def test_list_invoices():
    invoices = list_invoices()
    assert isinstance(invoices, list)
    assert "test.pdf" in invoices


def test_parse_and_validate_workflow():
    # 1. Parse PDF to XML
    parse_res = parse_invoice("test.pdf")
    assert parse_res["status"] == "success"
    assert parse_res["xml_file"] == "test.xml"

    # 2. Validate compliance on generated XML
    val_res = validate_compliance("test.xml")
    assert val_res["status"] == "success"
    assert val_res["approved_for_payment"] is True
    assert val_res["compliance_checks"]["is_valid"] is True


def test_validate_invoice_pdf_direct():
    res = validate_invoice_pdf("test.pdf")
    assert res["status"] == "success"
    assert res["approved_for_payment"] is True
    assert res["compliance_checks"]["is_valid"] is True


def test_server_non_existent_file():
    res = parse_invoice("does_not_exist.pdf")
    assert res["status"] == "error"

    res_val = validate_compliance("does_not_exist.xml")
    assert res_val["status"] == "error"

    res_pdf_val = validate_invoice_pdf("does_not_exist.pdf")
    assert res_pdf_val["status"] == "error"
