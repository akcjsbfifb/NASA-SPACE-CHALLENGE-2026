/**
 * Common geographic coordinates.
 */
export interface GeoCoordinates {
  lat: number;
  lng: number;
}

/**
 * Camera position and zoom.  Lower altitude = closer to Earth.
 */
export interface GlobeView extends GeoCoordinates {
  altitude: number;
}

/**
 * Unique identifier for any visualization layer.
 */
export type GlobeLayerId = string;

/**
 * A point displayed on the globe.
 */
export interface GlobePoint extends GeoCoordinates {
  id: string;
  label: string;
  color?: string;
  size?: number;
  altitude?: number;
}

/**
 * A geographic polygon.  Coordinates follow GeoJSON ordering: [longitude, latitude]
 */
export interface GlobePolygon {
  id: string;
  label?: string;
  color?: string;
  altitude?: number;
  coordinates: number[][][];
}

/**
 * A heatmap observation.
 */
export interface HeatmapPoint extends GeoCoordinates {
  weight: number;
}

/**
 * A heatmap visualization layer.
 */
export interface GlobeHeatmap {
  id: string;
  points: HeatmapPoint[];
  color?: (t: number) => string;
  maxHeight?: number;
}

/**
 * A geographic text label.
 */
export interface GlobeLabel extends GeoCoordinates {
  id: string;
  text: string;
  color?: string;
  size?: number;
  altitude?: number;
}

/**
 * Earth rendering configuration.
 */
export interface GlobeEarthConfig {
  textureUrl: string;
  bumpImageUrl?: string;
  backgroundImageUrl?: string;
  backgroundColor?: string;
  atmosphereColor?: string;
  atmosphereAltitude?: number;
}

/**
 * Initial component configuration.
 */
export interface InteractiveGlobeConfig {
  earth?: Partial<GlobeEarthConfig>;
  initialView?: GlobeView;
}

/**
 * Coordinates returned from globe interactions.
 */
export interface GlobeClickEvent extends GeoCoordinates {
  altitude: number;
}

/**
 * Events emitted by the globe.
 */
export interface InteractiveGlobeEvents {
  onLocationSelect?: (coordinates: GlobeClickEvent) => void;
  onPointSelect?: (point: GlobePoint) => void;
  onPolygonSelect?: (polygon: GlobePolygon) => void;
}
