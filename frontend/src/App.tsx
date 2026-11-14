import { useEffect, useRef, useState } from 'react';

import InteractiveGlobe from './components/Globe/InteractiveGlobe';

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

function App() {
	const globe = useRef<GlobeController>(null);

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

	function toggleLayer(layer: keyof typeof visibleLayers) {
		setVisibleLayers(previous => ({
			...previous,
			[layer]: !previous[layer],
		}));
	}

	useEffect(() => {
		globe.current?.setPoints(
			'analogs',
			visibleLayers.points ? points.map(toGlobePoint) : [],
		);
	}, [points, visibleLayers.points]);

	async function search() {
		setBusy(true);
		setSummary('Buscando en 82 millones de celdas…');
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
			const body = (await response.json()) as SearchResponse & { error?: string };
			if (!response.ok) throw new Error(body.error || 'la búsqueda falló');
			setPoints(body.points);
			const tempNote =
				body.temperature_mode === 'relative_cold'
					? ' La temperatura lunar queda fuera del rango terrestre: el puntaje premia el frío relativo.'
					: '';
			setSummary(
				body.returned === 0
					? `Ningún lugar llega a ${(body.min_closeness * 100).toFixed(0)}% de cercanía. Bajá la precisión.`
					: `${body.returned} lugares distintos, entre ${((body.loosest ?? 0) * 100).toFixed(0)}% y ${((body.closest ?? 0) * 100).toFixed(0)}% de cercanía.${tempNote}`,
			);
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

	return (
		<main className="app">
		<header className="topbar">
		<strong>ORBITAL</strong>
		<span>EARTH OBSERVATION SYSTEM</span>
		</header>

		<div className="workspace">

		<aside className="sidebar">
		<section className="sidebar-section">
		<h4>Objetivo</h4>
		<p className="muted">Cinco números del sitio lunar. La cercanía es el promedio de los cinco.</p>

		<label className="field">
		Pendiente (°)
		<input value={slope} onChange={(event) => setSlope(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Rugosidad (m)
		<input value={roughness} onChange={(event) => setRoughness(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Temperatura nocturna (°C)
		<input value={tmin} onChange={(event) => setTmin(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Hielo (m)
		<input value={ice} onChange={(event) => setIce(event.target.value)} inputMode="decimal" />
		</label>
		<label className="field">
		Roca
		<select value={rock} onChange={(event) => setRock(event.target.value)}>
		{ROCKS.map(([code, label]) => (
			<option key={code} value={code}>{label}</option>
		))}
		</select>
		</label>
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
		<button type="button" onClick={search} disabled={busy}>
		{busy ? 'Buscando…' : 'Buscar análogos'}
		</button>
		<p className="muted">{summary}</p>
		{points.slice(0, 6).map((point) => (
			<p key={`${point.lat},${point.lon}`}>
			{(point.closeness * 100).toFixed(0)}% · {point.lat.toFixed(2)}, {point.lon.toFixed(2)} · {point.rock}
			</p>
		))}
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
		onLocationSelect={setLocation}
		/>
		</section>

		</div>
		</main>
	);
}

export default App;
