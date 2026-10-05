import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Any


class FacturXValidator:
    """
    Validiert Factur-X / ZUGFeRD (CII) XML-Rechnungen anhand
    von Schematron-Regeln (MINIMUM / BASIC) und § 14 UStG.
    """

    # Offizielle Namespaces aus dem Schematron
    NAMESPACES = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
        "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
    }

    # ISO 3166-1 alpha-2 Ländercodes inkl. EL (Griechenland) gemäß BR-CO-09
    ISO_COUNTRY_CODES = set(
        ["1A", "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AN", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BL", "BJ", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE", "EG", "EH", "EL", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM", "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW", "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI", "VN", "VU", "WF", "WS", "XI", "YE", "YT", "ZA", "ZM", "ZW"]
    )

    def __init__(self, xml_content: str):
        self.xml_content = xml_content
        self.results: list[dict[str, Any]] = []
        self.parse_error: str | None = None
        self.root: ET.Element | None = None

        try:
            if isinstance(xml_content, str):
                self.root = ET.fromstring(xml_content.encode("utf-8"))
            elif isinstance(xml_content, bytes):
                self.root = ET.fromstring(xml_content)
            else:
                self.parse_error = "Ungültiger XML-Eingabetyp."
        except ET.ParseError as e:
            self.parse_error = f"XML Parsing Fehler: {e!s}"
        except Exception as e:
            self.parse_error = f"Unerwarteter XML Fehler: {e!s}"

    def get_invoice_id(self) -> str | None:
        """Extrahiert die Rechnungsnummer aus dem ExchangedDocument Header."""
        if self.root is None:
            return None
        return self._find_text("rsm:ExchangedDocument/ram:ID")

    def _find_text(self, xpath: str, node: ET.Element | None = None) -> str | None:
        if self.root is None and node is None:
            return None
        target = self.root if node is None else node
        if target is None:
            return None
        el = target.find(xpath, self.NAMESPACES)
        if el is not None and el.text:
            text = el.text.strip()
            return text if text else None
        return None

    def _record(self, rule_id: str, field_desc: str, passed: bool, message: str):
        self.results.append({
            "rule_id": rule_id,
            "field": field_desc,
            "status": "PASSED" if passed else "FAILED",
            "message": message,
        })

    def _check_max_decimals(self, value_str: str | None, max_decimals: int = 2) -> bool:
        if not value_str or "." not in value_str:
            return True
        decimals = len(value_str.split(".")[1])
        return decimals <= max_decimals

    def run_all_checks(self) -> dict[str, Any]:
        self.results.clear()

        # Falls XML-Parsing fehlgeschlagen ist:
        if self.parse_error is not None or self.root is None:
            self._record(
                "XML-PARSE",
                "XML Well-formedness",
                False,
                self.parse_error or "XML-Dokument konnte nicht geparst werden.",
            )
            return {
                "is_valid": False,
                "invoice_id": None,
                "total_checks": 1,
                "passed": 0,
                "failed": 1,
                "failed_details": self.results,
                "all_results": self.results,
            }

        # ---------------------------------------------------------
        # 1. Header & Kontext (BR-01 bis BR-05)
        # ---------------------------------------------------------
        guideline = self._find_text(
            "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID"
        )
        self._record(
            "BR-01",
            "Specification Identifier (BT-24)",
            guideline is not None,
            "Profil-Spezifikation (z. B. urn:factur-x.eu:1p0:minimum) muss vorhanden sein.",
        )

        inv_id = self.get_invoice_id()
        self._record(
            "BR-02",
            "Invoice Number (BT-1 / § 14 Abs. 4 Nr. 4 UStG)",
            inv_id is not None,
            "Fortlaufende Rechnungsnummer muss befüllt sein.",
        )

        issue_date = self._find_text(
            "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString"
        )
        date_el = self.root.find(
            "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString",
            self.NAMESPACES,
        )
        date_format = date_el.attrib.get("format") if date_el is not None else None
        date_valid = bool(
            issue_date
            and (date_format == "102" and len(issue_date) == 8 and issue_date.isdigit())
        )
        self._record(
            "BR-03",
            "Invoice Issue Date (BT-2 / § 14 Abs. 4 Nr. 3 UStG)",
            date_valid,
            "Ausstellungsdatum im Format 102 (YYYYMMDD) erforderlich.",
        )

        type_code = self._find_text("rsm:ExchangedDocument/ram:TypeCode")
        self._record(
            "BR-04",
            "Invoice Type Code (BT-3)",
            type_code in ["380", "381", "384", "389"],
            f"Gültiger Rechnungstyp-Code erforderlich (z. B. 380, 381). Gefunden: {type_code}",
        )

        currency = self._find_text(
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode"
        )
        self._record(
            "BR-05",
            "Invoice Currency Code (BT-5)",
            bool(currency and len(currency) == 3),
            f"ISO-Währungscode (3 Buchstaben) erforderlich. Gefunden: {currency}",
        )

        # ---------------------------------------------------------
        # 2. Beteiligte Parteien (BR-06 bis BR-09, BR-CO-26, BR-CO-09)
        # ---------------------------------------------------------
        seller_name = self._find_text(
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:Name"
        )
        self._record(
            "BR-06",
            "Seller Name (BT-27 / § 14 Abs. 4 Nr. 1 UStG)",
            seller_name is not None,
            "Name des Rechnungsstellers fehlt.",
        )

        buyer_name = self._find_text(
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:BuyerTradeParty/ram:Name"
        )
        self._record(
            "BR-07",
            "Buyer Name (BT-44 / § 14 Abs. 4 Nr. 1 UStG)",
            buyer_name is not None,
            "Name des Leistungsempfängers fehlt.",
        )

        seller_country = self._find_text(
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID"
        )
        self._record(
            "BR-09",
            "Seller Country Code (BT-40)",
            seller_country in self.ISO_COUNTRY_CODES,
            f"Verkäufer-Ländercode ungültig oder nicht vorhanden: {seller_country}",
        )

        # BR-CO-26: Identifikation Verkäufer
        seller_party = self.root.find(
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty",
            self.NAMESPACES,
        )
        has_seller_id = False
        seller_vat_id = None
        seller_tax_fc_id = None

        if seller_party is not None:
            seller_id = self._find_text("ram:ID", seller_party)
            seller_legal = self._find_text("ram:SpecifiedLegalOrganization/ram:ID", seller_party)

            # Steuernummern & USt-ID prüfen
            tax_regs = seller_party.findall("ram:SpecifiedTaxRegistration", self.NAMESPACES)
            for reg in tax_regs:
                id_node = reg.find("ram:ID", self.NAMESPACES)
                if id_node is not None and id_node.text:
                    scheme = id_node.attrib.get("schemeID")
                    if scheme == "VA":
                        seller_vat_id = id_node.text.strip()
                    elif scheme == "FC":
                        seller_tax_fc_id = id_node.text.strip()

            has_seller_id = bool(seller_id or seller_legal or seller_vat_id or seller_tax_fc_id)

        self._record(
            "BR-CO-26",
            "Seller Identifier (BT-29 / BT-30 / BT-31)",
            has_seller_id,
            "Mindestens Seller-ID, Legal-Org-ID oder USt-ID/Steuernummer muss vorhanden sein.",
        )

        # BR-CO-09 & § 14 UStG: USt-IdNr. Format- und Prefix-Prüfung
        if seller_vat_id:
            prefix = seller_vat_id[:2].upper()
            vat_valid = prefix in self.ISO_COUNTRY_CODES
            self._record(
                "BR-CO-09",
                "Seller VAT Identifier Prefix (BT-31 / § 14 Abs. 4 Nr. 2 UStG)",
                vat_valid,
                f"USt-IdNr. '{seller_vat_id}' muss mit gültigem ISO-2-Ländercode beginnen.",
            )
        else:
            self._record(
                "§14-STEUER-NR",
                "Steuernummer oder USt-IdNr (§ 14 Abs. 4 Nr. 2 UStG)",
                seller_tax_fc_id is not None,
                "Weder USt-IdNr. (VA) noch Steuernummer (FC) für den Verkäufer hinterlegt.",
            )

        # ---------------------------------------------------------
        # 3. Summen & Beträge (BR-13 bis BR-15, BR-DEC-12..18)
        # ---------------------------------------------------------
        summation = self.root.find(
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation",
            self.NAMESPACES,
        )

        net_str = self._find_text("ram:TaxBasisTotalAmount", summation) if summation is not None else None
        tax_str = self._find_text("ram:TaxTotalAmount", summation) if summation is not None else None
        gross_str = self._find_text("ram:GrandTotalAmount", summation) if summation is not None else None
        due_str = self._find_text("ram:DuePayableAmount", summation) if summation is not None else None

        self._record("BR-13", "TaxBasisTotalAmount (BT-109)", net_str is not None, "Nettobetrag fehlt.")
        self._record("BR-14", "GrandTotalAmount (BT-112)", gross_str is not None, "Bruttobetrag fehlt.")
        self._record("BR-15", "DuePayableAmount (BT-115)", due_str is not None, "Fälliger Zahlbetrag fehlt.")

        # Dezimalstellen-Regeln (Max 2 Nachkommastellen)
        self._record("BR-DEC-12", "Decimals Net Total", self._check_max_decimals(net_str, 2), "Max. 2 Nachkommastellen für Netto erlaubt.")
        self._record("BR-DEC-13", "Decimals Tax Total", self._check_max_decimals(tax_str, 2), "Max. 2 Nachkommastellen für Steuerbetrag erlaubt.")
        self._record("BR-DEC-14", "Decimals Grand Total", self._check_max_decimals(gross_str, 2), "Max. 2 Nachkommastellen für Brutto erlaubt.")
        self._record("BR-DEC-18", "Decimals Due Payable", self._check_max_decimals(due_str, 2), "Max. 2 Nachkommastellen für Zahlbetrag erlaubt.")

        # ---------------------------------------------------------
        # 4. Mathematische Konsistenz (§ 14 Abs. 4 Nr. 7/8 UStG)
        # ---------------------------------------------------------
        if net_str and gross_str:
            try:
                net = Decimal(net_str)
                tax = Decimal(tax_str) if tax_str else Decimal("0.00")
                gross = Decimal(gross_str)

                math_check = (net + tax) == gross
                self._record(
                    "CALC-01",
                    "Net + Tax == Gross (§ 14 UStG)",
                    math_check,
                    f"Berechnung {'korrekt' if math_check else f'falsch: {net} (Netto) + {tax} (USt) != {gross} (Brutto)'}",
                )
            except InvalidOperation:
                self._record("CALC-01", "Monetary Number Parsing", False, "Betragsfelder enthalten keine gültigen Zahlenwerte.")

        # Auswertung
        failed_checks = [c for c in self.results if c["status"] == "FAILED"]
        return {
            "is_valid": len(failed_checks) == 0,
            "invoice_id": inv_id,
            "total_checks": len(self.results),
            "passed": len(self.results) - len(failed_checks),
            "failed": len(failed_checks),
            "failed_details": failed_checks,
            "all_results": self.results,
        }
