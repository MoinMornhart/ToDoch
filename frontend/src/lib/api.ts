/**
 * Schlanker API-Client. Schickt bei zustandsändernden Anfragen das CSRF-Token aus dem
 * Cookie im Header mit (Double-Submit) und wandelt Fehler in `ApiError` um.
 */

export const CSRF_COOKIE = '__Host-todoch_csrf';

export class ApiError extends Error {
	constructor(
		public readonly status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions {
	method?: Method;
	body?: unknown;
	query?: Record<string, QueryValue>;
	signal?: AbortSignal;
}

export function readCookie(name: string, cookies: string): string | null {
	for (const part of cookies.split(';')) {
		const [key, ...rest] = part.trim().split('=');
		if (key === name) return decodeURIComponent(rest.join('='));
	}
	return null;
}

export function errorMessage(data: unknown, status: number): string {
	if (data && typeof data === 'object' && 'detail' in data) {
		const detail = (data as { detail: unknown }).detail;
		if (typeof detail === 'string') return detail;
		if (Array.isArray(detail) && detail.length > 0) {
			const first = detail[0] as { msg?: unknown };
			if (typeof first.msg === 'string') return first.msg.replace(/^Value error, /, '');
		}
	}
	if (status === 429) return 'Zu viele Versuche. Bitte später erneut versuchen.';
	if (status >= 500) return 'Der Server hat einen Fehler gemeldet. Bitte später erneut versuchen.';
	return `Fehler ${status}`;
}

let unauthorizedHandler: (() => void) | null = null;

export function onUnauthorized(handler: () => void): void {
	unauthorizedHandler = handler;
}

export function buildUrl(path: string, query: Record<string, QueryValue> = {}, base?: string): URL {
	const url = new URL(`/api${path}`, base ?? globalThis.location?.origin ?? 'http://localhost');
	for (const [key, value] of Object.entries(query)) {
		if (value !== undefined && value !== null && value !== '')
			url.searchParams.set(key, String(value));
	}
	return url;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const method = options.method ?? 'GET';
	const headers: Record<string, string> = { Accept: 'application/json' };
	if (options.body !== undefined) headers['Content-Type'] = 'application/json';
	if (method !== 'GET') {
		const token = readCookie(CSRF_COOKIE, globalThis.document?.cookie ?? '');
		if (token) headers['X-CSRF-Token'] = token;
	}

	let response: Response;
	try {
		response = await fetch(buildUrl(path, options.query), {
			method,
			headers,
			body: options.body === undefined ? undefined : JSON.stringify(options.body),
			credentials: 'same-origin',
			signal: options.signal
		});
	} catch (error) {
		if (error instanceof DOMException && error.name === 'AbortError') throw error;
		throw new ApiError(0, 'Keine Verbindung zum Server.');
	}

	if (response.status === 204) return undefined as T;
	const data: unknown = await response.json().catch(() => null);
	if (!response.ok) {
		if (response.status === 401 && !path.startsWith('/auth/login')) unauthorizedHandler?.();
		throw new ApiError(response.status, errorMessage(data, response.status));
	}
	return data as T;
}
