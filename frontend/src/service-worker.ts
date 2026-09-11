/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

/**
 * Service Worker: App-Shell offline verfügbar, GET-Antworten der API als
 * Lesestand für den Offline-Betrieb. Beim Ab- und Anmelden wird der API-Cache gelöscht.
 */
import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const SHELL_CACHE = `todoch-shell-${version}`;
const API_CACHE = 'todoch-api-v1';
const ASSETS = [...build, ...files, '/'];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(SHELL_CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys
						.filter((key) => key.startsWith('todoch-shell-') && key !== SHELL_CACHE)
						.map((key) => caches.delete(key))
				)
			)
			.then(() => sw.clients.claim())
	);
});

// Erinnerungen per Web-Push anzeigen
sw.addEventListener('push', (event) => {
	let data: { title?: string; body?: string; url?: string; tag?: string } = {};
	try {
		data = event.data?.json() ?? {};
	} catch {
		data = { body: event.data?.text() };
	}
	event.waitUntil(
		sw.registration.showNotification(data.title ?? 'Todoch', {
			body: data.body,
			tag: data.tag,
			icon: '/icon-192.png',
			badge: '/icon-192.png',
			data: { url: data.url ?? '/' }
		})
	);
});

sw.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const target = new URL(
		(event.notification.data as { url?: string } | null)?.url ?? '/',
		sw.location.origin
	);
	if (target.origin !== sw.location.origin) return;
	event.waitUntil(
		sw.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (clients) => {
			const client = clients[0];
			if (client) {
				await client.navigate(target.href).catch(() => undefined);
				return client.focus();
			}
			return sw.clients.openWindow(target.href);
		})
	);
});

sw.addEventListener('message', (event) => {
	if (event.data === 'clear-api-cache') event.waitUntil(caches.delete(API_CACHE));
});

async function networkFirst(request: Request): Promise<Response> {
	const cache = await caches.open(API_CACHE);
	try {
		const response = await fetch(request);
		if (response.ok) await cache.put(request, response.clone());
		return response;
	} catch {
		const cached = await cache.match(request);
		if (cached) return cached;
		return new Response(JSON.stringify({ detail: 'Offline' }), {
			status: 503,
			headers: { 'Content-Type': 'application/json' }
		});
	}
}

sw.addEventListener('fetch', (event) => {
	const request = event.request;
	if (request.method !== 'GET') return;
	const url = new URL(request.url);
	if (url.origin !== sw.location.origin) return;

	if (url.pathname.startsWith('/api/')) {
		if (url.pathname === '/api/health' || url.pathname.startsWith('/api/feeds/')) return;
		event.respondWith(networkFirst(request));
		return;
	}
	if (request.mode === 'navigate') {
		event.respondWith(
			fetch(request).catch(async () => (await caches.match('/')) ?? Response.error())
		);
		return;
	}
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(request).then((cached) => cached ?? fetch(request)));
	}
});
