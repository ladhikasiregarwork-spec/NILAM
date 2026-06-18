"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { useOrchestrationFeed } from "@/hooks/useOrchestrationFeed";
import { deriveDocumentStatuses } from "@/data/documents";
import type { OrchestrationEvent } from "@/types/orchestration";
import type { OcrResults, PreviewDoc } from "@/types/ocrExtract";
import type { EmploymentAgreement, SlikReport } from "@/types/profile";
import type { DocumentId } from "@/types/documents";
import type { AgunanData } from "@/types/agunan";
import type { UserInput } from "@/types/userInput";
import type { ApplicationView } from "@/types/applicationView";
import { ltvFromKlas, type AgunanKlasifikasi } from "@/data/ltv";
import { computeCreditScore } from "@/engines/scoring/creditScore";
import { anuitas } from "@/lib/kpr";
import { incomePartsFromOcr, kemampuanBayar } from "@/lib/kemampuan";

import { UploadedDocsStrip } from "./UploadedDocsStrip";
import { UserInformationCard } from "./UserInformationCard";
import { EmploymentAgreementCard } from "./EmploymentAgreementCard";
import { SlikOjkCard } from "./SlikOjkCard";
import { MatchingCard } from "./MatchingCard";
import { InstallmentCard } from "./InstallmentCard";
import { PreviewDocsCard } from "./PreviewDocsCard";
import { AgunanTabCard } from "./AgunanTabCard";
import { SummaryDecisionCard } from "./SummaryDecisionCard";

const BIG_TABS = [
  { id: "summary", label: "Summary" },
  { id: "transaksi", label: "Detail Transaksi" },
  { id: "slik", label: "Detail SLIK" },
  { id: "agunan", label: "Detail Agunan" },
  { id: "preview", label: "Preview Dokumen" },
] as const;
type BigTab = (typeof BIG_TABS)[number]["id"];

import { EMPLOYMENT_AGREEMENT } from "@/data/profileFixtures";
import { SLIK_LOANS, SLIK_TOTAL_ANGSURAN } from "@/data/slikLoansFixtures";
import { NASABAH_INCOME } from "@/data/incomeFixtures";
import { usiaDariKtp } from "@/lib/usia";

interface DocumentDashboardProps {
  events: OrchestrationEvent[];
  uploads: Record<string, boolean>;
  /** Real OCR-extracted data for Slip Gaji & SK Perusahaan (when uploaded). */
  ocr: OcrResults;
  /** Number of files classified per document type (Slip Gaji & Mutasi shown). */
  docCounts: Partial<Record<DocumentId, number>>;
  /** Collateral/property data (manual or from a link). */
  agunan?: AgunanData;
  /** SLIK report (from the SLIK CSV) — falls back to mock when absent. */
  slik?: SlikReport;
  /** Borrower application data from the Data Diri form. */
  userInput?: UserInput;
  /** Uploaded documents for the preview section. */
  previewDocs?: PreviewDoc[];
  /** NPW (Nilai Pasar Wajar) from the appraisal model. */
  npw?: number;
  /** Land-value portion of the NPW (for the land-price comparison). */
  npwLand?: number;
  /** Collateral classification (shared) + setter. */
  agunanKlas: AgunanKlasifikasi;
  setAgunanKlas: (patch: Partial<AgunanKlasifikasi>) => void;
  /** Authoritative ApplicationView from nilam_backend; when present its
   *  score/capacity/plafond override the client-side preview (server decides). */
  view?: ApplicationView;
}

/**
 * DocumentDashboard — analyst dashboard, grid layout:
 *
 *   DATA ALREADY UPLOAD                                   (full width)
 *   USER INFORMATION (+ employment) | MATCHING (2 tab: rekap · transaksi)
 *   SLIK (2 tab) | AGUNAN (2 tab) | RINGKASAN & KEPUTUSAN (approve/reject)
 *   PREVIEW DOKUMEN                                       (full width)
 */
export function DocumentDashboard({ events, uploads, ocr, docCounts, agunan, slik, userInput, previewDocs, npw, npwLand, agunanKlas, setAgunanKlas, view }: DocumentDashboardProps) {
  const { statusOf } = useOrchestrationFeed(events);
  const [tab, setTab] = useState<BigTab>("summary");

  const ocrStatus = statusOf("ocr");
  const slikStatus = statusOf("slik");
  const thpStatus = statusOf("thp");

  // Live document statuses (uploads + processing feed).
  const docStatuses = deriveDocumentStatuses(statusOf, uploads);

  // SK Perusahaan: prefer real OCR-extracted fields, fall back to the mock.
  const sk = ocr.skPerusahaan;
  const skAgreement: EmploymentAgreement = sk
    ? {
        perusahaan: sk.perusahaan || EMPLOYMENT_AGREEMENT.perusahaan,
        jabatan: sk.jabatan || EMPLOYMENT_AGREEMENT.jabatan,
        statusKepegawaian: sk.statusKepegawaian || EMPLOYMENT_AGREEMENT.statusKepegawaian,
        masaKerja: sk.masaKerja || EMPLOYMENT_AGREEMENT.masaKerja,
        gajiPokok: EMPLOYMENT_AGREEMENT.gajiPokok,
        tanggalMulai: sk.tanggalMulai || EMPLOYMENT_AGREEMENT.tanggalMulai,
        tanggalBerakhir: sk.tanggalBerakhir || EMPLOYMENT_AGREEMENT.tanggalBerakhir,
      }
    : EMPLOYMENT_AGREEMENT;

  // Age (from KTP) + real monthly income feed the credit score.
  const age = usiaDariKtp(ocr.ktp?.tanggalLahir);
  const slipThp = ocr.slipGaji?.records?.find((r) => r.thp != null)?.thp;
  const monthlyIncome =
    slipThp ?? ocr.mutasi?.gajiNominal ?? NASABAH_INCOME.components.find((c) => c.key === "Gaji")?.avg ?? 0;
  // SLIK: real report (from CSV by NIK) when available, else mock.
  const slikLoans = slik?.loans ?? SLIK_LOANS;
  const slikTotalAngsuran = slik?.totalAngsuran ?? SLIK_TOTAL_ANGSURAN;
  // Income components (gaji/THR/bonus) for the payment-capacity calc.
  const income = incomePartsFromOcr(ocr);

  // Deal ratios.
  const hargaRumah = agunan?.harga;
  const uangMuka = userInput?.uangMuka;
  const tenorTahun = userInput?.jangkaWaktu ?? 15;
  const plafond =
    hargaRumah != null
      ? uangMuka != null
        ? Math.max(0, hargaRumah - uangMuka)
        : Math.round(hargaRumah * 0.8)
      : undefined;
  const kprAngsuran = plafond ? anuitas(plafond, 0.105, tenorTahun * 12) : 0;
  const punyaSimpananBri =
    !!ocr.mutasi || slikLoans.some((l) => /bri|rakyat indonesia/i.test(l.lembaga));
  const creditResult = computeCreditScore({
    pendidikan: userInput?.pendidikan,
    statusKawin: userInput?.statusKawin ?? ocr.ktp?.statusPerkawinan,
    usia: userInput?.usia ?? age,
    punyaSimpananBri,
    jangkaWaktu: tenorTahun,
    hargaRumah,
    uangMuka,
    jumlahTanggungan: userInput?.jumlahTanggungan,
    incomeMonthly: monthlyIncome,
    angsuranBulanan: kprAngsuran + slikTotalAngsuran,
    plafond,
  });

  // Server-authoritative score/grade/factors once the backend run completes;
  // otherwise the client-side preview above (server decides).
  const score = view?.creditScore?.score ?? creditResult.score;
  const grade = view?.creditScore?.grade ?? creditResult.grade;
  const factors = view?.creditScore?.factors ?? creditResult.factors;

  // Summary metrics: kemampuan bayar, plafond pembiayaan (di-cap agunan NPW×LTV),
  // dan total DP (DP awal + tambahan DP bila plafon agunan kurang). Prefer the
  // server's capacity/plafond when available.
  const kemampuan =
    view?.capacity?.kemampuanBayar ??
    kemampuanBayar(income.gajiBulanan, income.thrTahunan, income.bonusTahunan, slikTotalAngsuran);
  const plafonAgunan =
    view?.plafond?.plafonAgunan ??
    (hargaRumah != null ? Math.round((npw ?? hargaRumah) * ltvFromKlas(agunanKlas, hargaRumah)) : undefined);
  const dpAwal = uangMuka ?? 0;
  const kebutuhan = hargaRumah != null ? Math.max(0, hargaRumah - dpAwal) : undefined;
  const ltv = hargaRumah != null ? ltvFromKlas(agunanKlas, hargaRumah) : 0;
  // Plafond pembiayaan & total DP dihitung di dalam SummaryDecisionCard agar
  // ikut berubah saat kemampuan bayar (bonus) diedit di sana.

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto scroll-thin bg-[#F5F7FA] p-3">
      {/* DATA ALREADY UPLOAD — pinned above the big tabs */}
      <UploadedDocsStrip statuses={docStatuses} />

      {/* Two big tabs: Summary | Detail */}
      <div className="flex shrink-0 gap-1 rounded-pill border border-bri-line bg-white p-1 shadow-soft">
        {BIG_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "flex-1 rounded-pill px-3 py-1.5 text-[11px] font-semibold transition-colors",
              tab === t.id ? "bg-bri-navy text-white shadow-soft" : "text-bri-muted hover:text-bri-ink",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── SUMMARY ─────────────────────────────────────────────────────── */}
      {tab === "summary" && (
        <div className="flex flex-col gap-3">
          {/* USER INFORMATION (+ employment) | SUMMARY INCOME + KEMAMPUAN BAYAR */}
          <div className="grid grid-cols-[250px_minmax(0,1fr)] items-start gap-3">
            <div className="flex flex-col gap-3">
              <UserInformationCard
                status={ocrStatus}
                ktp={ocr.ktp}
                kk={ocr.kk}
                nama={userInput?.nama}
                missing={!uploads.ktp && !uploads.kk}
              />
              <EmploymentAgreementCard
                status={ocrStatus}
                agreement={skAgreement}
                title="Company Employment Certificate"
                missing={!uploads.sk_perusahaan}
                sourceLabel={sk ? "Hasil OCR" : undefined}
              />
            </div>
            <div className="min-w-0">
              {/* Income Nasabah — Summary Income + Perhitungan Kemampuan Bayar (bonus editable) di dalam satu kartu */}
              <MatchingCard
                status={ocrStatus}
                mutasi={ocr.mutasi}
                slip={ocr.slipGaji}
                missing={!uploads.slip_gaji || !uploads.mutasi}
                mode="rekap"
                matching={view?.matching ?? undefined}
                footer={
                  <InstallmentCard
                    status={thpStatus}
                    gajiBulanan={income.gajiBulanan}
                    thrTahunan={income.thrTahunan}
                    bonusTahunan={income.bonusTahunan}
                    slikAngsuran={slikTotalAngsuran}
                    agunan={agunan}
                    uangMuka={userInput?.uangMuka}
                    jangkaWaktu={userInput?.jangkaWaktu}
                  />
                }
              />
            </div>
          </div>

          {/* SLIK Ringkasan | INFORMASI + PERHITUNGAN AGUNAN | RINGKASAN & KEPUTUSAN */}
          <div className="grid grid-cols-3 items-start gap-3">
            <SlikOjkCard status={slikStatus} loans={slikLoans} totalAngsuran={slikTotalAngsuran} score={score} view="summary" />
            <AgunanTabCard
              status={thpStatus}
              agunan={agunan}
              uangMuka={userInput?.uangMuka}
              npw={npw}
              npwLand={npwLand}
              klas={agunanKlas}
              setKlas={setAgunanKlas}
              view="informasi"
            />
            <SummaryDecisionCard
              status={thpStatus}
              kemampuan={kemampuan}
              angsuranKpr={kprAngsuran}
              score={score}
              grade={grade}
              breakdown={{
                harga: hargaRumah,
                dpAwal,
                kebutuhan,
                npw,
                ltv,
                plafonAgunan,
                tenorBulan: tenorTahun * 12,
                gajiBulanan: income.gajiBulanan,
                thrTahunan: income.thrTahunan,
                bonusTahunan: income.bonusTahunan,
                slikAngsuran: slikTotalAngsuran,
                factors,
              }}
            />
          </div>
        </div>
      )}

      {/* ── DETAIL TRANSAKSI — Transaksi Pemasukan ─────────────────────── */}
      {tab === "transaksi" && (
        <MatchingCard
          status={ocrStatus}
          mutasi={ocr.mutasi}
          slip={ocr.slipGaji}
          missing={!uploads.slip_gaji || !uploads.mutasi}
          mode="transaksi"
          matching={view?.matching ?? undefined}
        />
      )}

      {/* ── DETAIL SLIK — Detail Fasilitas + Riwayat Tunggakan ──────────── */}
      {tab === "slik" && (
        <div className="flex flex-col gap-3">
          <SlikOjkCard status={slikStatus} loans={slikLoans} totalAngsuran={slikTotalAngsuran} score={score} view="detail" />
          <SlikOjkCard status={slikStatus} loans={slikLoans} totalAngsuran={slikTotalAngsuran} score={score} view="tunggakan" />
        </div>
      )}

      {/* ── DETAIL AGUNAN — Gambar Agunan + Survey Harga Tanah Sekitar ──── */}
      {tab === "agunan" && (
        <AgunanTabCard
          status={thpStatus}
          agunan={agunan}
          uangMuka={userInput?.uangMuka}
          npw={npw}
          npwLand={npwLand}
          klas={agunanKlas}
          setKlas={setAgunanKlas}
          view="detail"
        />
      )}

      {/* ── PREVIEW DOKUMEN ────────────────────────────────────────────── */}
      {tab === "preview" && <PreviewDocsCard docs={previewDocs ?? []} />}
    </div>
  );
}
