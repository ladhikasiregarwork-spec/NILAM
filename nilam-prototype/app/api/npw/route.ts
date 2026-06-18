export const runtime = "nodejs";

const SERVICE_URL = process.env.NPW_URL || "http://127.0.0.1:8030";

/**
 * POST /api/npw  { luasTanah, luasBangunan?, kodepos?, kelurahan? }
 *
 * Forwards to the local house_fair_market_value service /predict and returns
 * the appraised NPW (Nilai Pasar Wajar) = land + building value.
 */
export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  if (!body?.luasTanah || Number(body.luasTanah) <= 0) {
    return Response.json({ ok: false, error: "luasTanah wajib (> 0)" }, { status: 400 });
  }
  const payload = {
    luas_tanah: Number(body.luasTanah),
    luas_bangunan: Number(body.luasBangunan ?? 0),
    kode_pos: body.kodepos ? String(body.kodepos) : undefined,
    kelurahan: body.kelurahan ? String(body.kelurahan) : undefined,
  };

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    return Response.json({ ok: false, error: `Service NPW tidak dapat dihubungi di ${SERVICE_URL}` }, { status: 502 });
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok || data == null) {
    return Response.json({ ok: false, error: `Service NPW error (${resp.status})`, raw: data }, { status: 502 });
  }
  return Response.json({
    ok: true,
    fairValue: data.fair_value,
    landValue: data.land_value,
    buildingValue: data.building_value,
    locationMatched: data.location_matched,
    warnings: data.warnings ?? [],
  });
}
