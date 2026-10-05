import os

from invoice_bridge.parser import extract_zugferd_xml_from_pdf
from invoice_bridge.validator import FacturXValidator

TEST_INVOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_invoices")


def test_validator_valid_invoice():
    pdf_path = os.path.join(TEST_INVOICES_DIR, "test.pdf")
    xml_content = extract_zugferd_xml_from_pdf(pdf_path)
    assert xml_content is not None

    validator = FacturXValidator(xml_content)
    assert validator.parse_error is None
    invoice_id = validator.get_invoice_id()
    assert invoice_id is not None

    results = validator.run_all_checks()
    assert results["is_valid"] is True
    assert results["failed"] == 0
    assert results["passed"] > 10
    assert results["invoice_id"] == invoice_id


def test_validator_malformed_xml():
    malformed_xml = "<?xml version='1.0'?><rsm:CrossIndustryInvoice><broken"
    validator = FacturXValidator(malformed_xml)
    assert validator.parse_error is not None

    results = validator.run_all_checks()
    assert results["is_valid"] is False
    assert results["failed"] == 1
    assert results["failed_details"][0]["rule_id"] == "XML-PARSE"


def test_validator_calculation_mismatch():
    pdf_path = os.path.join(TEST_INVOICES_DIR, "test.pdf")
    xml_content = extract_zugferd_xml_from_pdf(pdf_path)
    assert xml_content is not None

    # Manipulate GrandTotalAmount to cause a calculation check failure
    manipulated_xml = xml_content.replace("<ram:GrandTotalAmount>595.00</ram:GrandTotalAmount>", "<ram:GrandTotalAmount>999.99</ram:GrandTotalAmount>")
    if manipulated_xml != xml_content:
        validator = FacturXValidator(manipulated_xml)
        results = validator.run_all_checks()
        assert results["is_valid"] is False
        calc_check = [c for c in results["failed_details"] if c["rule_id"] == "CALC-01"]
        assert len(calc_check) > 0


def test_validator_invalid_currency_code():
    pdf_path = os.path.join(TEST_INVOICES_DIR, "test.pdf")
    xml_content = extract_zugferd_xml_from_pdf(pdf_path)
    assert xml_content is not None

    manipulated_xml = xml_content.replace("<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>", "<ram:InvoiceCurrencyCode>EURO</ram:InvoiceCurrencyCode>")
    if manipulated_xml != xml_content:
        validator = FacturXValidator(manipulated_xml)
        results = validator.run_all_checks()
        assert results["is_valid"] is False
        currency_check = [c for c in results["failed_details"] if c["rule_id"] == "BR-05"]
        assert len(currency_check) > 0
