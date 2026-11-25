/* Which city is the device in? Pure functions, no network: the position is only compared with the catalog on this device.
   A position is "covered" by a region when it is inside the region's bounding box grown by buffer_km (the area the data
   pipeline collects around the city). If several regions cover it, the smallest distance-to-centre over buffer_km wins. Mirrors atlas.regions.closest
   in Python; tests/js/regions.test.js runs the same golden cases (tests/js/regions_golden.json). */
(function (g) {
  'use strict';
  const KM_PER_DEG = 111.195;   // same constants as atlas.regions.closest
  function distanceKm(a, b) {
    const r = Math.PI / 180, dLa = (b[0] - a[0]) * r, dLo = (b[1] - a[1]) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLo / 2) ** 2;
    return 2 * 6371.0088 * Math.asin(Math.sqrt(h));
  }
  /** bbox = [south, west, north, east] grown by buffer_km on every side. */
  function covers(region, lat, lon) {
    const [s, w, n, e] = region.bbox, dLat = (region.buffer_km || 0) / KM_PER_DEG;
    const dLon = (region.buffer_km || 0) / (KM_PER_DEG * Math.cos((((s + n) / 2) * Math.PI) / 180));
    return lat >= s - dLat && lat <= n + dLat && lon >= w - dLon && lon <= e + dLon;
  }
  // Among the regions that cover the point the one with the smallest (km to its centre / buffer_km) wins: plain
  // nearest-centre would send Hamilton, Ohio to Oxford although it is well inside Cincinnati's area.
  function closest(catalog, lat, lon) {
    let best = null, bs = Infinity;
    for (const r of catalog) {
      if (!covers(r, lat, lon)) continue;
      const score = distanceKm([lat, lon], r.center) / (r.buffer_km || 1);
      if (score < bs) { bs = score; best = r; }
    }
    return best;
  }
  const R = { distanceKm, covers, closest };
  g.AtlasRegion = R;
  if (typeof module !== 'undefined') module.exports = R;
})(typeof globalThis !== 'undefined' ? globalThis : this);
