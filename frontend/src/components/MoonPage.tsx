import { useEffect, useRef, useState } from 'react';

import InteractiveGlobe from './Globe/InteractiveGlobe';
import type { GlobeController } from './Globe/globe.controller';
import type { GlobeClickEvent, GlobePoint } from './Globe/globe.types';
import {
	LUNAR_LANDINGS,
	landingNear,
	lookupLunarSample,
	type LunarLanding,
	type LunarSample,
} from '../data/lunarLandings';

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
};

export type EarthAnalogSet = {
	returned: number;
	min_closeness: number;
	closest: number | null;
	loosest: number | null;
	points: EarthAnalog[];
};

type MoonPageProps = {
	precision: number;
	onCompare: (selection: LunarSelection, analogs: EarthAnalogSet | null) => void;
};

function percent(value: number | null) {
	if (value === null) return '—';
	return `${(value * 100).toFixed(0)}%`;
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

function markersFor(picked: PickedPoint | null): GlobePoint[] {
	const sites = LUNAR_LANDINGS.map((site) => ({
		id: site.id,
		lat: site.lat,
		lng: site.lng,
		label: `${site.mission} · ${site.name}`,
		color: picked?.siteId === site.id ? '#7dffe1' : '#f0c14a',
		size: picked?.siteId === site.id ? 0.42 : 0.28,
		altitude: 0.012,
	}));
	if (picked && !picked.siteId) {
		sites.push({
			id: 'custom',
			lat: picked.lat,
			lng: picked.lng,
			label: picked.label,
			color: '#7dffe1',
			size: 0.36,
			altitude: 0.012,
		});
	}
	return sites;
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
		globe.current?.setPoints('landings', markersFor(picked));
		const labeled = LUNAR_LANDINGS.find((site) => site.id === picked?.siteId);
		globe.current?.setLabels(
			'landings',
			labeled
				? [{
					id: `${labeled.id}-label`,
					lat: labeled.lat,
					lng: labeled.lng,
					text: labeled.mission,
					color: '#ffd15c',
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
		fetch(`http://127.0.0.1:8787/search?${params}`, { signal: controller.signal })
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
		const site = landingNear(lat, lng);
		if (site) {
			chooseLanding(site);
			return;
		}
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
								</dl>
								<p className="muted">
									Pendiente, temperatura, hielo y roca no están en estos mapas. La comparación usa la rugosidad.
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
																? `ninguno llega a ${percent(analogs.min_closeness)}`
																: `${percent(analogs.loosest)} – ${percent(analogs.closest)}`}
														</dd>
													</div>
												</dl>
												<div className="result-list">
													{listPreview(analogs.points).map((point) => (
														<button
															key={`${point.lat},${point.lon}`}
															type="button"
															onClick={() => {
																if (!picked || !sample) return;
																onCompare({ ...picked, sample }, analogs);
															}}
														>
															{percent(point.closeness)} · {point.roughness_m.toFixed(1)} m · {point.lat.toFixed(2)}, {point.lon.toFixed(2)}
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
								onCompare({ ...picked, sample }, analogs);
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
