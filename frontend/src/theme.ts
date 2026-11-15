/**
 * One colour for "this is the point you picked", shared by both globes.
 *
 * The rest of the palette is mint and amber on dark navy, so the selection
 * uses a saturated red that survives the texture behind it.
 */
export const SELECTED_COLOR = '#ff4438';

/** Bigger and higher than every data point, so it is never buried. */
export const SELECTED_SIZE = 0.45;
export const SELECTED_ALTITUDE = 0.03;

/** Camera target used when a selection is made. */
export const SELECTED_FLY_ALTITUDE = 0.65;
export const SELECTED_FLY_MS = 900;
