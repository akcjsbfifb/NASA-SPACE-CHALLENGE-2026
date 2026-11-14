import { useEffect, useState } from 'react';

import { getCopy } from '../i18n';
import type { Language } from '../i18n';

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
	language: Language;
};

function formatMeters(value: number | null, noData: string, digits = 0) {
	if (value === null) return noData;
	return `${value.toFixed(digits)} m`;
}

export default function PointPanel({ place, onClose, language }: PointPanelProps) {
	const copy = getCopy(language);
	const [cell, setCell] = useState<EarthCell | null>(null);
	const [cellError, setCellError] = useState(false);
	const [sceneUrl, setSceneUrl] = useState('');
	const [sceneSource, setSceneSource] = useState('');
	const [imageError, setImageError] = useState(false);

	useEffect(() => {
		if (!place) return;
		const controller = new AbortController();
		setCell(null);
		setCellError(false);
		setImageError(false);
		const params = new URLSearchParams({
			lat: String(place.lat),
			lon: String(place.lng),
		});
		fetch(`http://127.0.0.1:8787/cell?${params}`, { signal: controller.signal })
			.then(async (response) => {
				const body = (await response.json()) as EarthCell & { error?: string };
				if (!response.ok) throw new Error(body.error || 'Cell data request failed');
				setCell(body);
			})
			.catch(() => {
				if (controller.signal.aborted) return;
				setCellError(true);
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
						<h3>{copy.point}</h3>
							<button type="button" onClick={onClose}>{copy.close}</button>
					</header>
					<div className="scene-frame">
						{imageError ? (
							<p className="muted">{copy.noSatelliteImage}</p>
						) : sceneUrl ? (
							<img
								src={sceneUrl}
								alt={copy.satelliteView(place.lat.toFixed(2), place.lng.toFixed(2))}
								onError={() => setImageError(true)}
							/>
						) : (
							<p className="muted">{copy.loadingImage}</p>
						)}
						{sceneUrl && !imageError && <span className="scene-mark" />}
					</div>
					<p className="scene-credit">
						{sceneSource === 'google' ? copy.googleSatellite : copy.esriSatellite}
					</p>
					<p className="scene-links">
						<a href={mapsUrl} target="_blank" rel="noreferrer">{copy.viewGoogleMaps}</a>
					</p>
					<dl className="cell-facts">
						<div>
							<dt>{copy.latitude}</dt>
							<dd>{(cell?.lat ?? place.lat).toFixed(4)}</dd>
						</div>
						<div>
							<dt>{copy.longitude}</dt>
							<dd>{(cell?.lon ?? place.lng).toFixed(4)}</dd>
						</div>
						{place.closeness !== undefined && (
							<div>
								<dt>{copy.closeness}</dt>
								<dd>{(place.closeness * 100).toFixed(0)}%</dd>
							</div>
						)}
						<div>
							<dt>{copy.elevation}</dt>
							<dd>{cell ? formatMeters(cell.elevation_m, copy.noData) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.slope}</dt>
							<dd>{cell ? `${cell.slope_deg.toFixed(2)}°` : '…'}</dd>
						</div>
						<div>
							<dt>{copy.roughness}</dt>
							<dd>{cell ? formatMeters(cell.roughness_m, copy.noData, 1) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.coldNight}</dt>
							<dd>{cell ? (cell.tmin_c === null ? copy.noData : `${cell.tmin_c.toFixed(1)} °C`) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.ice}</dt>
							<dd>{cell ? formatMeters(cell.ice_thickness_m, copy.noData) : '…'}</dd>
						</div>
						<div>
							<dt>{copy.rock}</dt>
							<dd>{cell ? `${copy.rocks[cell.rock] ?? cell.rock} (${cell.rock})` : '…'}</dd>
						</div>
					</dl>
					{cellError && <p className="muted">{copy.cellError}</p>}
					{cell && cell.distance_km > 1.5 && (
						<p className="muted">{copy.nearestCellDistance(cell.distance_km.toFixed(1))}</p>
					)}
				</>
			)}
		</aside>
	);
}
