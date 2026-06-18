import { mapSkPerusahaan } from "@/lib/ocrMappers";

export const runtime = "nodejs";

/** Base URL of the keterangan-kerja-ocr FastAPI service. */
const SERVICE_URL = process.env.SK_OCR_URL || "http://127.0.0.1:8011";

/**
 * POST /api/ocr/sk-perusahaan
 *
 * Accepts a single PDF (form field `file`), forwards it to the
 * keterangan-kerja-ocr FastAPI `/parse` endpoint, and returns a normalized
 * SkPerusahaanExtract.
 */
export async function POST(req: Request) {
  let inForm: FormData;
  try {
    inForm = await req.formData();
  } catch {
    return Response.json({ ok: false, error: "Form data tidak valid" }, { status: 400 });
  }

  const files = inForm.getAll("file").filter((f): f is File => f instanceof File);
  if (files.length === 0) {
    return Response.json({ ok: false, error: "Tidak ada file yang diunggah" }, { status: 400 });
  }
  const nonPdf = files.find((f) => !f.name.toLowerCase().endsWith(".pdf"));
  if (nonPdf) {
    return Response.json({ ok: false, error: "Hanya file PDF yang didukung" }, { status: 400 });
  }

  const out = new FormData();
  for (const f of files) out.append("files", f, f.name);
  const password = inForm.get("password");
  if (typeof password === "string" && password) out.append("password", password);

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/parse`, { method: "POST", body: out });
  } catch (e) {
    return Response.json(
      { ok: false, error: `Service SK Perusahaan OCR tidak dapat dihubungi di ${SERVICE_URL}` },
      { status: 502 },
    );
  }

  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data) {
    return Response.json(
      { ok: false, error: `Service SK Perusahaan OCR error (${resp.status})`, raw: data },
      { status: 502 },
    );
  }

  const extract = mapSkPerusahaan(data);
  if (extract.needsPassword) {
    return Response.json({ ok: false, error: "PDF terkunci password", raw: data }, { status: 422 });
  }
  if (extract.rejected) {
    return Response.json(
      { ok: false, error: "Dokumen tidak dikenali sebagai Surat Keterangan Kerja", raw: data },
      { status: 422 },
    );
  }
  return Response.json({ ok: true, extract, raw: data });
}
