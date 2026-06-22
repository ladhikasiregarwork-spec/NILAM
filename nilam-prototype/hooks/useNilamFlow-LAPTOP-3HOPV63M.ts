"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { FlowStep, PersonaConfig } from "@/types/flow";
import type { OrchestrationEvent, NodeId } from "@/types/orchestration";
import type { CustomerIncome, ComponentKey, ComponentMode } from "@/types/income";
import type { EventListener } from "@/engines/orchestrator/events";
import { planFlow } from "@/engines/persona/personaEngine";
import { WorkflowOrchestrator } from "@/engines/orchestrator/workflowOrchestrator";
import { DEFAULT_PERSONA } from "@/data/personas";
import { SLIP_GAJI, MUTASI, IDENTITY_PASANGAN } from "@/data/ocrFixtures";
import { SLIK_NASABAH, SLIK_PASANGAN } from "@/data/slikFixtures";
import { FRAUD_RESULT } from "@/data/fraudFixtures";
import { NASABAH_INCOME, PASANGAN_INCOME } from "@/data/incomeFixtures";

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface NilamState {
  persona: PersonaConfig;
  steps: FlowStep[];
  stepIndex: number;
  jointAnswer: "ya" | "tidak" | null;
  uploads: Record<string, boolean>;
  events: OrchestrationEvent[];
  nasabah?: CustomerIncome;
  pasangan?: CustomerIncome;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export type NilamAction =
  | { type: "setNasabahPayroll"; value: boolean }
  | { type: "setPasanganPayroll"; value: boolean }
  | { type: "next" }
  | { type: "goTo"; step: FlowStep }
  | { type: "goBack" }
  | { type: "setJointAnswer"; answer: "ya" | "tidak" }
  | { type: "setUpload"; key: string; value?: boolean }
  | { type: "appendEvent"; event: OrchestrationEvent }
  | { type: "setIncome"; role: "nasabah" | "pasangan"; income: CustomerIncome }
  | { type: "setComponent"; role: "nasabah" | "pasangan"; key: ComponentKey; patch: { mode?: ComponentMode; weight?: number } }
  | { type: "reset" };

// ---------------------------------------------------------------------------
// Initial state factory
// ---------------------------------------------------------------------------

export function initialState(): NilamState {
  return {
    persona: DEFAULT_PERSONA,
    steps: planFlow(DEFAULT_PERSONA),
    stepIndex: 0,
    jointAnswer: null,
    uploads: {},
    events: [],
    nasabah: undefined,
    pasangan: undefined,
  };
}

// ---------------------------------------------------------------------------
// Helper: reset flow fields but keep persona patch applied
// ---------------------------------------------------------------------------

function resetWithPersona(persona: PersonaConfig): NilamState {
  return {
    persona,
    steps: planFlow(persona),
    stepIndex: 0,
    jointAnswer: null,
    uploads: {},
    events: [],
    nasabah: undefined,
    pasangan: undefined,
  };
}

// ---------------------------------------------------------------------------
// Pure reducer — exported so it can be unit-tested in isolation
// ---------------------------------------------------------------------------

export function nilamReducer(state: NilamState, action: NilamAction): NilamState {
  switch (action.type) {
    case "setNasabahPayroll": {
      const persona: PersonaConfig = { ...state.persona, nasabahPayroll: action.value };
      return resetWithPersona(persona);
    }

    case "setPasanganPayroll": {
      const persona: PersonaConfig = { ...state.persona, pasanganPayroll: action.value };
      return resetWithPersona(persona);
    }

    case "next":
      return {
        ...state,
        stepIndex: Math.min(state.stepIndex + 1, state.steps.length - 1),
      };

    case "goTo": {
      const idx = state.steps.indexOf(action.step);
      if (idx === -1) return state;
      return { ...state, stepIndex: idx };
    }

    case "goBack": {
      const leavingStep = state.steps[state.stepIndex];
      const nextIndex = Math.max(state.stepIndex - 1, 0);
      const isRollingBack = leavingStep === "processing" || leavingStep === "analyst_decision";
      return {
        ...state,
        stepIndex: nextIndex,
        // Rollback pipeline state when leaving processing or analyst_decision
        ...(isRollingBack
          ? { events: [], nasabah: undefined, pasangan: undefined }
          : {}),
      };
    }

    case "setJointAnswer":
      return { ...state, jointAnswer: action.answer };

    case "setUpload":
      return {
        ...state,
        uploads: { ...state.uploads, [action.key]: action.value ?? true },
      };

    case "appendEvent":
      return { ...state, events: [...state.events, action.event] };

    case "setIncome":
      return {
        ...state,
        [action.role === "nasabah" ? "nasabah" : "pasangan"]: action.income,
      };

    case "setComponent": {
      const field = action.role === "nasabah" ? "nasabah" : "pasangan";
      const customer = state[field];
      if (!customer) return state;
      return {
        ...state,
        [field]: {
          ...customer,
          components: customer.components.map((c) =>
            c.key === action.key ? { ...c, ...action.patch } : c
          ),
        },
      };
    }

    case "reset":
      return initialState();

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useNilamFlow() {
  const [state, dispatch] = useReducer(nilamReducer, undefined, initialState);

  // Holds the active orchestrator so we can cancel it on navigation or reset.
  const orchestratorRef = useRef<WorkflowOrchestrator | null>(null);

  // Cancel the current orchestrator and clear the ref so the `.then` guard
  // in submit() knows the run was abandoned.
  const cancelOrchestrator = useCallback(() => {
    orchestratorRef.current?.cancel();
    orchestratorRef.current = null;
  }, []);

  // Cancel on unmount to prevent dispatching to a stale component.
  useEffect(() => {
    return () => {
      cancelOrchestrator();
    };
  }, [cancelOrchestrator]);

  // Derived state
  const currentStep = state.steps[state.stepIndex];
  const isJoint = state.jointAnswer === "ya";
  const canGoBack =
    state.stepIndex > 0 &&
    currentStep !== "processing" &&
    currentStep !== "analyst_decision";

  // -------------------------------------------------------------------------
  // Public actions
  // -------------------------------------------------------------------------

  const setNasabahPayroll = useCallback(
    (v: boolean) => {
      cancelOrchestrator();
      dispatch({ type: "setNasabahPayroll", value: v });
    },
    [cancelOrchestrator]
  );

  const setPasanganPayroll = useCallback(
    (v: boolean) => {
      cancelOrchestrator();
      dispatch({ type: "setPasanganPayroll", value: v });
    },
    [cancelOrchestrator]
  );

  const start = useCallback(() => {
    dispatch({ type: "next" });
  }, []);

  const next = useCallback(() => {
    dispatch({ type: "next" });
  }, []);

  const goBack = useCallback(() => {
    cancelOrchestrator();
    dispatch({ type: "goBack" });
  }, [cancelOrchestrator]);

  const setJointAnswer = useCallback((ans: "ya" | "tidak") => {
    dispatch({ type: "setJointAnswer", answer: ans });
  }, []);

  const setUpload = useCallback((key: string, value = true) => {
    dispatch({ type: "setUpload", key, value });
  }, []);

  const setComponentMode = useCallback(
    (role: "nasabah" | "pasangan", key: ComponentKey, mode: ComponentMode) => {
      dispatch({ type: "setComponent", role, key, patch: { mode } });
    },
    []
  );

  const setComponentWeight = useCallback(
    (role: "nasabah" | "pasangan", key: ComponentKey, weight: number) => {
      dispatch({ type: "setComponent", role, key, patch: { weight } });
    },
    []
  );

  const reset = useCallback(() => {
    cancelOrchestrator();
    dispatch({ type: "reset" });
  }, [cancelOrchestrator]);

  // -------------------------------------------------------------------------
  // submit() — orchestration kick (called from Requirement step)
  // -------------------------------------------------------------------------

  const submit = useCallback(() => {
    // Cancel any in-flight orchestrator before starting a new run.
    cancelOrchestrator();

    // Derive joint at submit time from current state.jointAnswer
    const joint = state.jointAnswer === "ya";

    // Build outputs keyed by NodeId
    const outputs: Partial<Record<NodeId, unknown>> = {
      upload:   { files: ["slip_gaji_nasabah.pdf", "mutasi_12_bulan.pdf"] },
      ocr:      { slip: SLIP_GAJI, mutasi: MUTASI },
      validasi: { monthsVerified: 12, complete: true },
      fraud:    FRAUD_RESULT,
      identity: joint ? IDENTITY_PASANGAN : null,
      slik:     { nasabah: SLIK_NASABAH, pasangan: joint ? SLIK_PASANGAN : undefined },
      income:   {
        nasabah: NASABAH_INCOME,
        pasangan: joint ? PASANGAN_INCOME : undefined,
      },
      thp:      null,
    };

    // Navigate to the processing step.
    dispatch({ type: "goTo", step: "processing" });

    // Create a fresh orchestrator and wire events.
    const orch = new WorkflowOrchestrator();
    orchestratorRef.current = orch;

    const emit: EventListener = (e) => {
      dispatch({ type: "appendEvent", event: e });
      // When income node succeeds, set nasabah/pasangan from its output.
      if (e.status === "success" && e.nodeId === "income" && e.output) {
        const out = e.output as { nasabah: CustomerIncome; pasangan?: CustomerIncome };
        dispatch({ type: "setIncome", role: "nasabah", income: out.nasabah });
        if (out.pasangan) {
          dispatch({ type: "setIncome", role: "pasangan", income: out.pasangan });
        }
      }
    };

    // Run the pipeline. Only advance to `analyst_decision` if this specific
    // orchestrator instance is still the active one.
    orch.run(state.persona, outputs, emit).then(() => {
      if (orchestratorRef.current === orch) {
        dispatch({ type: "goTo", step: "analyst_decision" });
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.persona, state.jointAnswer, cancelOrchestrator]);

  return {
    persona: state.persona,
    jointAnswer: state.jointAnswer,
    isJoint,
    steps: state.steps,
    currentStep,
    stepIndex: state.stepIndex,
    canGoBack,
    uploads: state.uploads,
    events: state.events,
    nasabah: state.nasabah,
    pasangan: state.pasangan,
    setNasabahPayroll,
    setPasanganPayroll,
    setJointAnswer,
    start,
    next,
    goBack,
    setUpload,
    submit,
    setComponentMode,
    setComponentWeight,
    reset,
  };
}
