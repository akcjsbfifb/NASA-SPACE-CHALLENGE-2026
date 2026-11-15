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
import { percent } from '../score';
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
	coverage?: number;
	tmin_c?: number | null;
	ice_thickness_m?: number | null;
};

export type EarthAnalogSet = {
	returned: number;
	min_closeness: number;
	closest: number | null;
	loosest: number | null;
	points: EarthAnalog[];
	variables_used?: { id: string; weight: number }[];
};

type MoonPageProps = {
	precision: number;
	onCompare: (
		selection: LunarSelection,
		analogs: EarthAnalogSet | null,
		chosen?: EarthAnalog,
	) => void;
};

function percentText(value: number | null) {
	if (value === null) return '—';
	return `${percent(value, 1)}%`;
}

export function listPreview<T extends { closeness: number }>(items: T[], count = 6): T[] {
	if (items.length <= count) return items;
	const head = items.slice(0, count);
	const percents = new Set(head.map((item) => Math.round(item.closeness * 100)));
	if (percents.size > 1) return head;
	const last = items.length - 1;
	return Array.from({ length: count }, (_, index) => items[Math.round((index * last) / (count - 1))]);
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

export default function MoonPage({ precision, onCompare }: MoonPageProps) {
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
		if (!picked || sampleState !== 'ready' || !sample || sample.roughness === null) {
			return;
		}
		const ticket = ++analogRequest.current;
		const controller = new AbortController();
		setAnalogs(null);
		setAnalogError('');
		setAnalogState('loading');
		const params = new URLSearchParams({
			roughness: String(sample.roughness),
			precision: String(precision),
		});
		if (sample.slope !== null) params.set('slope', String(sample.slope));
		fetch(`${SEARCH_API}/search?${params}`, { signal: controller.signal })
			.then(async (response) => {
				const body = (await response.json()) as EarthAnalogSet & { error?: string };
				if (!response.ok) throw new Error(body.error || 'la búsqueda falló');
				return body;
			})
			.then((body) => {
				if (ticket !== analogRequest.current) return;
				setAnalogs(body);
				setAnalogState('ready');
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
	}, [picked, sample, sampleState, precision]);

	function choose(next: PickedPoint) {
		const ticket = ++request.current;
		analogRequest.current += 1;
		setPicked(next);
		setSample(null);
		setSampleError('');
		setSampleState('loading');
		setAnalogs(null);
		setAnalogError('');
		setAnalogState('idle');
		globe.current?.flyTo({ lat: next.lat, lng: next.lng, altitude: 1.05 }, 900);
		lookupLunarSample(next.siteId, next.lat, next.lng)
			.then((found) => {
				if (ticket !== request.current) return;
				setSample(found);
				setSampleState(found.roughness === null ? 'missing' : 'ready');
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
									El puntaje es relativo; pendiente y rugosidad son aproximaciones con diferencias de escala y método. Las demás mediciones son contexto.
								</p>
								{sample.roughness !== null && (
									<>
										<h4>Análogos en la Tierra</h4>
										{analogState === 'loading' && (
											<p className="muted">Buscando lugares con esta rugosidad…</p>
										)}
										{analogError && <p className="muted">{analogError}</p>}
										{analogs && (
											<>
												<dl className="cell-facts">
													<div>
														<dt>Rugosidad usada</dt>
														<dd>{sample.roughness.toFixed(3)} m</dd>
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
																	<br />Pendiente: Luna {sample.slope ?? 'sin dato'}° · Tierra {point.slope_deg}° · {point.scores?.slope === undefined ? 'sin puntaje' : percentText(point.scores.slope)} · peso {analogs.variables_used?.find(v => v.id === 'slope')?.weight ?? 'no utilizado'}
																	<br />Rugosidad: Luna {sample.roughness} m · Tierra {point.roughness_m} m · {point.scores?.roughness === undefined ? 'sin puntaje' : percentText(point.scores.roughness)} · peso {analogs.variables_used?.find(v => v.id === 'roughness')?.weight ?? 'no utilizado'}
																	<br />Tierra: ETOPO; Luna: LOLA. Valores terrestres redondeados por el servicio.
																	<br />Elevación LOLA: Luna {sample.elevation ?? 'sin dato'} m · Tierra ETOPO: no incluida en esta respuesta · contextual.
																	<br />Rocas Diviner RA: Luna {sample.measurements.rock_abundance?.value ?? 'sin dato'} fracción · Tierra: sin equivalente medido · contextual.
																	<br />TBOL Diviner: Luna {sample.measurements.bolometric_temperature?.value ?? 'sin dato'} K · MODIS terrestre: no disponible · aproximada.
																	<br />TREG Diviner: Luna {sample.measurements.regolith_temperature?.value ?? 'sin dato'} K · suelo ERA5 terrestre: no disponible · contextual.
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
							disabled={sampleState !== 'ready'}
							onClick={() => {
								if (!picked || !sample || sample.roughness === null) return;
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
