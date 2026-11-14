import type {InteractiveGlobeConfig} from './globe.types';

export const DEFAULT_GLOBE_CONFIG: InteractiveGlobeConfig = {
	earth: {
		textureUrl: '/textures/2k_earth_daymap.jpg',
		highResolutionTextureUrl: '/textures/8k_earth_daymap.jpg',
		backgroundImageUrl: '/night-sky.png',
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
