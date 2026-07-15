"""Unit tests for the weighted scoring system (v2).

Context gate (CPV or title keywords) is the only hard gate.
Sector is a weighted bonus + classification attribute, not a hard gate.
"""

from src.scoring import score_entry, score_entries, classify_sector


# ===== FALSE POSITIVE TESTS (must score 0 — no IT context) =====

class TestFalsePositives:
    """Tenders without any IT/consulting context must score 0."""

    def test_holzbau(self):
        result = score_entry({"title": "Holzbauarbeiten Turnhalle", "buyer": "Gemeinde Y"})
        assert result["score"] == 0

    def test_dachinstandsetzung(self):
        result = score_entry({"title": "Dachinstandsetzung Gymnasium", "buyer": "Stadt X"})
        assert result["score"] == 0

    def test_kabelverlegung(self):
        result = score_entry({"title": "Kabelverlegung Ortsnetz", "buyer": "Baufirma GmbH"})
        assert result["score"] == 0

    def test_drees_sommer_bau(self):
        """'Projektmanagement' in the buyer name is not IT context."""
        result = score_entry({
            "title": "Feuerwehrgerätehaus - TWP inkl. Brandschutz",
            "buyer": "Drees & Sommer SE Hamburg - Projektmanagement",
        })
        assert result["score"] == 0

    def test_turnhalle_sanierung(self):
        result = score_entry({
            "title": "ZV - Sanierung Turnhalle - Abbrucharbeiten",
            "buyer": "Stadt Coburg - Beschaffungsamt",
        })
        assert result["score"] == 0

    def test_feuerwehr_rahmenvertrag(self):
        """LT FW = Löschfahrzeug, not IT — even with energy buyer."""
        result = score_entry({
            "title": "LT FW Rahmenvertrag",
            "buyer": "EnBW Energie Baden-Württemberg AG",
        })
        assert result["score"] == 0


# ===== CPV CONTEXT GATE (P2) =====

class TestCpvGate:
    """CPV codes open the context gate even without title keywords."""

    def test_cpv_it_code_passes_gate(self):
        result = score_entry({
            "title": "Rahmenvereinbarung Fachverfahren",
            "buyer": "Netze BW",
            "cpv": ["72000000"],
        })
        assert result["score"] > 0
        assert result["score_breakdown"]["context"] is True

    def test_cpv_consulting_code_passes_gate(self):
        result = score_entry({
            "title": "Begleitung Transformationsprogramm",
            "buyer": "Stadtwerke München",
            "cpv": ["79411000"],
        })
        assert result["score"] > 0

    def test_cpv_construction_code_blocked(self):
        """Construction CPV (45xxx) does not open the gate."""
        result = score_entry({
            "title": "Neubau Verwaltungsgebäude",
            "buyer": "Stadtwerke München",
            "cpv": ["45000000"],
        })
        assert result["score"] == 0

    def test_cpv_boosts_score_of_keyword_match(self):
        """Same title scores higher with matching CPV (context bonus)."""
        base = score_entry({"title": "IT-Beratung Digitalisierung", "buyer": "EnBW"})
        with_cpv = score_entry({
            "title": "IT-Beratung Digitalisierung", "buyer": "EnBW",
            "cpv": ["72220000"],
        })
        assert with_cpv["score"] > base["score"]


# ===== SOFT SECTOR (P3): non-target sectors score, but lower =====

class TestSoftSectorGate:
    """IT tenders outside target sectors score > 0 but below target sector."""

    def test_public_sector_scores_low_but_not_zero(self):
        result = score_entry({
            "title": "Vergabemanagement IT-Dienstleistungen",
            "buyer": "Landeshauptstadt München",
        })
        assert result["score"] > 0
        assert result["sector"] == "Public"
        assert result["score_breakdown"]["sector"] is False

    def test_university_scores_but_classified_public(self):
        result = score_entry({
            "title": "IT-Beratung Digitalisierung Campus",
            "buyer": "Universität Hamburg",
        })
        assert result["score"] > 0
        assert result["sector"] == "Public"

    def test_energy_scores_higher_than_public(self):
        """Same title: energy buyer must outrank public buyer."""
        energy = score_entry({"title": "IT-Beratung Digitalisierung", "buyer": "EnBW"})
        public = score_entry({"title": "IT-Beratung Digitalisierung", "buyer": "Landeshauptstadt München"})
        assert energy["score"] > public["score"]

    def test_unknown_buyer_with_energy_title_scores(self):
        """Real energy-IT with unknown buyer no longer scores 0 (P3)."""
        result = score_entry({
            "title": "IT-Beratung Redispatch Netzleitsystem",
            "buyer": "Unbekanntes Unternehmen",
        })
        assert result["score"] > 0
        assert result["score_breakdown"]["sector"] is True


# ===== TRUE POSITIVE TESTS (target sector, must score well) =====

class TestTruePositives:

    def test_it_beratung_energie(self):
        result = score_entry({
            "title": "Rahmenvertrag IT-Beratung und Projektsteuerung",
            "buyer": "EnBW",
        })
        assert result["score"] >= 40

    def test_lastenheft_erp(self):
        result = score_entry({
            "title": "Lastenhefterstellung für ERP-System",
            "buyer": "Bayernwerk",
        })
        assert result["score"] >= 30
        assert "Requirements Engineer" in result["matched_roles"]

    def test_sap_migration_beratung(self):
        result = score_entry({
            "title": "SAP-Migration Beratungsleistungen und Projektmanagement",
            "buyer": "Stadtwerke München",
        })
        assert result["score"] >= 30

    def test_softwarebeschaffung_energie(self):
        result = score_entry({
            "title": "Softwarebeschaffung und Softwareauswahl CRM",
            "buyer": "Mainova",
        })
        assert result["score"] >= 30
        assert "IT-Einkauf" in result["matched_roles"]

    def test_testmanagement_energie(self):
        result = score_entry({
            "title": "Testmanagement und Qualitätssicherung Software-Einführung",
            "buyer": "50Hertz",
        })
        assert result["score"] >= 20
        assert "Testmanager" in result["matched_roles"]

    def test_telko_it_beratung(self):
        result = score_entry({
            "title": "IT-Projektmanagement Digitalisierung",
            "buyer": "Deutsche Telekom",
        })
        assert result["score"] > 0
        assert result["sector"] == "Industrie"

    def test_immobilien_it(self):
        result = score_entry({
            "title": "Softwareeinführung Gebäudeautomation Smart Building",
            "buyer": "Vonovia Immobilien GmbH",
        })
        assert result["score"] > 0
        assert result["sector"] == "Industrie"


# ===== SECTOR CLASSIFICATION =====

class TestSectorClassification:

    def test_netzbetreiber(self):
        sector, buyer_type = classify_sector("", "50Hertz Transmission GmbH")
        assert sector == "Energie"
        assert buyer_type == "Netzbetreiber"

    def test_stadtwerke(self):
        sector, buyer_type = classify_sector("", "Stadtwerke Musterstadt GmbH")
        assert sector == "Energie"
        assert buyer_type == "Stadtwerke"

    def test_ministerium(self):
        sector, buyer_type = classify_sector("", "Ministerium für Wirtschaft NRW")
        assert sector == "Public"
        assert buyer_type == "Ministerium"

    def test_landkreis(self):
        sector, buyer_type = classify_sector("", "Landkreis Osnabrück")
        assert sector == "Public"
        assert buyer_type == "Landkreis"

    def test_kommune(self):
        sector, buyer_type = classify_sector("", "Stadt Coburg - Beschaffungsamt")
        assert sector == "Public"
        assert buyer_type == "Kommune"

    def test_stadtwerke_beats_stadt(self):
        """'Stadtwerke X' must be Energie, not Public ('Stadt ...')."""
        sector, _ = classify_sector("", "Stadtwerke Augsburg")
        assert sector == "Energie"

    def test_telko_industrie(self):
        sector, buyer_type = classify_sector("", "Deutsche Telekom AG")
        assert sector == "Industrie"
        assert buyer_type == "Telekommunikation"

    def test_unknown_is_sonstige(self):
        sector, buyer_type = classify_sector("Lieferung Büromaterial", "Müller & Partner")
        assert sector == "Sonstige"

    def test_no_substring_false_positive_rwe(self):
        """'meisterwerken' must not match 'RWE'."""
        sector, _ = classify_sector(
            "", "deutsches museum von meisterwerken der naturwissenschaft und technik")
        assert sector != "Energie"

    def test_no_substring_false_positive_eam(self):
        """'team' must not match 'EAM'."""
        sector, _ = classify_sector(
            "", "mpg, generalverwaltung, stabsreferat einkauf, team ek 1")
        assert sector != "Energie"

    def test_energy_title_fallback(self):
        """Energy topic in title classifies unknown buyer as Energie."""
        sector, _ = classify_sector("software redispatch plattform", "XYZ Consulting Partner")
        assert sector == "Energie"

    def test_score_entries_attaches_sector(self):
        entries = [{"title": "IT-Beratung SAP", "buyer": "EnBW"}]
        score_entries(entries)
        assert entries[0]["sector"] == "Energie"
        assert "buyer_type" in entries[0]


# ===== DESCRIPTION MATCHING =====

class TestDescriptionMatching:
    """Role keywords in the description count at half weight."""

    def test_description_roles_increase_score(self):
        """EWN case: 'Projektlastenheft' only in the description."""
        base = {
            "title": "Digitalisierung des Instandhaltungs- und Auftragswesens",
            "buyer": "EWN Entsorgungswerk für Nuklearanlagen GmbH",
            "cpv": ["72220000"],
        }
        without = score_entry(dict(base))
        with_desc = score_entry({**base, "details": {
            "beschreibung": "Erstellung einer Projektskizze und eines Projektlastenheftes "
                            "sowie der Anfangsplanung für die Digitalisierung.",
        }})
        assert with_desc["score"] > without["score"]
        assert "Requirements Engineer" in with_desc["matched_roles"]

    def test_description_weighs_less_than_title(self):
        """Same keyword scores higher in the title than in the description."""
        in_title = score_entry({
            "title": "Digitalisierung Lastenheft", "buyer": "EnBW",
        })
        in_desc = score_entry({
            "title": "Digitalisierung", "buyer": "EnBW",
            "details": {"beschreibung": "Erstellung Lastenheft."},
        })
        assert in_title["score"] > in_desc["score"]

    def test_description_alone_does_not_open_context_gate(self):
        """IT keywords only in the description do not pass the context gate."""
        result = score_entry({
            "title": "Neubau Betriebsgebäude",
            "buyer": "Stadtwerke München",
            "details": {"beschreibung": "Inklusive Software für die Gebäudeautomation."},
        })
        assert result["score"] == 0


# ===== SECTOR BONUS =====

class TestSectorBonus:

    def test_known_buyer_higher_than_unknown(self):
        entry_known = {"title": "IT-Beratung Digitalisierung", "buyer": "EnBW"}
        entry_sector = {"title": "IT-Beratung Digitalisierung", "buyer": "Stadtwerk Musterstadt"}
        assert score_entry(entry_known)["score"] >= score_entry(entry_sector)["score"]


# ===== SCORING MECHANICS =====

class TestScoringMechanics:

    def test_context_gate_blocks(self):
        result = score_entry({"title": "Tiefbauarbeiten Kanal", "buyer": "EnBW"})
        assert result["score"] == 0
        assert result["score_breakdown"]["context"] is False

    def test_score_capped_at_100(self):
        result = score_entry({
            "title": (
                "Rahmenvertrag IT-Beratung Softwarebeschaffung Lastenhefterstellung "
                "Projektmanagement Digitalisierung IT-Strategie Scrum Agile Coach "
                "Testmanagement Qualitätssicherung Anforderungsanalyse Prozessoptimierung "
                "IT-Architektur Cloud-Architektur PMO Programmmanagement Netzleitsystem"
            ),
            "buyer": "EnBW Energie",
            "cpv": ["72000000"],
        })
        assert result["score"] <= 100

    def test_case_insensitive(self):
        r1 = score_entry({"title": "PROJEKTMANAGEMENT IT-BERATUNG", "buyer": "EnBW"})
        r2 = score_entry({"title": "projektmanagement it-beratung", "buyer": "EnBW"})
        assert r1["score"] == r2["score"]

    def test_empty_title_scores_zero(self):
        result = score_entry({"title": "", "buyer": ""})
        assert result["score"] == 0

    def test_score_entries_attaches_fields(self):
        entries = [
            {"title": "IT-Beratung SAP", "buyer": "EnBW"},
            {"title": "Kabelverlegung", "buyer": "Baufirma"},
        ]
        score_entries(entries)
        for e in entries:
            assert "relevance_score" in e
            assert "matched_roles" in e
            assert "sector" in e
            assert "buyer_type" in e
