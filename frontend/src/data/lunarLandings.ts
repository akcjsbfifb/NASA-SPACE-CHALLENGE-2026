export type LunarSample = {
	elevation: number | null;
	roughness: number | null;
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
		lat: 0.67408,
		lng: 23.47297,
		date: '20 jul 1969',
	},
	{
		id: 'apollo-12',
		mission: 'Apolo 12',
		name: 'Océano de las Tormentas',
		lat: -3.01239,
		lng: -23.42157,
		date: '19 nov 1969',
	},
	{
		id: 'apollo-14',
		mission: 'Apolo 14',
		name: 'Fra Mauro',
		lat: -3.64544,
		lng: -17.47136,
		date: '5 feb 1971',
	},
	{
		id: 'apollo-15',
		mission: 'Apolo 15',
		name: 'Hadley-Apeninos',
		lat: 26.13222,
		lng: 3.63386,
		date: '30 jul 1971',
	},
	{
		id: 'apollo-16',
		mission: 'Apolo 16',
		name: 'Descartes',
		lat: -8.97301,
		lng: 15.50019,
		date: '21 abr 1972',
	},
	{
		id: 'apollo-17',
		mission: 'Apolo 17',
		name: 'Taurus-Littrow',
		lat: 20.1908,
		lng: 30.77168,
		date: '11 dic 1972',
	},
];

type MoonResponse = {
	elevation_m: number | null;
	roughness_m: number | null;
	error?: string;
};

export async function lookupLunarSample(
	_siteId: string | undefined,
	lat: number,
	lng: number,
): Promise<LunarSample> {
	const params = new URLSearchParams({
		lat: String(lat),
		lon: String(lng),
	});
	const response = await fetch(`http://127.0.0.1:8787/moon?${params}`);
	const body = (await response.json()) as MoonResponse;
	if (!response.ok) throw new Error(body.error || 'sin mediciones de este punto');
	return {
		elevation: body.elevation_m,
		roughness: body.roughness_m,
	};
}

export function landingNear(lat: number, lng: number): LunarLanding | undefined {
	return LUNAR_LANDINGS.find(
		(site) => Math.hypot(site.lat - lat, site.lng - lng) < 1.2,
	);
}
