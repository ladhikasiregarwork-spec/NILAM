import type { ReactNode } from "react";
import { ClipboardList } from "lucide-react";
import { AppHeader } from "./AppHeader";
import { AppFooter } from "./AppFooter";

interface AppShellProps {
  /** Phone-frame UI rendered in the left "Mobile App" canvas. */
  mobile: ReactNode;
  /** Behind-the-scene dashboard rendered in the right canvas. */
  dashboard: ReactNode;
}

/** Fixed canvas dimensions — the single design frame.
 *  Both canvases share CANVAS_H so they align side-by-side; the dashboard is
 *  designed so ALL content fits inside this frame with no internal scroll. */
const CANVAS_H = "h-[900px]";
const MOBILE_W = "w-[360px]";
const DASH_W = "w-[960px]";

/**
 * SOFIA-model showcase layout.
 *
 * The page (this <main>) is the only thing that scrolls. Inside it:
 *   1. Centered title block (NILAM wordmark) — OUTSIDE both canvases
 *   2. A wrap-aware, centered row holding two FIXED-size canvases:
 *        - left  : Mobile App canvas  (no title — phone speaks for itself)
 *        - right : Behind The Scene canvas (title lives INSIDE its header)
 *   3. Centered System Status footer — below the canvases
 *
 * Because both canvases are fixed px, browser zoom scales them uniformly and
 * proportions/spacing stay identical at any resolution. On wide screens the
 * row is centered with margins; on narrow screens `flex-wrap` drops the right
 * canvas below the phone and the PAGE scrolls (canvases never scroll inside).
 */
export function AppShell({ mobile, dashboard }: AppShellProps) {
  return (
    <main className="flex min-h-screen flex-col items-center bg-[#F5F7FA] px-4 py-8">
      {/* ── 1. Centered title block (outside canvases) ────────────────── */}
      <AppHeader />

      {/* ── 2. Two fixed-size canvases, centered & wrap-aware ─────────── */}
      <div className="mt-7 flex w-full max-w-[1340px] flex-wrap items-start justify-center gap-5">
        {/* Left — Mobile App canvas (no external title) */}
        <div
          className={`flex ${MOBILE_W} ${CANVAS_H} shrink-0 flex-col overflow-hidden rounded-card bg-white ring-1 ring-bri-line shadow-soft`}
        >
          {mobile}
        </div>

        {/* Right — Behind The Scene canvas (title inside header) */}
        <div
          className={`flex ${DASH_W} ${CANVAS_H} shrink-0 flex-col overflow-hidden rounded-card bg-white ring-1 ring-bri-line shadow-soft`}
        >
          {/* Canvas header — title INSIDE the canvas (SOFIA panel style);
              Demo Mode pill pinned to the top-right corner of the canvas. */}
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-bri-line px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-bri-bg text-bri-blue">
                <ClipboardList size={16} strokeWidth={2.25} aria-hidden="true" />
              </span>
              <h2 className="text-sm font-bold text-bri-navy">Behind The Scene Logic</h2>
              <span className="text-[11px] text-bri-muted">(NILAM Engine)</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-pill border border-bri-line bg-bri-bg px-3 py-1 text-xs font-medium text-bri-ink">
              <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
              Demo Mode
            </div>
          </div>

          {/* Canvas body — dashboard fills the rest, no internal scroll */}
          <div className="min-h-0 flex-1 overflow-hidden">{dashboard}</div>
        </div>
      </div>

      {/* ── 3. System Status footer (below canvases, centered) ─────────── */}
      <div className="mt-6 w-full max-w-[1340px]">
        <AppFooter />
      </div>
    </main>
  );
}
