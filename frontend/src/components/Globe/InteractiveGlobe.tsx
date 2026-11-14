import {
	forwardRef,
	useEffect,
	useImperativeHandle,
	useRef,
	useState,
} from 'react';

import Globe from 'react-globe.gl';

import type {GlobeController} from './globe.controller';

import type {
	GlobeEarthConfig,
	GlobeHeatmap,
	GlobeLabel,
	GlobePoint,
	GlobePolygon,
	GlobeView,
	InteractiveGlobeConfig,
	GlobeClickEvent,
} from './globe.types';

import {DEFAULT_GLOBE_CONFIG} from './globe.defaults';

interface InteractiveGlobeProps {
	config?: InteractiveGlobeConfig;
	onLocationSelect?: (location: GlobeClickEvent) => void;
	onPointSelect?: (point: GlobePoint) => void;
	onPolygonSelect?: (polygon: GlobePolygon) => void;
}

interface GlobeRuntime {
	pointOfView(view?: Partial<GlobeView>, transitionDuration?: number): GlobeRuntime | GlobeView;
}

type LayerData<T> = Record<string, T[]>;

const HIGH_RESOLUTION_ALTITUDE = 1.5;

function InteractiveGlobe(
	{
		config = {},
		onLocationSelect,
		onPointSelect,
		onPolygonSelect,
	}: InteractiveGlobeProps,
	forwardedRef: React.ForwardedRef<GlobeController>
) {
	const containerRef = useRef<HTMLDivElement>(null);
	const globeRef = useRef<GlobeRuntime | null>(null);
	const initialView = {
		...DEFAULT_GLOBE_CONFIG.initialView!,
		...config.initialView,
	};

	const [_view, setView] = useState<GlobeView>(initialView);

	const currentViewRef = useRef<GlobeView>(initialView);

	const [dimensions, setDimensions] = useState({
		width: 800,
		height: 600,
	});

	const [earth, setEarth] = useState<GlobeEarthConfig>({
		...DEFAULT_GLOBE_CONFIG.earth!,
		...config.earth,
	} as GlobeEarthConfig);

	const [highResolution, setHighResolution] = useState(false);

	const [points, setPoints] = useState<LayerData<GlobePoint>>({});

	const [polygons, setPolygons] = useState<LayerData<GlobePolygon>>({});

	const [heatmaps, setHeatmaps] = useState<Record<string, GlobeHeatmap>>({});

	const [labels, setLabels] = useState<LayerData<GlobeLabel>>({});

	useEffect(() => {
		const container = containerRef.current;

		if (!container) return;

		const observer = new ResizeObserver(([entry]) => {
			setDimensions({
				width: entry.contentRect.width,
				height: entry.contentRect.height,
			});
		});

		observer.observe(container);

		return () => observer.disconnect();
	}, []);

	useEffect(() => {
		globeRef.current?.pointOfView(currentViewRef.current, 0);
	}, []);

	const flyTo = (nextView: GlobeView, transitionDuration = 1000) => {
		currentViewRef.current = nextView;
		setView(nextView);
		setHighResolution(nextView.altitude < HIGH_RESOLUTION_ALTITUDE);

		globeRef.current?.pointOfView(nextView, transitionDuration);
	};

	const setPointsForLayer = (layerId: string, data: GlobePoint[]) => {
		setPoints(previous => ({
			...previous,
			[layerId]: data,
		}));
	};

	const addPoint = (layerId: string, point: GlobePoint) => {
		setPoints(previous => ({
			...previous,
			[layerId]: [
				...(previous[layerId] ?? []),
				point,
			],
		}));
	};

	const removePoint = (layerId: string, pointId: string) => {
		setPoints(previous => ({
			...previous,
			[layerId]: (previous[layerId] ?? []).filter(
				point => point.id !== pointId
			),
		}));
	};

	const setPolygonsForLayer = (layerId: string, data: GlobePolygon[]) => {
		setPolygons(previous => ({
			...previous,
			[layerId]: data,
		}));
	};

	const addPolygon = (layerId: string, polygon: GlobePolygon) => {
		setPolygons(previous => ({
			...previous,
			[layerId]: [
				...(previous[layerId] ?? []),
				polygon,
			],
		}));
	};

	const setHeatmap = (layerId: string, heatmap: GlobeHeatmap) => {
		setHeatmaps(previous => ({
			...previous,
			[layerId]: heatmap,
		}));
	};

	const removeHeatmap = (layerId: string) => {
		setHeatmaps(previous => {
			const next = { ...previous };
			delete next[layerId];
			return next;
		});
	};

	const setLabelsForLayer = (layerId: string, data: GlobeLabel[]) => {
		setLabels(previous => ({
			...previous,
			[layerId]: data,
		}));
	};

	const removeLayer = (layerId: string) => {
		setPoints(previous => {
			const next = { ...previous };
			delete next[layerId];
			return next;
		});

		setPolygons(previous => {
			const next = { ...previous };
			delete next[layerId];
			return next;
		});

		setHeatmaps(previous => {
			const next = { ...previous };
			delete next[layerId];
			return next;
		});

		setLabels(previous => {
			const next = { ...previous };
			delete next[layerId];
			return next;
		});
	};

	const clearLayers = () => {
		setPoints({});
		setPolygons({});
		setHeatmaps({});
		setLabels({});
	};

	const setEarthTexture = (url: string) => {
		setEarth(previous => ({
			...previous,
			textureUrl: url,
		}));
	};

	const configureEarth = (
		config: Partial<GlobeEarthConfig>
	) => {
		setEarth(previous => ({
			...previous,
			...config,
		}));
	};

	useImperativeHandle(
		forwardedRef,
		() => ({
			flyTo,

			getView: () => currentViewRef.current,

			setEarthTexture,
			configureEarth,

			setPoints: setPointsForLayer,
			addPoint,
			removePoint,

			setPolygons: setPolygonsForLayer,
			addPolygon,

			setHeatmap,
			removeHeatmap,

			setLabels: setLabelsForLayer,

			removeLayer,
			clearLayers,
		}),
		[]
	);

	const allPoints = Object.values(points).flat();

	const allPolygons = Object.values(polygons).flat();

	const allHeatmaps = Object.values(heatmaps);

	const allLabels = Object.values(labels).flat();

	return (
		<div
		ref={containerRef}
		style={{
			width: '100%',
			height: '100%',
			minWidth: 0,
			minHeight: 0,
		}}
		>
		<Globe
		ref={(instance) => {
			globeRef.current = instance as GlobeRuntime | null;
		}}

		width={dimensions.width}
		height={dimensions.height}

		globeImageUrl={highResolution ? earth.highResolutionTextureUrl : earth.textureUrl}
		bumpImageUrl={earth.bumpImageUrl}
		backgroundImageUrl={earth.backgroundImageUrl}
		backgroundColor={earth.backgroundColor}
		atmosphereColor={earth.atmosphereColor}
		atmosphereAltitude={earth.atmosphereAltitude}
		showAtmosphere={earth.showAtmosphere ?? true}

		pointsData={allPoints}
		pointLat="lat"
		pointLng="lng"
		pointAltitude={(point: object) => (point as GlobePoint).altitude ?? 0.01 }
		pointRadius={(point: object) => (point as GlobePoint).size ?? 0.15 }
		pointColor={(point: object) => (point as GlobePoint).color ?? '#00d9ff' }
		pointLabel="label"

		onPointClick={(point: object) => { onPointSelect?.(point as GlobePoint); }}

		polygonsData={allPolygons}
		polygonGeoJsonGeometry={(polygon: object) => ({
			type: 'Polygon',
			coordinates: (polygon as GlobePolygon).coordinates,
		})}
		polygonCapColor={(polygon: object) => (polygon as GlobePolygon).color ?? '#00aaff' }
		polygonSideColor={() => 'rgba(0, 100, 255, 0.1)'}
		polygonStrokeColor={() => '#ffffff'}
		polygonAltitude={(polygon: object) => (polygon as GlobePolygon).altitude ?? 0.01 }
		polygonLabel="label"

		onPolygonClick={(polygon: object) => { onPolygonSelect?.(polygon as GlobePolygon); }}

		heatmapsData={allHeatmaps}
		heatmapPoints={(heatmap: object) => (heatmap as GlobeHeatmap).points }
		heatmapPointLat="lat"
		heatmapPointLng="lng"
		heatmapPointWeight="weight"
		heatmapColorFn={(heatmap: object) => (heatmap as GlobeHeatmap).color ?? defaultHeatmapColor }
		heatmapTopAltitude={(heatmap: object) => (heatmap as GlobeHeatmap).maxHeight ?? 0.08 }
		heatmapBaseAltitude={0.005}
		heatmapsTransitionDuration={500}

		labelsData={allLabels}
		labelLat="lat"
		labelLng="lng"
		labelText="text"
		labelColor={(label: object) => (label as GlobeLabel).color ?? '#ffffff' }
		labelSize={(label: object) => (label as GlobeLabel).size ?? 1 }
		labelAltitude={(label: object) => (label as GlobeLabel).altitude ?? 0.02 }
		labelIncludeDot={false}
		labelLabel="text"

		onGlobeClick={({ lat, lng }) => {
			onLocationSelect?.({
				lat,
				lng,
				altitude: 0,
			});
		}}

		onZoom={(nextView) => {
			currentViewRef.current = nextView;
			const shouldUseHighResolution = nextView.altitude < HIGH_RESOLUTION_ALTITUDE;
			setHighResolution(previous => previous === shouldUseHighResolution?
				previous : shouldUseHighResolution);
		}}

		animateIn
		/>
		</div>
	);
}

function defaultHeatmapColor(t: number): string {
	if (t < 0.25) return 'rgba(0, 100, 255, 0.2)';
	if (t < 0.5) return 'rgba(0, 255, 100, 0.5)';
	if (t < 0.75) return 'rgba(255, 220, 0, 0.75)';
	return 'rgba(255, 50, 0, 0.9)';
}

export default forwardRef(InteractiveGlobe);
