import type {InteractiveGlobeConfig} from './globe.types';

export const DEFAULT_GLOBE_CONFIG: InteractiveGlobeConfig = {
	earth: {
		textureUrl: '//unpkg.com/three-globe/example/img/earth-night.jpg',
		backgroundImageUrl: '//unpkg.com/three-globe/example/img/night-sky.png',
		backgroundColor: '#050914',
		atmosphereColor: '#4da6ff',
		atmosphereAltitude: 0.15,
	},

	initialView: {
		lat: 0,
		lng: -60,
		altitude: 2,
	},
};
