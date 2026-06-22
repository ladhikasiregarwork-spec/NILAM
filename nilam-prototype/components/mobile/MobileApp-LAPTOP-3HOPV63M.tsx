"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { FlowStep, PersonaConfig } from "@/types/flow";

import { PhoneMockup } from "./PhoneMockup";
import { MobileHeader } from "./MobileHeader";
import { BottomNav } from "./BottomNav";
import { FlowStepper } from "./FlowStepper";

import { OpeningScreen } from "./screens/OpeningScreen";
import { RequirementScreen } from "./screens/RequirementScreen";
import { ProcessingScreen } from "./screens/ProcessingScreen";
import { AnalystDecisionScreen } from "./screens/AnalystDecisionScreen";

// ─── Slide variants ──────────────────────────────────────────────────────────

const slideVariants = {
  enter: { opacity: 0, x: 20 },
  center: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
};

const slideTransition = { duration: 0.22, ease: "easeInOut" };

// ─── Props ───────────────────────────────────────────────────────────────────

interface MobileAppProps {
  persona: PersonaConfig;
  isJoint: boolean;
  currentStep: FlowStep;
  canGoBack: boolean;
  uploads: Record<string, boolean>;
  start: () => void;
  next: () => void;
  goBack: () => void;
  setUpload: (key: string, value?: boolean) => void;
  setJointAnswer: (ans: "ya" | "tidak") => void;
  submit: () => void;
  reset: () => void;
}

/**
 * MobileApp — composes the iPhone mockup + animated screen switch + bottom nav
 * + the FlowStepper below the phone.
 *
 * Manages local `validating` state: on Submit → 1.4s delay → calls flow.submit().
 */
export function MobileApp({
  persona,
  isJoint,
  currentStep,
  canGoBack,
  uploads,
  start,
  next,
  goBack,
  setUpload,
  setJointAnswer,
  submit,
  reset,
}: MobileAppProps) {
  const [validating, setValidating] = useState(false);

  function handleSubmit() {
    if (validating) return;
    setValidating(true);
    setTimeout(() => {
      setValidating(false);
      submit();
    }, 1400);
  }

  // ─── Render the current screen ─────────────────────────────────────────────

  function renderScreen() {
    switch (currentStep) {
      case "opening":
        return (
          <OpeningScreen
            key="opening"
            personaSelected={true}
            onStart={start}
          />
        );
      case "requirement":
        return (
          <RequirementScreen
            key="requirement"
            uploads={uploads}
            onUpload={setUpload}
            onSubmit={handleSubmit}
            validating={validating}
            onGoBack={goBack}
            canGoBack={canGoBack}
          />
        );
      case "processing":
        return <ProcessingScreen key="processing" />;
      case "analyst_decision":
        return (
          <AnalystDecisionScreen key="analyst_decision" onRestart={reset} />
        );
      default:
        return (
          <OpeningScreen
            key="opening-fallback"
            personaSelected={true}
            onStart={start}
          />
        );
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {/* ── iPhone mockup — flex-1 so phone fills remaining column height ── */}
      <div className="flex min-h-0 flex-1 items-center justify-center px-4 py-3">
        <PhoneMockup>
          {/* In-screen header */}
          <MobileHeader />

          {/* Animated screen area */}
          <div className="relative min-h-0 flex-1 overflow-hidden">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={currentStep}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={slideTransition}
                className="flex h-full flex-col"
              >
                {renderScreen()}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Bottom nav bar */}
          <BottomNav />
        </PhoneMockup>
      </div>

      {/* ── Flow stepper — shrink-0 pinned below phone, no gap ────────── */}
      <div className="shrink-0 border-t border-bri-line bg-white px-2 pb-2 pt-1.5">
        <FlowStepper currentStep={currentStep} />
      </div>
    </div>
  );
}
