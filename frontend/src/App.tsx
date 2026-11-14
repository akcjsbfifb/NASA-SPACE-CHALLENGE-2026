import { useState } from 'react';
import InteractiveGlobe from './components/Globe/InteractiveGlobe';
import { mockPoints } from './data/mockData';
import './App.css';

type Coordinates = {
	lat: number;
	lng: number;
};

function App() {
	const [coordinates, setCoordinates] = useState<Coordinates | null>(null);

	return (
		<main className="app">
		<header className="topbar">
		<div className="brand">ORBITAL</div>
		<div className="topbar-status">EARTH OBSERVATION SYSTEM</div>
		</header>

		<div className="workspace">
		<aside className="sidebar">
		<h3>EXPLORER</h3>

		<section className="sidebar-section">
		<h4>Visualization layers</h4>

		<label>
		<input type="checkbox" defaultChecked />
		Globe
		</label>

		<label>
		<input type="checkbox" />
		Heatmap
		</label>

		<label>
		<input type="checkbox" defaultChecked />
		Locations
		</label>

		<label>
		<input type="checkbox" />
		Areas
		</label>
		</section>

		<section className="sidebar-section">
		<h4>Selected location</h4>

		{coordinates ? (
			<>
			<p>Latitude: {coordinates.lat.toFixed(5)}</p>
			<p>Longitude: {coordinates.lng.toFixed(5)}</p>
			</>
		) : (
		<p className="muted">Click anywhere on the globe.</p>
		)}
		</section>
		</aside>

		<section className="globe-container">
		<InteractiveGlobe points={mockPoints} onLocationSelect={setCoordinates} />

		<div className="globe-overlay">
		<span>EARTH / 3D VIEW</span>
		<span>INTERACTIVE MODE</span>
		</div>
		</section>
		</div>
		</main>
	);
}

export default App;
