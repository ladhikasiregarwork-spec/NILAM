"use client";

import { AppShell } from "@/components/layout/AppShell";
import { MobileApp } from "@/components/mobile/MobileApp";
import { DocumentDashboard } from "@/components/dashboard/DocumentDashboard";
import { useNilamFlow } from "@/hooks/useNilamFlow";

export default function Page() {
  const {
    persona,
    isJoint,
    currentStep,
    canGoBack,
    uploads,
    events,
    setJointAnswer,
    start,
    next,
    goBack,
    setUpload,
    submit,
    reset,
  } = useNilamFlow();

  return (
    <AppShell
      mobile={
        <MobileApp
          persona={persona}
          isJoint={isJoint}
          currentStep={currentStep}
          canGoBack={canGoBack}
          uploads={uploads}
          start={start}
          next={next}
          goBack={goBack}
          setUpload={setUpload}
          setJointAnswer={setJointAnswer}
          submit={submit}
          reset={reset}
        />
      }
      dashboard={<DocumentDashboard events={events} uploads={uploads} />}
    />
  );
}
