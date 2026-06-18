import type { ReactNode } from "react";
import { ClipboardList } from "lucide-react";
import { AppHeader } from "./AppHeader";
import { AppFooter } from "./AppFooter";

interface AppShellProps {
  /** Phone-frame UI rendered in the left "Mobile App" canvas (nasabah). */
  mobile: ReactNode;
  /** Relationship Manager phone-frame UI, same size, beside the nasabah phone. */
  rmMobile: ReactNode;
  /** Behind-the-scene analyst dashboard, full-width below the phones. */
  dashboard: ReactNode;
}

/** Fixed canvas dimensions — the single design frame. */
const CANVAS_H = "h-[900px]";
const MOBILE_W = "w-[360px]";
const PHONE_CANVAS = `flex ${MOBILE_W} ${CANVAS_H} shrink-0 flex-col overflow-hidden rounded-card bg-white ring-1 ring-bri-line shadow-soft`;
const MAX_W = "max-w-[1820px]";

/**
 * NILAM showcase layout:
 *   1. Centered title block
 *   2. Two identical phone canvases (Nasabah + Relationship Manager), side by side
 *   3. The analyst dashboard ("Behind The Scene") — full-width below the phones, large
 *   4. Centered System Status footer
 */
export function AppShell({ mobile, rmMobile, dashboard }: AppShellProps) {
  return (
    <main className="flex min-h-screen flex-col items-center bg-[#F5F7FA] px-4 py-8">
      {/* ── 1. Centered title block ────────────────────────────────────── */}
      <AppHeader />

      {/* ── 2. Two phone canvases (Nasabah + Relationship Manager) ─────── */}
      <div className={`mt-7 flex w-full ${MAX_W} flex-wrap items-start justify-center gap-5`}>
        <div className={PHONE_CANVAS}>{mobile}</div>
        <div className={PHONE_CANVAS}>{rmMobile}</div>
      </div>

      {/* ── 3. Analyst dashboard — full width, below the phones, enlarged ── */}
      <div className={`mt-5 flex h-[1180px] w-full ${MAX_W} flex-col overflow-hidden rounded-card bg-white ring-1 ring-bri-line shadow-soft`}>
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
        <div className="min-h-0 flex-1 overflow-hidden">{dashboard}</div>
      </div>

      {/* ── 4. System Status footer ────────────────────────────────────── */}
      <div className={`mt-6 w-full ${MAX_W}`}>
        <AppFooter />
      </div>
    </main>
  );
}
