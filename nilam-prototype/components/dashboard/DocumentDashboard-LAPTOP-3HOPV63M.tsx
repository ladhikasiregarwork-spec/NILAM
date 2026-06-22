"use client";

import { useOrchestrationFeed } from "@/hooks/useOrchestrationFeed";
import { deriveDocumentStatuses } from "@/data/documents";
import type { OrchestrationEvent } from "@/types/orchestration";

import { UploadedDocsStrip } from "./UploadedDocsStrip";
import { KtpInfoCard } from "./KtpInfoCard";
import { KkInfoCard } from "./KkInfoCard";
import { EmploymentAgreementCard } from "./EmploymentAgreementCard";
import { SalarySlipCard } from "./SalarySlipCard";
import { BankStatementTableCard } from "./BankStatementTableCard";
import { SlikOjkCard } from "./SlikOjkCard";
import { InstallmentCard } from "./InstallmentCard";

import { CUSTOMER_PROFILE, EMPLOYMENT_AGREEMENT } from "@/data/profileFixtures";
import { KK_INFO } from "@/data/kkFixtures";
import { SLIP_GAJI } from "@/data/ocrFixtures";
import { BANK_STATEMENT_ROWS } from "@/data/bankStatementFixtures";
import { SLIK_LOANS, SLIK_TOTAL_ANGSURAN } from "@/data/slikLoansFixtures";
import { SLIK_NASABAH } from "@/data/slikFixtures";
import { NASABAH_INCOME } from "@/data/incomeFixtures";

interface DocumentDashboardProps {
  events: OrchestrationEvent[];
  uploads: Record<string, boolean>;
}

/**
 * DocumentDashboard — the document-centric dashboard (Image 2). A vertical,
 * scrollable stack:
 *
 *   DATA ALREADY UPLOAD            (5-document status strip)
 *   KTP INFO | KK INFO | SK PERUSAHAAN
 *   SALARY SLIP
 *   BANK STATEMENT
 *   SLIK OJK (every loan)
 *   CALCULATE INSTALLMENT PAYMENTS
 *
 * Each section is gated on the live processing feed: document/identity info on
 * OCR success, SLIK on the bureau pull, installment on the THP step. The panel
 * scrolls internally within the fixed canvas.
 */
export function DocumentDashboard({ events, uploads }: DocumentDashboardProps) {
  const { statusOf } = useOrchestrationFeed(events);

  const ocrStatus = statusOf("ocr");
  const slikStatus = statusOf("slik");
  const thpStatus = statusOf("thp");

  // Live document statuses (uploads + processing feed).
  const docStatuses = deriveDocumentStatuses(statusOf, uploads);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto scroll-thin bg-[#F5F7FA] p-3">
      {/* DATA ALREADY UPLOAD */}
      <UploadedDocsStrip statuses={docStatuses} />

      {/* KTP · KK · SK Perusahaan */}
      <div className="grid grid-cols-3 gap-3">
        <KtpInfoCard
          status={ocrStatus}
          profile={CUSTOMER_PROFILE}
          alamat={KK_INFO.alamat}
          missing={!uploads.ktp}
        />
        <KkInfoCard status={ocrStatus} kk={KK_INFO} missing={!uploads.kk} />
        <EmploymentAgreementCard
          status={ocrStatus}
          agreement={EMPLOYMENT_AGREEMENT}
          title="SK Perusahaan"
          missing={!uploads.sk_perusahaan}
        />
      </div>

      {/* SALARY SLIP */}
      <SalarySlipCard
        status={ocrStatus}
        gajiPokok={SLIP_GAJI.Gaji}
        components={NASABAH_INCOME.components}
        missing={!uploads.slip_gaji}
      />

      {/* BANK STATEMENT — month-by-month credits table */}
      <BankStatementTableCard
        status={ocrStatus}
        rows={BANK_STATEMENT_ROWS}
        missing={!uploads.mutasi}
      />

      {/* SLIK OJK — every loan */}
      <SlikOjkCard
        status={slikStatus}
        loans={SLIK_LOANS}
        totalAngsuran={SLIK_TOTAL_ANGSURAN}
        score={SLIK_NASABAH.score}
      />

      {/* CALCULATE INSTALLMENT PAYMENTS */}
      <InstallmentCard
        status={thpStatus}
        income={NASABAH_INCOME}
        totalAngsuran={SLIK_TOTAL_ANGSURAN}
      />
    </div>
  );
}
