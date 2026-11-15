export type AdditionalMeasurement = {
	value: number | null;
	unit?: string;
	available: boolean;
	status: string;
	reason?: string | null;
	source?: string;
	original_value?: number | null;
	original_unit?: string;
	raw_value?: number | null;
	raw_unit?: string;
	raw?: Record<string, number>;
	quality?: Record<string, unknown>;
	selected_hours?: number;
};

export type AdditionalMeasurements = Record<string, AdditionalMeasurement>;

export function extraValue(item: AdditionalMeasurement | undefined, pending: string): string {
	if (!item) return pending;
	if (!item.available || item.value === null) return `${item.status}: ${item.reason ?? pending}`;
	const raw = item.original_value ?? item.raw_value ?? item.raw?.LST_Night_CMG;
	const rawUnit = item.original_unit ?? item.raw_unit;
	const qa = item.quality?.mandatory_qa;
	const nights = item.quality?.clear_sky_nights_count;
	return `${item.value} ${item.unit ?? ''} (${item.source ?? ''}${raw !== undefined && raw !== null ? `; ${raw} ${rawUnit ?? ''}` : ''}${qa !== undefined ? `; QA ${qa}, n=${nights}` : ''}${item.selected_hours !== undefined ? `; n=${item.selected_hours}` : ''})`;
}

export const extraCopy = {
	es: { title: 'Enriquecimiento contextual · enero 2025', pending: 'No procesado', loading: 'Consultando hasta 50 candidatos preseleccionados…', failed: 'Fuentes adicionales no disponibles', modis: 'Temperatura superficial nocturna · MODIS', era: 'Temperatura de suelo 0–7 cm · ERA5-Land', soil: 'Fragmentos gruesos 0–5 cm · SoilGrids', lunar: 'Luna', earth: 'Tierra', approx: 'aproximada', context: 'contextual', noScore: 'fuera del puntaje', scope: 'Candidatos preseleccionados por geometría; no es búsqueda global multivariable.' },
	en: { title: 'Context enrichment · January 2025', pending: 'Not processed', loading: 'Enriching up to 50 preselected candidates…', failed: 'Additional sources unavailable', modis: 'Night surface temperature · MODIS', era: 'Soil temperature 0–7 cm · ERA5-Land', soil: 'Coarse fragments 0–5 cm · SoilGrids', lunar: 'Moon', earth: 'Earth', approx: 'approximate', context: 'contextual', noScore: 'not scored', scope: 'Candidates preselected by geometry; not a global multivariable search.' },
	fr: { title: 'Enrichissement contextuel · janvier 2025', pending: 'Non traité', loading: 'Enrichissement de 50 candidats présélectionnés au maximum…', failed: 'Sources supplémentaires indisponibles', modis: 'Température de surface nocturne · MODIS', era: 'Température du sol 0–7 cm · ERA5-Land', soil: 'Fragments grossiers 0–5 cm · SoilGrids', lunar: 'Lune', earth: 'Terre', approx: 'approximative', context: 'contextuelle', noScore: 'hors score', scope: 'Candidats présélectionnés par géométrie ; pas une recherche globale multivariable.' },
	it: { title: 'Arricchimento contestuale · gennaio 2025', pending: 'Non elaborato', loading: 'Arricchimento di massimo 50 candidati preselezionati…', failed: 'Fonti aggiuntive non disponibili', modis: 'Temperatura superficiale notturna · MODIS', era: 'Temperatura del suolo 0–7 cm · ERA5-Land', soil: 'Frammenti grossolani 0–5 cm · SoilGrids', lunar: 'Luna', earth: 'Terra', approx: 'approssimativa', context: 'contestuale', noScore: 'fuori dal punteggio', scope: 'Candidati preselezionati per geometria; non una ricerca globale multivariabile.' },
} as const;
