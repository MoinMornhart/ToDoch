/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

/**
 * Service Worker: App-Shell offline verfügbar, Aufgaben, Termine und Bereiche als
 * Lesestand für den Offline-Betrieb. Nie im Gerät: Mails, Konto, Sitzungen, Passkeys,
 * Zwei-Faktor, Einladungen. Beim Ab- und Anmelden und bei abgelaufener Sitzung (401)
 * wird der API-Cache gelöscht.
 */
import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const SHELL_CACHE = `todoch-shell-${version}`;
const API_CACHE = 'todoch-api-v2';
const ASSETS = [...build, ...files, '/'];
const OFFLINE_API = ['/api/meta', '/api/auth/me', '/api/tasks', '/api/events', '/api/areas'];

function offlineReadable(path: string): boolean {
	if (path.includes('/invites')) return false;
	return OFFLINE_API.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

/** Sitzung abgelaufen oder anderswo beendet: Offline-Stand nicht im Gerät lassen. */
async function dropCacheIfSignedOut(): Promise<void> {
	try {
		const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
		if (response.status === 401) await caches.delete(API_CACHE);
	} catch {
		// offline – Stand behalten, dafür ist er da
	}
}

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
						// alte Shell-Stände und alte API-Caches (v1 speicherte noch alles, auch Mails)
						.filter(
							(key) =>
								(key.startsWith('todoch-shell-') && key !== SHELL_CACHE) ||
								(key.startsWith('todoch-api-') && key !== API_CACHE)
						)
						.map((key) => caches.delete(key))
				)
			)
			.then(() => dropCacheIfSignedOut())
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
		sw.registration.showNotification(data.title ?? 'ToDoch', {
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
		if (response.status === 401) await caches.delete(API_CACHE);
		else if (response.ok) await cache.put(request, response.clone());
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
		if (!offlineReadable(url.pathname)) return; // direkt ans Netz, nie in den Cache
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
