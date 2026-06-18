import type { MutasiExtract } from "@/types/ocrExtract";

export const runtime = "nodejs";

const SERVICE_URL = process.env.CLASSIFIER_URL || "http://127.0.0.1:8020";

/**
 * POST /api/ocr/mutasi  (multipart: file)
 *
 * Forwards a bank-statement PDF to the local classifier's /extract-mutasi
 * endpoint (pypdfium2 text / Tesseract + regex) and returns the parsed
 * transactions (tanggal, nominal, remark, klasifikasi, debit/kredit).
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

  // The classifier's /extract-mutasi accepts many files (e.g. 6 months) under
  // the "files" field and merges them.
  const out = new FormData();
  for (const f of files) out.append("files", f, f.name);

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/extract-mutasi`, { method: "POST", body: out });
  } catch {
    return Response.json(
      { ok: false, error: `Service OCR mutasi tidak dapat dihubungi di ${SERVICE_URL}` },
      { status: 502 },
    );
  }

  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data?.ok) {
    return Response.json(
      { ok: false, error: `Service OCR mutasi error (${resp.status})`, raw: data },
      { status: 502 },
    );
  }

  const extract: MutasiExtract = { ...data.fields, fileName: data.filename ?? files[0]?.name };
  return Response.json({ ok: true, extract });
}
