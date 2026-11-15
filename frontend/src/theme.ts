/**
 * One colour for "this is the point you picked", shared by both globes.
 *
 * The rest of the palette is mint and amber on dark navy, so the selection
 * uses a saturated red that survives the texture behind it.
 */
export const SELECTED_COLOR = '#ff4438';

/**
 * The selection is a map pin drawn in the DOM overlay, so its size is in
 * pixels and stays the same at every zoom level.
 */
export const SELECTED_PIN_SIZE = 34;

/** Lifted off the surface so it is never buried in the texture behind it. */
export const SELECTED_ALTITUDE = 0.03;

/** Camera target used when a selection is made. */
export const SELECTED_FLY_ALTITUDE = 0.65;
export const SELECTED_FLY_MS = 900;
