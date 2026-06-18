"use client";

import { useEffect, useState } from "react";
import { Link2, PencilLine, Loader2, ShieldCheck, Sparkles, AlertTriangle, MapPin, Home, Trash2 } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import type { AgunanData } from "@/types/agunan";

interface AgunanScreenProps {
  agunan?: AgunanData;
  onFetchLink: (url: string) => Promise<{ ok: boolean; error?: string }>;
  onSetAgunan: (data: AgunanData) => void;
  onClear: () => void;
  onSubmit: () => void;
  validating: boolean;
  onGoBack?: () => void;
  canGoBack?: boolean;
}

type Mode = "link" | "manual";

/** Text input row bound to an AgunanData string field. */
function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-[8px] font-medium text-bri-muted">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-bri-line bg-white px-2 py-1 text-[10px] text-bri-ink outline-none focus:border-bri-blue"
      />
    </label>
  );
}

/** Read-only key/value row for the fetched-from-link summary. */
function SummaryRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="shrink-0 text-[8.5px] text-bri-muted">{label}</span>
      <span className="text-right text-[8.5px] font-medium text-bri-ink">{value || "—"}</span>
    </div>
  );
}

/**
 * AgunanScreen — input data agunan (jaminan KPR) dengan 2 cara:
 *   - Link  : tempel URL listing (Rumah123) → sistem ambil 8 field otomatis.
 *   - Manual: isi 8 field sendiri.
 * Plus input NPWP. "Ajukan KPR" → lanjut ke processing.
 */
export function AgunanScreen({
  agunan,
  onFetchLink,
  onSetAgunan,
  onClear,
  onSubmit,
  validating,
  onGoBack,
  canGoBack,
}: AgunanScreenProps) {
  // Re-entry to swap the collateral ("Ganti Agunan") arrives with data already
  // filled. Open straight in the editable Manual tab (fields visible & editable)
  // and skip the prescreening check the second time round.
  const hasAgunan = agunan?.harga != null || !!agunan?.kelurahan;
  const [mode, setMode] = useState<Mode>(hasAgunan ? "manual" : "link");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  // Brief prescreening check before the FIRST agunan input only.
  const [prescreen, setPrescreen] = useState(!hasAgunan);
  useEffect(() => {
    if (!prescreen) return;
    const t = setTimeout(() => setPrescreen(false), 1800);
    return () => clearTimeout(t);
  }, [prescreen]);

  const numField = (patch: Partial<AgunanData>) => onSetAgunan(patch as AgunanData);
  const canSubmit = !!agunan?.harga;

  async function handleFetch() {
    if (!url.trim() || loading) return;
    setError(undefined);
    setLoading(true);
    const res = await onFetchLink(url.trim());
    setLoading(false);
    if (!res.ok) setError(res.error || "Gagal mengambil data");
  }

  function handleClear() {
    onClear();
    setUrl("");
    setError(undefined);
  }

  if (prescreen) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6">
        <div className="relative flex h-14 w-14 items-center justify-center">
          <Loader2 size={56} className="absolute animate-spin text-bri-blue/40" strokeWidth={1.5} />
          <ShieldCheck size={24} className="text-bri-blue" strokeWidth={2} />
        </div>
        <div className="text-center">
          <p className="text-[12px] font-bold text-bri-ink">Pengecekan Prescreening…</p>
          <p className="mt-1 text-[9px] leading-relaxed text-bri-muted">
            Memverifikasi kelayakan awal sebelum input data agunan.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto scroll-thin px-3 py-2">
      {/* Title */}
      <div className="mb-2">
        <h2 className="text-[13px] font-bold text-bri-ink">Data Agunan (KPR)</h2>
        <p className="text-[9px] text-bri-muted">Isi data properti jaminan — dari link atau manual</p>
      </div>

      {/* Mode toggle */}
      <div className="mb-2 flex gap-1 rounded-pill bg-bri-bg p-0.5">
        {(["link", "manual"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1 rounded-pill py-1 text-[9px] font-semibold transition-colors",
              mode === m ? "bg-bri-navy text-white" : "text-bri-muted hover:text-bri-ink"
            )}
          >
            {m === "link" ? <Link2 size={10} /> : <PencilLine size={10} />}
            {m === "link" ? "Dari Link" : "Manual"}
          </button>
        ))}
      </div>

      {/* Link mode */}
      {mode === "link" && (
        <div className="flex flex-col gap-1.5">
          <Field label="URL Listing (Rumah123)" value={url} onChange={setUrl} placeholder="https://www.rumah123.com/properti/…" />
          <button
            type="button"
            onClick={handleFetch}
            disabled={!url.trim() || loading}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-lg py-2 text-[10px] font-semibold text-white transition-all",
              !url.trim() || loading ? "cursor-not-allowed bg-bri-muted/50" : "bg-bri-blue hover:opacity-90 active:scale-[0.98]"
            )}
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            {loading ? "Mengambil data…" : "Ambil Data dari Link"}
          </button>
          {error && (
            <p className="flex items-center gap-1 text-[8.5px] font-medium text-red-500">
              <AlertTriangle size={10} /> {error}
            </p>
          )}
        </div>
      )}

      {/* Manual mode */}
      {mode === "manual" && (
        <div className="grid grid-cols-2 gap-1.5">
          <Field label="Luas Bangunan (m²)" type="number" value={agunan?.luasBangunan?.toString() ?? ""} onChange={(v) => numField({ luasBangunan: v === "" ? undefined : Number(v) })} />
          <Field label="Luas Tanah (m²)" type="number" value={agunan?.luasTanah?.toString() ?? ""} onChange={(v) => numField({ luasTanah: v === "" ? undefined : Number(v) })} />
          <Field label="Provinsi" value={agunan?.provinsi ?? ""} onChange={(v) => onSetAgunan({ provinsi: v })} />
          <Field label="Kota/Kabupaten" value={agunan?.kota ?? ""} onChange={(v) => onSetAgunan({ kota: v })} />
          <Field label="Kecamatan" value={agunan?.kecamatan ?? ""} onChange={(v) => onSetAgunan({ kecamatan: v })} />
          <Field label="Kelurahan" value={agunan?.kelurahan ?? ""} onChange={(v) => onSetAgunan({ kelurahan: v })} />
          <Field label="Kodepos" value={agunan?.kodepos ?? ""} onChange={(v) => onSetAgunan({ kodepos: v })} />
          <Field label="Harga Rumah (Rp)" type="number" value={agunan?.harga?.toString() ?? ""} onChange={(v) => numField({ harga: v === "" ? undefined : Number(v) })} />
        </div>
      )}

      {/* Summary of agunan */}
      {agunan && (agunan.harga || agunan.kelurahan) && (
        <div className="mt-2 rounded-xl border border-bri-line bg-bri-bg/50 px-2.5 py-2">
          <div className="mb-1 flex items-center gap-1">
            <Home size={10} className="text-bri-navy" />
            <span className="text-[8px] font-semibold uppercase tracking-[0.1em] text-bri-muted">Data Agunan</span>
            <div className="ml-auto flex items-center gap-1.5">
              {agunan.sumber === "link" && (
                <span className="flex items-center gap-0.5 rounded-pill bg-bri-navy/10 px-1.5 py-px text-[7px] font-semibold text-bri-navy">
                  <Sparkles size={7} /> dari link
                </span>
              )}
              <button
                type="button"
                onClick={handleClear}
                className="flex items-center gap-0.5 text-[7.5px] font-semibold text-bri-muted transition-colors hover:text-red-500"
              >
                <Trash2 size={9} /> Hapus
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-0.5">
            <SummaryRow label="Harga Rumah" value={agunan.harga ? formatRupiah(agunan.harga) : undefined} />
            <SummaryRow label="Luas Bangunan / Tanah" value={agunan.luasBangunan || agunan.luasTanah ? `${agunan.luasBangunan ?? "—"} m² / ${agunan.luasTanah ?? "—"} m²` : undefined} />
            <div className="flex items-start gap-1 pt-0.5">
              <MapPin size={9} className="mt-0.5 shrink-0 text-bri-muted" />
              <span className="text-[8.5px] text-bri-ink">
                {[agunan.kelurahan, agunan.kecamatan, agunan.kota, agunan.provinsi, agunan.kodepos].filter(Boolean).join(", ") || "—"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {!canSubmit && (
        <p className="mt-1 text-center text-[8px] text-bri-muted">Lengkapi data agunan (minimal harga rumah) untuk lanjut.</p>
      )}

      {/* Submit */}
      <button
        type="button"
        onClick={canSubmit && !validating ? onSubmit : undefined}
        disabled={!canSubmit || validating}
        className={cn(
          "mt-2 flex w-full items-center justify-center gap-2 rounded-bubble py-2.5 text-[12px] font-semibold text-white transition-all",
          canSubmit && !validating ? "hover:opacity-90 active:scale-[0.98]" : "cursor-not-allowed opacity-60"
        )}
        style={{ background: canSubmit ? "linear-gradient(135deg, #00529C 0%, #1A6FC4 100%)" : "#94A3B8" }}
      >
        {validating ? (
          <>
            <Loader2 size={13} className="animate-spin" />
            Memproses…
          </>
        ) : (
          "Ajukan KPR"
        )}
      </button>

      {canGoBack && (
        <button
          type="button"
          onClick={onGoBack}
          className="mt-2 text-center text-[10px] text-bri-muted transition-colors hover:text-bri-blue"
        >
          ← Kembali
        </button>
      )}
    </div>
  );
}
