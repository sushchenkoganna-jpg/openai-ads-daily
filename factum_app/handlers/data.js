// Serves dashboard/data.json from the private repo sushchenkoganna-jpg/openai-ads-daily (GitHub Action rebuilds it daily).
// One GitHub call per hour at most: the answer is kept in the app cache "gh".
const SRC = "https://api.github.com/repos/sushchenkoganna-jpg/openai-ads-daily/contents/dashboard/data.json";
const json = (o) => new Response(JSON.stringify(o), { headers: { "content-type": "application/json" } });
export default {
  async fetch(request, env) {
    const c = `${env.FACTUM_CACHE_URL}/data`;
    try {
      const hit = await fetch(c);
      if (hit.ok) return new Response(await hit.text(), { headers: { "content-type": "application/json" } });
    } catch (e) { console.log("cache read failed", String(e)); }
    const res = await fetch(SRC, { headers: { accept: "application/vnd.github.raw+json", "user-agent": "factum-openai-ads", "x-github-api-version": "2022-11-28" } });
    const body = await res.text();
    if (!res.ok) {
      console.log("github", res.status, body.slice(0, 500));
      return json({ error: `GitHub ${res.status}`, detail: body.slice(0, 300) });
    }
    let text = body;
    try { const j = JSON.parse(body); if (j && j.content && j.encoding === "base64") text = atob(j.content.replace(/\n/g, "")); }
    catch (e) { console.log("parse", String(e)); }
    try { await fetch(`${c}?ttl=3600`, { method: "PUT", headers: { "content-type": "application/json" }, body: text }); }
    catch (e) { console.log("cache write failed", String(e)); }
    return new Response(text, { headers: { "content-type": "application/json" } });
  },
};
