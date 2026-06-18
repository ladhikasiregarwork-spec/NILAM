import type { SlikReport } from "@/types/profile";

export const runtime = "nodejs";

const SERVICE_URL = process.env.CLASSIFIER_URL || "http://127.0.0.1:8020";

/**
 * GET /api/slik?nik=...
 *
 * Forwards to the local classifier's /slik endpoint, which reads the SLIK CSV
 * (data/sample_slik_arie.csv) and returns the parsed report for that NIK.
 */
export async function GET(req: Request) {
  const nik = new URL(req.url).searchParams.get("nik");
  if (!nik) {
    return Response.json({ ok: false, error: "nik wajib diisi" }, { status: 400 });
  }

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/slik?nik=${encodeURIComponent(nik)}`);
  } catch {
    return Response.json(
      { ok: false, error: `Service SLIK tidak dapat dihubungi di ${SERVICE_URL}` },
      { status: 502 },
    );
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data?.ok) {
    return Response.json({ ok: false, error: data?.error ?? `SLIK error (${resp.status})` }, { status: 502 });
  }
  const report: SlikReport = {
    nik: data.nik,
    namaDebitur: data.namaDebitur,
    loans: data.loans ?? [],
    totalAngsuran: data.totalAngsuran ?? 0,
    kolekTerburuk: data.kolekTerburuk ?? 1,
    totalFasilitas: data.totalFasilitas ?? (data.loans?.length ?? 0),
  };
  return Response.json({ ok: true, report });
}
