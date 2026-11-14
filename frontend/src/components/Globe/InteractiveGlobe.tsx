import { useRef, useEffect } from 'react';
import Globe from 'react-globe.gl';

export type GlobePoint = {
	lat: number;
	lng: number;
	size?: number;
	color?: string;
	name: string;
};

type InteractiveGlobeProps = {
	points?: GlobePoint[];
	onLocationSelect?: (coords: { lat: number; lng: number }) => void;
};

export default function InteractiveGlobe({
	points = [],
	onLocationSelect,
}: InteractiveGlobeProps) {
	const globeRef = useRef<any>(null);

	useEffect(() => {
		globeRef.current?.pointOfView({
			lat: 0,
			lng: -60,
			altitude: 2,
		});
	}, []);

	return (
		<Globe
		ref={globeRef}
		width={window.innerWidth}
		height={window.innerHeight}
		backgroundColor="#050914"
		globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
		backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"

		// Points
		pointsData={points}
		pointAltitude={(d: any) => d.size ?? 0.1}
		pointColor={(d: any) => d.color ?? '#00d9ff'}
		pointLabel="name"

		// Interaction
		onGlobeClick={({ lat, lng }) => {
			onLocationSelect?.({ lat, lng });
		}}

		// Globe appearance
		atmosphereColor="#4da6ff"
		atmosphereAltitude={0.15}

		animateIn
		/>
	);
}
