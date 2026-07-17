# ReqPOOL Tender Scout

Automatischer Ausschreibungs-Scout für Energie-IT-Projekte.
Täglich aktualisiert, keine manuelle Pflege nötig.

## Was er macht

Durchsucht täglich mehrere Vergabeportale nach relevanten
Energie- & IT-Ausschreibungen und zeigt sie übersichtlich
auf einer Webseite an.

**Quellen:**
- TED Europa (Search API v3, CPV 72xxx/794xx, Deutschland)
- oeffentlichevergabe.de — Datenservice Öffentlicher Einkauf
  (täglicher eForms-Bulk-Export; enthält Bekanntmachungen vieler
  Plattformen wie DTVP, subreport ELViS, Vergabe.NRW)
- tender24.de (Suche nach bekannten Energieversorgern)
- ausschreibung.at (neueste Bekanntmachungen, Österreich)

**Relevanz-Scoring (0–100):** Ein Kontext-Gate (CPV-Code oder
IT/Consulting-Keywords im Titel) filtert Fremdgewerke aus.
Danach gewichtete Punkte für ReqPOOL-Rollen-Treffer, Service-Fit
und Zielbranche. Jeder Eintrag wird zusätzlich nach Branche
(Energie/Public/Industrie) und Auftraggeber-Typ (Netzbetreiber,
Stadtwerke, Landkreis, Ministerium, …) klassifiziert.

**Webseite:** Sortierung nach Relevanz, Min-Relevanz-Slider,
Branchen-/Quellen-/Status-Filter, Frist-Ampel (rot < 7 Tage,
gelb < 14 Tage), Ausblenden abgelaufener Fristen,
Status-Workflow pro Ausschreibung (Neu → Geprüft → Weitergeleitet
→ Beworben/Verworfen, mit Zeitstempel und Name des Empfängers)
und Einseiten-PDF-Export pro Eintrag.

**Geteilter Status:** Der Bearbeitungsstatus liegt zentral in
Cloudflare KV — alle Nutzer sehen denselben Stand und damit, ob eine
Ausschreibung bereits jemand weitergeleitet hat. Gelesen und
geschrieben wird über einen kleinen Cloudflare Worker; die Nutzer
brauchen dafür weder Konto noch Token noch sonst eine Einrichtung.
Details: [cloudflare-worker-SETUP.md](cloudflare-worker-SETUP.md).

**Hervorhebung:** Die drei relevantesten Einträge, die neu *und* am
selben Tag veröffentlicht wurden, werden dezent grün hinterlegt.

## Setup (einmalig)

```bash
git clone https://github.com/KaempfRP/RP--KK
cd RP--KK
pip install -r requirements.txt
python main.py
```

Danach `docs/index.html` im Browser öffnen.

## GitHub Pages aktivieren

Settings → Pages → Source: Deploy from branch → Branch: main → /docs

## Manuell auslösen

GitHub → Actions → "Tender Scout" → "Run workflow"

## Tests ausführen

```bash
pytest              # alle Tests
pytest -m smoke     # nur Smoke Tests
pytest -m e2e       # nur E2E Tests
```

## Manuelle Abnahme-Checkliste (nach erstem Deployment)

- [ ] GitHub Actions Workflow läuft grün durch
- [ ] GitHub Pages URL öffnet sich
- [ ] Mindestens eine Quelle liefert Ausschreibungen
- [ ] NEU-Badge erscheint bei frischen Einträgen
- [ ] Quellenfilter funktioniert im Browser
- [ ] Seite ist auf Mobilgerät lesbar

## Geplante Erweiterungen (nach MVP)

- KI-Bewertung der Relevanz via Claude API
- Weitere Quellen (Freelancermap als Sales-Signal)
- E-Mail-Benachrichtigung bei neuen Treffern
- Kundeninformationen anreichern

## Architektur

Siehe [PLANNING.md](PLANNING.md)
