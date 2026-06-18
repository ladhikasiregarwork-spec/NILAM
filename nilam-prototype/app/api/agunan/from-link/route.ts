import { parseRumah123Html } from "@/lib/agunanFromLink";
import type { AgunanData } from "@/types/agunan";

export const runtime = "nodejs";

const BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";
const NOMINATIM_UA = "NILAM-KPR/1.0 (at.gondrol@gmail.com)";

/**
 * POST /api/agunan/from-link  { url }
 *
 * Fetches a Rumah123 listing, extracts luas tanah/bangunan + harga + geo from
 * the page, then reverse-geocodes the coordinates (OpenStreetMap/Nominatim) to
 * fill provinsi / kota / kecamatan / kelurahan / kodepos.
 */
export async function POST(req: Request) {
  let url: unknown;
  try {
    ({ url } = await req.json());
  } catch {
    return Response.json({ ok: false, error: "Body tidak valid" }, { status: 400 });
  }
  if (typeof url !== "string" || !url.trim()) {
    return Response.json({ ok: false, error: "URL kosong" }, { status: 400 });
  }

  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    return Response.json({ ok: false, error: "URL tidak valid" }, { status: 400 });
  }
  if (!host.toLowerCase().includes("rumah123.com")) {
    return Response.json({ ok: false, error: "Saat ini hanya mendukung link Rumah123" }, { status: 400 });
  }

  // 1) Fetch the listing HTML.
  let html: string;
  try {
    const resp = await fetch(url, { headers: { "User-Agent": BROWSER_UA } });
    if (!resp.ok) {
      return Response.json({ ok: false, error: `Gagal membuka halaman (${resp.status})` }, { status: 502 });
    }
    html = await resp.text();
  } catch {
    return Response.json({ ok: false, error: "Tidak dapat mengambil halaman listing" }, { status: 502 });
  }

  const parsed = parseRumah123Html(html);

  // 2) Reverse-geocode the coordinates for the admin levels + postcode.
  // Reverse-geocode the coordinates → kelurahan + kodepos. Try a fine zoom
  // first, then a coarser one if village/postcode are still missing.
  async function geocode(zoom: number): Promise<Partial<AgunanData>> {
    const nu = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${parsed.lat}&lon=${parsed.lon}&addressdetails=1&zoom=${zoom}&accept-language=id`;
    const gr = await fetch(nu, { headers: { "User-Agent": NOMINATIM_UA } });
    const gj: any = await gr.json();
    const a = gj?.address ?? {};
    return {
      provinsi: a.state,
      kota: a.county ?? a.city ?? a.municipality,
      kecamatan: a.town ?? a.city_district ?? a.municipality ?? a.suburb,
      kelurahan: a.village ?? a.suburb ?? a.neighbourhood ?? a.hamlet ?? a.quarter,
      kodepos: a.postcode,
    };
  }

  let geo: Partial<AgunanData> = {};
  if (parsed.lat != null && parsed.lon != null) {
    for (const zoom of [18, 16, 14]) {
      try {
        const g = await geocode(zoom);
        geo = { ...g, ...Object.fromEntries(Object.entries(geo).filter(([, v]) => v)) };
        if (geo.kelurahan && geo.kodepos) break;
      } catch {
        // Non-fatal: try next zoom / fall back to schema.org address.
      }
    }
  }

  const data: AgunanData = {
    luasBangunan: parsed.luasBangunan,
    luasTanah: parsed.luasTanah,
    harga: parsed.harga,
    // Provinsi/kota/kecamatan come from the listing (reliable); the reverse
    // geocode (approximate coords) only fills kelurahan + kodepos.
    provinsi: parsed.provinsi ?? geo.provinsi,
    kota: parsed.kota ?? geo.kota,
    kecamatan: parsed.kecamatan ?? geo.kecamatan,
    kelurahan: geo.kelurahan,
    kodepos: geo.kodepos,
    lat: parsed.lat,
    lon: parsed.lon,
    imageUrl: parsed.imageUrl,
    imageUrls: parsed.imageUrls,
    sumber: "link",
    url,
  };

  return Response.json({ ok: true, data });
}
