# Vendored Leaflet

The map libraries are copied here so no page loads a script from another host.

| File | Version | Licence | Source |
|---|---|---|---|
| `leaflet.js`, `leaflet.css` | Leaflet 1.9.4 | BSD 2-Clause (`LICENSE-leaflet.txt`) | https://unpkg.com/leaflet@1.9.4/dist/ |
| `leaflet.markercluster.js`, `MarkerCluster.css` | Leaflet.markercluster 1.5.3 | MIT (`LICENSE-markercluster.txt`) | https://unpkg.com/leaflet.markercluster@1.5.3/dist/ |

The files are unchanged. `atlas.leaflet.head()` puts them inline in the page head. Leaflet's stylesheet names three images
(`layers.png`, `marker-icon.png`, `marker-shadow.png`) that this app never uses (no layer control, no default markers), so they
are not copied. To update: replace the four files, change the versions here, run `tests/test_vendor_leaflet.py`.
