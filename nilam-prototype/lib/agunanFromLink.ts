/**
 * Parse a Rumah123 listing HTML into the property fields we care about.
 *
 * Rumah123 embeds the data in the page: a schema.org JSON-LD block (price, geo,
 * address) plus Next.js data (land_size / building_size). This is a pure
 * function over the HTML string so it can be unit-tested without the network.
 */

export interface ParsedListing {
  luasTanah?: number;
  luasBangunan?: number;
  harga?: number;
  lat?: number;
  lon?: number;
  /** schema.org addressRegion (province) — fallback when geocode fails. */
  provinsi?: string;
  /** Kecamatan parsed from addressLocality (first part). */
  kecamatan?: string;
  /** Kota/Kabupaten parsed from addressLocality (last part). */
  kota?: string;
  /** schema.org addressLocality, e.g. "Bojong Gede, Bogor". */
  lokalitas?: string;
  /** Primary listing photo URL (og:image / schema.org image). */
  imageUrl?: string;
  /** All listing photo URLs (gallery). */
  imageUrls?: string[];
}

/** Parse a captured numeric string ("72" / "72,5") into a number. */
function num(s?: string): number | undefined {
  if (s == null) return undefined;
  const n = parseFloat(String(s).replace(",", "."));
  return Number.isFinite(n) ? n : undefined;
}

/** First capture group across a list of patterns. */
function pick(html: string, patterns: RegExp[]): string | undefined {
  for (const re of patterns) {
    const m = html.match(re);
    if (m && m[1] != null) return m[1];
  }
  return undefined;
}

export function parseRumah123Html(html: string): ParsedListing {
  const harga = num(
    pick(html, [
      /"priceCurrency"\s*:\s*"IDR"\s*,\s*"price"\s*:\s*(\d{6,})/,
      /"price"\s*:\s*(\d{6,})/,
    ]),
  );

  const luasTanah = num(
    pick(html, [
      /"land_size"\s*:\s*"?(\d+(?:[.,]\d+)?)/,
      /landSize\\?"\s*:\s*\\?"(\d+(?:[.,]\d+)?)\s*m/,
      /landSize\\?"\s*:\s*\{\s*\\?"value\\?"\s*:\s*\\?"(\d+(?:[.,]\d+)?)/,
    ]),
  );

  const luasBangunan = num(
    pick(html, [
      /"building_size"\s*:\s*"?(\d+(?:[.,]\d+)?)/,
      /buildingSize\\?"\s*:\s*\\?"(\d+(?:[.,]\d+)?)\s*m/,
      /buildingSize\\?"\s*:\s*\{\s*\\?"value\\?"\s*:\s*\\?"(\d+(?:[.,]\d+)?)/,
    ]),
  );

  const lat = num(pick(html, [/"latitude"\s*:\s*(-?\d+\.\d+)/]));
  const lon = num(pick(html, [/"longitude"\s*:\s*(-?\d+\.\d+)/]));

  // Listing photo: prefer og:image, fall back to a schema.org image URL.
  const imageUrl = pick(html, [
    /<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i,
    /"image"\s*:\s*"(https:[^"]+?\.(?:jpe?g|png|webp)[^"]*)"/i,
    /"image"\s*:\s*\[\s*"(https:[^"]+?)"/i,
  ])?.replace(/\\\//g, "/");

  // Property gallery only (house exterior + interiors) — NOT page-wide images
  // (agent photos, ads, map, related listings). Take URLs from the listing's own
  // photo array; only fall back to a page-wide scan if no array is found.
  const unesc = html.replace(/\\\//g, "/");
  const EXCLUDE = /logo|icon|avatar|sprite|favicon|placeholder|maps?\.|google|gstatic|\.svg|agent|agen|profile|broker|banner|\/ads?\/|iklan|watermark|sponsor|related|similar|thumb-?s?mall/i;
  const findUrls = (s: string) => s.match(/https?:\/\/[^"'\s),\\]+?\.(?:jpe?g|png|webp)(?:\?[^"'\s),\\]*)?/gi) || [];
  // URLs inside a "<key>": [ ... ] JSON array (the property photo gallery).
  const arrayOf = (key: string): string[] => {
    const m = unesc.match(new RegExp(`"${key}"\\s*:\\s*\\[([\\s\\S]{0,5000}?)\\]`, "i"));
    return m ? findUrls(m[1]) : [];
  };
  let imageUrls = [
    ...arrayOf("photos"),
    ...arrayOf("images"),
    ...arrayOf("galleryImages"),
    ...arrayOf("propertyPhotos"),
    ...arrayOf("media"),
    ...arrayOf("image"),
  ];
  if (imageUrls.length === 0) imageUrls = findUrls(unesc); // fallback: page-wide

  const host = (() => {
    try {
      return imageUrl ? new URL(imageUrl).host : undefined;
    } catch {
      return undefined;
    }
  })();
  imageUrls = Array.from(new Set(imageUrls)).filter((u) => !EXCLUDE.test(u));
  if (host) {
    const sameHost = imageUrls.filter((u) => {
      try {
        return new URL(u).host === host;
      } catch {
        return false;
      }
    });
    if (sameHost.length) imageUrls = sameHost;
  }
  if (imageUrl) imageUrls = [imageUrl, ...imageUrls.filter((u) => u !== imageUrl)];
  imageUrls = imageUrls.slice(0, 16);

  // The PROPERTY's PostalAddress sits just before its offer/price block. Anchor
  // extraction there so we don't accidentally grab the agent/organization
  // address (e.g. the Rumah123 office in Jakarta) elsewhere on the page.
  const priceAnchor = html.search(/"priceCurrency"\s*:\s*"IDR"/);
  const addrWindow = priceAnchor >= 0 ? html.slice(Math.max(0, priceAnchor - 700), priceAnchor) : "";
  const provinsi = pick(addrWindow, [/"addressRegion"\s*:\s*"([^"]+)"/]);
  const lokalitas = pick(addrWindow, [/"addressLocality"\s*:\s*"([^"]+)"/]);

  // addressLocality is typically "Kecamatan, Kota/Kabupaten".
  let kecamatan: string | undefined;
  let kota: string | undefined;
  if (lokalitas) {
    const parts = lokalitas.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length >= 2) {
      kecamatan = parts[0];
      kota = parts[parts.length - 1];
    } else if (parts.length === 1) {
      kota = parts[0];
    }
  }

  return { harga, luasTanah, luasBangunan, lat, lon, provinsi, kecamatan, kota, lokalitas, imageUrl, imageUrls };
}
