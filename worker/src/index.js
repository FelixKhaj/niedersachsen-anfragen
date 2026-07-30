export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Content-Type": "application/json; charset=utf-8",
    };

    if (url.pathname === "/health") {
      return new Response(
        JSON.stringify({ ok: true }),
        { headers: corsHeaders }
      );
    }

    if (url.pathname !== "/search") {
      return new Response(
        JSON.stringify({ error: "Nutze /search?q=Suchbegriff" }),
        { status: 404, headers: corsHeaders }
      );
    }

    const query = (url.searchParams.get("q") || "").trim().toLowerCase();
    const limit = Math.min(
      Math.max(parseInt(url.searchParams.get("limit") || "10", 10), 1),
      20
    );

    if (query.length < 2) {
      return new Response(
        JSON.stringify({ error: "q muss mindestens zwei Zeichen haben" }),
        { status: 400, headers: corsHeaders }
      );
    }

    const response = await fetch(env.DATA_URL, {
      cf: { cacheTtl: 300, cacheEverything: true },
    });

    if (!response.ok) {
      return new Response(
        JSON.stringify({ error: "Datenquelle nicht erreichbar" }),
        { status: 502, headers: corsHeaders }
      );
    }

    const documents = await response.json();
    const terms = query.split(/\s+/).filter(Boolean);

    const results = documents
      .map((doc) => {
        const haystack = [
          doc.title,
          doc.listing_text,
          doc.ministerium,
          doc.anfragende,
          doc.full_text,
        ].filter(Boolean).join(" ").toLowerCase();

        const score = terms.reduce(
          (total, term) => total + (haystack.includes(term) ? 1 : 0),
          0
        );
        return { doc, score };
      })
      .filter((entry) => entry.score === terms.length)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(({ doc }) => ({
        drucksache: doc.drucksache,
        title: doc.title,
        ministerium: doc.ministerium || null,
        antwortdatum: doc.antwortdatum || null,
        anfragende: doc.anfragende || null,
        excerpt: makeExcerpt(doc.full_text || doc.listing_text || "", terms[0]),
        pdf_url: doc.pdf_url,
      }));

    return new Response(
      JSON.stringify({ query, count: results.length, results }),
      { headers: corsHeaders }
    );
  },
};

function makeExcerpt(text, term) {
  const compact = text.replace(/\s+/g, " ").trim();
  const position = compact.toLowerCase().indexOf(term.toLowerCase());
  const start = Math.max(position - 180, 0);
  return compact.slice(start, start + 700);
}
