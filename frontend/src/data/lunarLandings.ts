export type LunarSample = {
	elevation: number | null;
	roughness: number | null;
	slope: number | null;
	measurements: Record<string, LunarMeasurement>;
};

export type LunarMeasurement = {
	value: number | null;
	unit: string | null;
	available: boolean | null;
	status: string;
	reason: string | null;
	source_ref: string | null;
};

export type LunarLanding = {
	id: string;
	mission: string;
	name: string;
	lat: number;
	lng: number;
	date: string;
	sample?: LunarSample;
};

export const LUNAR_LANDINGS: LunarLanding[] = [
	{
		id: 'apollo-11',
		mission: 'Apolo 11',
		name: 'Base de la Tranquilidad',
		lat: 0.6742,
		lng: 23.4731,
		date: '20 jul 1969',
	},
	{
		id: 'apollo-12',
		mission: 'Apolo 12',
		name: 'Océano de las Tormentas',
		lat: -3.0128,
		lng: -23.4219,
		date: '19 nov 1969',
	},
	{
		id: 'apollo-14',
		mission: 'Apolo 14',
		name: 'Fra Mauro',
		lat: -3.6459,
		lng: -17.4719,
		date: '5 feb 1971',
	},
	{
		id: 'apollo-15',
		mission: 'Apolo 15',
		name: 'Hadley-Apeninos',
		lat: 26.1324,
		lng: 3.6333,
		date: '30 jul 1971',
	},
	{
		id: 'apollo-16',
		mission: 'Apolo 16',
		name: 'Descartes',
		lat: -8.9734,
		lng: 15.5011,
		date: '21 abr 1972',
	},
	{
		id: 'apollo-17',
		mission: 'Apolo 17',
		name: 'Taurus-Littrow',
		lat: 20.1911,
		lng: 30.7723,
		date: '11 dic 1972',
	},
];

type MoonResponse = {
	elevation_m: number | null;
	roughness_m: number | null;
	slope_deg?: number | null;
	measurements?: Record<string, LunarMeasurement>;
	error?: string;
};

export async function lookupLunarSample(
	siteId: string | undefined,
	lat: number,
	lng: number,
): Promise<LunarSample> {
	// A known landing site is answered from the published JSON by id; a free
	// click still samples the LOLA rasters by coordinate.
	const params = siteId
		? new URLSearchParams({ site: siteId })
		: new URLSearchParams({ lat: String(lat), lon: String(lng) });
	const response = await fetch(`http://127.0.0.1:8787/moon?${params}`);
	const body = (await response.json()) as MoonResponse;
	if (!response.ok) throw new Error(body.error || 'sin mediciones de este punto');
	return {
		elevation: body.elevation_m,
		roughness: body.roughness_m,
		slope: body.slope_deg ?? null,
		measurements: body.measurements ?? {},
	};
}

export function landingNear(lat: number, lng: number): LunarLanding | undefined {
	return LUNAR_LANDINGS.find(
		(site) => Math.hypot(site.lat - lat, site.lng - lng) < 1.2,
	);
}
