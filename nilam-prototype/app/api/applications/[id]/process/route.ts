export const runtime = "nodejs";

const BACKEND_URL = process.env.NILAM_BACKEND_URL || "http://127.0.0.1:8600";

/**
 * POST /api/applications/{id}/process
 *
 * Forwards the assembled ProcessRequest to the authoritative nilam_backend,
 * which drives the 8-node pipeline in-process and returns the emitted events +
 * the assembled ApplicationView. The browser then renders the server's view.
 */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.text(); // forward the JSON body verbatim

  let resp: Response;
  try {
    resp = await fetch(`${BACKEND_URL}/api/applications/${encodeURIComponent(id)}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
  } catch {
    return Response.json(
      { ok: false, error: `Backend NILAM tidak dapat dihubungi di ${BACKEND_URL}` },
      { status: 502 },
    );
  }

  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data?.ok) {
    return Response.json(
      { ok: false, error: `Backend NILAM error (${resp.status})`, raw: data },
      { status: 502 },
    );
  }
  // The backend already returns events; fetch the full list so the browser can
  // replay the timeline (process returns only the view + eventCount).
  let events = data.events;
  if (!events) {
    try {
      const ev = await fetch(`${BACKEND_URL}/api/applications/${encodeURIComponent(id)}/events`);
      const evJson = await ev.json().catch(() => null);
      if (ev.ok && evJson?.ok) events = evJson.events;
    } catch {
      /* events are best-effort; the view still renders */
    }
  }
  return Response.json({ ...data, events: events ?? [] });
}
