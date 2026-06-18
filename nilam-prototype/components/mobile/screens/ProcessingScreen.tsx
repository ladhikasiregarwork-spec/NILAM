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

      <div className="max-w-[230px] text-center">
        <p className="text-[13px] font-semibold text-bri-ink">Pengajuan Anda sedang kami proses</p>
        <p className="mt-1 text-[10px] leading-relaxed text-bri-muted">
          Silakan menunggu, petugas kami akan menghubungi Anda dalam waktu dekat.
        </p>
      </div>
    </div>
  );
}
