import { useEffect, useState } from 'react';

import { SEARCH_API } from '../searchApi';
import { getCopy } from '../i18n';
import type { Language } from '../i18n';
import { locate, loadCountries } from '../data/geo';
import type { PlaceInfo } from '../data/geo';
import { formatDelta, formatValue, percent, truncated } from '../score';
import type { ActivityPreset, Grade, VariableInfo } from '../score';
import type { LunarSelection } from './MoonPage';
import { extraCopy, extraValue } from '../data/earthMeasurements';
import { lunarSearchCopy } from '../data/lunarSearchCopy';
import type { AdditionalMeasurements } from '../data/earthMeasurements';

export type SelectedPlace = {
	lat: number;
	lng: number;
	closeness?: number;
	coverage?: number;
	worst?: number;
	scores?: Record<string, number>;
	weighted_shares?: Record<string, number>;
	effective_weights?: Record<string, number>;
	grades?: Record<string, Grade>;
	grade?: Grade;
	deltas?: Record<string, number>;
	target?: Record<string, number | string | null>;
	activity?: string | null;
	additional_measurements?: AdditionalMeasurements;
	measurements?: Record<string, { value: number | null; source: string | null; unit: string; status: string; reason: string | null }>;
	quality_warnings?: string[];
	coordinates_original?: { lat: number; lon: number };
};

type EarthCell = {
	lat: number;
	lon: number;
	distance_km: number;
	elevation_m: number | null;
	slope_deg: number;
	roughness_m: number;
	tmin_c: number | null;
	ice_thickness_m: number;
	rock: string;
};

type PointPanelProps = {
	place: SelectedPlace | null;
	onClose: () => void;
	language: Language;
	variables: VariableInfo[];
	activities: ActivityPreset[];
	lunar: LunarSelection | null;
};

/** Labels come from i18n by id, with the raw id as a fallback for new variables. */
function variableLabel(copy: ReturnType<typeof getCopy>, id: string): string {
	const known: Record<string, string> = {
		slope: copy.slope,
		roughness: copy.roughness,
		temperature: copy.nightTemperature,
		ice: copy.ice,
		rock: copy.rock,
		tbol_modis: 'TBOL / MODIS',
		treg_era5: 'TREG / ERA5-Land',
	};
	return known[id] ?? id;
}

const BREAKDOWN_SLICE_COLORS: Record<string, string> = {
	slope: '#7dffe1',
	roughness: '#f0c14a',
	temperature: '#9fd4c4',
	ice: '#c9a86a',
	rock: '#e07a4a',
};

function polarToCartesian(cx: number, cy: number, radius: number, angleDeg: number) {
	const angleRad = ((angleDeg - 90) * Math.PI) / 180;
	return { x: cx + radius * Math.cos(angleRad), y: cy + radius * Math.sin(angleRad) };
}

function pieWedgePath(cx: number, cy: number, radius: number, startDeg: number, endDeg: number) {
	if (endDeg - startDeg >= 359.99) {
		return `M ${cx} ${cy - radius} A ${radius} ${radius} 0 1 1 ${cx - 0.001} ${cy - radius} Z`;
	}
	const start = polarToCartesian(cx, cy, radius, endDeg);
	const end = polarToCartesian(cx, cy, radius, startDeg);
	const largeArc = endDeg - startDeg > 180 ? 1 : 0;
	return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

type BreakdownSlice = {
	id: string;
	name: string;
	color: string;
	share: number;
	shareLabel: string;
	score: number;
	similarityLabel: string;
	startDeg: number;
	endDeg: number;
};

function breakdownSlices(
	variables: VariableInfo[],
	scores: Record<string, number>,
	copy: ReturnType<typeof getCopy>,
	weightedShares?: Record<string, number>,
): BreakdownSlice[] {
	const active = variables.filter((variable) => typeof scores[variable.id] === 'number');
	const scoreSum = active.reduce((sum, variable) => sum + scores[variable.id]!, 0);
	if (scoreSum <= 0 || active.length === 0) return [];
	let cursor = 0;
	return active.map((variable) => {
		const score = scores[variable.id]!;
		const share = weightedShares?.[variable.id] ?? score / scoreSum;
		const span = share * 360;
		const startDeg = cursor;
		const endDeg = cursor + span;
		cursor = endDeg;
		const shareLabel = truncated(share * 100, 1);
		const similarityLabel = (score * 100).toFixed(1);
		const name = variableLabel(copy, variable.id);
		return {
			id: variable.id,
			name,
			color: BREAKDOWN_SLICE_COLORS[variable.id] ?? '#8fa2b8',
			share,
			shareLabel,
			score,
			similarityLabel,
			startDeg,
			endDeg,
		};
	});
}

/** What the Earth cell holds for a variable, in the panel's own column names. */
function cellValue(cell: EarthCell, id: string): number | string | null {
	switch (id) {
		case 'slope':
			return cell.slope_deg;
		case 'roughness':
			return cell.roughness_m;
		case 'temperature':
			return cell.tmin_c;
		case 'ice':
			return cell.ice_thickness_m;
		case 'rock':
			return cell.rock;
		default:
			return null;
	}
}

function formatMeters(value: number | null, noData: string, digits = 0) {
	if (value === null) return noData;
	return `${value.toFixed(digits)} m`;
}

export default function PointPanel(props: PointPanelProps) {
	const key = props.place ? `${props.place.lat},${props.place.lng}` : 'none';
	return <PointPanelContent key={key} {...props} />;
}

function PointPanelContent({ place, lunar, onClose, language, variables, activities }: PointPanelProps) {
	const copy = getCopy(language);
	const extra = extraCopy[language];
	const [extraResult, setExtraResult] = useState<{ key: string; values: AdditionalMeasurements | null; failed: boolean } | null>(null);
	const extraKey = place ? `${place.coordinates_original?.lat ?? place.lat},${place.coordinates_original?.lon ?? place.lng}` : '';
	const enriched = extraResult?.key === extraKey ? extraResult.values : null;
	const additional = enriched ? { ...place?.additional_measurements, ...enriched,
		...Object.fromEntries(Object.entries(place?.additional_measurements ?? {}).filter(([key, value]) => value.available && !enriched[key]?.available)),
	} : place?.additional_measurements ?? null;
	const extraStatus = additional ? 'ready' : extraResult?.key === extraKey && extraResult.failed ? 'failed' : 'loading';
	const [cell, setCell] = useState<EarthCell | null>(null);
	const [cellError, setCellError] = useState(false);
	const [sceneUrl, setSceneUrl] = useState('');
	const [sceneSource, setSceneSource] = useState('');
	const [imageError, setImageError] = useState(false);
	const [where, setWhere] = useState<PlaceInfo | null | undefined>(undefined);

	useEffect(() => {
		if (!place || !lunar) return;
		const existing = place.additional_measurements;
		if (existing && !Object.values(existing).some(item => item.reason === 'source_not_selected')) return;
		const controller = new AbortController();
		const key = `${place.coordinates_original?.lat ?? place.lat},${place.coordinates_original?.lon ?? place.lng}`;
		const load = async () => {
			for (let attempt = 0; attempt < 8; attempt++) {
				const response = await fetch(`${SEARCH_API}/enrich`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ candidates: [place.coordinates_original ?? { lat: place.lat, lon: place.lng }] }), signal: controller.signal });
				if (response.status === 429 && attempt < 7) {
					await new Promise(resolve => setTimeout(resolve, 8000));
					if (controller.signal.aborted) throw new Error('aborted');
					continue;
				}
				if (!response.ok) throw new Error('enrichment failed');
				return response.json() as Promise<{ candidates: { additional_measurements: AdditionalMeasurements }[] }>;
			}
			throw new Error('enrichment busy');
		};
		void load()
			.then(data => { setExtraResult({ key, values: data.candidates[0]?.additional_measurements ?? null, failed: false }); })
			.catch(() => { if (!controller.signal.aborted) setExtraResult({ key, values: null, failed: true }); });
		return () => controller.abort();
	}, [place, lunar]);

	// Continent and country come from a bundled Natural Earth extract: no key,
	// no quota, and it still answers over Antarctica and ice shelves.
	useEffect(() => {
		if (!place) return;
		let alive = true;
		loadCountries()
			.then((features) => {
				if (alive) setWhere(locate(features, place.lat, place.lng));
			})
			.catch(() => {
				if (alive) setWhere(null);
			});
		return () => {
			alive = false;
		};
	}, [place]);

	useEffect(() => {
		if (!place) return;
		const controller = new AbortController();
		const params = new URLSearchParams({
			lat: String(place.lat),
			lon: String(place.lng),
		});
		fetch(`${SEARCH_API}/cell?${params}`, { signal: controller.signal })
			.then(async (response) => {
				const body = (await response.json()) as EarthCell & { error?: string };
				if (!response.ok) throw new Error(body.error || 'Cell data request failed');
				setCell(body);
			})
			.catch(() => {
				if (controller.signal.aborted) return;
				setCellError(true);
			});
		return () => controller.abort();
	}, [place]);

	useEffect(() => {
		if (!place) return;
		const controller = new AbortController();
		let objectUrl = '';
		const params = new URLSearchParams({
			lat: String(place.lat),
			lon: String(place.lng),
		});
		fetch(`${SEARCH_API}/scene?${params}`, { signal: controller.signal })
			.then(async (response) => {
				if (!response.ok) throw new Error('sin imagen');
				const blob = await response.blob();
				if (!blob.type.startsWith('image/')) throw new Error('sin imagen');
				objectUrl = URL.createObjectURL(blob);
				setSceneUrl(objectUrl);
				setSceneSource(response.headers.get('X-Image-Source') || 'esri');
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				setImageError(true);
				if (error instanceof Error && error.name !== 'AbortError') return;
			});
		return () => {
			controller.abort();
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, [place]);

	const mapsUrl = place
		? `https://www.google.com/maps/@${place.lat},${place.lng},400m/data=!3m1!1e3`
		: '';

	return (
		<aside className={`detail-panel ${place ? 'open' : ''}`} aria-hidden={!place}>
			{place && (
				<>
					<header className="detail-head">
						<h3>{copy.point}</h3>
							<button type="button" onClick={onClose}>{copy.close}</button>
					</header>
					<div className="scene-frame">
						{imageError ? (
							<p className="muted">{copy.noSatelliteImage}</p>
						) : sceneUrl ? (
							<img
								src={sceneUrl}
								alt={copy.satelliteView(place.lat.toFixed(2), place.lng.toFixed(2))}
								onError={() => setImageError(true)}
							/>
						) : (
							<p className="muted">{copy.loadingImage}</p>
						)}
						{sceneUrl && !imageError && <span className="scene-mark" />}
					</div>
					<p className="scene-credit">
						{sceneSource === 'google' ? copy.googleSatellite : copy.esriSatellite}
					</p>
					<p className="scene-links">
						<a href={mapsUrl} target="_blank" rel="noreferrer">{copy.viewGoogleMaps}</a>
					</p>
					{lunar && <p className="muted">{({ es: 'Datos terrestres complementarios: WorldClim, hielo y litología son contexto y no participan en la comparación lunar.', en: 'Additional Earth data: WorldClim, ice and lithology are context and do not contribute to the lunar comparison.', fr: 'Données terrestres complémentaires : WorldClim, glace et lithologie sont contextuels et ne participent pas à la comparaison lunaire.', it: 'Dati terrestri aggiuntivi: WorldClim, ghiaccio e litologia sono contestuali e non partecipano al confronto lunare.' })[language]}</p>}
					<dl className="cell-facts">
						{where !== undefined && (
							<>
								<div>
									<dt>{copy.continent}</dt>
									<dd>
										{where === null
											? copy.openOcean
											: (copy.continentNames[where.continent ?? ''] ?? where.continent ?? copy.noData)}
										{where?.approximate ? ` · ${copy.nearby}` : ''}
									</dd>
								</div>
								<div>
									<dt>{copy.country}</dt>
									<dd>{where?.country ?? copy.noCountry}</dd>
								</div>
							</>
						)}
						<div>
							<dt>{copy.latitude}</dt>
							<dd>{(cell?.lat ?? place.lat).toFixed(4)}</dd>
						</div>
						<div>
							<dt>{copy.longitude}</dt>
							<dd>{(cell?.lon ?? place.lng).toFixed(4)}</dd>
						</div>
						{place.closeness !== undefined && (
							<>
								<div>
									<dt>{copy.closeness}</dt>
									<dd>
										{place.grade && <span className={`grade grade-${place.grade}`}>{place.grade}</span>}
										{lunar ? (place.closeness * 100).toFixed(2) : percent(place.closeness, 2)}%
									</dd>
								</div>
								{variables.length > 0 && (
									<div>
										<dt>{copy.coverage}</dt>
										<dd>{copy.coverageOf(String(place.coverage ?? 0), String(variables.length))}</dd>
									</div>
								)}
								{place.worst !== undefined && variables.length > 1 && (
									<div>
										<dt>{copy.worstVariable}</dt>
										<dd>{percent(place.worst, 1)}%</dd>
									</div>
								)}
							</>
						)}
						<div>
							<dt>{copy.elevation}</dt>
							<dd>{cell ? formatMeters(cell.elevation_m, copy.noData) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.slope}</dt>
							<dd>{cell ? `${cell.slope_deg.toFixed(2)}°` : '…'}</dd>
						</div>
						<div>
							<dt>{copy.roughness}</dt>
							<dd>{cell ? formatMeters(cell.roughness_m, copy.noData, 1) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.coldNight}</dt>
							<dd>{cell ? (cell.tmin_c === null ? copy.noData : `${cell.tmin_c.toFixed(1)} °C`) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.ice}</dt>
							<dd>{cell ? formatMeters(cell.ice_thickness_m, copy.noData) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.rock}</dt>
							<dd>{cell ? `${copy.rocks[cell.rock] ?? cell.rock} (${cell.rock})` : '…'}</dd>
						</div>
					</dl>
					{lunar && <section className="compare">
						<h4>{({ es: 'Mediciones adicionales · enero 2025', en: 'Additional measurements · January 2025', fr: 'Mesures supplémentaires · janvier 2025', it: 'Misure aggiuntive · gennaio 2025' })[language]}</h4>
						<p>{extra.scope} {extraStatus === 'loading' ? extra.loading : extraStatus === 'failed' ? extra.failed : ''}</p>
						<p>{extra.modis}: {extra.lunar} TBOL {lunar.sample.measurements.bolometric_temperature?.value ?? extra.pending} K · {extra.earth} {extraValue(additional?.surface_temperature_modis, extra.pending, language)} · {extra.approx}, {place.scores?.tbol_modis === undefined ? extra.noScore : `${(place.scores.tbol_modis * 100).toFixed(1)}%`}.</p>
						<p>{extra.era}: {extra.lunar} TREG {lunar.sample.measurements.regolith_temperature?.value ?? extra.pending} K · {extra.earth} {extraValue(additional?.soil_temperature_0_to_7cm, extra.pending, language)} · {place.scores?.treg_era5 === undefined ? extra.context : lunarSearchCopy[language].indirect}, {place.scores?.treg_era5 === undefined ? extra.noScore : `${(place.scores.treg_era5 * 100).toFixed(1)}%`}.</p>
						<p>{extra.soil}: {extra.lunar} RA {lunar.sample.measurements.rock_abundance?.value ?? extra.pending} · {extra.earth} {extraValue(additional?.coarse_fragments_0_to_5cm, extra.pending, language)} · {extra.context}, {extra.noScore}.</p>
						<p>Lunar Prospector H: {lunar.sample.measurements.hydrogen_abundance_ppm?.value ?? extra.pending} ppm · {extra.noScore}.</p>
					</section>}
					{place.scores && Object.keys(place.scores).length > 0 && (
						<section className="compare">
							<h4>{copy.compare}</h4>
							<div className="compare-head">
								<span />
								<span>{copy.reference}</span>
								<span>{copy.earthColumn}</span>
								<span>{copy.differsBy}</span>
							</div>
							{variables.map((variable) => {
								const earth = variable.id === 'tbol_modis' ? additional?.surface_temperature_modis?.value ?? null : variable.id === 'treg_era5' ? additional?.soil_temperature_0_to_7cm?.value ?? null : place.measurements?.[variable.id]?.value ?? (cell ? cellValue(cell, variable.id) : null);
								const delta = place.deltas?.[variable.id];
								return (
									<div className="compare-row" key={variable.id}>
										<span className="compare-name">{variableLabel(copy, variable.id)}</span>
										<span className="compare-reference">
											{formatValue(place.target?.[variable.id], variable.unit)}
										</span>
										<span className="compare-earth">
											{cell || place.measurements?.[variable.id] || variable.id === 'tbol_modis' || variable.id === 'treg_era5'
												? formatValue(earth, variable.unit) || copy.noData
												: '…'}
										{lunar && typeof earth === 'number' && <small> ({earth} {variable.unit ?? ''})</small>}
										</span>
										<span className="compare-differs">
											{typeof delta === 'number'
												? formatDelta(delta, variable.unit)
												: cell
													? '—'
													: '…'}
										</span>
									</div>
								);
							})}
						</section>
					)}
					{place.scores && Object.keys(place.scores).length > 0 && (() => {
						const slices = breakdownSlices(variables, place.scores, copy, place.weighted_shares);
						return (
						<section className="breakdown">
							<h4>{copy.breakdown}</h4>
							{lunar && <p className="muted">{lunarSearchCopy[language].weight}: {variables.map(v => `${variableLabel(copy, v.id)} ${v.weight ?? '—'}`).join(' · ')}</p>}
							{place.effective_weights && <p className="muted">{lunarSearchCopy[language].effective}: {Object.entries(place.effective_weights).map(([id, weight]) => `${variableLabel(copy, id)} ${(weight * 100).toFixed(1)}%`).join(' · ')}</p>}
							{slices.length > 0 && (
								<div className="breakdown-pie">
									<svg className="breakdown-pie-chart" viewBox="0 0 100 100" role="img" aria-hidden>
										{slices.map((slice) => (
											<path
												key={slice.id}
												d={pieWedgePath(50, 50, 42, slice.startDeg, slice.endDeg)}
												fill={slice.color}
												aria-label={copy.breakdownPieSlice(slice.name, slice.shareLabel)}
											/>
										))}
									</svg>
									<ul className="breakdown-pie-legend">
										{slices.map((slice) => {
											const variable = variables.find((v) => v.id === slice.id);
											const delta = place.deltas?.[slice.id];
											const showDelta =
												typeof delta === 'number' &&
												variable?.unit &&
												variable.unit !== 'class';
											return (
												<li key={slice.id}>
													<span
														className="breakdown-pie-swatch"
														style={{ backgroundColor: slice.color }}
														aria-hidden
													/>
													<div className="breakdown-pie-item">
														<div className="breakdown-pie-item-row">
															<span className="breakdown-pie-label">{slice.name}</span>
															<span className="breakdown-pie-share">{slice.shareLabel}%</span>
														</div>
														<div className="breakdown-pie-meta">
															<span className="breakdown-pie-similarity">
																{copy.similarity}: {slice.similarityLabel}%
															</span>
															{showDelta && (
																<span className="breakdown-pie-delta">
																	{copy.differsBy} {formatDelta(delta, variable.unit)}
																</span>
															)}
														</div>
													</div>
												</li>
											);
										})}
									</ul>
								</div>
							)}
							{variables.some((variable) => place.scores?.[variable.id] === undefined) && (
								<ul>
									{variables
										.filter((variable) => place.scores?.[variable.id] === undefined)
										.map((variable) => {
											const name = variableLabel(copy, variable.id);
											return (
												<li key={variable.id}>
													<span className="breakdown-name">{name}</span>
													<span>{copy.noData}</span>
												</li>
											);
										})}
								</ul>
							)}
							{variables.some((variable) => variable.tier === 'C') && (
								<p className="muted warn">{copy.unalikeWarning}</p>
							)}
						</section>
						);
					})()}
					{place.activity && (
						<p className="muted activity-line">
							{copy.activityLabel}:{' '}
							{activities.find((activity) => activity.id === place.activity)?.serves[language]
								?? place.activity}
						</p>
					)}
					{cellError && <p className="muted">{copy.cellError}</p>}
					{cell && cell.distance_km > 1.5 && (
						<p className="muted">{copy.nearestCellDistance(cell.distance_km.toFixed(1))}</p>
					)}
					<p className="muted limitations">{lunar ? lunarSearchCopy[language].limitations : copy.limitations}</p>
					{place.quality_warnings?.map(warning => <p className="muted warn" key={warning}>{warning}</p>)}
				</>
			)}
		</aside>
	);
}
