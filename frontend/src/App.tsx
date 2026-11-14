import { useRef, useState } from 'react';

import InteractiveGlobe from './components/Globe/InteractiveGlobe';

import type {
	GlobeController,
} from './components/Globe/globe.controller';

import type {
	GlobeClickEvent,
} from './components/Globe/globe.types';

import './App.css';

function App() {
	const globe = useRef<GlobeController>(null);

	const [location, setLocation] = useState<GlobeClickEvent | null>(null);

	const [visibleLayers, setVisibleLayers] = useState({
		points: true,
		heatmaps: false,
		polygons: false,
		labels: true,
	});

	function toggleLayer(layer: keyof typeof visibleLayers) {
		setVisibleLayers(previous => ({
			...previous,
			[layer]: !previous[layer],
		}));
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
