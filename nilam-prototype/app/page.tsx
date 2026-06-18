"use client";

import { AppShell } from "@/components/layout/AppShell";
import { MobileApp } from "@/components/mobile/MobileApp";
import { DocumentDashboard } from "@/components/dashboard/DocumentDashboard";
import { RmMobileApp } from "@/components/rm/RmMobileApp";
import { useNilamFlow } from "@/hooks/useNilamFlow";
import { incomePartsFromOcr, kemampuanBayar } from "@/lib/kemampuan";
import { ltvFromKlas } from "@/data/ltv";

export default function Page() {
  const {
    persona,
    isJoint,
    currentStep,
    canGoBack,
    uploads,
    events,
    ocr,
    docCounts,
    agunan,
    setJointAnswer,
    start,
    next,
    goBack,
    editAgunan,
    classifyAndUpload,
    clearUploads,
    fetchAgunanFromLink,
    setAgunan,
    clearAgunan,
    slik,
    npw,
    npwLand,
    agunanKlas,
    setAgunanKlas,
    userInput,
    setUserInput,
    previewDocs,
    surveyStatus,
    surveyValue,
    surveyNote,
    submitSurvey,
    submit,
    reset,
    view,
  } = useNilamFlow();

  // Client compute is the live preview; once the backend run completes, its
  // ApplicationView is authoritative (server decides).
  const _income = incomePartsFromOcr(ocr);
  const kemampuan =
    view?.capacity?.kemampuanBayar ??
    kemampuanBayar(
      _income.gajiBulanan,
      _income.thrTahunan,
      _income.bonusTahunan,
      slik?.totalAngsuran ?? 0,
    );
  // Once the RM approves the survey, the offer uses the RM's appraised value
  // instead of the model NPW.
  const effectiveNpw = surveyStatus === "approved" && surveyValue != null ? surveyValue : npw;
  // Collateral plafond cap = NPW × LTV (shared classification). Prefer the
  // server's plafond (it already reflects any RM survey NPW override).
  const plafonAgunan =
    view?.plafond?.plafonAgunan ??
    (agunan?.harga != null
      ? Math.round((effectiveNpw ?? agunan.harga) * ltvFromKlas(agunanKlas, agunan.harga))
      : undefined);

  return (
    <AppShell
      mobile={
        <MobileApp
          persona={persona}
          isJoint={isJoint}
          currentStep={currentStep}
          canGoBack={canGoBack}
          uploads={uploads}
          docCounts={docCounts}
          ocr={ocr}
          userInput={userInput}
          setUserInput={setUserInput}
          kemampuan={kemampuan}
          plafonAgunan={plafonAgunan}
          offering={view?.offering ?? undefined}
          agunan={agunan}
          surveyStatus={surveyStatus}
          surveyNote={surveyNote}
          surveyValue={surveyValue}
          start={start}
          editAgunan={editAgunan}
          next={next}
          goBack={goBack}
          classifyAndUpload={classifyAndUpload}
          clearUploads={clearUploads}
          fetchAgunanFromLink={fetchAgunanFromLink}
          setAgunan={setAgunan}
          clearAgunan={clearAgunan}
          setJointAnswer={setJointAnswer}
          submit={submit}
          reset={reset}
        />
      }
      dashboard={
        <DocumentDashboard
          events={events}
          uploads={uploads}
          ocr={ocr}
          docCounts={docCounts}
          agunan={agunan}
          slik={slik}
          userInput={userInput}
          previewDocs={previewDocs}
          npw={npw}
          npwLand={npwLand}
          agunanKlas={agunanKlas}
          setAgunanKlas={setAgunanKlas}
          view={view}
        />
      }
      rmMobile={
        <RmMobileApp
          live={{ nama: userInput?.nama, agunan, npw, npwLand, surveyStatus, surveyValue, surveyNote }}
          agunanKlas={agunanKlas}
          setAgunanKlas={setAgunanKlas}
          onSubmitSurvey={submitSurvey}
        />
      }
    />
  );
}
