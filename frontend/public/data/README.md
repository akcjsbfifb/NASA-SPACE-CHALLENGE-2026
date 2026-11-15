# Bundled map data

`ne_110m_admin_0_countries.geojson` — Natural Earth, 1:110m Cultural Vectors,
Admin 0 Countries. Public domain (naturalearthdata.com/about/terms-of-use).

- Source: https://github.com/nvkelso/natural-earth-vector/tree/master/geojson
- Fields used: `CONTINENT`, `NAME` (country).
- Consumer: `src/data/geo.ts` (point in polygon, offline).

The file is served as a static asset and loaded on the first click, so it never
enters the initial bundle. It is deliberately the coarse 1:110m edition: about
800 KB and enough to name a continent and a country. Antarctica is simplified at
this scale, which is why `geo.ts` falls back to "Antarctica" south of 60° when a
point falls outside the polygon.

Country names are shown as Natural Earth writes them (English). Continent names
are translated in `src/i18n.ts`.
