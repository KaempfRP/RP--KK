"""Unit tests for the portal connectors (offline, fixture-based)."""

from src.portal_sources import _parse_eforms_notice, _parse_ausschreibung_at_detail


EFORMS_CONTRACT_NOTICE = """<?xml version="1.0" encoding="UTF-8"?>
<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1">
  <cbc:IssueDate>2026-07-10+02:00</cbc:IssueDate>
  <efac:Organizations>
    <efac:Organization>
      <efac:Company>
        <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
        <cac:PartyName><cbc:Name>Stadtwerke Musterstadt GmbH</cbc:Name></cac:PartyName>
      </efac:Company>
    </efac:Organization>
    <efac:Organization>
      <efac:Company>
        <cac:PartyIdentification><cbc:ID>ORG-0002</cbc:ID></cac:PartyIdentification>
        <cac:PartyName><cbc:Name>Vergabekammer Musterland</cbc:Name></cac:PartyName>
      </efac:Company>
    </efac:Organization>
  </efac:Organizations>
  <cac:ContractingParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
    </cac:Party>
  </cac:ContractingParty>
  <cac:ProcurementProject>
    <cbc:Name>IT-Beratung  ERP-Einführung</cbc:Name>
    <cac:MainCommodityClassification>
      <cbc:ItemClassificationCode listName="cpv">72220000</cbc:ItemClassificationCode>
    </cac:MainCommodityClassification>
  </cac:ProcurementProject>
  <cac:TenderingProcess>
    <cac:TenderSubmissionDeadlinePeriod>
      <cbc:EndDate>2026-08-11+02:00</cbc:EndDate>
    </cac:TenderSubmissionDeadlinePeriod>
  </cac:TenderingProcess>
</ContractNotice>
"""

EFORMS_AWARD_NOTICE = EFORMS_CONTRACT_NOTICE.replace("ContractNotice", "ContractAwardNotice")


class TestEformsParsing:

    def test_contract_notice_parsed(self):
        entry = _parse_eforms_notice(EFORMS_CONTRACT_NOTICE.encode(), "abc-123")
        assert entry is not None
        assert entry["id"] == "oevg-abc-123"
        assert entry["title"] == "IT-Beratung ERP-Einführung"
        assert entry["buyer"] == "Stadtwerke Musterstadt GmbH"
        assert entry["published"] == "2026-07-10"
        assert entry["deadline"] == "2026-08-11"
        assert entry["cpv"] == ["72220000"]
        assert entry["source"] == "oeffentlichevergabe.de"
        assert "abc-123" in entry["url"]

    def test_award_notice_skipped(self):
        assert _parse_eforms_notice(EFORMS_AWARD_NOTICE.encode(), "abc-123") is None

    def test_invalid_xml_returns_none(self):
        assert _parse_eforms_notice(b"<not-xml", "x") is None

    def test_buyer_resolved_via_contracting_party_reference(self):
        """The buyer is the referenced org, not the first one in document order."""
        swapped = EFORMS_CONTRACT_NOTICE.replace("ORG-0001", "TMP").replace(
            "ORG-0002", "ORG-0001").replace("TMP", "ORG-0002")
        entry = _parse_eforms_notice(swapped.encode(), "x")
        # ContractingParty now references ORG-0002 = Stadtwerke
        assert entry["buyer"] == "Stadtwerke Musterstadt GmbH"


EFORMS_NATIONAL_NOTICE = """<?xml version="1.0" encoding="UTF-8"?>
<ns9:ContractNotice xmlns:ns9="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cac:ContractingParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>EWN Entsorgungswerk für Nuklearanlagen GmbH</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:ContractingParty>
  <cac:ProcurementProject>
    <cbc:Name>Digitalisierung des Instandhaltungs- und Auftragswesens</cbc:Name>
    <cac:MainCommodityClassification>
      <cbc:ItemClassificationCode listName="cpv">72220000</cbc:ItemClassificationCode>
    </cac:MainCommodityClassification>
  </cac:ProcurementProject>
  <cac:TenderingProcess>
    <cac:TenderSubmissionDeadlinePeriod>
      <cbc:EndDate>2026-08-10+02:00</cbc:EndDate>
    </cac:TenderSubmissionDeadlinePeriod>
  </cac:TenderingProcess>
</ns9:ContractNotice>
"""


class TestNationalEformsParsing:
    """National eForms-DE notices: no Organization list, no IssueDate."""

    def test_buyer_from_contracting_party_name(self):
        entry = _parse_eforms_notice(EFORMS_NATIONAL_NOTICE.encode(), "25575098-1")
        assert entry is not None
        assert entry["buyer"] == "EWN Entsorgungswerk für Nuklearanlagen GmbH"
        assert entry["title"] == "Digitalisierung des Instandhaltungs- und Auftragswesens"
        assert entry["deadline"] == "2026-08-10"

    def test_published_falls_back_to_export_day(self):
        entry = _parse_eforms_notice(
            EFORMS_NATIONAL_NOTICE.encode(), "25575098-1", fallback_published="2026-07-11")
        assert entry["published"] == "2026-07-11"


AT_DETAIL_HTML = """
<html><body>
<div>ÜBERBLICK AUSSCHREIBUNG</div>
<h1>Software für Energiedatenmanagement</h1>
<div>Art des Dokuments</div><div>Bekanntmachung</div>
<div>Veröffentlicht am</div><div>13.07.2026</div>
<div>Kurzbeschreibung</div><div>EDM-System für einen Netzbetreiber.</div>
</body></html>
"""

AT_AWARD_HTML = AT_DETAIL_HTML.replace("Bekanntmachung", "Vergebener Auftrag")


class TestAusschreibungAtParsing:

    def test_detail_parsed(self):
        entry = _parse_ausschreibung_at_detail(
            AT_DETAIL_HTML, "https://www.ausschreibung.at/Ausschreibung/564800/")
        assert entry is not None
        assert entry["id"] == "at-564800"
        assert entry["title"] == "Software für Energiedatenmanagement"
        assert entry["published"] == "13.07.2026"
        assert entry["source"] == "ausschreibung.at"

    def test_award_skipped(self):
        entry = _parse_ausschreibung_at_detail(
            AT_AWARD_HTML, "https://www.ausschreibung.at/Ausschreibung/564800/")
        assert entry is None

    def test_empty_page_returns_none(self):
        assert _parse_ausschreibung_at_detail("<html></html>", "https://x.at/Ausschreibung/1/") is None
