import type { SkPerusahaanExtract } from "@/types/ocrExtract";

export const runtime = "nodejs";

const SERVICE_URL = process.env.CLASSIFIER_URL || "http://127.0.0.1:8020";

/**
 * POST /api/ocr/sk  (multipart: file)
 *
 * Forwards a Surat Keterangan Kerja PDF/image to the local /extract-sk endpoint
 * (reads the actual document text — no stale data) and returns
 * { perusahaan, namaPekerja, jabatan, nik, tanggalMulai, statusKepegawaian, nomorSurat }.
 */
export async function POST(req: Request) {
  let inForm: FormData;
  try {
    inForm = await req.formData();
  } catch {
    return Response.json({ ok: false, error: "Form data tidak valid" }, { status: 400 });
  }
  const file = inForm.get("file");
  if (!(file instanceof File)) {
    return Response.json({ ok: false, error: "Tidak ada file yang diunggah" }, { status: 400 });
  }

  const out = new FormData();
  out.append("file", file, file.name);

  let resp: Response;
  try {
    resp = await fetch(`${SERVICE_URL}/extract-sk`, { method: "POST", body: out });
  } catch {
    return Response.json(
      { ok: false, error: `Service OCR SK tidak dapat dihubungi di ${SERVICE_URL}` },
      { status: 502 },
    );
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data?.ok) {
    return Response.json({ ok: false, error: `Service OCR SK error (${resp.status})`, raw: data }, { status: 502 });
  }
  const extract: SkPerusahaanExtract = { ...data.fields, fileName: data.filename ?? file.name };
  return Response.json({ ok: true, extract });
}
