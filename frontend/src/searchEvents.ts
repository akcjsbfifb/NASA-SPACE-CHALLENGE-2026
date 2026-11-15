import { SEARCH_API } from './searchApi';

type SearchEventHandler = (body: unknown) => void;

let source: EventSource | null = null;
const handlers = new Set<SearchEventHandler>();
let subscriberCount = 0;
let closeTimer: ReturnType<typeof setTimeout> | null = null;
let reopenTimer: ReturnType<typeof setTimeout> | null = null;

function attachSource() {
	if (source) {
		return;
	}
	source = new EventSource(`${SEARCH_API}/events`);
	source.onmessage = (event) => {
		let body: unknown;
		try {
			body = JSON.parse(event.data);
		} catch {
			return;
		}
		for (const handler of handlers) {
			handler(body);
		}
	};
	source.onerror = () => {
		if (!source || source.readyState !== EventSource.CLOSED) {
			return;
		}
		source = null;
		if (subscriberCount === 0) {
			return;
		}
		if (reopenTimer) {
			clearTimeout(reopenTimer);
		}
		reopenTimer = setTimeout(() => {
			reopenTimer = null;
			if (subscriberCount > 0) {
				attachSource();
			}
		}, 2000);
	};
}

/**
 * One shared EventSource for the app. Deferred close avoids React StrictMode
 * tearing down the stream on the dev remount (Firefox shows those as Blocked).
 */
export function subscribeSearchEvents(handler: SearchEventHandler): () => void {
	if (closeTimer) {
		clearTimeout(closeTimer);
		closeTimer = null;
	}
	subscriberCount += 1;
	handlers.add(handler);
	attachSource();
	return () => {
		handlers.delete(handler);
		subscriberCount -= 1;
		if (subscriberCount > 0) {
			return;
		}
		closeTimer = setTimeout(() => {
			closeTimer = null;
			if (subscriberCount > 0) {
				return;
			}
			source?.close();
			source = null;
		}, 250);
	};
}
