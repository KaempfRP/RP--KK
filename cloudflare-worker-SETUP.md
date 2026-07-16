# Setup: Zentraler Status-Sync (einmalig, nur du)

Ziel: Alle 40 Nutzer sehen und ändern denselben Status, ohne selbst
irgendetwas einzurichten. Der GitHub-Zugriff läuft über einen kleinen
kostenlosen Cloud-Dienst (Cloudflare Worker), den nur du einrichtest.

Dauer: ca. 10 Minuten, keine Kreditkarte nötig.

## 1. Cloudflare-Account (falls noch nicht vorhanden)

1. https://dash.cloudflare.com/sign-up öffnen
2. Mit E-Mail registrieren (kostenlos)

## 2. Worker erstellen

1. Im Cloudflare-Dashboard: **Workers & Pages** → **Create** → **Workers** → **Create Worker**
2. Namen vergeben, z. B. `tender-scout-status`
3. **Deploy** klicken (erzeugt erstmal einen Platzhalter)
4. Danach **Edit code** klicken → der Code-Editor öffnet sich
5. Den kompletten Inhalt der Datei `cloudflare-worker-status.js` (liegt neben
   dieser Anleitung) kopieren und den Beispielcode im Editor komplett ersetzen
6. Oben rechts **Deploy** klicken

## 3. GitHub-Token als Secret hinterlegen

Der Worker braucht selbst einen GitHub-Token mit Schreibrecht auf
`KaempfRP/RP--KK` (Contents: Read and write) — genau wie die Tokens, die
wir vorhin schon mal erstellt haben.

1. Neuen Fine-grained Token erstellen: github.com/settings/tokens →
   Fine-grained tokens → Generate new token → Repository access nur
   `KaempfRP/RP--KK` → Permissions → Contents: **Read and write**
2. Zurück im Cloudflare Worker: **Settings** → **Variables and Secrets**
   → **Add** → Name: `GH_TOKEN`, Wert: der eben erstellte Token,
   Typ: **Secret** (nicht "Text"!) → Speichern

## 4. Worker-URL ins Dashboard eintragen

Auf der Worker-Übersichtsseite steht oben eine URL wie:

`https://tender-scout-status.<dein-name>.workers.dev`

Diese URL muss an genau eine Stelle — in `templates/index.html.j2`:

```js
var STATUS_API = '';   // <- hier die Worker-URL eintragen
```

Also z. B.:

```js
var STATUS_API = 'https://tender-scout-status.dein-name.workers.dev';
```

Danach committen und pushen. Der GitHub-Action-Workflow baut die Seite
automatisch neu (er läuft bei jeder Änderung an `templates/`), und ab
dann speichern alle Nutzer zentral — ohne selbst etwas einzurichten.

Solange das Feld leer ist, zeigt das Dashboard „nur lokal gespeichert"
und der Status bleibt im jeweiligen Browser. Es geht nichts kaputt,
das Feature ist nur noch nicht scharf.

## 5. Prüfen, ob es läuft

1. Dashboard öffnen, bei einer Ausschreibung Status auf
   **Weitergeleitet** setzen und einen Namen eintragen
2. Oben muss „✓ geteilter Status aktiv" stehen (nicht „⚠ …")
3. In `data/status.json` im Repo sollte kurz darauf ein neuer Commit
   `Status: <id> -> weitergeleitet` auftauchen
4. Gegenprobe: Seite in einem anderen Browser öffnen — der Status ist da

## Gut zu wissen

Der Worker prüft nicht, *wer* schreibt: Wer die Worker-URL kennt, kann
einen Status setzen. Für einen internen Statuszettel, dessen Daten
ohnehin öffentlich im Repo liegen, ist das vertretbar — schlimmstenfalls
verstellt jemand einen Wert, und die Git-Historie zeigt jede Änderung.
Der `ALLOWED_ORIGIN` im Worker-Code ist nur ein CORS-Header für Browser,
kein Zugriffsschutz.

## Kosten

Cloudflare Workers Free Tier: 100.000 Requests/Tag kostenlos. Für 40
Nutzer, die gelegentlich einen Status ändern, wird das nie erreicht —
Kosten bleiben bei 0 €.
