import { useEffect, useRef, useState } from 'react';

import InteractiveGlobe from './Globe/InteractiveGlobe';
import type { GlobeController } from './Globe/globe.controller';
import type { GlobeClickEvent, GlobeMarker, GlobePoint } from './Globe/globe.types';
import {
	LUNAR_LANDINGS,
	lookupLunarSample,
	type LunarLanding,
	type LunarSample,
} from '../data/lunarLandings';
import { SEARCH_API } from '../searchApi';
import type { VariableInfo } from '../score';
import type { Language } from '../i18n';
import { extraCopy, extraValue } from '../data/earthMeasurements';
import { lunarSearchCopy } from '../data/lunarSearchCopy';
import type { AdditionalMeasurements } from '../data/earthMeasurements';
import { SELECTED_COLOR, SELECTED_PIN_SIZE } from '../theme';

const MOON_GLOBE = {
	initialView: { lat: 8, lng: 6, altitude: 2.45 },
	earth: {
		textureUrl: '/textures/2k_moonmap.jpg',
		highResolutionTextureUrl: '/textures/8k_moonmap.jpg',
		backgroundImageUrl: '/night-sky.png',
		backgroundColor: '#050914',
		atmosphereColor: '#c8c2b8',
		atmosphereAltitude: 0.01,
		showAtmosphere: false,
	},
};

export type LunarSelection = {
	lat: number;
	lng: number;
	label: string;
	siteId?: string;
	sample: LunarSample;
};

export type EarthAnalog = {
	lat: number;
	lon: number;
	closeness: number;
	roughness_m: number;
	rock: string;
	slope_deg: number;
	scores?: Record<string, number>;
	weighted_shares?: Record<string, number>;
	effective_weights?: Record<string, number>;
	coverage?: number;
	coverage_requested?: number;
	quality_warnings?: string[];
	tmin_c?: number | null;
	ice_thickness_m?: number | null;
	measurements?: Record<string, { value: number | null; unit: string; available: boolean; status: string; reason: string | null; source: string | null; method: string | null }>;
	additional_measurements?: AdditionalMeasurements;
	coordinates_original?: { lat: number; lon: number };
	deltas?: Record<string, number>;
};

export type EarthAnalogSet = {
	returned: number;
	min_closeness: number;
	closest: number | null;
	loosest: number | null;
	points: EarthAnalog[];
	variables_used?: VariableInfo[];
	target?: Record<string, number | string | null>;
	candidate_generation?: { scope: string; evaluated: number; minimum_coverage: number; limitation: string; variables: string[] };
};

type LunarCriterion = 'slope' | 'roughness' | 'tbol_modis' | 'treg_era5';
const CRITERIA: LunarCriterion[] = ['slope', 'roughness', 'tbol_modis', 'treg_era5'];

type MoonPageProps = {
	precision: number;
	language: Language;
	onCompare: (
		selection: LunarSelection,
		analogs: EarthAnalogSet | null,
		chosen?: EarthAnalog,
	) => void;
};

function percentText(value: number | null) {
	if (value === null) return '—';
	return `${(value * 100).toFixed(1)}%`;
}

type PickedPoint = {
	lat: number;
	lng: number;
	label: string;
	siteId?: string;
};

/**
 * Every landing except the picked one, which becomes a pin instead of a
 * cylinder.  The others stay clickable cylinders.
 */
function pointsFor(picked: PickedPoint | null): GlobePoint[] {
	return LUNAR_LANDINGS.filter((site) => site.id !== picked?.siteId).map((site) => ({
		id: site.id,
		lat: site.lat,
		lng: site.lng,
		label: `${site.mission} · ${site.name}`,
		color: '#f0c14a',
		size: 0.28,
		altitude: 0.012,
	}));
}

/** The picked site, or the free point, as a red pin. */
function pinsFor(picked: PickedPoint | null): GlobeMarker[] {
	if (!picked) return [];
	return [{
		id: 'picked',
		lat: picked.lat,
		lng: picked.lng,
		label: picked.label,
		color: SELECTED_COLOR,
		size: SELECTED_PIN_SIZE,
		altitude: 0.012,
	}];
}

export default function MoonPage({ precision, language, onCompare }: MoonPageProps) {
	const extras = extraCopy[language];
	const searchCopy = lunarSearchCopy[language];
	const globe = useRef<GlobeController>(null);
	const request = useRef(0);
	const analogRequest = useRef(0);
	const ignoreGlobeClick = useRef(false);
	const [picked, setPicked] = useState<PickedPoint | null>(null);
	const [sample, setSample] = useState<LunarSample | null>(null);
	const [sampleError, setSampleError] = useState('');
	const [sampleState, setSampleState] = useState<'idle' | 'loading' | 'ready' | 'missing'>('idle');
	const [analogs, setAnalogs] = useState<EarthAnalogSet | null>(null);
	const [analogError, setAnalogError] = useState('');
	const [analogState, setAnalogState] = useState<'idle' | 'loading' | 'ready'>('idle');
	const [enrichment, setEnrichment] = useState<'idle' | 'loading' | 'ready' | 'failed'>('idle');
	const [included, setIncluded] = useState<Record<LunarCriterion, boolean>>({ slope: true, roughness: true, tbol_modis: false, treg_era5: false });
	const [weights, setWeights] = useState<Record<LunarCriterion, number>>({ slope: 1, roughness: 1, tbol_modis: 1, treg_era5: 1 });
	const [minimumCoverage, setMinimumCoverage] = useState(1);
	const [applied, setApplied] = useState({ included, weights, minimumCoverage });

	useEffect(() => {
		globe.current?.setPoints('landings', pointsFor(picked));
		globe.current?.setMarkers('picked', pinsFor(picked));
		const labeled = LUNAR_LANDINGS.find((site) => site.id === picked?.siteId);
		globe.current?.setLabels(
			'landings',
			labeled
				? [{
					id: `${labeled.id}-label`,
					lat: labeled.lat,
					lng: labeled.lng,
					text: labeled.mission,
					color: SELECTED_COLOR,
					size: 1.6,
					altitude: 0.02,
				}]
				: [],
		);
	}, [picked]);

	useEffect(() => {
		if (!picked || sampleState !== 'ready' || !sample) {
			return;
		}
		const ticket = ++analogRequest.current;
		const controller = new AbortController();
		const params = new URLSearchParams({ precision: String(precision), min_coverage: String(applied.minimumCoverage), candidate_limit: '50' });
		const targets: Record<LunarCriterion, number | null> = {
			slope: sample.slope, roughness: sample.roughness,
			tbol_modis: sample.measurements.bolometric_temperature?.available ? sample.measurements.bolometric_temperature.value : null,
			treg_era5: sample.measurements.regolith_temperature?.available ? sample.measurements.regolith_temperature.value : null,
		};
		for (const name of CRITERIA) {
			if (applied.included[name] && targets[name] !== null) {
				params.set(name, String(targets[name]));
				params.set(`w_${name}`, String(applied.weights[name]));
			}
		}
		fetch(`${SEARCH_API}/search?${params}`, { signal: controller.signal })
			.then(async (response) => {
				const body = (await response.json()) as EarthAnalogSet & { error?: string };
				if (!response.ok) {
					if (body.error === 'unsupported_candidate_generation') throw new Error(({ es: 'Seleccioná pendiente o rugosidad con peso positivo para generar candidatos.', en: 'Select slope or roughness with a positive weight to generate candidates.', fr: 'Sélectionnez une pente ou une rugosité avec un poids positif pour générer des candidats.', it: 'Seleziona pendenza o rugosità con peso positivo per generare candidati.' })[language]);
					throw new Error((body as EarthAnalogSet & { message?: string }).message || body.error || 'la búsqueda falló');
				}
				return body;
			})
			.then((body) => {
				if (ticket !== analogRequest.current) return;
				setAnalogs(body);
				setAnalogState('ready');
				if (!body.points.length) return;
				setEnrichment('loading');
				void fetch(`${SEARCH_API}/enrich`, {
					method: 'POST', headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ candidates: body.points.slice(0, 50).map(p => p.coordinates_original ?? { lat: p.lat, lon: p.lon }) }),
					signal: controller.signal,
				}).then(async response => {
					if (!response.ok) throw new Error('enrichment failed');
					return response.json() as Promise<{ candidates: { lat: number; lon: number; additional_measurements: AdditionalMeasurements }[] }>;
				}).then(data => {
					if (ticket !== analogRequest.current) return;
					setAnalogs(current => current ? { ...current, points: current.points.map((point, index) => {
						const additional = { ...data.candidates[index]?.additional_measurements };
						for (const [key, value] of Object.entries(point.additional_measurements ?? {})) {
							if (value.available && !additional[key]?.available) additional[key] = value;
						}
						return { ...point, additional_measurements: additional };
					}) } : current);
					setEnrichment('ready');
				}).catch(() => {
					if (ticket === analogRequest.current && !controller.signal.aborted) setEnrichment('failed');
				});
			})
			.catch((error: unknown) => {
				if (ticket !== analogRequest.current || controller.signal.aborted) return;
				setAnalogs(null);
				setAnalogError(
					error instanceof TypeError
						? 'No llega al servidor de búsqueda (puerto 8787).'
						: error instanceof Error
							? error.message
							: 'no se pudo comparar con la Tierra',
				);
				setAnalogState('ready');
			});
		return () => controller.abort();
	}, [picked, sample, sampleState, precision, applied, language]);

	function choose(next: PickedPoint) {
		const ticket = ++request.current;
		analogRequest.current += 1;
		setPicked(next);
		setSample(null);
		setSampleError('');
		setSampleState('loading');
		setAnalogs(null);
		setAnalogError('');
		setAnalogState('loading');
		globe.current?.flyTo({ lat: next.lat, lng: next.lng, altitude: 1.05 }, 900);
		lookupLunarSample(next.siteId, next.lat, next.lng)
			.then((found) => {
				if (ticket !== request.current) return;
				setSample(found);
				setSampleState(found.roughness === null && found.slope === null ? 'missing' : 'ready');
			})
			.catch((error: unknown) => {
				if (ticket !== request.current) return;
				setSample(null);
				setSampleError(error instanceof Error ? error.message : 'sin mediciones de este punto');
				setSampleState('missing');
			});
	}

	function chooseLanding(site: LunarLanding) {
		choose({
			lat: site.lat,
			lng: site.lng,
			label: `${site.mission} · ${site.name}`,
			siteId: site.id,
		});
	}

	function chooseCoordinates(lat: number, lng: number) {
		choose({
			lat,
			lng,
			label: `Punto ${lat.toFixed(2)}, ${lng.toFixed(2)}`,
		});
	}

	const selectedLanding = LUNAR_LANDINGS.find((site) => site.id === picked?.siteId);

	return (
		<>
			<aside className="sidebar">
				<section className="sidebar-section">
					<h4>Alunizajes tripulados</h4>
					<p className="muted">
						Los seis sitios donde bajó una tripulación. También podés marcar otro punto en la Luna.
					</p>
					<div className="result-list">
						{LUNAR_LANDINGS.map((site) => (
							<button
								key={site.id}
								type="button"
								className={picked?.siteId === site.id ? 'active' : undefined}
								onClick={() => chooseLanding(site)}
							>
								{site.mission} · {site.name}
							</button>
						))}
					</div>
				</section>

				<hr />

				<h3>SITIO LUNAR</h3>
				{picked ? (
					<>
						<p>{picked.label}</p>
						{selectedLanding && <p className="muted">{selectedLanding.date}</p>}
						<p>Latitud: {picked.lat.toFixed(5)}</p>
						<p>Longitud: {picked.lng.toFixed(5)}</p>
						{sampleState === 'loading' && <p className="muted">Buscando mediciones de este punto…</p>}
						{sampleState === 'missing' && (
							<p className="muted">
								{sampleError || 'Este punto no tiene rugosidad LOLA, así que no se puede comparar con la Tierra.'}
							</p>
						)}
						{sample && (
							<>
								<fieldset>
									<legend>{searchCopy.criteria}</legend>
									{CRITERIA.map(name => {
										const labels: Record<LunarCriterion, string> = { slope: searchCopy.slope, roughness: searchCopy.roughness, tbol_modis: `TBOL / MODIS · ${searchCopy.approx}`, treg_era5: `TREG / ERA5-Land · ${searchCopy.indirect}` };
										const available = name === 'slope' ? sample.slope !== null : name === 'roughness' ? sample.roughness !== null : name === 'tbol_modis' ? sample.measurements.bolometric_temperature?.available : sample.measurements.regolith_temperature?.available;
										return <div key={name}><label><input type="checkbox" checked={included[name]} onChange={event => setIncluded(old => ({ ...old, [name]: event.target.checked }))} /> {labels[name]}{!available ? ` · ${searchCopy.missing}` : ''}</label> <input aria-label={`${searchCopy.weight} ${labels[name]}`} type="range" min="0" max="1" step="0.1" value={weights[name]} onChange={event => setWeights(old => ({ ...old, [name]: Number(event.target.value) }))} /> {weights[name]}</div>;
									})}
									<p>{searchCopy.context}</p>
									<label>{searchCopy.coverage} <input type="number" min="1" max="4" value={minimumCoverage} onChange={event => setMinimumCoverage(Number(event.target.value))} /></label>
									<button type="button" onClick={() => { setAnalogs(null); setAnalogError(''); setAnalogState('loading'); setEnrichment('idle'); setApplied({ included: { ...included }, weights: { ...weights }, minimumCoverage }); }}>{searchCopy.apply}</button>
								</fieldset>
								<dl className="cell-facts">
									<div>
										<dt>Elevación</dt>
										<dd>{sample.elevation === null ? 'sin dato' : `${sample.elevation.toFixed(1)} m`}</dd>
									</div>
									<div>
										<dt>Rugosidad</dt>
										<dd>{sample.roughness === null ? 'sin dato' : `${sample.roughness.toFixed(3)} m`}</dd>
									</div>
									<div>
										<dt>Pendiente</dt>
										<dd>{sample.slope === null ? 'sin dato' : `${sample.slope.toFixed(2)}°`}</dd>
									</div>
								</dl>
								<dl className="cell-facts">
									{([
										['rock_abundance', 'Abundancia de rocas · Diviner RA'],
										['bolometric_temperature', 'Temperatura bolométrica nocturna · Diviner TBOL'],
										['regolith_temperature', 'Temperatura del regolito · Diviner TREG'],
										['hydrogen_abundance_ppm', 'Hidrógeno estimado · Lunar Prospector'],
									] as const).map(([key, label]) => {
										const item = sample.measurements[key];
										return <div key={key}><dt>{label}</dt><dd>{item?.available && item.value !== null ? `${item.value} ${item.unit ?? ''}` : `sin dato (${item?.reason ?? 'no disponible'})`}</dd></div>;
									})}
								</dl>
								<p className="muted">
									{searchCopy.note}
								</p>
								{(sample.roughness !== null || sample.slope !== null) && (
									<>
										<h4>Análogos en la Tierra</h4>
										{analogState === 'loading' && (
											<p className="muted">{searchCopy.loading}</p>
										)}
										{analogError && <p className="muted">{analogError}</p>}
										{analogs && (
											<>
												<p className="muted">{extras.scope} {enrichment === 'loading' ? extras.loading : enrichment === 'failed' ? extras.failed : ''}</p>
												<dl className="cell-facts">
													<div>
																<dt>Variables usadas</dt>
																<dd>{analogs.variables_used?.map(v => v.id).join(', ') ?? '—'}</dd>
													</div>
													<div>
														<dt>Lugares</dt>
														<dd>{analogs.returned}</dd>
													</div>
													<div>
														<dt>Cercanía</dt>
														<dd>
															{analogs.returned === 0
																? `ninguno llega a ${percentText(analogs.min_closeness)}`
																: `${percentText(analogs.loosest)} – ${percentText(analogs.closest)}`}
														</dd>
													</div>
												</dl>
																{analogs.candidate_generation && <p className="muted">{searchCopy.preselect} {analogs.candidate_generation.variables?.join(', ')} · {analogs.candidate_generation.evaluated}</p>}
												<div className="result-list">
														{analogs.points.map((point) => (
														<button
															key={`${point.lat},${point.lon}`}
															type="button"
															onClick={() => {
																if (!picked || !sample) return;
																onCompare({ ...picked, sample }, analogs, point);
															}}
														>
															{percentText(point.closeness)} · {point.roughness_m.toFixed(1)} m · {point.lat.toFixed(2)}, {point.lon.toFixed(2)}
																	<br />Cobertura: {point.coverage ?? 0}/{point.coverage_requested ?? analogs.variables_used?.length ?? 0}. {point.quality_warnings?.join(', ')}
																			<br />Participación ponderada: {Object.entries(point.weighted_shares ?? {}).map(([name, share]) => `${name} ${percentText(share)}`).join(' · ') || 'no disponible'}.
																			{point.effective_weights && <><br />Pesos efectivos: {Object.entries(point.effective_weights).map(([name, weight]) => `${name} ${percentText(weight)}`).join(' · ')}.</>}
																	<br />Pendiente: Luna {sample.slope ?? 'sin dato'}° · Tierra {point.measurements?.slope?.value ?? 'sin dato'}° · {point.scores?.slope === undefined ? 'sin puntaje' : percentText(point.scores.slope)} · peso {analogs.variables_used?.find(v => v.id === 'slope')?.weight ?? 'no utilizado'}
																	<br />Rugosidad: Luna {sample.roughness} m · Tierra {point.measurements?.roughness?.value ?? 'sin dato'} m · {point.scores?.roughness === undefined ? 'sin puntaje' : percentText(point.scores.roughness)} · peso {analogs.variables_used?.find(v => v.id === 'roughness')?.weight ?? 'no utilizado'}
																	<br />Tierra: {point.measurements?.slope?.source ?? 'fuente no disponible'}; Luna: LOLA. Comparaciones aproximadas.
																	<br />Elevación LOLA: Luna {sample.elevation ?? 'sin dato'} m · Tierra ETOPO: {point.measurements?.elevation?.value ?? 'sin dato'} m · contextual.
																	<br />{extras.soil}: {extras.lunar} RA {sample.measurements.rock_abundance?.value ?? extras.pending} · {extras.earth} {extraValue(point.additional_measurements?.coarse_fragments_0_to_5cm, extras.pending)} · {extras.context}, {extras.noScore}.
																	<br />{extras.modis}: {extras.lunar} TBOL {sample.measurements.bolometric_temperature?.value ?? extras.pending} K · {extras.earth} {extraValue(point.additional_measurements?.surface_temperature_modis, extras.pending)} · {extras.approx}, {point.scores?.tbol_modis === undefined ? extras.noScore : `${percentText(point.scores.tbol_modis)} · peso ${analogs.variables_used?.find(v => v.id === 'tbol_modis')?.weight}` }.
																	<br />{extras.era}: {extras.lunar} TREG {sample.measurements.regolith_temperature?.value ?? extras.pending} K · {extras.earth} {extraValue(point.additional_measurements?.soil_temperature_0_to_7cm, extras.pending)} · {extras.context}, {point.scores?.treg_era5 === undefined ? extras.noScore : `${percentText(point.scores.treg_era5)} · peso ${analogs.variables_used?.find(v => v.id === 'treg_era5')?.weight}` }.
																	<br />Hidrógeno Lunar Prospector: Luna {sample.measurements.hydrogen_abundance_ppm?.value ?? 'sin dato'} ppm · Tierra: sin equivalente · contextual.
																	<br />Contexto terrestre: mínima del aire del mes más frío WorldClim {point.tmin_c ?? 'sin dato'} °C · hielo ETOPO {point.ice_thickness_m ?? 'sin dato'} m · litología GLiM {point.rock}.
														</button>
													))}
												</div>
											</>
										)}
									</>
								)}
							</>
						)}
						<button
							type="button"
							disabled={sampleState !== 'ready' || !analogs || analogState !== 'ready'}
							onClick={() => {
								if (!picked || !sample || (sample.roughness === null && sample.slope === null)) return;
								onCompare({ ...picked, sample }, analogs, analogs?.points[0]);
							}}
						>
							{sampleState === 'loading'
								? 'Buscando mediciones…'
								: sampleState === 'ready'
									? 'Verlos en la Tierra'
									: 'Sin mediciones de este punto'}
						</button>
					</>
				) : (
					<p>Elegí un alunizaje o hacé clic en la Luna.</p>
				)}
			</aside>

			<section className="globe-container">
				<InteractiveGlobe
					ref={globe}
					config={MOON_GLOBE}
					onLocationSelect={(coords: GlobeClickEvent) => {
						if (ignoreGlobeClick.current) {
							ignoreGlobeClick.current = false;
							return;
						}
						chooseCoordinates(coords.lat, coords.lng);
					}}
					onPointSelect={(point: GlobePoint) => {
						ignoreGlobeClick.current = true;
						queueMicrotask(() => {
							ignoreGlobeClick.current = false;
						});
						const site = LUNAR_LANDINGS.find((item) => item.id === point.id);
						if (site) chooseLanding(site);
						else chooseCoordinates(point.lat, point.lng);
					}}
				/>
				<div className="globe-overlay">
					<span>LUNA · CARA VISIBLE</span>
					<span>6 ALUNIZAJES</span>
				</div>
			</section>
		</>
	);
}
