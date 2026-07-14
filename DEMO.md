# Demo-Ablauf für Team-Präsentation

## Vorbereitung (5 Min. vorher)
- GitHub Actions einmal manuell ausgelöst → Seite ist frisch
- GitHub Pages URL im Browser geöffnet
- Mobile Ansicht bereit (DevTools oder echtes Handy)

## Ablauf (10 Minuten)

**1. Problem zeigen (2 Min.)**
"Bisher macht [Kollege] das manuell so: TED aufrufen,
erweiterte Suche, CPV auswählen, Land Deutschland,
Richtlinie 2014/25/EU — das dauert jeden Tag X Minuten."

**2. Lösung zeigen (3 Min.)**
- GitHub Pages URL öffnen
- Tabelle zeigen: alle Ausschreibungen, NEU-Badges
- Quellenfilter live demonstrieren
- Auf Mobilgerät zeigen

**3. Automation zeigen (3 Min.)**
- GitHub Actions → letzten Workflow-Run zeigen
- "Das läuft jeden Werktag um 7 Uhr automatisch"
- "Kein Server, keine Kosten"

**4. Nächste Schritte (2 Min.)**
- KI-Bewertung: Relevanz-Score per Claude API
- E-Mail bei neuen Treffern
- Weitere Quellen ergänzen

## Häufige Fragen

Q: Was kostet das?
A: 0 € — GitHub Free Tier reicht vollständig.

Q: Was wenn eine Quelle ausfällt?
A: Warnung im Log, alle anderen laufen weiter.

Q: Können wir weitere Quellen ergänzen?
A: Ja, jede mit RSS-Feed in ca. 30 Minuten ergänzbar.

Q: Wie aktuell sind die Daten?
A: Täglich um 7 Uhr morgens aktualisiert.
   Manueller Refresh jederzeit per Knopfdruck möglich.
