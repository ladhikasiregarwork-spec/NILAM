export const runtime = "nodejs";

const BACKEND_URL = process.env.NILAM_BACKEND_URL || "http://127.0.0.1:8600";

/**
 * GET /api/applications/{id}
 *
 * Returns the assembled ApplicationView the backend stored for this job (used
 * after a survey recompute to refresh the dashboard).
 */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  let resp: Response;
  try {
    resp = await fetch(`${BACKEND_URL}/api/applications/${encodeURIComponent(id)}`);
  } catch {
    return Response.json(
      { ok: false, error: `Backend NILAM tidak dapat dihubungi di ${BACKEND_URL}` },
      { status: 502 },
    );
  }
  const data = await resp.json().catch(() => null);
  return Response.json(data ?? { ok: false, error: "respons tidak valid" }, { status: resp.status });
}
