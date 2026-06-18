import type { ClassifyLabel } from "@/types/ocrExtract";

export const runtime = "nodejs";

/** Base URL of the local rule-based classifier service. */
const SERVICE_URL = process.env.CLASSIFIER_URL || "http://127.0.0.1:8020";

const LABELS: ClassifyLabel[] = ["ktp", "kk", "slip", "mutasi", "sk", "unknown"];

/** POST with a few retries — smooths over the classifier's restart / Paddle
 *  cold-start window (a transient connection refusal) instead of failing hard. */
async function postWithRetry(url: string, body: FormData, attempts = 3): Promise<Response> {
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fetch(url, { method: "POST", body });
    } catch (e) {
      lastErr = e;
      if (i < attempts - 1) await new Promise((r) => setTimeout(r, 1500));
    }
  }
  throw lastErr;
}

/**
 * POST /api/ocr/classify
 *
 * Accepts one or more files (form field `file`, repeated), forwards them to the
 * local classifier `/classify-batch`, and returns a normalized list of
 * { fileName, type, confidence } — one per uploaded file, in order.
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

  const out = new FormData();
  for (const f of files) out.append("files", f, f.name);

  let resp: Response;
  try {
    resp = await postWithRetry(`${SERVICE_URL}/classify-batch`, out);
  } catch {
    return Response.json(
      { ok: false, error: `Service classifier tidak dapat dihubungi di ${SERVICE_URL} (sudah dicoba ulang). Pastikan service berjalan, lalu coba lagi.` },
      { status: 502 },
    );
  }

  const data = await resp.json().catch(() => null);
  if (!resp.ok || !data) {
    return Response.json(
      { ok: false, error: `Service classifier error (${resp.status})`, raw: data },
      { status: 502 },
    );
  }

  const results = (data.results ?? []).map((r: any) => {
    const type: ClassifyLabel = LABELS.includes(r?.document_type) ? r.document_type : "unknown";
    const base = { fileName: r?.filename ?? "dokumen.pdf", type, confidence: r?.confidence ?? "low" };
    // The classifier already OCR-extracted KTP fields in the same pass — pass
    // them through so the browser need not call /extract-ktp again.
    return r?.fields ? { ...base, extract: r.fields } : base;
  });

  return Response.json({ ok: true, results });
}
