// Serves dashboard/data.json from the private repo sushchenkoganna-jpg/openai-ads-daily (GitHub Action rebuilds it daily).
// One GitHub call per hour at most: the answer is kept in the app cache "gh".
const URL_ = "https://api.github.com/repos/sushchenkoganna-jpg/openai-ads-daily/contents/dashboard/data.json?ref=main";
export default {
  async fetch(request, env) {
    const c = `${env.FACTUM_CACHE_URL}/data`;
    const hit = await fetch(c);
    if (hit.ok) return new Response(await hit.text(), { headers: { "content-type": "application/json" } });
    const res = await fetch(URL_, { headers: { accept: "application/vnd.github.raw+json", "user-agent": "factum-openai-ads" } });
    if (!res.ok) return new Response(JSON.stringify({ error: `GitHub ${res.status}`, detail: (await res.text()).slice(0, 300) }), { status: 502, headers: { "content-type": "application/json" } });
    const body = await res.text();
    await fetch(`${c}?ttl=3600`, { method: "PUT", headers: { "content-type": "application/json" }, body });
    return new Response(body, { headers: { "content-type": "application/json" } });
  },
};
