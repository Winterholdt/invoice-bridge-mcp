import os

from mcp.server.fastmcp import FastMCP

from invoice_bridge.parser import extract_zugferd_xml_from_pdf
from invoice_bridge.validator import FacturXValidator

mcp = FastMCP("Invoice-Bridge")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INVOICE_DIR = os.getenv("INVOICE_INPUT_DIR", os.path.join(BASE_DIR, "input"))


def _get_safe_path(filename: str, allowed_extensions: tuple = ('.xml', '.pdf')) -> str | None:
    """
    Validiert den Dateinamen gegen Path-Traversal Angriffe und stellt sicher,
    dass die Datei im konfigurierten INVOICE_DIR liegt.
    """
    if not filename or not isinstance(filename, str):
        return None

    clean_name = os.path.basename(filename.strip())
    if not clean_name or clean_name != filename.strip():
        return None

    if not any(clean_name.lower().endswith(ext) for ext in allowed_extensions):
        return None

    target_path = os.path.abspath(os.path.join(INVOICE_DIR, clean_name))
    invoice_dir_abs = os.path.abspath(INVOICE_DIR)

    # Prüfen, ob der Zielpfad unterhalb von INVOICE_DIR liegt
    if os.path.commonpath([target_path, invoice_dir_abs]) != invoice_dir_abs:
        return None

    return target_path


@mcp.resource("invoices://list")
def list_invoices() -> list[str]:
    """Listet alle verfügbaren E-Rechnungen im Eingangsordner auf."""
    if not os.path.exists(INVOICE_DIR):
        return []
    try:
        return [
            f for f in os.listdir(INVOICE_DIR)
            if f.lower().endswith(('.xml', '.pdf')) and os.path.isfile(os.path.join(INVOICE_DIR, f))
        ]
    except Exception:
        return []


@mcp.tool()
def parse_invoice(invoice_pdf_name: str) -> dict:
    """
    Extrahiert die eingebetteten XML-Daten aus einer PDF/A-3-Datei und speichert sie im Eingangsordner.
    """
    file_path = _get_safe_path(invoice_pdf_name, allowed_extensions=('.pdf',))
    if not file_path or not os.path.exists(file_path):
        return {
            "status": "error",
            "message": "Datei nicht gefunden oder ungültiger Dateipfad.",
        }

    extracted_xml_data = extract_zugferd_xml_from_pdf(file_path)

    if not extracted_xml_data or not extracted_xml_data.strip():
        return {
            "status": "error",
            "message": "Keine ZUGFeRD/Factur-X-Daten in der PDF gefunden.",
        }

    xml_file_name = os.path.splitext(os.path.basename(file_path))[0] + ".xml"
    xml_file_path = os.path.join(INVOICE_DIR, xml_file_name)

    try:
        os.makedirs(INVOICE_DIR, exist_ok=True)
        with open(xml_file_path, "w", encoding="utf-8") as f:
            f.write(extracted_xml_data)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Fehler beim Speichern der XML-Datei: {e!s}",
        }

    return {"status": "success", "xml_file": xml_file_name}


@mcp.tool()
def validate_compliance(invoice_xml_name: str) -> dict:
    """
    Prüft eine ZUGFeRD/Factur-X-XML-Datei auf formale und rechnerische
    Konformität nach § 14 UStG und EN 16931.
    """
    file_path = _get_safe_path(invoice_xml_name, allowed_extensions=('.xml',))
    if not file_path or not os.path.exists(file_path):
        return {
            "status": "error",
            "message": "Datei nicht gefunden oder ungültiger Dateipfad.",
        }

    try:
        with open(file_path, encoding="utf-8") as f:
            xml_content = f.read()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Fehler beim Lesen der XML-Datei: {e!s}",
        }

    validator = FacturXValidator(xml_content)
    checks = validator.run_all_checks()

    if checks.get("is_valid"):
        return {
            "status": "success",
            "invoice_id": checks.get("invoice_id"),
            "compliance_checks": checks,
            "approved_for_payment": True,
        }
    else:
        return {
            "status": "validation_failed",
            "invoice_id": checks.get("invoice_id"),
            "compliance_checks": checks,
            "approved_for_payment": False,
        }


@mcp.tool()
def validate_invoice_pdf(invoice_pdf_name: str) -> dict:
    """
    Direkte Prüfung einer PDF-Rechnung in einem Schritt:
    Extrahiert eingebettete ZUGFeRD/Factur-X XML-Daten und validiert die Konformität nach § 14 UStG.
    """
    file_path = _get_safe_path(invoice_pdf_name, allowed_extensions=('.pdf',))
    if not file_path or not os.path.exists(file_path):
        return {
            "status": "error",
            "message": "Datei nicht gefunden oder ungültiger Dateipfad.",
        }

    xml_content = extract_zugferd_xml_from_pdf(file_path)
    if not xml_content or not xml_content.strip():
        return {
            "status": "error",
            "message": "Keine ZUGFeRD/Factur-X-Daten in der PDF-Datei gefunden.",
        }

    validator = FacturXValidator(xml_content)
    checks = validator.run_all_checks()

    is_valid = bool(checks.get("is_valid"))
    return {
        "status": "success" if is_valid else "validation_failed",
        "invoice_id": checks.get("invoice_id"),
        "compliance_checks": checks,
        "approved_for_payment": is_valid,
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()
