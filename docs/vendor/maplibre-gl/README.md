# MapLibre GL JS (vendored)

The map library behind Map view (`docs/mapView.js`, WEBSITE-76 / WEBSITE-102). A copy of the official
build is kept here, not loaded from a CDN, so the page's library requests go only to our own site (the
tiles themselves come from OpenFreeMap, see `OPERATIONS.md`) and the version can't change under us.

- **Version:** 6.17.0 (npm `maplibre-gl@6.17.0`), licence 3-Clause BSD (`LICENSE.txt`)
- **Source:** `https://cdn.jsdelivr.net/npm/maplibre-gl@6.17.0/dist/<file>`
- **Files** (renamed from `.mjs` to `.js` so any static host serves them with a JavaScript MIME type, which
  ES module scripts require; the contents are unchanged):

| Here | Original in the package | SHA-256 |
|---|---|---|
| `maplibre-gl.js` | `dist/maplibre-gl.mjs` | `e02cb08c572fd0950a75343cd558099c2a1dbbaf67f26b0c96f115431962d1ae` |
| `maplibre-gl-worker.js` | `dist/maplibre-gl-worker.mjs` | `73d7a024a4efe1a46e49db193e18cfe33271e3ecc652ec7542c281a4ef5f0f04` |
| `maplibre-gl.css` | `dist/maplibre-gl.css` | `a90798a1953017790e590f7e1bd35ff103a8a4263972cb47290b78adf86f8c20` |

- **Weight (gzipped):** about 295 KB + 147 KB (worker) + 10 KB CSS. Loaded only when a visitor opens Map view.
- **Loaded by** `mapView.js` with `import()` and `setWorkerUrl(...)` (the worker file sits next to the library).

## Updating
1. Pick the new version on npm, download the three files from the URL above, save them under the names in the table.
2. Update the version and the three hashes in this file (`shasum -a 256 <original download>`).
3. Open a region page with `?view=map` and check the map loads, pans with two fingers on a phone, and shows
   its attribution; then run `node --test tests/`.
