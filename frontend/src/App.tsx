import { useEffect, useRef, useState } from 'react';

import InteractiveGlobe from './components/Globe/InteractiveGlobe';
import MoonPage from './components/MoonPage';
import type { EarthAnalogSet, LunarSelection } from './components/MoonPage';
import { listPreview } from './components/MoonPage';
import PointPanel from './components/PointPanel';
import type { SelectedPlace } from './components/PointPanel';

import type {
	GlobeController,
} from './components/Globe/globe.controller';

import type {
	GlobeClickEvent,
	GlobePoint,
} from './components/Globe/globe.types';

import './App.css';

const ROCKS = [
	['vb', 'basalto'],
	['va', 'volcánico ácido'],
	['vi', 'volcánico intermedio'],
	['py', 'piroclástico'],
	['pb', 'plutónico básico'],
	['pa', 'plutónico ácido'],
	['pi', 'plutónico intermedio'],
	['su', 'sedimento suelto'],
	['ss', 'sedimentaria'],
	['sm', 'sedimentaria mixta'],
	['sc', 'carbonato'],
	['mt', 'metamórfica'],
	['ev', 'evaporita'],
	['ig', 'hielo'],
] as const;

type SearchPoint = {
	lat: number;
	lon: number;
	closeness: number;
	roughness_m: number;
	rock: string;
};

type SearchResponse = {
	returned: number;
	min_closeness: number;
	closest: number | null;
	loosest: number | null;
	temperature_mode: string;
	points: SearchPoint[];
};

function colorFor(closeness: number) {
	if (closeness >= 0.8) return '#7dffe1';
	if (closeness >= 0.65) return '#f0c14a';
	return '#e07a4a';
}

function toGlobePoint(point: SearchPoint): GlobePoint {
	return {
		id: `${point.lat},${point.lon}`,
		lat: point.lat,
		lng: point.lon,
		label: `${point.rock} · ${(point.closeness * 100).toFixed(0)}%`,
		color: colorFor(point.closeness),
		size: 0.12 + point.closeness * 0.1,
		altitude: 0.01,
	};
}

type SearchInputs = {
	slope?: string;
	roughness?: string;
	tmin?: string;
	ice?: string;
	rock?: string;
	precision: number;
};

function pageFromHash(): 'moon' | 'earth' {
	return window.location.hash === '#luna' ? 'moon' : 'earth';
}

function App() {
	const globe = useRef<GlobeController>(null);

	const [page, setPage] = useState<'moon' | 'earth'>(pageFromHash);
	const [location, setLocation] = useState<GlobeClickEvent | null>(null);

	const [visibleLayers, setVisibleLayers] = useState({
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
	const [summary, setSummary] = useState('Elegí los 5 números del sitio lunar y buscá.');
	const [busy, setBusy] = useState(false);
	const [selection, setSelection] = useState<SelectedPlace | null>(null);
	const [lunarLabel, setLunarLabel] = useState<string | null>(null);
	const [lunarElevation, setLunarElevation] = useState<number | null>(null);
	const [roughnessOnly, setRoughnessOnly] = useState(false);

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

	function selectPlace(lat: number, lng: number, closeness?: number) {
		setLocation({ lat, lng, altitude: 0 });
		setSelection({ lat, lng, closeness });
	}

	function toggleLayer(layer: keyof typeof visibleLayers) {
		setVisibleLayers(previous => ({
			...previous,
			[layer]: !previous[layer],
		}));
	}

	useEffect(() => {
		if (page !== 'earth') return;
		globe.current?.setPoints(
			'analogs',
			visibleLayers.points ? points.map(toGlobePoint) : [],
		);
	}, [points, visibleLayers.points, page]);

	function leaveLunarQuery() {
		setLunarLabel(null);
		setLunarElevation(null);
		setRoughnessOnly(false);
		setSlope('8');
		setRoughness('30');
		setTmin('-20');
		setIce('0');
		setRock('vb');
		setPoints([]);
		setSummary('Elegí los 5 números del sitio lunar y buscá.');
	}

	function editField<T>(setter: (value: T) => void) {
		return (value: T) => {
			setLunarLabel(null);
			setRoughnessOnly(false);
			setLunarElevation(null);
			setter(value);
		};
	}

	function describe(
		body: Pick<SearchResponse, 'returned' | 'min_closeness' | 'closest' | 'loosest'> & {
			temperature_mode?: string;
		},
		originName: string | null,
	) {
		const tempNote =
			body.temperature_mode === 'relative_cold'
				? ' La temperatura lunar queda fuera del rango terrestre: el puntaje premia el frío relativo.'
				: '';
		const origin = originName ? ` Origen lunar: ${originName}.` : '';
		return body.returned === 0
			? `Ningún lugar llega a ${(body.min_closeness * 100).toFixed(0)}% de cercanía. Bajá la precisión.${origin}`
			: `${body.returned} lugares distintos, entre ${((body.loosest ?? 0) * 100).toFixed(0)}% y ${((body.closest ?? 0) * 100).toFixed(0)}% de cercanía.${tempNote}${origin}`;
	}

	async function search(override?: SearchInputs, originLabel?: string | null) {
		const query = override ?? (
			roughnessOnly
				? { roughness, precision }
				: { slope, roughness, tmin, ice, rock, precision }
		);
		const originName = originLabel === undefined ? lunarLabel : originLabel;
		setBusy(true);
		setSummary('Buscando en 82 millones de celdas…');
		const params = new URLSearchParams({ precision: String(query.precision) });
		for (const [key, value] of Object.entries(query)) {
			if (key === 'precision' || value === undefined || value === '') continue;
			params.set(key, String(value));
		}
		try {
			const response = await fetch(`http://127.0.0.1:8787/search?${params}`);
			const body = (await response.json()) as SearchResponse & { error?: string };
			if (!response.ok) throw new Error(body.error || 'la búsqueda falló');
			setPoints(body.points);
			setSummary(describe(body, originName));
		} catch (error) {
			const offline = error instanceof TypeError;
			setSummary(
				offline
					? 'No llega al servidor de búsqueda (puerto 8787). En la raíz del repo: .venv/bin/python scripts/serve_search.py'
					: error instanceof Error
						? error.message
						: 'no se pudo buscar',
			);
		} finally {
			setBusy(false);
		}
	}

	function compareFromMoon(lunar: LunarSelection, analogs: EarthAnalogSet | null) {
		if (lunar.sample.roughness === null) return;
		const next = {
			roughness: String(lunar.sample.roughness),
			precision,
		};
		setSlope('');
		setTmin('');
		setIce('');
		setRock('');
		setRoughness(next.roughness);
		setLunarElevation(lunar.sample.elevation);
		setRoughnessOnly(true);
		setLunarLabel(lunar.label);
		openPage('earth');
		if (analogs) {
			setPoints(analogs.points);
			setSummary(describe(analogs, lunar.label));
			return;
		}
		void search(next, lunar.label);
	}

	return (
		<main className="app">
		<header className="topbar">
		<strong>ORBITAL</strong>
		<nav className="page-nav" aria-label="Cuerpo">
		<button type="button" aria-current={page === 'moon' ? 'page' : undefined} onClick={() => openPage('moon')}>
		Luna
		</button>
		<button type="button" aria-current={page === 'earth' ? 'page' : undefined} onClick={() => openPage('earth')}>
		Tierra
		</button>
		</nav>
		<span>{page === 'moon' ? 'SITIOS TRIPULADOS' : 'EARTH OBSERVATION SYSTEM'}</span>
		</header>

		<div className="workspace">
		{page === 'moon' ? (
			<MoonPage precision={precision} onCompare={compareFromMoon} />
		) : (
		<>

		<aside className="sidebar">
		<section className="sidebar-section">
		<h4>Objetivo</h4>
		<p className="muted">
		{lunarLabel
			? `Rugosidad LOLA de ${lunarLabel}${lunarElevation === null ? '' : `, elevación ${lunarElevation.toFixed(1)} m`}. La comparación usa solo esa rugosidad.`
			: 'Cinco números del sitio lunar. La cercanía es el promedio de los cinco.'}
		</p>

		{roughnessOnly ? (
		<>
		<dl className="cell-facts">
		<div>
		<dt>Pendiente</dt>
		<dd>sin dato</dd>
		</div>
		<div>
		<dt>Temperatura nocturna</dt>
		<dd>sin dato</dd>
		</div>
		<div>
		<dt>Hielo</dt>
		<dd>sin dato</dd>
		</div>
		<div>
		<dt>Roca</dt>
		<dd>sin dato</dd>
		</div>
		</dl>
		<p className="muted">Esos mapas no están. No forman parte de esta búsqueda.</p>
		<label className="field">
		Rugosidad LOLA (m)
		<input value={roughness} onChange={(event) => setRoughness(event.target.value)} inputMode="decimal" />
		</label>
		</>
		) : (
		<>
		<label className="field">
		Pendiente (°)
		<input value={slope} onChange={(event) => editField(setSlope)(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Rugosidad (m)
		<input value={roughness} onChange={(event) => editField(setRoughness)(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Temperatura nocturna (°C)
		<input value={tmin} onChange={(event) => editField(setTmin)(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Hielo (m)
		<input value={ice} onChange={(event) => editField(setIce)(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Roca
		<select value={rock} onChange={(event) => editField(setRock)(event.target.value)}>
		{ROCKS.map(([code, label]) => (
			<option key={code} value={code}>{label}</option>
		))}
		</select>
		</label>
		</>
		)}
		<label className="field">
		Precisión {precision.toFixed(2)}
		<input
		type="range"
		min="0"
		max="1"
		step="0.05"
		value={precision}
		onChange={(event) => setPrecision(Number(event.target.value))}
		/>
		<span className="range-labels">
		<span>más lugares</span>
		<span>más precisos</span>
		</span>
		</label>
		<button type="button" onClick={() => void search()} disabled={busy}>
		{busy ? 'Buscando…' : 'Buscar análogos'}
		</button>
		{roughnessOnly && (
		<button type="button" onClick={leaveLunarQuery}>
		Buscar con otros datos
		</button>
		)}
		<p className="muted">{summary}</p>
		<div className="result-list">
		{listPreview(points).map((point) => (
			<button
			key={`${point.lat},${point.lon}`}
			type="button"
			onClick={() => selectPlace(point.lat, point.lon, point.closeness)}
			>
			{(point.closeness * 100).toFixed(0)}% · {point.roughness_m.toFixed(1)} m · {point.lat.toFixed(2)}, {point.lon.toFixed(2)} · {point.rock}
			</button>
		))}
		</div>
		</section>

		<section className="sidebar-section">
		<h4>Visualization layers</h4>

		<label>
		<input
		type="checkbox"
		checked={visibleLayers.points}
		onChange={() => toggleLayer('points')}
		/>
		Locations
		</label>

		<label>
		<input
		type="checkbox"
		checked={visibleLayers.heatmaps}
		onChange={() => toggleLayer('heatmaps')}
		/>
		Heatmap
		</label>

		<label>
		<input
		type="checkbox"
		checked={visibleLayers.polygons}
		onChange={() => toggleLayer('polygons')}
		/>
		Areas
		</label>

		<label>
		<input
		type="checkbox"
		checked={visibleLayers.labels}
		onChange={() => toggleLayer('labels')}
		/>
		Labels
		</label>
		</section>

		<hr />

		<h3>SELECTED LOCATION</h3>

		{location ? (
			<>
			<p>Latitude: {location.lat.toFixed(5)}</p>
			<p>Longitude: {location.lng.toFixed(5)}</p>
			</>
		) : (
		<p>Click the globe to select a location.</p>
		)}
		</aside>

		<section className="globe-container">
		<InteractiveGlobe
		ref={globe}
		onLocationSelect={(coords) => selectPlace(coords.lat, coords.lng)}
		onPointSelect={(point) => {
			const hit = points.find(
				(item) => Math.abs(item.lat - point.lat) < 0.001 && Math.abs(item.lon - point.lng) < 0.001,
			);
			selectPlace(point.lat, point.lng, hit?.closeness);
		}}
		/>
		<PointPanel place={selection} onClose={() => setSelection(null)} />
		</section>
		</>
		)}

		</div>
		</main>
	);
}

export default App;
