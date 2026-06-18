import type { SlipGajiExtract } from "@/types/ocrExtract";

export const runtime = "nodejs";

const SERVICE_URL = process.env.CLASSIFIER_URL || "http://127.0.0.1:8020";

/**
 * POST /api/ocr/slip  (multipart: one or many "file")
 *
 * Forwards salary-slip PDFs/images to the local /extract-slip endpoint and
 * returns one record per slip (per payment date):
 * { tanggalPembayaran, totalUpah, totalPotongan, thp, thr, bonus }.
 */
export async function POST(req: Request) {
  let inForm: FormData;
  try {
    inForm = await req.formData();
  } catch {
    return Response.json({ ok: false, error: "Form data tidak valid" }, { status: 400 });
  }
  const list = inForm.getAll("file").filter((f): f is File => f instanceof File);
  if (list.length === 0) {
    return Response.json({ ok: false, error: "Tidak ada file yang diunggah" }, { status: 400 });
  }

  const out = new FormData();
  for (const f of list) out.append("files", f, f.name);

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/extract-slip`, { method: "POST", body: out });
  } catch {
    return Response.json(
      { ok: false, error: `Service OCR slip tidak dapat dihubungi di ${SERVICE_URL}` },
      { status: 502 },
    );
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data?.ok) {
    return Response.json({ ok: false, error: `Service OCR slip error (${resp.status})`, raw: data }, { status: 502 });
  }
  const extract: SlipGajiExtract = { records: data.records ?? [] };
  return Response.json({ ok: true, extract });
}
