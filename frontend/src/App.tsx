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

import { getCopy, isLanguage } from './i18n';
import type { Language } from './i18n';

import { primaryDelta, truncated } from './score';
import type { ScoreDetail, VariableInfo } from './score';

import {
	SELECTED_ALTITUDE,
	SELECTED_COLOR,
	SELECTED_FLY_ALTITUDE,
	SELECTED_FLY_MS,
	SELECTED_SIZE,
} from './theme';

import './App.css';

const ROCKS = ['vb', 'va', 'vi', 'py', 'pb', 'pa', 'pi', 'su', 'ss', 'sm', 'sc', 'mt', 'ev', 'ig'] as const;

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
	ignored?: string[];
};

function text(value: unknown): string {
	return typeof value === 'number' ? String(value) : '';
}

function pageFromHash(): 'moon' | 'earth' {
	return window.location.hash === '#luna' ? 'moon' : 'earth';
}

function colorFor(closeness: number) {
	if (closeness >= 0.8) return '#7dffe1';
	if (closeness >= 0.65) return '#f0c14a';
	return '#e07a4a';
}

function toGlobePoint(point: SearchPoint, rockLabel: string): GlobePoint {
	return {
		id: `${point.lat},${point.lon}`,
		lat: point.lat,
		lng: point.lon,
		label: `${rockLabel} · ${(point.closeness * 100).toFixed(0)}%`,
		color: colorFor(point.closeness),
		size: 0.12 + point.closeness * 0.1,
		altitude: 0.01,
	};
}

function App() {
	const globe = useRef<GlobeController>(null);

	const [page, setPage] = useState<'moon' | 'earth'>(pageFromHash);
	const [language, setLanguage] = useState<Language>('es');
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

	const summaryText = (() => {
		switch (summary.type) {
			case 'initial':
				return copy.initialSummary;
			case 'searching':
				return copy.searchingSummary;
			case 'no-results':
				return copy.noResults(truncated(summary.closeness, 1));
			case 'results':
				return copy.resultSummary(
					summary.count,
					truncated(summary.lowest, 1),
					truncated(summary.highest, 1),
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
					deltas: point.deltas,
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

	// One red marker on its own layer, and the camera turns to face it. Running
	// this on `page` too covers arriving from the Moon page, where the globe
	// mounts after the selection already exists.
	useEffect(() => {
		if (page !== 'earth' || !selection) {
			globe.current?.setPoints('selected', []);
			return;
		}
		globe.current?.setPoints('selected', [
			{
				id: 'selected',
				lat: selection.lat,
				lng: selection.lng,
				label: '',
				color: SELECTED_COLOR,
				size: SELECTED_SIZE,
				altitude: SELECTED_ALTITUDE,
			},
		]);
		globe.current?.flyTo(
			{ lat: selection.lat, lng: selection.lng, altitude: SELECTED_FLY_ALTITUDE },
			SELECTED_FLY_MS,
		);
	}, [page, selection]);

	function applySearchResult(body: SearchResponse) {
		setPoints(body.points);
		setVariables(body.variables_used ?? []);
		if (body.precision !== undefined) setPrecision(body.precision);
		const target = body.target;
		if (target) {
			setSlope(text(target.slope));
			setRoughness(text(target.roughness));
			setTmin(text(target.temperature));
			setIce(text(target.ice));
			setRock(target.rock != null ? String(target.rock) : '');
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

	useEffect(() => {
		let events: EventSource | null = null;
		let stopped = false;
		const connect = () => {
			if (stopped) return;
			events = new EventSource('http://127.0.0.1:8787/events');
			events.onmessage = (event) => {
				applySearchResult(JSON.parse(event.data) as SearchResponse);
			};
			events.onerror = () => {
				if (!events || events.readyState !== EventSource.CLOSED) return;
				window.setTimeout(connect, 2000);
			};
		};
		connect();
		return () => {
			stopped = true;
			events?.close();
		};
	}, []);

	async function search() {
		setBusy(true);
		setSummary({ type: 'searching' });
		const params = new URLSearchParams({
			slope,
			roughness,
			tmin,
			ice,
			rock,
			precision: String(precision),
		});
		try {
			const response = await fetch(`http://127.0.0.1:8787/search?${params}`);
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
		void fetch(`http://127.0.0.1:8787/search?${params}`)
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

	return (
		<main className="app">
		<header className="topbar">
		<strong className="brand">ORBITAL</strong>
		<nav className="page-nav" aria-label="Cuerpo">
			<button type="button" aria-current={page === 'moon' ? 'page' : undefined} onClick={() => openPage('moon')}>
				Luna
			</button>
			<button type="button" aria-current={page === 'earth' ? 'page' : undefined} onClick={() => openPage('earth')}>
				Tierra
			</button>
		</nav>
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
			{copy.slope} (°)
			<input value={slope} onChange={(event) => setSlope(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
			{copy.roughness} (m)
			<input value={roughness} onChange={(event) => setRoughness(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
			{copy.nightTemperature} (°C)
			<input value={tmin} onChange={(event) => setTmin(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
			{copy.ice} (m)
			<input value={ice} onChange={(event) => setIce(event.target.value)} inputMode="decimal" />
		</label>
			<label className="field">
			{copy.rock}
			<select value={rock} onChange={(event) => setRock(event.target.value)}>
			{ROCKS.map((code) => (
				<option key={code} value={code}>{copy.rocks[code]}</option>
			))}
		</select>
		</label>
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
			<button type="button" onClick={search} disabled={busy}>
			{busy ? copy.searching : copy.searchAnalogs}
			</button>
			<p className="muted search-summary">{summaryText}</p>
			<div className="result-list">
				{points.slice(0, 6).map((point) => {
					const delta = primaryDelta(point, variables);
					return (
					<button
					key={`${point.lat},${point.lon}`}
					type="button"
					onClick={() => selectPlace(point.lat, point.lon, point)}
					>
					{truncated(point.closeness, 1)}% · {point.lat.toFixed(2)}, {point.lon.toFixed(2)}
					{delta ? ` · ${delta}` : ''}
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
			<PointPanel place={selection} onClose={() => setSelection(null)} language={language} variables={variables} />
		</section>

		</>
		)}

		</div>
		</main>
	);
}

export default App;
