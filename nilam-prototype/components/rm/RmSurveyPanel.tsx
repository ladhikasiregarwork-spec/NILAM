"use client";

import { useEffect, useMemo, useState } from "react";
import {
  UserCheck,
  MapPin,
  Home,
  CheckCircle2,
  XCircle,
  ClipboardList,
  Radio,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import { RM_QUEUE_DEMO } from "@/data/rmQueueFixtures";
import type { AgunanData } from "@/types/agunan";
import type { SurveyStatus } from "@/types/flow";

interface RmSurveyPanelProps {
  /** Live application from the customer flow (in the queue once surveyStatus !== "none"). */
  live?: {
    nama?: string;
    agunan?: AgunanData;
    npw?: number;
    surveyStatus: SurveyStatus;
    surveyValue?: number;
    surveyNote?: string;
  };
  /** Submit the survey result for the LIVE application (releases / rejects the offer). */
  onSubmitSurvey: (decision: "approved" | "rejected", value?: number, note?: string) => void;
}

type Decision = "none" | "approved" | "rejected";

interface Row {
  id: string;
  nama: string;
  kota: string;
  harga: number;
  luasBangunan?: number;
  luasTanah?: number;
  npw: number;
  tanggalAjuan: string;
  isLive: boolean;
  decision: Decision;
  decidedValue?: number;
  decidedNote?: string;
}

function DecisionBadge({ decision }: { decision: Decision }) {
  if (decision === "approved")
    return (
      <span className="flex items-center gap-0.5 rounded-pill bg-emerald-100 px-1.5 py-px text-[7.5px] font-semibold text-emerald-700">
        <CheckCircle2 size={8} /> Disetujui
      </span>
    );
  if (decision === "rejected")
    return (
      <span className="flex items-center gap-0.5 rounded-pill bg-red-100 px-1.5 py-px text-[7.5px] font-semibold text-red-600">
        <XCircle size={8} /> Ditolak
      </span>
    );
  return (
    <span className="rounded-pill bg-amber-100 px-1.5 py-px text-[7.5px] font-semibold text-amber-700">
      Menunggu
    </span>
  );
}

/**
 * RmSurveyPanel — the Relationship Manager workspace. Lists applications whose
 * collateral is ≥ Rp500 juta (the live customer application + demo entries),
 * lets the RM open one, record the survey result (appraised value + note), then
 * Approve or Reject. Approving the LIVE application releases the offer to the
 * customer (using the RM's appraised value); rejecting shows them the rejection.
 */
export function RmSurveyPanel({ live, onSubmitSurvey }: RmSurveyPanelProps) {
  const liveActive = !!live && live.surveyStatus !== "none";

  // Cosmetic decisions for the demo (static) queue entries.
  const [demoDecisions, setDemoDecisions] = useState<Record<string, { decision: Decision; value?: number; note?: string }>>({});

  const rows: Row[] = useMemo(() => {
    const list: Row[] = [];
    if (liveActive && live) {
      const harga = live.agunan?.harga ?? 0;
      list.push({
        id: "live",
        nama: live.nama?.trim() || "Nasabah (pengajuan aktif)",
        kota: live.agunan?.kota || "—",
        harga,
        luasBangunan: live.agunan?.luasBangunan,
        luasTanah: live.agunan?.luasTanah,
        npw: live.npw ?? harga,
        tanggalAjuan: "Hari ini",
        isLive: true,
        decision:
          live.surveyStatus === "approved" ? "approved" : live.surveyStatus === "rejected" ? "rejected" : "none",
        decidedValue: live.surveyValue,
        decidedNote: live.surveyNote,
      });
    }
    for (const d of RM_QUEUE_DEMO) {
      const dec = demoDecisions[d.id];
      list.push({
        id: d.id,
        nama: d.nama,
        kota: d.kota,
        harga: d.hargaAgunan,
        luasBangunan: d.luasBangunan,
        luasTanah: d.luasTanah,
        npw: d.npw,
        tanggalAjuan: d.tanggalAjuan,
        isLive: false,
        decision: dec?.decision ?? "none",
        decidedValue: dec?.value,
        decidedNote: dec?.note,
      });
    }
    return list;
  }, [liveActive, live, demoDecisions]);

  const [selectedId, setSelectedId] = useState<string>(rows[0]?.id ?? "");
  // Auto-focus the live application as soon as it enters the queue.
  useEffect(() => {
    if (liveActive) setSelectedId("live");
  }, [liveActive]);
  // Keep the selection valid if the current row disappears.
  useEffect(() => {
    if (!rows.some((r) => r.id === selectedId) && rows.length) setSelectedId(rows[0].id);
  }, [rows, selectedId]);

  const selected = rows.find((r) => r.id === selectedId);

  // Survey form (reset when the selected row changes).
  const [formValue, setFormValue] = useState<number | "">("");
  const [formNote, setFormNote] = useState("");
  useEffect(() => {
    setFormValue(selected ? Math.round(selected.npw) : "");
    setFormNote("");
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  const pendingCount = rows.filter((r) => r.decision === "none").length;

  function decide(decision: "approved" | "rejected") {
    if (!selected) return;
    const value = formValue === "" ? Math.round(selected.npw) : Number(formValue);
    const note = formNote.trim() || undefined;
    if (selected.isLive) {
      onSubmitSurvey(decision, value, note);
    } else {
      setDemoDecisions((prev) => ({ ...prev, [selected.id]: { decision, value, note } }));
    }
  }

  return (
    <div className="overflow-hidden rounded-card bg-white ring-1 ring-bri-line shadow-soft">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-bri-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-bri-bg text-bri-blue">
            <UserCheck size={16} strokeWidth={2.25} />
          </span>
          <div>
            <h2 className="text-sm font-bold text-bri-navy">Relationship Manager</h2>
            <p className="text-[10px] text-bri-muted">Antrian Survey Agunan · plafon agunan ≥ Rp500 juta</p>
          </div>
        </div>
        <span className="flex items-center gap-1.5 rounded-pill border border-bri-line bg-bri-bg px-3 py-1 text-[11px] font-medium text-bri-ink">
          <span className={cn("h-2 w-2 rounded-full", pendingCount ? "bg-amber-500" : "bg-emerald-500")} />
          {pendingCount} menunggu survey
        </span>
      </div>

      <div className="grid grid-cols-[300px_1fr]">
        {/* ── Queue list ───────────────────────────────────────────────────── */}
        <div className="border-r border-bri-line bg-bri-bg/30 p-2">
          <p className="mb-1 px-1 text-[8px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
            Antrian ({rows.length})
          </p>
          <div className="flex flex-col gap-1">
            {rows.map((r) => {
              const active = r.id === selectedId;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setSelectedId(r.id)}
                  className={cn(
                    "flex flex-col gap-0.5 rounded-lg border px-2.5 py-2 text-left transition-all",
                    active ? "border-bri-blue bg-white shadow-soft" : "border-bri-line bg-white/60 hover:border-bri-blue/40",
                  )}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="flex items-center gap-1 truncate text-[10px] font-semibold text-bri-ink">
                      {r.isLive && <Radio size={9} className="shrink-0 text-bri-blue" />}
                      {r.nama}
                    </span>
                    <DecisionBadge decision={r.decision} />
                  </div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[8.5px] text-bri-muted">{r.kota}</span>
                    <span className="text-[9px] font-semibold tabular-nums text-bri-navy">{formatRupiah(r.harga)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Detail + survey form ─────────────────────────────────────────── */}
        <div className="p-4">
          {!selected ? (
            <div className="flex h-full items-center justify-center">
              <span className="text-[10px] italic text-bri-muted/50">Tidak ada pengajuan untuk disurvey.</span>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {/* Applicant + property */}
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-[13px] font-bold text-bri-ink">{selected.nama}</h3>
                    {selected.isLive && (
                      <span className="rounded-pill bg-bri-blue/10 px-1.5 py-px text-[7.5px] font-semibold text-bri-blue">
                        pengajuan aktif
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 flex items-center gap-1 text-[9px] text-bri-muted">
                    <MapPin size={9} /> {selected.kota} · diajukan {selected.tanggalAjuan}
                  </p>
                </div>
                <DecisionBadge decision={selected.decision} />
              </div>

              {/* Collateral facts */}
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                  <p className="flex items-center gap-1 text-[8px] text-bri-muted"><Home size={9} /> Harga Agunan</p>
                  <p className="text-[11px] font-bold text-bri-navy tabular-nums">{formatRupiah(selected.harga)}</p>
                </div>
                <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                  <p className="text-[8px] text-bri-muted">NPW (model)</p>
                  <p className="text-[11px] font-bold text-bri-ink tabular-nums">{formatRupiah(selected.npw)}</p>
                </div>
                <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                  <p className="text-[8px] text-bri-muted">Luas (LB / LT)</p>
                  <p className="text-[11px] font-bold text-bri-ink tabular-nums">
                    {selected.luasBangunan ?? "—"} / {selected.luasTanah ?? "—"} m²
                  </p>
                </div>
              </div>

              {selected.decision === "none" ? (
                /* Survey form */
                <div className="rounded-xl border border-bri-line bg-white px-3 py-2.5">
                  <p className="mb-2 flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.1em] text-bri-muted">
                    <ClipboardList size={11} /> Input Hasil Survey
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="flex flex-col gap-0.5">
                      <span className="text-[8px] font-medium text-bri-muted">Nilai Taksiran (hasil survey)</span>
                      <input
                        type="number"
                        value={formValue}
                        onChange={(e) => setFormValue(e.target.value === "" ? "" : Number(e.target.value))}
                        className="rounded-lg border border-bri-line bg-white px-2 py-1 text-[10px] tabular-nums text-bri-ink outline-none focus:border-bri-blue"
                      />
                    </label>
                    <label className="flex flex-col gap-0.5">
                      <span className="text-[8px] font-medium text-bri-muted">Catatan Surveyor</span>
                      <input
                        type="text"
                        value={formNote}
                        onChange={(e) => setFormNote(e.target.value)}
                        placeholder="kondisi bangunan, akses jalan…"
                        className="rounded-lg border border-bri-line bg-white px-2 py-1 text-[10px] text-bri-ink outline-none focus:border-bri-blue"
                      />
                    </label>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => decide("approved")}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 py-2 text-[10px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
                    >
                      <CheckCircle2 size={13} /> Survey Selesai · Setujui
                    </button>
                    <button
                      type="button"
                      onClick={() => decide("rejected")}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-red-300 bg-red-50 py-2 text-[10px] font-semibold text-red-600 transition-all hover:bg-red-100 active:scale-[0.98]"
                    >
                      <XCircle size={13} /> Tolak
                    </button>
                  </div>
                  {selected.isLive && (
                    <p className="mt-1.5 text-center text-[8px] text-bri-muted">
                      Keputusan ini langsung diteruskan ke aplikasi nasabah.
                    </p>
                  )}
                </div>
              ) : (
                /* Recorded result */
                <div
                  className={cn(
                    "rounded-xl border px-3 py-2.5",
                    selected.decision === "approved" ? "border-emerald-200 bg-emerald-50/60" : "border-red-200 bg-red-50/60",
                  )}
                >
                  <p className="text-[9px] font-semibold uppercase tracking-[0.1em] text-bri-muted">Hasil Survey</p>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="text-[10px] text-bri-ink">Nilai taksiran survey</span>
                    <span className="text-[12px] font-bold tabular-nums text-bri-navy">
                      {selected.decidedValue != null ? formatRupiah(selected.decidedValue) : "—"}
                    </span>
                  </div>
                  {selected.decidedNote && (
                    <p className="mt-1 text-[9px] leading-relaxed text-bri-muted">“{selected.decidedNote}”</p>
                  )}
                  <p
                    className={cn(
                      "mt-1.5 text-[9px] font-semibold",
                      selected.decision === "approved" ? "text-emerald-700" : "text-red-600",
                    )}
                  >
                    {selected.decision === "approved"
                      ? selected.isLive
                        ? "Disetujui — penawaran diteruskan ke nasabah."
                        : "Disetujui."
                      : selected.isLive
                        ? "Ditolak — nasabah menerima pemberitahuan penolakan."
                        : "Ditolak."}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
