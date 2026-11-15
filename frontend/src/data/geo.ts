/**
 * Continent and country for a clicked coordinate, offline.
 *
 * Natural Earth 1:110m admin-0 (public domain) ships with the app, so the panel
 * works without a key, a quota or a network round trip. Google reverse
 * geocoding does not return a continent and answers poorly over Antarctica and
 * ice shelves, which is where most of this shortlist sits.
 *
 * Polygons are split at the antimeridian in this dataset, so planar ray casting
 * is correct for them; no spherical library is needed.
 */

export type PlaceInfo = {
	continent: string | null;
	country: string | null;
	/** True when the point is not inside a country but within ~55 km of one. */
	approximate: boolean;
};

type Ring = number[][];
type Geometry =
	| { type: 'Polygon'; coordinates: Ring[] }
	| { type: 'MultiPolygon'; coordinates: Ring[][] };

export type CountryFeature = {
	properties: { CONTINENT?: string; NAME?: string; ADMIN?: string };
	geometry: Geometry;
};

const COUNTRIES_URL = '/data/ne_110m_admin_0_countries.geojson';
/** Half a degree is about 55 km: enough to absorb a click on a coastline. */
const NEAR_DEGREES = 0.5;

let cache: CountryFeature[] | null = null;
let pending: Promise<CountryFeature[]> | null = null;

export function loadCountries(): Promise<CountryFeature[]> {
	if (cache) return Promise.resolve(cache);
	if (!pending) {
		pending = fetch(COUNTRIES_URL)
			.then((response) => {
				if (!response.ok) throw new Error(`countries ${response.status}`);
				return response.json() as Promise<{ features: CountryFeature[] }>;
			})
			.then((data) => {
				cache = data.features;
				return cache;
			})
			.finally(() => {
				pending = null;
			});
	}
	return pending;
}

export function normalizeLon(lon: number): number {
	return (((lon + 180) % 360) + 360) % 360 - 180;
}

function polygons(geometry: Geometry): Ring[][] {
	return geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
}

function inRing(ring: Ring, lon: number, lat: number): boolean {
	let inside = false;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const xi = ring[i][0];
		const yi = ring[i][1];
		const xj = ring[j][0];
		const yj = ring[j][1];
		if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
			inside = !inside;
		}
	}
	return inside;
}

function bboxArea(ring: Ring): number {
	let west = Infinity;
	let east = -Infinity;
	let south = Infinity;
	let north = -Infinity;
	for (const point of ring) {
		if (point[0] < west) west = point[0];
		if (point[0] > east) east = point[0];
		if (point[1] < south) south = point[1];
		if (point[1] > north) north = point[1];
	}
	return (east - west) * (north - south);
}

function segmentDistanceSq(ring: Ring, lon: number, lat: number): number {
	let best = Infinity;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const x1 = ring[j][0];
		const y1 = ring[j][1];
		const dx = ring[i][0] - x1;
		const dy = ring[i][1] - y1;
		const lengthSq = dx * dx + dy * dy;
		const t = lengthSq === 0
			? 0
			: Math.max(0, Math.min(1, ((lon - x1) * dx + (lat - y1) * dy) / lengthSq));
		const px = x1 + t * dx - lon;
		const py = y1 + t * dy - lat;
		best = Math.min(best, px * px + py * py);
	}
	return best;
}

function describe(feature: CountryFeature, approximate: boolean): PlaceInfo {
	return {
		continent: feature.properties.CONTINENT ?? null,
		country: feature.properties.NAME ?? feature.properties.ADMIN ?? null,
		approximate,
	};
}

export function locate(features: CountryFeature[], lat: number, lon: number): PlaceInfo | null {
	const lng = normalizeLon(lon);

	// A point can fall inside two features when a small country sits inside a
	// bigger one (Lesotho in South Africa). The smaller bounding box wins.
	let best: { feature: CountryFeature; area: number } | null = null;
	for (const feature of features) {
		for (const rings of polygons(feature.geometry)) {
			if (!rings.length || !inRing(rings[0], lng, lat)) continue;
			if (rings.slice(1).some((hole) => inRing(hole, lng, lat))) continue;
			const area = bboxArea(rings[0]);
			if (!best || area < best.area) best = { feature, area };
		}
	}
	if (best) return describe(best.feature, false);

	let nearest: { feature: CountryFeature; distance: number } | null = null;
	for (const feature of features) {
		for (const rings of polygons(feature.geometry)) {
			if (!rings.length) continue;
			const distance = segmentDistanceSq(rings[0], lng, lat);
			if (!nearest || distance < nearest.distance) nearest = { feature, distance };
		}
	}
	if (nearest && nearest.distance <= NEAR_DEGREES * NEAR_DEGREES) {
		return describe(nearest.feature, true);
	}

	// 1:110m Antarctica is heavily simplified, so ice shelves and the polar cap
	// south of 60° fall outside the polygon. Labelling the region is more useful
	// than saying "no country" for a continent with no countries.
	if (lat <= -60) {
		return { continent: 'Antarctica', country: null, approximate: true };
	}
	return null;
}
