import { useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';

import './PrecisionDial.css';

type PrecisionDialProps = {
	value: number;
	label: string;
	unit?: string;
	onChange: (value: number) => void;
};

const CENTER = 100;
const RADIUS = 80;
const DEAD_ZONE = 44;
const SWEEP = 320;
const START = 110;
const STEP = 5;
const TRAIL_SEGMENTS = 8;

function clamp(value: number, min: number, max: number) {
	return Math.min(max, Math.max(min, value));
}

function pointAt(degrees: number): [number, number] {
	const radians = (degrees * Math.PI) / 180;
	return [
		CENTER + Math.cos(radians) * RADIUS,
		CENTER + Math.sin(radians) * RADIUS,
	];
}

function arcPath(start: number, end: number) {
	const [startX, startY] = pointAt(start);
	const [endX, endY] = pointAt(end);
	const largeArc = end - start > 180 ? 1 : 0;
	return `M ${startX} ${startY} A ${RADIUS} ${RADIUS} 0 ${largeArc} 1 ${endX} ${endY}`;
}

function dialValueAt(event: PointerEvent<SVGSVGElement>) {
	const bounds = event.currentTarget.getBoundingClientRect();
	const x = ((event.clientX - bounds.left) / bounds.width) * 200 - CENTER;
	const y = ((event.clientY - bounds.top) / bounds.height) * 200 - CENTER;
	const degrees = (Math.atan2(y, x) * 180) / Math.PI;
	let progress = (degrees - START + 360) % 360;
	const gap = 360 - SWEEP;

	if (progress > SWEEP) {
		progress = progress < SWEEP + gap / 2 ? SWEEP : 0;
	}

	return Math.round((clamp(progress / SWEEP, 0, 1) * 100) / STEP) * STEP;
}

export default function PrecisionDial({ value, label, unit = '%', onChange }: PrecisionDialProps) {
	const [dragging, setDragging] = useState(false);
	const pointerId = useRef<number | null>(null);
	const progress = clamp(value, 0, 100) / 100;
	const angle = START + progress * SWEEP;
	const [headX, headY] = pointAt(angle);

	function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
		if (event.button > 0) return;
		const bounds = event.currentTarget.getBoundingClientRect();
		const x = ((event.clientX - bounds.left) / bounds.width) * 200 - CENTER;
		const y = ((event.clientY - bounds.top) / bounds.height) * 200 - CENTER;
		if (Math.hypot(x, y) < DEAD_ZONE) return;
		event.preventDefault();
		pointerId.current = event.pointerId;
		event.currentTarget.setPointerCapture(event.pointerId);
		setDragging(true);
		onChange(dialValueAt(event));
	}

	function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
		if (pointerId.current !== event.pointerId) return;
		onChange(dialValueAt(event));
	}

	function handlePointerUp(event: PointerEvent<SVGSVGElement>) {
		if (pointerId.current !== event.pointerId) return;
		pointerId.current = null;
		setDragging(false);
		if (event.currentTarget.hasPointerCapture(event.pointerId)) {
			event.currentTarget.releasePointerCapture(event.pointerId);
		}
	}

	function handleKeyDown(event: KeyboardEvent<SVGSVGElement>) {
		let nextValue: number;
		switch (event.key) {
			case 'ArrowRight':
			case 'ArrowUp':
				nextValue = value + STEP * (event.shiftKey ? 2 : 1);
				break;
			case 'ArrowLeft':
			case 'ArrowDown':
				nextValue = value - STEP * (event.shiftKey ? 2 : 1);
				break;
			case 'Home':
				nextValue = 0;
				break;
			case 'End':
				nextValue = 100;
				break;
			default:
				return;
		}

		event.preventDefault();
		onChange(clamp(nextValue, 0, 100));
	}

	const trails = Array.from({ length: TRAIL_SEGMENTS }, (_, index) => {
		const trailEnd = angle - index * 3;
		const trailStart = Math.max(START, trailEnd - 3);
		return {
			path: arcPath(trailStart, trailEnd),
			opacity: 1 - index / TRAIL_SEGMENTS,
			visible: trailEnd > START,
		};
	});

	return (
		<svg
			className="precision-dial"
			viewBox="0 0 200 200"
			role="slider"
			tabIndex={0}
			aria-label={label}
			aria-valuemin={0}
			aria-valuemax={100}
			aria-valuenow={value}
			aria-valuetext={`${value}${unit}`}
			data-dragging={dragging || undefined}
			onPointerDown={handlePointerDown}
			onPointerMove={handlePointerMove}
			onPointerUp={handlePointerUp}
			onPointerCancel={handlePointerUp}
			onKeyDown={handleKeyDown}
		>
			<path className="precision-dial__track" d={arcPath(START, START + SWEEP)} />
			<path className="precision-dial__value-arc" d={progress > 0 ? arcPath(START, angle) : ''} />
			<g className="precision-dial__comet">
				{trails.map((trail, index) => (
					<path
						key={index}
						d={trail.visible ? trail.path : ''}
						style={{ opacity: dragging && trail.visible ? trail.opacity * 0.8 : 0 }}
					/>
				))}
			</g>
			<circle className="precision-dial__head" cx={headX} cy={headY} r="9" />
			<text className="precision-dial__readout" x={CENTER} y={CENTER + 7} textAnchor="middle">
				{value}{unit}
			</text>
		</svg>
	);
}
