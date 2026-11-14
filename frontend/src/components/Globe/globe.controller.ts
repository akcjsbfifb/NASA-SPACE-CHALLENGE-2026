import type {
	GlobeView,
	GlobeLayerId,
	GlobePoint,
	GlobePolygon,
	GlobeHeatmap,
	GlobeLabel,
	GlobeEarthConfig,
} from './globe.types';

/**
 * Public imperative API for InteractiveGlobe.  Obtain an instance through a React ref.
 */
export interface GlobeController {
	/**
	 * Move the camera to a geographic location.
	 */
	flyTo(view: GlobeView, transitionDuration?: number): void;

	/**
	 * Return the camera to a geographic location.
	 */
	getView(): GlobeView;

	/**
	 * Replace the Earth texture.
	 *
	 * Example: setEarthTexture('/textures/earth-8k.jpg')
	 */
	setEarthTexture(url: string): void;

	/**
	 * Update Earth rendering properties.
	 */
	configureEarth(config: Partial<GlobeEarthConfig>): void;

	/**
	 * Replace all points belonging to a named layer.
	 */
	setPoints(layerId: GlobeLayerId, points: GlobePoint[]): void;

	/**
	 * Add one point to a named layer.
	 */
	addPoint(layerId: GlobeLayerId, point: GlobePoint): void;

	/**
	 * Remove a point by its ID.
	 */
	removePoint(layerId: GlobeLayerId, pointId: string): void;

	/**
	 * Replace all polygons belonging to a named layer.
	 */
	setPolygons(layerId: GlobeLayerId, polygons: GlobePolygon[]): void;

	/**
	 * Add one polygon to a named layer.
	 */
	addPolygon(layerId: GlobeLayerId, polygon: GlobePolygon): void;

	/**
	 * Create or replace a heatmap layer.
	 */
	setHeatmap(layerId: GlobeLayerId, heatmap: GlobeHeatmap): void;

	/**
	 * Remove a heatmap layer.
	 */
	removeHeatmap(layerId: GlobeLayerId): void;

	/**
	 * Create or replace a label layer.
	 */
	setLabels(layerId: GlobeLayerId, labels: GlobeLabel[]): void;

	/**
	 * Remove all visualization data belonging to a layer ID.
	 */
	removeLayer(layerId: GlobeLayerId): void;

	/**
	 * Remove every visualization layer.
	 */
	clearLayers(): void;
}
