import io
import os

from pypdf import PdfReader


def extract_zugferd_xml_from_pdf(pdf_source: str | bytes | io.BytesIO) -> str | None:
    """
    Sucht nach eingebetteten XML-Anhängen in einer ZUGFeRD/Factur-X PDF/A-3 Datei
    und gibt den XML-Inhalt als UTF-8 String zurück.

    :param pdf_source: Dateipfad, Bytes oder BytesIO-Objekt der PDF-Datei.
    :return: XML-Inhalt als String oder None, falls kein ZUGFeRD-Anhang gefunden wurde.
    """
    try:
        if isinstance(pdf_source, str):
            if not os.path.exists(pdf_source):
                return None
            reader = PdfReader(pdf_source)
        elif isinstance(pdf_source, bytes):
            reader = PdfReader(io.BytesIO(pdf_source))
        else:
            reader = PdfReader(pdf_source)

        attachments = reader.attachments
    except Exception:
        return None

    if not attachments:
        return None

    target_filenames = {
        "factur-x.xml",
        "zugferd-invoice.xml",
        "xrechnung.xml",
        "zugferd_invoice.xml",
    }

    for name, files in attachments.items():
        clean_name = name.strip().lower()
        if clean_name in target_filenames:
            try:
                raw_file = files[0] if isinstance(files, list) and files else files
                raw_bytes = raw_file.get_data() if hasattr(raw_file, "get_data") else raw_file
                if not raw_bytes:
                    continue
                if isinstance(raw_bytes, str):
                    text = raw_bytes
                else:
                    text = raw_bytes.decode("utf-8")
                if text.strip():
                    return text
            except Exception:
                continue

    return None
