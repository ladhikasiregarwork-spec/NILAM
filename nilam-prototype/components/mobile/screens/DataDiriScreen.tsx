"use client";

import type { ReactNode } from "react";
import { UserCog, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import type { UserInput } from "@/types/userInput";
import { PENDIDIKAN_OPSI, STATUS_KAWIN_OPSI } from "@/types/userInput";

interface DataDiriScreenProps {
  userInput: UserInput;
  setUserInput: (patch: Partial<UserInput>) => void;
  /** True when KTP/KK OCR prefilled some fields. */
  prefilled?: boolean;
  onSubmit: () => void;
  onGoBack?: () => void;
  canGoBack?: boolean;
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-[8px] font-semibold uppercase tracking-[0.06em] text-bri-muted">
        {label}
        {hint && <span className="ml-1 font-normal normal-case text-bri-blue">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-bri-line bg-white px-2 py-1.5 text-[10px] text-bri-ink focus:border-bri-blue focus:outline-none";

/**
 * DataDiriScreen — borrower application form. NIK / nama / usia / status kawin /
 * jumlah tanggungan are prefilled from the KTP & KK OCR (editable); pendidikan,
 * jangka waktu and uang muka are entered here. Feeds the credit score.
 */
export function DataDiriScreen({ userInput, setUserInput, prefilled, onSubmit, onGoBack, canGoBack }: DataDiriScreenProps) {
  const u = userInput;
  const num = (v: string) => (v === "" ? undefined : Number(v.replace(/[^\d]/g, "")));

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto scroll-thin px-3 py-2">
      <div className="mb-1 flex items-center gap-1.5">
        <UserCog size={14} className="text-bri-blue" />
        <h2 className="text-[13px] font-bold text-bri-ink">Data Diri Pemohon</h2>
      </div>
      <p className="mb-2 flex items-center gap-1 text-[9px] text-bri-muted">
        {prefilled && <Sparkles size={9} className="text-bri-blue" />}
        Sebagian terisi otomatis dari KTP/KK — silakan periksa & lengkapi.
      </p>

      <div className="grid grid-cols-2 gap-2">
        <div className="col-span-2">
          <Field label="NIK" hint={u.nik ? "dari KTP" : undefined}>
            <input className={inputCls} value={u.nik ?? ""} onChange={(e) => setUserInput({ nik: e.target.value })} />
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Nama" hint={u.nama ? "dari KTP" : undefined}>
            <input className={inputCls} value={u.nama ?? ""} onChange={(e) => setUserInput({ nama: e.target.value })} />
          </Field>
        </div>

        <Field label="Usia (tahun)" hint={u.usia != null ? "dari KTP" : undefined}>
          <input className={inputCls} inputMode="numeric" value={u.usia ?? ""} onChange={(e) => setUserInput({ usia: num(e.target.value) })} />
        </Field>
        <Field label="Status Kawin" hint={u.statusKawin ? "dari KTP" : undefined}>
          <select className={inputCls} value={u.statusKawin ?? ""} onChange={(e) => setUserInput({ statusKawin: e.target.value || undefined })}>
            <option value="">— pilih —</option>
            {STATUS_KAWIN_OPSI.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>

        <Field label="Pendidikan">
          <select className={inputCls} value={u.pendidikan ?? ""} onChange={(e) => setUserInput({ pendidikan: e.target.value || undefined })}>
            <option value="">— pilih —</option>
            {PENDIDIKAN_OPSI.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Jumlah Tanggungan" hint={u.jumlahTanggungan != null ? "dari KK" : undefined}>
          <input className={inputCls} inputMode="numeric" value={u.jumlahTanggungan ?? ""} onChange={(e) => setUserInput({ jumlahTanggungan: num(e.target.value) })} />
        </Field>

        <Field label="Jangka Waktu (tahun)">
          <input className={inputCls} inputMode="numeric" placeholder="mis. 15" value={u.jangkaWaktu ?? ""} onChange={(e) => setUserInput({ jangkaWaktu: num(e.target.value) })} />
        </Field>
        <Field label="Uang Muka (Rp)">
          <input
            className={inputCls}
            inputMode="numeric"
            placeholder="mis. 100000000"
            value={u.uangMuka != null ? u.uangMuka.toLocaleString("id-ID") : ""}
            onChange={(e) => setUserInput({ uangMuka: num(e.target.value) })}
          />
        </Field>
      </div>

      <div className="flex-1" />

      <button
        type="button"
        onClick={onSubmit}
        className="mt-3 w-full rounded-bubble py-2.5 text-[12px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
        style={{ background: "linear-gradient(135deg, #00529C 0%, #1A6FC4 100%)" }}
      >
        Lanjut
      </button>
      {canGoBack && (
        <button type="button" onClick={onGoBack} className={cn("mt-2 text-center text-[10px] text-bri-muted transition-colors hover:text-bri-blue")}>
          ← Kembali
        </button>
      )}
    </div>
  );
}
