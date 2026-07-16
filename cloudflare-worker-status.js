/**
 * Tender Scout — Status-Sync Worker
 *
 * Nimmt Status-Änderungen vom Dashboard entgegen und schreibt sie
 * sicher in data/status.json im GitHub-Repo. Der GitHub-Token bleibt
 * hier auf dem Server (als Secret) — die 40 Nutzer brauchen selbst
 * keinen Token und keine Einrichtung.
 *
 * Einrichtung: siehe SETUP.md im selben Ordner.
 */

const ALLOWED_ORIGIN = "https://kaempfrp.github.io";
const GH_OWNER = "KaempfRP";
const GH_REPO = "RP--KK";
const GH_BRANCH = "main";
const GH_PATH = "data/status.json";

function withCors(resp) {
  resp.headers.set("Access-Control-Allow-Origin", ALLOWED_ORIGIN);
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

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }));
    }

    if (request.method === "GET") {
      // Health check
      return withCors(json({ ok: true, service: "tender-scout-status-worker" }));
    }

    if (request.method !== "POST") {
      return withCors(json({ error: "Method not allowed" }, 405));
    }

    let payload;
    try {
      payload = await request.json();
    } catch (e) {
      return withCors(json({ error: "Invalid JSON" }, 400));
    }

    const { id, status, forwardedTo } = payload || {};
    if (!id || !status) {
      return withCors(json({ error: "id und status erforderlich" }, 400));
    }

    if (!env.GH_TOKEN) {
      return withCors(json({ error: "Server nicht konfiguriert (GH_TOKEN fehlt)" }, 500));
    }

    const ghHeaders = {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "tender-scout-worker",
    };
    const apiUrl = `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/contents/${GH_PATH}?ref=${GH_BRANCH}`;

    for (let attempt = 0; attempt < 3; attempt++) {
      let sha = null;
      let data = {};

      const getRes = await fetch(apiUrl, { headers: ghHeaders });
      if (getRes.status === 200) {
        const fileJson = await getRes.json();
        sha = fileJson.sha;
        try {
          data = JSON.parse(atob(fileJson.content.replace(/\n/g, "")));
        } catch (e) {
          data = {};
        }
      } else if (getRes.status !== 404) {
        return withCors(json({ error: "GitHub-Lesefehler", status: getRes.status }, 502));
      }

      data[id] = {
        status,
        ts: new Date().toISOString(),
        forwardedTo: forwardedTo || "",
      };

      const putBody = {
        message: `Status: ${id} -> ${status}`,
        content: btoa(unescape(encodeURIComponent(JSON.stringify(data, null, 2)))),
        branch: GH_BRANCH,
      };
      if (sha) putBody.sha = sha;

      const putRes = await fetch(
        `https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/contents/${GH_PATH}`,
        {
          method: "PUT",
          headers: { ...ghHeaders, "Content-Type": "application/json" },
          body: JSON.stringify(putBody),
        }
      );

      if (putRes.status === 409) continue; // Konflikt, erneut versuchen
      if (!putRes.ok) {
        const detail = await putRes.text();
        return withCors(json({ error: "GitHub-Schreibfehler", detail }, 502));
      }

      return withCors(json({ ok: true, data }));
    }

    return withCors(json({ error: "Konflikt, bitte erneut versuchen" }, 409));
  },
};
