"use client";

import { useEffect, useState } from "react";
import {
  UserCheck,
  MapPin,
  Home,
  Calculator,
  CheckCircle2,
  XCircle,
  ClipboardList,
  Inbox,
  Images,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import {
  ltvFromKlas, TIER_LABEL, PROPERTI_LABEL, UKURAN_LABEL, LAMA_LABEL,
  type AgunanKlasifikasi, type AgunanKategori, type DeveloperTier, type PropertiTipe, type UkuranTipe, type RumahLamaJenis,
} from "@/data/ltv";
import { PhoneMockup } from "../mobile/PhoneMockup";
import { LandPriceComparison } from "../dashboard/LandPriceComparison";
import type { AgunanData } from "@/types/agunan";
import type { SurveyStatus } from "@/types/flow";

const pctLtv = (r: number) => `${(r * 100).toFixed(2).replace(/\.?0+$/, "").replace(".", ",")}%`;

interface RmMobileAppProps {
  live?: {
    nama?: string;
    agunan?: AgunanData;
    npw?: number;
    npwLand?: number;
    surveyStatus: SurveyStatus;
    surveyValue?: number;
    surveyNote?: string;
  };
  /** Collateral classification (shared) — the RM sets it during the survey. */
  agunanKlas: AgunanKlasifikasi;
  setAgunanKlas: (patch: Partial<AgunanKlasifikasi>) => void;
  onSubmitSurvey: (decision: "approved" | "rejected", value?: number, note?: string) => void;
}

/**
 * RmMobileApp — Relationship Manager dalam bentuk aplikasi mobile (di samping
 * aplikasi nasabah). Menampilkan SATU pengajuan aktif yang perlu survey (agunan
 * ≥ Rp500jt). RM mengisi nilai taksiran + catatan → Setujui / Tolak. Keputusan
 * langsung diteruskan ke aplikasi nasabah (lepas / tolak penawaran).
 */
export function RmMobileApp({ live, agunanKlas, setAgunanKlas, onSubmitSurvey }: RmMobileAppProps) {
  const active = !!live && live.surveyStatus !== "none";
  const harga = live?.agunan?.harga ?? 0;
  const npw = live?.npw ?? harga;
  const nama = live?.nama?.trim() || "Nasabah (pengajuan aktif)";
  const kota = live?.agunan?.kota || "—";
  const imgs = live?.agunan?.imageUrls?.length ? live.agunan.imageUrls : live?.agunan?.imageUrl ? [live.agunan.imageUrl] : [];
  const decided = live?.surveyStatus === "approved" ? "approved" : live?.surveyStatus === "rejected" ? "rejected" : "none";

  const [formValue, setFormValue] = useState<number | "">("");
  const [formNote, setFormNote] = useState("");
  // Prefill the appraised value with the model NPW each time a new application
  // enters the queue.
  useEffect(() => {
    if (active && decided === "none") {
      setFormValue(Math.round(npw));
      setFormNote("");
    }
  }, [active, decided, npw]);

  function decide(decision: "approved" | "rejected") {
    const value = formValue === "" ? Math.round(npw) : Number(formValue);
    const note = formNote.trim() || undefined;
    onSubmitSurvey(decision, value, note);
  }

  // Perhitungan agunan oleh RM: plafon = nilai taksiran survey × LTV (klasifikasi).
  const taksiran = formValue === "" ? Math.round(npw) : Number(formValue);
  const ltvRm = ltvFromKlas(agunanKlas, harga);
  const plafonAgunanRm = Math.round(taksiran * ltvRm);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 items-center justify-center px-4 py-3">
        <PhoneMockup>
      {/* RM header */}
      <div className="flex shrink-0 items-center gap-2 border-b border-bri-line bg-bri-navy px-3 py-2 text-white">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-white/15"><UserCheck size={12} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold leading-tight">Relationship Manager</p>
          <p className="text-[8px] text-white/70">Survey Agunan · NILAM</p>
        </div>
        {active && decided === "none" && (
          <span className="rounded-pill bg-amber-400/20 px-2 py-0.5 text-[8px] font-semibold text-amber-100">perlu survey</span>
        )}
      </div>

      {/* Body */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto scroll-thin px-3 py-2.5">
        {!active ? (
          /* Empty — no application waiting for survey */
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-bri-bg">
              <Inbox size={26} className="text-bri-muted/60" />
            </div>
            <p className="text-[11px] font-bold text-bri-ink">Belum ada pengajuan</p>
            <p className="text-[9px] leading-relaxed text-bri-muted">
              Pengajuan dengan agunan ≥ Rp500 juta akan muncul di sini untuk disurvey.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            <div className="mb-0.5">
              <h2 className="text-[12px] font-bold text-bri-ink">Antrian Survey Agunan</h2>
              <p className="text-[8px] text-bri-muted">Agunan ≥ Rp500 juta · perlu survey RM</p>
            </div>

            {/* Applicant */}
            <div>
              <h3 className="text-[13px] font-bold text-bri-ink">{nama}</h3>
              <p className="flex items-center gap-1 text-[8.5px] text-bri-muted"><MapPin size={9} /> {kota} · diajukan hari ini</p>
            </div>

            {/* Foto rumah yang disurvey */}
            {imgs.length > 0 && (
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 p-1.5">
                <p className="mb-1 flex items-center gap-1 text-[8px] font-semibold uppercase tracking-[0.06em] text-bri-muted">
                  <Images size={10} className="text-bri-navy" /> Foto Rumah Disurvey · {imgs.length} foto
                </p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={imgs[0]} alt="Foto rumah disurvey" referrerPolicy="no-referrer" className="h-28 w-full rounded-md border border-bri-line object-cover" />
                {imgs.length > 1 && (
                  <div className="mt-1 grid grid-cols-4 gap-1">
                    {imgs.slice(1, 5).map((u, i) => (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img key={i} src={u} alt={`Foto rumah ${i + 2}`} referrerPolicy="no-referrer" className="h-10 w-full rounded border border-bri-line object-cover" />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Collateral facts */}
            <div className="grid grid-cols-2 gap-1.5">
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2 py-1.5">
                <p className="flex items-center gap-1 text-[8px] text-bri-muted"><Home size={9} /> Harga Agunan</p>
                <p className="text-[11px] font-bold tabular-nums text-bri-navy">{formatRupiah(harga)}</p>
              </div>
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2 py-1.5">
                <p className="text-[8px] text-bri-muted">NPW (model)</p>
                <p className="text-[11px] font-bold tabular-nums text-bri-ink">{formatRupiah(npw)}</p>
              </div>
              <div className="col-span-2 rounded-lg border border-bri-line bg-bri-bg/40 px-2 py-1.5">
                <p className="text-[8px] text-bri-muted">Luas Bangunan / Tanah</p>
                <p className="text-[11px] font-bold tabular-nums text-bri-ink">{live?.agunan?.luasBangunan ?? "—"} m² / {live?.agunan?.luasTanah ?? "—"} m²</p>
              </div>
            </div>

            {/* #4 Survey harga tanah sekitar (pembanding vs NPW) */}
            <LandPriceComparison agunan={live?.agunan} npwLand={live?.npwLand} npw={live?.npw} compact />

            {decided === "none" ? (
              <div className="rounded-xl border border-bri-line bg-white px-2.5 py-2">
                <p className="mb-1.5 flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-bri-muted">
                  <ClipboardList size={10} /> Hasil Survey
                </p>
                <label className="mb-1.5 flex flex-col gap-0.5">
                  <span className="text-[8px] font-medium text-bri-muted">Nilai Taksiran (survey)</span>
                  <input
                    type="number"
                    value={formValue}
                    onChange={(e) => setFormValue(e.target.value === "" ? "" : Number(e.target.value))}
                    className="rounded-lg border border-bri-line bg-white px-2 py-1 text-[10px] tabular-nums text-bri-ink outline-none focus:border-bri-blue"
                  />
                </label>

                {/* #3 Perhitungan agunan oleh RM: klasifikasi LTV → plafon = taksiran × LTV */}
                <div className="mb-1.5 rounded-lg border border-bri-line bg-bri-bg/40 px-2 py-1.5">
                  <p className="mb-1 flex items-center gap-1 text-[8px] font-semibold uppercase tracking-[0.06em] text-bri-muted"><Calculator size={9} /> Perhitungan Agunan</p>
                  <div className="mb-1 grid grid-cols-2 gap-1">
                    {(["baru", "lama"] as AgunanKategori[]).map((k) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setAgunanKlas({ kategori: k })}
                        className={cn("rounded-md border px-1.5 py-1 text-[8.5px] font-semibold transition-all", agunanKlas.kategori === k ? "border-bri-blue bg-bri-blue/5 text-bri-blue" : "border-bri-line text-bri-muted")}
                      >
                        {k === "baru" ? "Rumah Baru" : "Rumah Lama"}
                      </button>
                    ))}
                  </div>
                  {agunanKlas.kategori === "baru" ? (
                    <div className="flex flex-col gap-1">
                      <label className="flex flex-col gap-0.5">
                        <span className="text-[7px] font-semibold uppercase tracking-[0.05em] text-bri-muted">Developer</span>
                        <select
                          value={agunanKlas.tier}
                          onChange={(e) => setAgunanKlas({ tier: e.target.value as DeveloperTier })}
                          className="w-full rounded-md border border-bri-line bg-white px-1.5 py-1 text-[8.5px] text-bri-ink focus:border-bri-blue focus:outline-none"
                        >
                          {(Object.keys(TIER_LABEL) as DeveloperTier[]).map((t) => <option key={t} value={t}>{TIER_LABEL[t]}</option>)}
                        </select>
                      </label>
                      <label className="flex flex-col gap-0.5">
                        <span className="text-[7px] font-semibold uppercase tracking-[0.05em] text-bri-muted">Properti</span>
                        <select
                          value={agunanKlas.prop}
                          onChange={(e) => setAgunanKlas({ prop: e.target.value as PropertiTipe })}
                          className="w-full rounded-md border border-bri-line bg-white px-1.5 py-1 text-[8.5px] text-bri-ink focus:border-bri-blue focus:outline-none"
                        >
                          {(Object.keys(PROPERTI_LABEL) as PropertiTipe[]).map((p) => <option key={p} value={p}>{PROPERTI_LABEL[p]}</option>)}
                        </select>
                      </label>
                      {agunanKlas.prop !== "ruko" && (
                        <label className="flex flex-col gap-0.5">
                          <span className="text-[7px] font-semibold uppercase tracking-[0.05em] text-bri-muted">Tipe</span>
                          <select
                            value={agunanKlas.ukuran}
                            onChange={(e) => setAgunanKlas({ ukuran: e.target.value as UkuranTipe })}
                            className="w-full rounded-md border border-bri-line bg-white px-1.5 py-1 text-[8.5px] text-bri-ink focus:border-bri-blue focus:outline-none"
                          >
                            {(Object.keys(UKURAN_LABEL) as UkuranTipe[]).map((u) => <option key={u} value={u}>{UKURAN_LABEL[u]}</option>)}
                          </select>
                        </label>
                      )}
                    </div>
                  ) : (
                    <label className="flex flex-col gap-0.5">
                      <span className="text-[7px] font-semibold uppercase tracking-[0.05em] text-bri-muted">Jenis</span>
                      <select
                        value={agunanKlas.jenisLama}
                        onChange={(e) => setAgunanKlas({ jenisLama: e.target.value as RumahLamaJenis })}
                        className="w-full rounded-md border border-bri-line bg-white px-1.5 py-1 text-[8.5px] text-bri-ink focus:border-bri-blue focus:outline-none"
                      >
                        {(Object.keys(LAMA_LABEL) as RumahLamaJenis[]).map((j) => <option key={j} value={j}>{LAMA_LABEL[j]}</option>)}
                      </select>
                    </label>
                  )}
                  <div className="mt-1.5 flex items-center justify-between border-t border-bri-line/60 pt-1">
                    <span className="text-[8px] text-bri-muted">LTV {pctLtv(ltvRm)} · Plafon Agunan</span>
                    <span className="text-[11px] font-bold tabular-nums text-bri-navy">{formatRupiah(plafonAgunanRm)}</span>
                  </div>
                  <p className="text-[7px] text-bri-muted/70">= Taksiran {formatRupiah(taksiran)} × LTV {pctLtv(ltvRm)}</p>
                </div>

                <label className="flex flex-col gap-0.5">
                  <span className="text-[8px] font-medium text-bri-muted">Catatan Surveyor</span>
                  <input
                    type="text"
                    value={formNote}
                    onChange={(e) => setFormNote(e.target.value)}
                    placeholder="kondisi bangunan, akses…"
                    className="rounded-lg border border-bri-line bg-white px-2 py-1 text-[10px] text-bri-ink outline-none focus:border-bri-blue"
                  />
                </label>
                <div className="mt-2.5 flex gap-2">
                  <button type="button" onClick={() => decide("approved")} className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-emerald-600 py-2 text-[10px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]">
                    <CheckCircle2 size={13} /> Setujui
                  </button>
                  <button type="button" onClick={() => decide("rejected")} className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-red-300 bg-red-50 py-2 text-[10px] font-semibold text-red-600 transition-all hover:bg-red-100 active:scale-[0.98]">
                    <XCircle size={13} /> Tolak
                  </button>
                </div>
                <p className="mt-1.5 text-center text-[8px] text-bri-muted">Keputusan diteruskan ke aplikasi nasabah.</p>
              </div>
            ) : (
              <div className={cn("rounded-xl border px-2.5 py-2", decided === "approved" ? "border-emerald-200 bg-emerald-50/60" : "border-red-200 bg-red-50/60")}>
                <p className="flex items-center gap-1 text-[10px] font-bold">
                  {decided === "approved" ? <CheckCircle2 size={13} className="text-emerald-600" /> : <XCircle size={13} className="text-red-500" />}
                  <span className={decided === "approved" ? "text-emerald-700" : "text-red-600"}>
                    {decided === "approved" ? "Survey Disetujui" : "Survey Ditolak"}
                  </span>
                </p>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="text-[9px] text-bri-muted">Nilai taksiran</span>
                  <span className="text-[11px] font-bold tabular-nums text-bri-navy">{live?.surveyValue != null ? formatRupiah(live.surveyValue) : "—"}</span>
                </div>
                {live?.surveyNote && <p className="mt-0.5 text-[8.5px] text-bri-muted">“{live.surveyNote}”</p>}
                <p className="mt-1 text-[8px] text-bri-muted">
                  {decided === "approved" ? "Penawaran diteruskan ke nasabah." : "Nasabah menerima pemberitahuan penolakan."}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
        </PhoneMockup>
      </div>
      {/* Bottom bar — same height as the nasabah stepper so phones match */}
      <div className="flex h-[60px] shrink-0 flex-col items-center justify-center border-t border-bri-line bg-white px-3">
        <span className="flex items-center gap-1.5 text-bri-muted">
          <UserCheck size={13} />
          <span className="text-[9px] font-medium">Survey Agunan · Relationship Manager</span>
        </span>
      </div>
    </div>
  );
}
