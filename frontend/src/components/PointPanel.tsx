import { useEffect, useState } from 'react';

const ROCK_LABEL: Record<string, string> = {
	vb: 'basalto',
	va: 'volcánico ácido',
	vi: 'volcánico intermedio',
	py: 'piroclástico',
	pb: 'plutónico básico',
	pa: 'plutónico ácido',
	pi: 'plutónico intermedio',
	su: 'sedimento suelto',
	ss: 'sedimentaria',
	sm: 'sedimentaria mixta',
	sc: 'carbonato',
	mt: 'metamórfica',
	ev: 'evaporita',
	ig: 'hielo',
};

export type SelectedPlace = {
	lat: number;
	lng: number;
	closeness?: number;
};

type EarthCell = {
	lat: number;
	lon: number;
	distance_km: number;
	elevation_m: number | null;
	slope_deg: number;
	roughness_m: number;
	tmin_c: number | null;
	ice_thickness_m: number;
	rock: string;
};

type PointPanelProps = {
	place: SelectedPlace | null;
	onClose: () => void;
};

function formatMeters(value: number | null, digits = 0) {
	if (value === null) return 'sin dato';
	return `${value.toFixed(digits)} m`;
}

export default function PointPanel({ place, onClose }: PointPanelProps) {
	const [cell, setCell] = useState<EarthCell | null>(null);
	const [cellError, setCellError] = useState('');
	const [sceneUrl, setSceneUrl] = useState('');
	const [sceneSource, setSceneSource] = useState('');
	const [imageError, setImageError] = useState(false);

	useEffect(() => {
		if (!place) return;
		const controller = new AbortController();
		setCell(null);
		setCellError('');
		setImageError(false);
		const params = new URLSearchParams({
			lat: String(place.lat),
			lon: String(place.lng),
		});
		fetch(`http://127.0.0.1:8787/cell?${params}`, { signal: controller.signal })
			.then(async (response) => {
				const body = (await response.json()) as EarthCell & { error?: string };
				if (!response.ok) throw new Error(body.error || 'sin datos de esa celda');
				setCell(body);
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				setCellError(error instanceof Error ? error.message : 'no se pudo leer la celda');
			});
		return () => controller.abort();
	}, [place]);

	useEffect(() => {
		if (!place) return;
		const controller = new AbortController();
		let objectUrl = '';
		setSceneUrl('');
		setSceneSource('');
		setImageError(false);
		const params = new URLSearchParams({
			lat: String(place.lat),
			lon: String(place.lng),
		});
		fetch(`http://127.0.0.1:8787/scene?${params}`, { signal: controller.signal })
			.then(async (response) => {
				if (!response.ok) throw new Error('sin imagen');
				const blob = await response.blob();
				if (!blob.type.startsWith('image/')) throw new Error('sin imagen');
				objectUrl = URL.createObjectURL(blob);
				setSceneUrl(objectUrl);
				setSceneSource(response.headers.get('X-Image-Source') || 'esri');
			})
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				setImageError(true);
				if (error instanceof Error && error.name !== 'AbortError') return;
			});
		return () => {
			controller.abort();
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, [place]);

	const mapsUrl = place
		? `https://www.google.com/maps/@${place.lat},${place.lng},400m/data=!3m1!1e3`
		: '';

	return (
		<aside className={`detail-panel ${place ? 'open' : ''}`} aria-hidden={!place}>
			{place && (
				<>
					<header className="detail-head">
						<h3>PUNTO</h3>
						<button type="button" onClick={onClose}>Cerrar</button>
					</header>
					<div className="scene-frame">
						{imageError ? (
							<p className="muted">No hay imagen satelital para este punto.</p>
						) : sceneUrl ? (
							<img
								src={sceneUrl}
								alt={`Vista satelital de ${place.lat.toFixed(2)}, ${place.lng.toFixed(2)}`}
								onError={() => setImageError(true)}
							/>
						) : (
							<p className="muted">Cargando imagen…</p>
						)}
						{sceneUrl && !imageError && <span className="scene-mark" />}
					</div>
					<p className="scene-credit">
						{sceneSource === 'google' ? 'Google Maps · satelital' : 'Esri World Imagery · recorte de 800 m'}
					</p>
					<p className="scene-links">
						<a href={mapsUrl} target="_blank" rel="noreferrer">Ver en Google Maps</a>
					</p>
					<dl className="cell-facts">
						<div>
							<dt>Latitud</dt>
							<dd>{(cell?.lat ?? place.lat).toFixed(4)}</dd>
						</div>
						<div>
							<dt>Longitud</dt>
							<dd>{(cell?.lon ?? place.lng).toFixed(4)}</dd>
						</div>
						{place.closeness !== undefined && (
							<div>
								<dt>Cercanía</dt>
								<dd>{(place.closeness * 100).toFixed(0)}%</dd>
							</div>
						)}
						<div>
							<dt>Elevación</dt>
							<dd>{cell ? formatMeters(cell.elevation_m) : '…'}</dd>
						</div>
						<div>
							<dt>Pendiente</dt>
							<dd>{cell ? `${cell.slope_deg.toFixed(2)}°` : '…'}</dd>
						</div>
						<div>
							<dt>Rugosidad</dt>
							<dd>{cell ? formatMeters(cell.roughness_m, 1) : '…'}</dd>
						</div>
						<div>
							<dt>Noche fría</dt>
							<dd>{cell ? (cell.tmin_c === null ? 'sin dato' : `${cell.tmin_c.toFixed(1)} °C`) : '…'}</dd>
						</div>
						<div>
							<dt>Hielo</dt>
							<dd>{cell ? formatMeters(cell.ice_thickness_m) : '…'}</dd>
						</div>
						<div>
							<dt>Roca</dt>
							<dd>{cell ? `${ROCK_LABEL[cell.rock] ?? cell.rock} (${cell.rock})` : '…'}</dd>
						</div>
					</dl>
					{cellError && <p className="muted">{cellError}</p>}
					{cell && cell.distance_km > 1.5 && (
						<p className="muted">La celda de tierra más cercana está a {cell.distance_km.toFixed(1)} km del clic.</p>
					)}
				</>
			)}
		</aside>
	);
}
