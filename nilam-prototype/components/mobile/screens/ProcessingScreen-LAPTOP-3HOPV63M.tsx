"use client";

/**
 * Processing screen — shown while the orchestration pipeline is running.
 * Centered animated ring + "Memproses…" label.
 */
export function ProcessingScreen() {
  return (
    <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-4">
      {/* Animated spinner ring — BRI navy + sky */}
      <div className="relative flex h-14 w-14 items-center justify-center">
        {/* Outer track */}
        <div className="absolute inset-0 rounded-full border-4 border-bri-bg" />
        {/* Spinning arc */}
        <div
          className="absolute inset-0 animate-spin rounded-full border-4 border-transparent"
          style={{
            borderTopColor: "#00529C",
            borderRightColor: "#4FB3E8",
          }}
        />
        {/* Inner dot */}
        <div className="h-3 w-3 rounded-full bg-bri-navy opacity-70" />
      </div>

      <div className="text-center">
        <p className="text-sm font-semibold text-bri-ink">Mengidentifikasi data…</p>
        <p className="mt-0.5 text-[9px] text-bri-muted">Membaca dokumen yang diunggah</p>
      </div>
    </div>
  );
}
