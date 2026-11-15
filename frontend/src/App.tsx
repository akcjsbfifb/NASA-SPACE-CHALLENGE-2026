import { useEffect, useRef, useState } from 'react';

import InteractiveGlobe from './components/Globe/InteractiveGlobe';
import MoonPage from './components/MoonPage';
import type { EarthAnalog, EarthAnalogSet, LunarSelection } from './components/MoonPage';
import PointPanel from './components/PointPanel';
import PrecisionDial from './components/PrecisionDial';
import type { SelectedPlace } from './components/PointPanel';

import type {
	GlobeController,
} from './components/Globe/globe.controller';

import type {
	GlobeClickEvent,
	GlobePoint,
} from './components/Globe/globe.types';

import { SEARCH_API } from './searchApi';
import { subscribeSearchEvents } from './searchEvents';
import { getCopy, isAudience, isLanguage } from './i18n';
import type { Audience, Language } from './i18n';

import { percent, worstDelta } from './score';
import type { ActivityPreset, Grade, MatchLevel, ScoreDetail, VariableInfo } from './score';

import {
	SELECTED_ALTITUDE,
	SELECTED_COLOR,
	SELECTED_FLY_ALTITUDE,
	SELECTED_FLY_MS,
	SELECTED_PIN_SIZE,
} from './theme';

import './App.css';

const ROCKS = ['vb', 'va', 'vi', 'py', 'pb', 'pa', 'pi', 'su', 'ss', 'sm', 'sc', 'mt', 'ev', 'ig'] as const;

const WEIGHT_KEYS = ['slope', 'roughness', 'temperature', 'ice', 'rock'] as const;

type WeightKey = (typeof WEIGHT_KEYS)[number];

type Weights = Record<WeightKey, number>;

const NEUTRAL_WEIGHTS: Weights = { slope: 1, roughness: 1, temperature: 1, ice: 1, rock: 1 };

type Included = Record<WeightKey, boolean>;

const ALL_INCLUDED: Included = { slope: true, roughness: true, temperature: true, ice: true, rock: true };

const ROUGHNESS_ONLY_INCLUDED: Included = {
	slope: false,
	roughness: true,
	temperature: false,
	ice: false,
	rock: false,
};

function anyIncluded(included: Included): boolean {
	return WEIGHT_KEYS.some((key) => included[key]);
}

type SearchSummary =
	| { type: 'initial' }
	| { type: 'searching' }
	| { type: 'no-results'; closeness: number }
	| { type: 'results'; count: number; lowest: number; highest: number; relativeCold: boolean }
	| { type: 'offline' }
	| { type: 'failed' };

type SearchPoint = ScoreDetail & {
	lat: number;
	lon: number;
	rock: string;
	match?: MatchLevel;
	grade?: Grade;
	grades?: Record<string, Grade>;
	target?: Record<string, number | string | null>;
	activity?: string | null;
};

type SearchResponse = {
	returned: number;
	min_closeness: number;
	closest: number | null;
	loosest: number | null;
	temperature_mode?: string;
	precision?: number;
	points: SearchPoint[];
	target?: Record<string, number | string | null>;
	variables_used?: VariableInfo[];
	variables?: VariableInfo[];
	ignored?: string[];
	weights?: Record<string, number | null>;
	activity?: { id: string } | null;
};

function text(value: unknown): string {
	return typeof value === 'number' ? String(value) : '';
}

function pageFromHash(): 'moon' | 'earth' {
	return window.location.hash === '#luna' ? 'moon' : 'earth';
}

/** The server decides the cut; the list, the globe and the panel share it. */
function colorFor(match: MatchLevel | undefined) {
	if (match === 'very') return '#7dffe1';
	if (match === 'close') return '#f0c14a';
	return '#e07a4a';
}

function toGlobePoint(point: SearchPoint, rockLabel: string): GlobePoint {
	return {
		id: `${point.lat},${point.lon}`,
		lat: point.lat,
		lng: point.lon,
		label: `${rockLabel} · ${(point.closeness * 100).toFixed(0)}%`,
		color: colorFor(point.match),
		size: 0.12 + point.closeness * 0.1,
		altitude: 0.01,
	};
}

function App() {
	const globe = useRef<GlobeController>(null);

	const [page, setPage] = useState<'moon' | 'earth'>(pageFromHash);
	const [language, setLanguage] = useState<Language>('es');
	const [audience, setAudience] = useState<Audience>('profesional');
	const [preferenceReady, setPreferenceReady] = useState(false);
	const copy = getCopy(language);
	const [location, setLocation] = useState<GlobeClickEvent | null>(null);

	const [visibleLayers] = useState({
		points: true,
		heatmaps: false,
		polygons: false,
		labels: true,
	});

	const [slope, setSlope] = useState('8');
	const [roughness, setRoughness] = useState('30');
	const [tmin, setTmin] = useState('-20');
	const [ice, setIce] = useState('0');
	const [rock, setRock] = useState('vb');
	const [precision, setPrecision] = useState(0.75);
	const [weights, setWeights] = useState<Weights>(NEUTRAL_WEIGHTS);
	const [included, setIncluded] = useState<Included>(ALL_INCLUDED);
	const [activities, setActivities] = useState<ActivityPreset[]>([]);
	const [points, setPoints] = useState<SearchPoint[]>([]);
	const [variables, setVariables] = useState<VariableInfo[]>([]);
	const [summary, setSummary] = useState<SearchSummary>({ type: 'initial' });
	const [busy, setBusy] = useState(false);
	const [selection, setSelection] = useState<SelectedPlace | null>(null);

	function openPage(next: 'moon' | 'earth') {
		setPage(next);
		const hash = next === 'moon' ? '#luna' : '#tierra';
		if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
	}

	useEffect(() => {
		const onHash = () => setPage(pageFromHash());
		window.addEventListener('hashchange', onHash);
		return () => window.removeEventListener('hashchange', onHash);
	}, []);
	useEffect(() => {
		document.documentElement.lang = language;
		document.title = copy.pageTitle;
	}, [copy.pageTitle, language]);
	useEffect(() => {
		const storedLanguage = localStorage.getItem('artemis.language');
		const storedAudience = localStorage.getItem('artemis.audience');
		if (storedLanguage && isLanguage(storedLanguage)) setLanguage(storedLanguage);
		if (storedAudience && isAudience(storedAudience)) setAudience(storedAudience);
		setPreferenceReady(true);
	}, []);
	useEffect(() => {
		if (!preferenceReady) return;
		localStorage.setItem('artemis.language', language);
		localStorage.setItem('artemis.audience', audience);
		fetch(`${SEARCH_API}/audience`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ audience, language }),
		}).catch(() => {});
	}, [preferenceReady, audience, language]);

	// The catalog is the only source of activity labels: no `activity.<id>` keys.
	useEffect(() => {
		let alive = true;
		fetch(`${SEARCH_API}/activities`)
			.then(async (response) => {
				const body = (await response.json()) as { activities?: ActivityPreset[] };
				if (!response.ok) throw new Error('Activities request failed');
				if (alive) setActivities(body.activities ?? []);
			})
			.catch(() => {
				if (alive) setActivities([]);
			});
		return () => {
			alive = false;
		};
	}, []);

	const summaryText = (() => {
		switch (summary.type) {
			case 'initial':
				return copy.initialSummary;
			case 'searching':
				return copy.searchingSummary;
			case 'no-results':
				return copy.noResults(percent(summary.closeness, 1));
			case 'results':
				return copy.resultSummary(
					summary.count,
					percent(summary.lowest, 1),
					percent(summary.highest, 1),
				) + (summary.relativeCold ? copy.relativeColdNote : '');
			case 'offline':
				return copy.serverOffline;
			case 'failed':
				return copy.searchFailed;
		}
	})();

	function selectPlace(lat: number, lng: number, point?: SearchPoint) {
		setLocation({ lat, lng, altitude: 0 });
		setSelection(
			point
				? {
					lat: point.lat,
					lng: point.lon,
					closeness: point.closeness,
					coverage: point.coverage,
					worst: point.worst,
					scores: point.scores,
					grades: point.grades,
					grade: point.grade,
					deltas: point.deltas,
					target: point.target,
					activity: point.activity ?? null,
				}
				: { lat, lng },
		);
	}

	useEffect(() => {
		globe.current?.setPoints(
			'analogs',
			visibleLayers.points
				? points.map(point => toGlobePoint(point, copy.rocks[point.rock] ?? point.rock))
				: [],
		);
	}, [copy, points, visibleLayers.points]);

	// One pin on its own layer, and the camera turns to face it. Running
	// this on `page` too covers arriving from the Moon page, where the globe
	// mounts after the selection already exists.
	useEffect(() => {
		if (page !== 'earth' || !selection) {
			globe.current?.setMarkers('selected', []);
			return;
		}
		globe.current?.setMarkers('selected', [
			{
				id: 'selected',
				lat: selection.lat,
				lng: selection.lng,
				label: '',
				color: SELECTED_COLOR,
				size: SELECTED_PIN_SIZE,
				altitude: SELECTED_ALTITUDE,
			},
		]);
		globe.current?.flyTo(
			{ lat: selection.lat, lng: selection.lng, altitude: SELECTED_FLY_ALTITUDE },
			SELECTED_FLY_MS,
		);
	}, [page, selection]);

	function applySearchResult(body: SearchResponse) {
		// Every point keeps the reference it was searched against, so the panel
		// shows the target of that search and not the inputs of a later one.
		const activity = body.activity?.id ?? null;
		setPoints(body.points.map((point) => ({ ...point, target: body.target, activity })));
		const usedList = body.variables_used ?? body.variables;
		setVariables(usedList ?? []);
		if (usedList && usedList.length > 0) {
			const usedIds = new Set(usedList.map((variable) => variable.id));
			setIncluded({
				slope: usedIds.has('slope'),
				roughness: usedIds.has('roughness'),
				temperature: usedIds.has('temperature'),
				ice: usedIds.has('ice'),
				rock: usedIds.has('rock'),
			});
		}
		if (body.precision !== undefined) setPrecision(body.precision);
		// A null weight means the variable had no target: the slider stays where
		// the user left it. A number, 0 included, is the weight the server used.
		const resultWeights = body.weights;
		if (resultWeights) {
			setWeights((current) => {
				const next = { ...current };
				for (const key of WEIGHT_KEYS) {
					const value = resultWeights[key];
					if (typeof value === 'number') next[key] = value;
				}
				return next;
			});
		}
		const target = body.target;
		if (target) {
			if (target.slope != null) setSlope(text(target.slope));
			if (target.roughness != null) setRoughness(text(target.roughness));
			if (target.temperature != null) setTmin(text(target.temperature));
			if (target.ice != null) setIce(text(target.ice));
			if (target.rock != null) setRock(String(target.rock));
		}
		setSummary(body.returned === 0
			? { type: 'no-results', closeness: body.min_closeness }
			: {
				type: 'results',
				count: body.returned,
				lowest: body.loosest ?? 0,
				highest: body.closest ?? 0,
				relativeCold: body.temperature_mode === 'relative_cold',
			});
	}

	const applySearchResultRef = useRef(applySearchResult);
	applySearchResultRef.current = applySearchResult;

	useEffect(() => {
		return subscribeSearchEvents((body) => {
			applySearchResultRef.current(body as SearchResponse);
		});
	}, []);

	async function search() {
		if (!anyIncluded(included)) return;
		setBusy(true);
		setSummary({ type: 'searching' });
		const params = new URLSearchParams({ precision: String(precision) });
		if (included.slope) {
			params.set('slope', slope);
			if (weights.slope !== 1) params.set('w_slope', String(weights.slope));
		}
		if (included.roughness) {
			params.set('roughness', roughness);
			if (weights.roughness !== 1) params.set('w_roughness', String(weights.roughness));
		}
		if (included.temperature) {
			params.set('tmin', tmin);
			if (weights.temperature !== 1) params.set('w_temperature', String(weights.temperature));
		}
		if (included.ice) {
			params.set('ice', ice);
			if (weights.ice !== 1) params.set('w_ice', String(weights.ice));
		}
		if (included.rock) {
			params.set('rock', rock);
			if (weights.rock !== 1) params.set('w_rock', String(weights.rock));
		}
		try {
			const response = await fetch(`${SEARCH_API}/search?${params}`);
			const body = (await response.json()) as SearchResponse;
			if (!response.ok) throw new Error('Search request failed');
			applySearchResult(body);
		} catch (error) {
			setSummary(error instanceof TypeError ? { type: 'offline' } : { type: 'failed' });
		} finally {
			setBusy(false);
		}
	}

	function compareFromMoon(
		lunar: LunarSelection,
		analogs: EarthAnalogSet | null,
		chosen?: EarthAnalog,
	) {
		if (lunar.sample.roughness === null) return;
		setSlope('');
		setTmin('');
		setIce('');
		setRock('');
		setRoughness(String(lunar.sample.roughness));
		setIncluded(ROUGHNESS_ONLY_INCLUDED);
		// The analog the user clicked in the Moon panel keeps its red marker on
		// Earth. The footer button has no specific row, so it falls back to the
		// closest point of the set.
		const picked = chosen ?? analogs?.points[0];
		setSelection(picked ? { lat: picked.lat, lng: picked.lon, closeness: picked.closeness } : null);
		setLocation(picked ? { lat: picked.lat, lng: picked.lon, altitude: 0 } : null);
		openPage('earth');
		if (analogs) {
			applySearchResult(analogs);
			return;
		}
		const params = new URLSearchParams({
			roughness: String(lunar.sample.roughness),
			precision: String(precision),
		});
		setBusy(true);
		setSummary({ type: 'searching' });
		void fetch(`${SEARCH_API}/search?${params}`)
			.then(async (response) => {
				const body = (await response.json()) as SearchResponse;
				if (!response.ok) throw new Error('Search request failed');
				applySearchResult(body);
			})
			.catch((error: unknown) => {
				setSummary(error instanceof TypeError ? { type: 'offline' } : { type: 'failed' });
			})
			.finally(() => setBusy(false));
	}

	const weightNames: Record<WeightKey, string> = {
		slope: copy.slope,
		roughness: copy.roughness,
		temperature: copy.nightTemperature,
		ice: copy.ice,
		rock: copy.rock,
	};

	const includeLabels: Record<WeightKey, string> = {
		slope: copy.includeSlope,
		roughness: copy.includeRoughness,
		temperature: copy.includeTemperature,
		ice: copy.includeIce,
		rock: copy.includeRock,
	};

	function toggleIncluded(key: WeightKey, on: boolean) {
		setIncluded((current) => ({ ...current, [key]: on }));
	}

	const matchLabels: Record<MatchLevel, string> = {
		very: copy.matchVery,
		close: copy.matchClose,
		barely: copy.matchBarely,
	};

	return (
		<main className="app">
		<header className="topbar">
		<strong className="brand">ARTEMIS</strong>
		<nav className="page-nav" aria-label="Cuerpo">
			<button type="button" aria-current={page === 'moon' ? 'page' : undefined} onClick={() => openPage('moon')}>
				Luna
			</button>
			<button type="button" aria-current={page === 'earth' ? 'page' : undefined} onClick={() => openPage('earth')}>
				Tierra
			</button>
		</nav>
			<div className="language-selects">
			<select
				className="language-select"
				aria-label={copy.language}
				value={language}
				onChange={(event) => {
					const selectedLanguage = event.target.value;
					if (isLanguage(selectedLanguage)) setLanguage(selectedLanguage);
				}}
			>
				<option value="es">Español</option>
				<option value="en">English</option>
				<option value="fr">Français</option>
				<option value="it">Italiano</option>
			</select>
			<select
				className="language-select"
				aria-label={copy.audience}
				value={audience}
				onChange={(event) => {
					const selectedAudience = event.target.value;
					if (isAudience(selectedAudience)) setAudience(selectedAudience);
				}}
			>
				<option value="profesional">{copy.audienceProfesional}</option>
				<option value="aficionado">{copy.audienceAficionado}</option>
			</select>
			</div>
		</header>

		<div className="workspace">
		{page === 'moon' ? (
			<MoonPage precision={precision} onCompare={compareFromMoon} />
		) : (
		<>

		<aside className="sidebar">
		<section className="sidebar-section">
		<h4>{copy.objective}</h4>
		<p className="muted">{copy.objectiveDescription}</p>

		<label className="field">
			<span className="field-header">
				<span>{copy.slope} (°)</span>
				<input
					type="checkbox"
					role="switch"
					className="var-switch"
					checked={included.slope}
					aria-label={includeLabels.slope}
					onChange={(event) => toggleIncluded('slope', event.target.checked)}
				/>
			</span>
			<input
				value={slope}
				disabled={!included.slope}
				onChange={(event) => setSlope(event.target.value)}
				inputMode="decimal"
			/>
		</label>
		<label className="field">
			<span className="field-header">
				<span>{copy.roughness} (m)</span>
				<input
					type="checkbox"
					role="switch"
					className="var-switch"
					checked={included.roughness}
					aria-label={includeLabels.roughness}
					onChange={(event) => toggleIncluded('roughness', event.target.checked)}
				/>
			</span>
			<input
				value={roughness}
				disabled={!included.roughness}
				onChange={(event) => setRoughness(event.target.value)}
				inputMode="decimal"
			/>
		</label>
		<label className="field">
			<span className="field-header">
				<span>{copy.nightTemperature} (°C)</span>
				<input
					type="checkbox"
					role="switch"
					className="var-switch"
					checked={included.temperature}
					aria-label={includeLabels.temperature}
					onChange={(event) => toggleIncluded('temperature', event.target.checked)}
				/>
			</span>
			<input
				value={tmin}
				disabled={!included.temperature}
				onChange={(event) => setTmin(event.target.value)}
				inputMode="decimal"
			/>
		</label>
		<label className="field">
			<span className="field-header">
				<span>{copy.ice} (m)</span>
				<input
					type="checkbox"
					role="switch"
					className="var-switch"
					checked={included.ice}
					aria-label={includeLabels.ice}
					onChange={(event) => toggleIncluded('ice', event.target.checked)}
				/>
			</span>
			<input
				value={ice}
				disabled={!included.ice}
				onChange={(event) => setIce(event.target.value)}
				inputMode="decimal"
			/>
		</label>
		<label className="field">
			<span className="field-header">
				<span>{copy.rock}</span>
				<input
					type="checkbox"
					role="switch"
					className="var-switch"
					checked={included.rock}
					aria-label={includeLabels.rock}
					onChange={(event) => toggleIncluded('rock', event.target.checked)}
				/>
			</span>
			<select value={rock} disabled={!included.rock} onChange={(event) => setRock(event.target.value)}>
			{ROCKS.map((code) => (
				<option key={code} value={code}>{copy.rocks[code]}</option>
			))}
		</select>
		</label>
		<div className="weight-group">
			<span className="weight-label">{copy.weight}</span>
			{WEIGHT_KEYS.map((key) => (
				<label className="weight-row" key={key}>
					<span className="weight-name">{weightNames[key]}</span>
					<input
						type="range"
						min={0}
						max={1}
						step={0.1}
						disabled={!included[key]}
						value={weights[key]}
						onChange={(event) => {
							const value = Number(event.target.value);
							setWeights((current) => ({ ...current, [key]: value }));
						}}
					/>
				</label>
			))}
		</div>
		<div className="precision-control">
			<span className="precision-label">{copy.precision}</span>
			<PrecisionDial
				value={Math.round(precision * 100)}
				label={copy.precision}
				onChange={(value) => setPrecision(value / 100)}
			/>
			<div className="range-labels">
				<span>{copy.morePlaces}</span>
				<span>{copy.morePrecise}</span>
			</div>
		</div>
			<button type="button" onClick={search} disabled={busy || !anyIncluded(included)}>
			{busy ? copy.searching : copy.searchAnalogs}
			</button>
			<p className="muted search-summary">{summaryText}</p>
			<div className="result-list">
				{points.slice(0, 6).map((point) => {
					const delta = worstDelta(point, variables);
					const match = point.match ? matchLabels[point.match] ?? '' : '';
					return (
					<button
					key={`${point.lat},${point.lon}`}
					type="button"
					onClick={() => selectPlace(point.lat, point.lon, point)}
					>
					{percent(point.closeness, 1)}% · {point.lat.toFixed(2)}, {point.lon.toFixed(2)}
					{delta ? ` · ${delta}` : ''}
					{match ? ` · ${match}` : ''}
					</button>
					);
				})}
			</div>
		</section>

		{/* <section className="sidebar-section">
			<h4>{copy.visualizationLayers}</h4>

			<label>
				<input type="checkbox" checked={visibleLayers.points} onChange={() => toggleLayer('points')} /> {copy.locations}
			</label>

			<label>
				<input type="checkbox" checked={visibleLayers.heatmaps} onChange={() => toggleLayer('heatmaps')} /> {copy.heatmap}
			</label>

			<label>
				<input type="checkbox" checked={visibleLayers.polygons} onChange={() => toggleLayer('polygons')} /> {copy.areas}
			</label>

			<label>
				<input type="checkbox" checked={visibleLayers.labels} onChange={() => toggleLayer('labels')} /> {copy.labels}
			</label>

		</section>
 */}	

		<section className="sidebar-section">
			<h4>{copy.selectedPoint}</h4>

			{location ? (<>
				<p>{copy.latitude}: {location.lat.toFixed(5)}</p>
				<p>{copy.longitude}: {location.lng.toFixed(5)}</p>
			</>) : (<p>{copy.noPointSelected}</p>)}
		</section>

		</aside>

		<section className="globe-container">
			<InteractiveGlobe ref={globe} onLocationSelect={(coords) => selectPlace(coords.lat, coords.lng)} onPointSelect={(point) => {
				const hit = points.find(
					(item) => Math.abs(item.lat - point.lat) < 0.001 && Math.abs(item.lon - point.lng) < 0.001,
				);
				selectPlace(point.lat, point.lng, hit); }} />
			<PointPanel place={selection} onClose={() => setSelection(null)} language={language} variables={variables} activities={activities} />
		</section>

		</>
		)}

		</div>
		</main>
	);
}

export default App;
