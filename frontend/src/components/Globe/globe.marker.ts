import type {GlobeMarker} from './globe.types';

/**
 * Lucide "map-pin", inlined instead of loaded as an image so that
 * `currentColor` follows the marker colour and the outline stays crisp at any
 * zoom level.
 */
export const MAP_PIN_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
	<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/>
	<circle cx="12" cy="10" r="3"/>
</svg>`;

export const DEFAULT_MARKER_SIZE = 34;

/**
 * How far above the box centre the visible tip of the pin sits, as a fraction
 * of its height.  The path bottoms out at y=21.799 in a 24-unit viewBox and the
 * 2-unit stroke adds one unit, so the tip is at ~22.8/24.
 */
const TIP_BELOW_CENTRE = 0.45;

/**
 * Build the DOM node the globe anchors at a marker's coordinates.
 *
 * It takes `object` because that is what react-globe.gl passes to its accessor;
 * a module-level function also keeps a stable identity, so the HTML layer is not
 * rebuilt on every render.
 *
 * three-globe centres the returned element on the point, so the glyph is moved
 * up by its own tip offset: the pin looks planted on the coordinate instead of
 * floating above or sinking into the surface.
 */
export function createMarkerElement(data: object): HTMLElement {
	const marker = data as GlobeMarker;
	const size = marker.size ?? DEFAULT_MARKER_SIZE;
	const pin = document.createElement('div');
	pin.className = 'globe-pin';
	pin.style.width = `${size}px`;
	pin.style.height = `${size}px`;
	if (marker.color) pin.style.color = marker.color;
	pin.innerHTML = `<div class="globe-pin-glyph" style="transform: translateY(-${TIP_BELOW_CENTRE * 100}%)">${MAP_PIN_SVG}</div>`;
	return pin;
}
