"use client";

import { useState } from "react";
import { ImageOff, MapPin, Images, ChevronLeft, ChevronRight, X } from "lucide-react";
import { AgunanInfoCard } from "./AgunanInfoCard";
import { AgunanCalcCard } from "./AgunanCalcCard";
import { LandPriceComparison } from "./LandPriceComparison";
import type { NodeStatus } from "@/types/orchestration";
import type { AgunanData } from "@/types/agunan";
import type { AgunanKlasifikasi } from "@/data/ltv";

interface AgunanTabCardProps {
  status: NodeStatus;
  agunan?: AgunanData;
  uangMuka?: number;
  npw?: number;
  npwLand?: number;
  klas: AgunanKlasifikasi;
  setKlas: (patch: Partial<AgunanKlasifikasi>) => void;
  /** informasi = info + perhitungan agunan; detail = gambar + survey harga tanah. */
  view?: "informasi" | "detail";
}

/** Collateral photo gallery from the listing link (all images); placeholder when absent. */
function GambarAgunan({ agunan }: { agunan?: AgunanData }) {
  const lokasi = agunan
    ? [agunan.kelurahan, agunan.kecamatan, agunan.kota, agunan.provinsi].filter(Boolean).join(", ")
    : "";
  const imgs = agunan?.imageUrls?.length ? agunan.imageUrls : agunan?.imageUrl ? [agunan.imageUrl] : [];
  const [open, setOpen] = useState<number | null>(null);
  const show = (i: number) => (imgs.length ? setOpen(((i % imgs.length) + imgs.length) % imgs.length) : null);

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
          <Images size={11} className="text-bri-navy" strokeWidth={2} /> Gambar Agunan
        </span>
        {imgs.length > 0 && (
          <span className="rounded-pill bg-bri-bg px-2 py-0.5 text-[7.5px] font-semibold text-bri-navy">{imgs.length} foto · dari link</span>
        )}
      </div>

      {imgs.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border border-dashed border-bri-line bg-bri-bg/40 px-3 py-3">
          <ImageOff size={18} className="text-bri-muted/60" />
          <span className="text-[8px] text-bri-muted/70">Foto properti belum tersedia (input manual).</span>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {/* Primary photo — klik untuk perbesar */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imgs[0]}
            alt="Foto agunan utama"
            referrerPolicy="no-referrer"
            onClick={() => show(0)}
            className="h-40 w-full cursor-zoom-in rounded-lg border border-bri-line object-cover transition hover:opacity-90"
          />
          {/* Thumbnails of the rest */}
          {imgs.length > 1 && (
            <div className="grid grid-cols-5 gap-1.5">
              {imgs.slice(1).map((u, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={i}
                  src={u}
                  alt={`Foto agunan ${i + 2}`}
                  referrerPolicy="no-referrer"
                  onClick={() => show(i + 1)}
                  className="h-14 w-full cursor-zoom-in rounded-md border border-bri-line object-cover transition hover:opacity-90"
                />
              ))}
            </div>
          )}
          <p className="text-[7px] text-bri-muted/70">Klik foto untuk memperbesar.</p>
        </div>
      )}

      {lokasi && (
        <p className="mt-1.5 flex items-start gap-1 border-t border-bri-line pt-1.5 text-[8px] text-bri-ink">
          <MapPin size={9} className="mt-0.5 shrink-0 text-bri-muted" /> {lokasi}
        </p>
      )}

      {/* Lightbox */}
      {open !== null && imgs[open] && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 p-6" onClick={() => setOpen(null)}>
          <button
            type="button"
            onClick={() => setOpen(null)}
            className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-white/15 text-white transition hover:bg-white/30"
            aria-label="Tutup"
          >
            <X size={18} />
          </button>
          {imgs.length > 1 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); show(open - 1); }}
              className="absolute left-4 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/15 text-white transition hover:bg-white/30"
              aria-label="Sebelumnya"
            >
              <ChevronLeft size={22} />
            </button>
          )}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imgs[open]}
            alt={`Foto agunan ${open + 1}`}
            referrerPolicy="no-referrer"
            onClick={(e) => e.stopPropagation()}
            className="max-h-[88vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
          />
          {imgs.length > 1 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); show(open + 1); }}
              className="absolute right-4 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/15 text-white transition hover:bg-white/30"
              aria-label="Berikutnya"
            >
              <ChevronRight size={22} />
            </button>
          )}
          <span className="absolute bottom-5 left-1/2 -translate-x-1/2 rounded-pill bg-black/50 px-3 py-1 text-[12px] font-medium text-white">
            {open + 1} / {imgs.length}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * AgunanTabCard — bagian agunan, dipecah per `view`:
 *   informasi → Informasi Agunan + Perhitungan Agunan (NPW × LTV)
 *   detail    → Gambar Agunan + Survey Harga Tanah Sekitar
 */
export function AgunanTabCard({ status, agunan, uangMuka, npw, npwLand, klas, setKlas, view = "informasi" }: AgunanTabCardProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {view === "informasi" ? (
        <AgunanInfoCard
          agunan={agunan}
          footer={<AgunanCalcCard status={status} agunan={agunan} uangMuka={uangMuka} npw={npw} klas={klas} setKlas={setKlas} />}
        />
      ) : (
        <>
          <GambarAgunan agunan={agunan} />
          <LandPriceComparison agunan={agunan} npwLand={npwLand} npw={npw} />
        </>
      )}
    </div>
  );
}
