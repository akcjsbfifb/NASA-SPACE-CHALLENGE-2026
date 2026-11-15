/**
 * How a closeness number is presented.
 *
 * The score is a rank, not a measurement: neither LDRM nor ETOPO declare a
 * per-pixel uncertainty, so 3.5 mm of difference is not "better" than 3.6 mm.
 * Two rules follow from that: never round up (99.96 must not read as 100) and
 * always show the physical difference next to the number.
 */

export type VariableInfo = {
	id: string;
	tier: string | null;
	weight: number | null;
	unit: string | null;
};

/** How close a point is, as the server decides it. The UI only paints it. */
export type MatchLevel = 'very' | 'close' | 'barely';

/** Letter for a percentage: A 90+, B 80+, C 70+, D 60+, F below. */
export type Grade = 'A' | 'B' | 'C' | 'D' | 'F';

/** One entry of `GET /activities`: weights and search values of a preset. */
export type ActivityPreset = {
	id: string;
	weights: Record<string, number>;
	search: Record<string, number | string | null>;
	measured: string[];
	serves: Record<string, string>;
	source: string;
};

export type ScoreDetail = {
	closeness: number;
	coverage?: number;
	worst?: number;
	scores?: Record<string, number>;
	deltas?: Record<string, number>;
};

/** Truncate instead of rounding, so nothing reaches 100 by rounding. */
export function truncated(value: number, decimals: number): string {
	const factor = 10 ** decimals;
	return (Math.floor(value * factor) / factor).toFixed(decimals);
}

/** A 0..1 closeness as a percentage, truncated, and capped below 100. */
export function percent(value: number, decimals: number): string {
	// Two different sensors on two bodies never produce an identical place, and
	// "100%" reads as "same place". The physical delta carries the exact match.
	const capped = Math.min(value, 0.999);
	return truncated(capped * 100, decimals);
}

export function formatDelta(value: number, unit: string | null): string {
	const size = Math.abs(value);
	if (unit === 'deg') return `${value.toFixed(2)}°`;
	// A difference that rounds to 0.0 hides why a score is not 100%.
	if (unit === 'C') return `${value.toFixed(size > 0 && size < 0.1 ? 2 : 1)} °C`;
	if (unit === 'm') {
		if (size > 0 && size < 0.001) return `${value.toFixed(4)} m`;
		return value >= 10 ? `${value.toFixed(0)} m` : `${value.toFixed(3)} m`;
	}
	return value.toFixed(2);
}

/**
 * The same units as `formatDelta`, for values that are shown, not subtracted:
 * a target may be a rock code and a cell may have no value at all.
 */
export function formatValue(value: number | string | null | undefined, unit: string | null): string {
	if (value === null || value === undefined) return '';
	if (typeof value === 'string') return value;
	if (unit === 'deg') return `${value.toFixed(2)}°`;
	if (unit === 'C') return `${value.toFixed(1)} °C`;
	if (unit === 'm') return value >= 10 ? `${value.toFixed(0)} m` : `${value.toFixed(3)} m`;
	if (unit === 'class') return String(value);
	return value.toFixed(2);
}

/**
 * The difference of the variable that matches worst: that is what limits the
 * analog. Showing the best one reads "0.00°" and says nothing.
 */
export function worstDelta(point: ScoreDetail, variables: VariableInfo[]): string {
	let worst: { value: number; unit: string | null } | null = null;
	let worstScore = Infinity;
	for (const variable of variables) {
		const delta = point.deltas?.[variable.id];
		const score = point.scores?.[variable.id];
		if (typeof delta !== 'number' || !variable.unit || variable.unit === 'class') continue;
		if (typeof score === 'number' && score < worstScore) {
			worstScore = score;
			worst = { value: delta, unit: variable.unit };
		} else if (!worst) {
			worst = { value: delta, unit: variable.unit };
		}
	}
	return worst ? formatDelta(worst.value, worst.unit) : '';
}

export const TIER_NOTE: Record<string, string> = {
	A: 'comparable',
	B: 'proxy',
	C: 'sin equivalente',
};
