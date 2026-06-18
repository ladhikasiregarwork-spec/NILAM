import type { KtpExtract, KkExtract } from "@/types/ocrExtract";

export const runtime = "nodejs";

const SERVICE_URL = process.env.CLASSIFIER_URL || "http://127.0.0.1:8020";

/**
 * POST /api/ocr/identitas  (multipart: file + type=ktp|kk)
 *
 * Forwards a KTP or KK image/PDF to the local classifier's /extract-ktp or
 * /extract-kk endpoint (Tesseract + regex) and returns the extracted fields.
 */
export async function POST(req: Request) {
  let inForm: FormData;
  try {
    inForm = await req.formData();
  } catch {
    return Response.json({ ok: false, error: "Form data tidak valid" }, { status: 400 });
  }

  const file = inForm.get("file");
  const type = inForm.get("type");
  if (!(file instanceof File)) {
    return Response.json({ ok: false, error: "Tidak ada file yang diunggah" }, { status: 400 });
  }
  if (type !== "ktp" && type !== "kk") {
    return Response.json({ ok: false, error: "type harus 'ktp' atau 'kk'" }, { status: 400 });
  }

  const out = new FormData();
  out.append("file", file, file.name);

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/extract-${type}`, { method: "POST", body: out });
  } catch {
    return Response.json(
      { ok: false, error: `Service OCR identitas tidak dapat dihubungi di ${SERVICE_URL}` },
      { status: 502 },
    );
  }

  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data?.ok) {
    return Response.json(
      { ok: false, error: `Service OCR identitas error (${resp.status})`, raw: data },
      { status: 502 },
    );
  }

  const fields = data.fields ?? {};
  const extract: KtpExtract | KkExtract = { ...fields, fileName: data.filename ?? file.name };
  return Response.json({ ok: true, type, extract });
}
