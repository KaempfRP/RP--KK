# Tender Scout — Architektur & Planung

## Architekturübersicht

```
[TED API] ──┐
[DTVP RSS] ─┼──► [rss_sources.py] ──► [dedup.py] ──► [render.py] ──► [docs/index.html]
[NRW RSS]  ─┤                              ▲
[Bund RSS] ─┘                         [seen.db]
```

Der TED-Connector (`ted_api.py`) und die RSS-Connectoren (`rss_sources.py`)
liefern Einträge in einem einheitlichen Format. Die Deduplizierung (`dedup.py`)
filtert bereits bekannte Einträge per SQLite-Datenbank. Der Renderer (`render.py`)
erzeugt aus allen Einträgen eine statische HTML-Seite via Jinja2-Template.

## Module

### src/ted_api.py
Verbindet sich mit der TED Search API V3 (POST, anonym, kein API-Key).
Filtert nach CPV 72000000 + 79410000, Land DEU, Richtlinie 2014/25/EU.

- **Input:** Keine Parameter (Filterlogik ist fest konfiguriert)
- **Output:** Liste von Dicts mit Feldern: id, title, buyer, published, deadline, url, source

### src/rss_sources.py
Liest vier RSS-Feeds (DTVP, Vergabe.NRW, Bund.de) via feedparser.
Jeder Feed wird einzeln abgefragt; Fehler in einem Feed blockiert die anderen nicht.

- **Input:** Keine Parameter (Feed-URLs sind fest konfiguriert)
- **Output:** Liste von Dicts im selben Format wie ted_api.py

### src/dedup.py
Verwaltet eine SQLite-Datenbank (data/seen.db) mit bereits gesehenen Ausschreibungs-IDs.
Stellt sicher, dass jede Ausschreibung nur einmal als "neu" markiert wird.

- **Input:** Liste von Eintrags-Dicts
- **Output:** Gefilterte Liste (nur neue Einträge), Persistierung der neuen IDs

### src/render.py
Rendert alle Einträge in eine statische HTML-Seite mittels Jinja2-Template.
Markiert neue Einträge mit einem "NEU"-Badge und erstellt Filter-Buttons pro Quelle.

- **Input:** Alle Einträge + Set der neuen IDs
- **Output:** docs/index.html (statische Datei für GitHub Pages)

### main.py
Orchestriert den gesamten Ablauf: DB initialisieren → Quellen abfragen →
Deduplizieren → Rendern → Abschlussbericht auf der Konsole.

- **Input:** Keine (Einstiegspunkt)
- **Output:** docs/index.html + aktualisierte seen.db + Konsolenausgabe

## Datenfluss

```
1. ted_api.fetch_ted()       → List[Dict]  (TED-Ergebnisse)
2. rss_sources.fetch_rss()   → List[Dict]  (RSS-Ergebnisse)
3. all = ted + rss            → List[Dict]  (alle Ergebnisse)
4. dedup.filter_new(all)      → List[Dict]  (nur neue)
5. dedup.save_seen(new)       → seen.db     (IDs persistiert)
6. render.render_page(all, new_ids) → docs/index.html
```

## Bekannte Risiken und Gegenmaßnahmen

| Risiko | Maßnahme |
|--------|----------|
| TED API nicht erreichbar | Warning loggen, leere Liste zurückgeben, Rest läuft weiter |
| RSS-Feed nicht erreichbar | Jeder Feed in eigenem try/except, Fehler = Warning + leere Liste |
| TED API ändert Response-Format | Unit Tests mit gemockten Responses erkennen Abweichungen |
| RSS-Feed liefert unvollständige Einträge | Fehlende Felder mit Defaults ("–") auffangen |
| seen.db wird beschädigt | SQLite ist robust; im Notfall: Datei löschen, alle Einträge werden als "neu" gewertet |
| Zu viele Ergebnisse | TED-Limit auf 50, RSS-Feeds liefern naturgemäß begrenzte Mengen |
| GitHub Pages Quota überschritten | Bei einer statischen HTML-Seite praktisch unmöglich |

## Architektur-Entscheidungen

### Warum TED API statt RSS?
TED bietet keinen geeigneten RSS-Feed mit den benötigten Filterkriterien
(CPV + Land + Richtlinie). Die Search API V3 erlaubt präzise Abfragen und
ist anonym (ohne API-Key) nutzbar.

### Warum SQLite statt Datei (JSON/CSV)?
SQLite ist ACID-konform, concurrent-safe und benötigt keine externe Abhängigkeit.
Die Deduplizierung per PRIMARY KEY ist atomar und schneller als Datei-Parsing.
Die DB wird im Repo versioniert, sodass die Historie nachvollziehbar bleibt.

### Warum GitHub Pages statt eigenem Server?
Kein Server = keine Kosten, kein Wartungsaufwand, kein Sicherheitsrisiko.
GitHub Actions generiert die Seite, GitHub Pages hostet sie — alles im Free Tier.

### Warum Jinja2 statt React/Vue?
Eine statische HTML-Seite genügt für die Darstellung einer Tabelle mit Filtern.
Kein Build-Schritt, keine JavaScript-Dependencies, maximale Einfachheit.

### Warum einheitliches Dict-Format?
Alle Quellen liefern dasselbe Format → Dedup und Rendering sind quellenunabhängig.
Neue Quellen lassen sich ergänzen, ohne Dedup oder Rendering anzupassen.
