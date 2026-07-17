# Geteilter Status — wie er funktioniert

Alle Nutzer sehen und ändern denselben Bearbeitungsstatus (Neu → Geprüft →
Weitergeleitet → Beworben/Verworfen, inklusive Empfänger und Zeitstempel).
Niemand muss dafür etwas einrichten — kein Konto, kein Token, nichts.

**Für die Nutzer gibt es hier nichts zu tun.** Diese Datei beschreibt nur,
wie es intern läuft und wie man es im Notfall wiederherstellt.

## Aufbau

```
Dashboard (GitHub Pages)  →  Cloudflare Worker  →  Cloudflare KV
   kaempfrp.github.io          tender-scout        tender-scout-status
```

- **Worker:** `tender-scout` unter
  `https://tender-scout.kim-noah-kaempf.workers.dev`
  Code: `cloudflare-worker-status.js` (in diesem Repo)
- **Speicher:** Cloudflare KV, Namespace `tender-scout-status`
- **Konfiguration:** `wrangler.toml` (Worker-Name, Einstiegsdatei, KV-Binding)
- **Im Dashboard:** die Worker-URL steht in `templates/index.html.j2` unter
  `var STATUS_API`

Das Dashboard liest den Stand beim Laden per `GET` vom Worker und schreibt
Änderungen per `POST`. Der Worker legt alles unter einem Schlüssel in KV ab.

## Deployment

Der Worker ist mit diesem Repo verbunden und deployt sich **automatisch bei
jedem Push auf `main`** (Deploy-Befehl: `npx wrangler deploy`). Der Code im
Repo ist die Quelle der Wahrheit — im Cloudflare-Dashboard muss nichts von
Hand eingefügt werden.

> **Wichtig:** `wrangler.toml` muss existieren. Fehlt sie, findet wrangler
> keinen Einstiegspunkt und deployt stattdessen die statischen Dateien. Die
> Worker-URL liefert dann die Dashboard-HTML aus und der Status-Sync ist tot
> (`POST` antwortet mit `405`). Genau das ist schon einmal passiert.

## Warum kein GitHub-Token mehr

Früher lag der Status in `data/status.json` in diesem Repo. Das verlangte
einen GitHub-Token mit Schreibrecht im Worker — mit drei Problemen:

1. Der Token musste von Hand im Dashboard hinterlegt werden (fehleranfällig:
   Secrets gehören in „Variables and secrets **used at runtime**", nicht in
   den Build-Bereich).
2. Ein fehlerhafter Deploy hat das Secret verloren — danach speicherte gar
   nichts mehr.
3. Jede Statusänderung erzeugte einen Commit. Bei 40 Nutzern wird die
   Historie schnell unbrauchbar.

KV hat nichts davon. Kein Geheimnis, das verlorengehen kann.

## Prüfen, ob es läuft

Die Worker-URL im Browser aufrufen. Erwartet:

```json
{"ok":true,"service":"tender-scout-status-worker","data":{ ... }}
```

- `data` enthält den aktuellen Stand aller Einträge.
- Kommt stattdessen HTML: `wrangler.toml` fehlt oder der Build ist schiefgegangen.
- Kommt `KV-Binding STATUS_KV fehlt`: Das KV-Binding ist nicht verbunden —
  `wrangler.toml` prüfen.

Im Dashboard muss oben **„✓ geteilter Status aktiv"** stehen.

## Wiederherstellen (falls der KV-Speicher mal neu muss)

1. Cloudflare → Storage & databases → Workers KV → Namespace anlegen
2. Dessen ID in `wrangler.toml` unter `[[kv_namespaces]]` → `id` eintragen
3. Committen und pushen — der Rest passiert automatisch

## Kosten

Cloudflare Free Tier: 100.000 Worker-Anfragen und 100.000 KV-Lesevorgänge pro
Tag. Für 40 Nutzer wird das nie erreicht — Kosten bleiben bei 0 €.
