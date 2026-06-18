export const runtime = "nodejs";

const BACKEND_URL = process.env.NILAM_BACKEND_URL || "http://127.0.0.1:8600";

/**
 * GET/POST /api/applications/{id}/survey
 *
 * RM field-appraisal gate for collateral ≥ SURVEY_THRESHOLD. POST forwards the
 * decision; on approval the backend overrides NPW with the appraised value and
 * recomputes the offer/decision before returning the survey state.
 */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const resp = await fetch(`${BACKEND_URL}/api/applications/${encodeURIComponent(id)}/survey`);
    const data = await resp.json().catch(() => null);
    return Response.json(data ?? { ok: false, error: "respons tidak valid" }, { status: resp.status });
  } catch {
    return Response.json(
      { ok: false, error: `Backend NILAM tidak dapat dihubungi di ${BACKEND_URL}` },
      { status: 502 },
    );
  }
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.text();
  try {
    const resp = await fetch(`${BACKEND_URL}/api/applications/${encodeURIComponent(id)}/survey`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    const data = await resp.json().catch(() => null);
    return Response.json(data ?? { ok: false, error: "respons tidak valid" }, { status: resp.status });
  } catch {
    return Response.json(
      { ok: false, error: `Backend NILAM tidak dapat dihubungi di ${BACKEND_URL}` },
      { status: 502 },
    );
  }
}
