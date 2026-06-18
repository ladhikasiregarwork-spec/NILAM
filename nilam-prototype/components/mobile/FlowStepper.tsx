import { Check } from "lucide-react";
import { cn } from "@/lib/cn";
import type { FlowStep } from "@/types/flow";

interface FlowStepperProps {
  currentStep: FlowStep;
}

interface StepNode {
  number: number;
  label: string;
  sublabel?: string;
}

const NODES: StepNode[] = [
  { number: 1, label: "Masuk" },
  { number: 2, label: "S&K" },
  { number: 3, label: "Upload" },
  { number: 4, label: "Data", sublabel: "Diri" },
  { number: 5, label: "Agunan" },
  { number: 6, label: "Proses" },
  { number: 7, label: "Penawa-", sublabel: "ran" },
  { number: 8, label: "Cair" },
];

// Map currentStep → which node index (0-based) is "active".
function getActiveIndex(step: FlowStep): number {
  switch (step) {
    case "opening":         return 0;
    case "term_condition":  return 1;
    case "requirement":     return 2;
    case "data_diri":       return 3;
    case "agunan":          return 4;
    case "processing":      return 5;
    // Survey shares the "Proses" node — from the borrower's progress view the
    // RM survey is part of the review/processing stage.
    case "survey":          return 5;
    case "offering":        return 6;
    case "disburse":        return 7;
    default:                return 0;
  }
}

/**
 * Horizontal flow stepper rendered BELOW the iPhone — SOFIA/BRI theme.
 * 5 numbered circles connected by dotted lines, with tiny labels underneath.
 *
 * Node states:
 *   done   = filled bri-navy, white check icon
 *   active = filled bri-navy, white number (bold) + soft glow ring
 *   future = white bg, bri-line border, bri-muted number
 */
export function FlowStepper({ currentStep }: FlowStepperProps) {
  const activeIdx = getActiveIndex(currentStep);

  return (
    <div className="flex shrink-0 items-start justify-center gap-0">
      {NODES.map((node, i) => {
        const isDone   = i < activeIdx;
        const isActive = i === activeIdx;

        return (
          <div key={node.number} className="flex items-start">
            {/* Node + label */}
            <div className="flex flex-col items-center" style={{ minWidth: 40 }}>
              {/* Circle */}
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold transition-all",
                  isDone
                    ? "bg-bri-navy text-white"
                    : isActive
                    ? "bg-bri-navy text-white"
                    : "border-2 border-bri-line bg-white text-bri-muted"
                )}
                style={
                  isActive
                    ? { boxShadow: "0 0 0 3px rgba(0,82,156,0.18)" }
                    : undefined
                }
              >
                {isDone ? (
                  <Check size={12} strokeWidth={3} />
                ) : (
                  <span>{node.number}</span>
                )}
              </div>

              {/* Label */}
              <div className="mt-0.5 text-center">
                <span
                  className={cn(
                    "block text-[8px] leading-tight",
                    isActive
                      ? "font-semibold text-bri-navy"
                      : isDone
                      ? "font-medium text-bri-blue"
                      : "text-bri-muted"
                  )}
                  style={{ maxWidth: 40 }}
                >
                  {node.label}
                </span>
                {node.sublabel && (
                  <span
                    className={cn(
                      "block text-[8px] leading-tight",
                      isActive
                        ? "font-semibold text-bri-navy"
                        : isDone
                        ? "font-medium text-bri-blue"
                        : "text-bri-muted"
                    )}
                  >
                    {node.sublabel}
                  </span>
                )}
              </div>
            </div>

            {/* Dotted connector (not after last node) */}
            {i < NODES.length - 1 && (
              <div
                className="mt-[13px] flex-1"
                style={{
                  width: 16,
                  height: 2,
                  borderTop: `2px dotted ${i < activeIdx ? "#00529C" : "#E5E7EB"}`,
                  minWidth: 10,
                  maxWidth: 20,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
