import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	api,
	ApiError,
	buildUrl,
	CSRF_COOKIE,
	errorMessage,
	onUnauthorized,
	readCookie
} from './api';
import { detectLocale } from './i18n/index.svelte';

function stubFetch(status: number, body: unknown) {
	const fetchMock = vi.fn(
		async () => new Response(body === null ? null : JSON.stringify(body), { status })
	);
	vi.stubGlobal('fetch', fetchMock);
	return fetchMock;
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('api helpers', () => {
	it('reads cookies', () => {
		const cookies = `a=1; ${CSRF_COOKIE}=tok%3Den; b=2`;
		expect(readCookie(CSRF_COOKIE, cookies)).toBe('tok=en');
		expect(readCookie('missing', cookies)).toBeNull();
	});

	it('extracts error messages', () => {
		expect(errorMessage({ detail: 'Nicht gefunden.' }, 404)).toBe('Nicht gefunden.');
		expect(
			errorMessage({ detail: [{ msg: 'Value error, Eine Uhrzeit braucht ein Datum.' }] }, 422)
		).toBe('Eine Uhrzeit braucht ein Datum.');
		expect(errorMessage(null, 500)).toMatch(/Server/);
		expect(errorMessage(null, 429)).toMatch(/Zu viele/);
		expect(errorMessage(null, 418)).toBe('Fehler 418');
	});

	it('picks the language before sign-in', () => {
		expect(detectLocale('en', ['de-DE'])).toBe('en');
		expect(detectLocale(null, ['en-GB', 'de'])).toBe('en');
		expect(detectLocale(null, ['fr-FR', 'de-AT'])).toBe('de');
		expect(detectLocale('xx', ['fr'])).toBe('de');
	});

	it('builds URLs without empty parameters', () => {
		const url = buildUrl('/tasks', { view: 'today', area_id: undefined, q: '' }, 'https://x.de');
		expect(url.toString()).toBe('https://x.de/api/tasks?view=today');
	});
});

describe('api()', () => {
	it('sends the CSRF token only on unsafe requests', async () => {
		vi.stubGlobal('document', { cookie: `${CSRF_COOKIE}=abc` });
		vi.stubGlobal('location', { origin: 'https://todoch.test' });
		const fetchMock = stubFetch(200, { ok: true });

		await api('/tasks');
		await api('/tasks', { method: 'POST', body: { title: 'x' } });

		const calls = fetchMock.mock.calls as unknown as [URL, RequestInit][];
		const getHeaders = calls[0]?.[1].headers as Record<string, string>;
		const postHeaders = calls[1]?.[1].headers as Record<string, string>;
		expect(getHeaders['X-CSRF-Token']).toBeUndefined();
		expect(postHeaders['X-CSRF-Token']).toBe('abc');
		expect(postHeaders['Accept-Language']).toBe('de');
		expect(postHeaders['Content-Type']).toBe('application/json');
		expect(calls[1]?.[1].body).toBe('{"title":"x"}');
	});

	it('returns undefined for 204 and raises ApiError otherwise', async () => {
		stubFetch(204, null);
		await expect(api('/x', { method: 'DELETE' })).resolves.toBeUndefined();
		stubFetch(404, { detail: 'Nicht gefunden.' });
		await expect(api('/x')).rejects.toEqual(new ApiError(404, 'Nicht gefunden.'));
	});

	it('notifies about expired sessions', async () => {
		const handler = vi.fn();
		onUnauthorized(handler);
		stubFetch(401, { detail: 'Bitte anmelden.' });
		await expect(api('/tasks')).rejects.toBeInstanceOf(ApiError);
		expect(handler).toHaveBeenCalledOnce();
	});

	it('reports network failures', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new TypeError('Failed to fetch');
			})
		);
		await expect(api('/tasks')).rejects.toMatchObject({ status: 0 });
	});
});
