/**
 * Tender Scout — Status-Sync Worker
 *
 * Haelt den Bearbeitungsstatus der Ausschreibungen (Neu → Geprueft →
 * Weitergeleitet → Beworben/Verworfen, inkl. Empfaenger und Zeitstempel)
 * zentral in Cloudflare KV. Alle Nutzer sehen denselben Stand, ohne selbst
 * irgendetwas einzurichten.
 *
 * Bewusst ohne GitHub-Token: Der Status lag frueher in data/status.json im
 * Repo, was einen Token mit Schreibrecht verlangte. Der musste von Hand
 * hinterlegt werden, ging bei einem Deploy verloren und erzeugte bei jeder
 * Statusaenderung einen Commit. KV braucht nichts davon.
 *
 * GET  -> { ok, service, data }        aktueller Gesamtstand
 * POST -> { id, status, forwardedTo }  setzt einen Eintrag, liefert data
 *
 * Einrichtung: siehe cloudflare-worker-SETUP.md.
 */

// Mehrere Herkuenfte, damit waehrend eines Umzugs altes und neues Dashboard
// parallel speichern koennen. Access-Control-Allow-Origin erlaubt nur einen
// Wert pro Antwort — deshalb wird die Herkunft der Anfrage zurueckgespiegelt,
// sofern sie in dieser Liste steht.
const ALLOWED_ORIGINS = [
  "https://reqpool.github.io",
  "https://kaempfrp.github.io",
];
const KV_KEY = "status";

function withCors(resp, request) {
  const origin = request && request.headers.get("Origin");
  resp.headers.set(
    "Access-Control-Allow-Origin",
    ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0]
  );
  resp.headers.set("Vary", "Origin");
  resp.headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  resp.headers.set("Access-Control-Allow-Headers", "Content-Type");
  return resp;
}

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "Content-Type": "application/json" },
  });
}

async function readStatus(env) {
  const raw = await env.STATUS_KV.get(KV_KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (e) {
    // Kaputter Inhalt darf den Sync nicht dauerhaft blockieren.
    return {};
  }
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }), request);
    }

    // Fehlende Einrichtung klar melden, statt still leere Daten zu liefern.
    if (!env.STATUS_KV) {
      return withCors(
        json({ error: "Server nicht konfiguriert (KV-Binding STATUS_KV fehlt)" }, 500),
        request
      );
    }

    if (request.method === "GET") {
      const data = await readStatus(env);
      return withCors(
        json({ ok: true, service: "tender-scout-status-worker", data }),
        request
      );
    }

    if (request.method !== "POST") {
      return withCors(json({ error: "Method not allowed" }, 405), request);
    }

    let payload;
    try {
      payload = await request.json();
    } catch (e) {
      return withCors(json({ error: "Invalid JSON" }, 400), request);
    }

    const { id, status, forwardedTo } = payload || {};
    if (!id || !status) {
      return withCors(json({ error: "id und status erforderlich" }, 400), request);
    }

    const data = await readStatus(env);
    data[id] = {
      status,
      ts: new Date().toISOString(),
      forwardedTo: forwardedTo || "",
    };
    await env.STATUS_KV.put(KV_KEY, JSON.stringify(data));

    // Gesamtstand zurueck, damit das Dashboard zwischenzeitliche Aenderungen
    // anderer Nutzer sofort mitbekommt.
    return withCors(json({ ok: true, data }), request);
  },
};
