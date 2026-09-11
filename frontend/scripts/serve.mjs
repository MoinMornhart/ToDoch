// Kleiner Server für E2E-Tests und lokale Vorschau des Produktions-Builds.
// Verhält sich wie Caddy: statische Dateien, SPA-Fallback, /api → Backend, Security-Header.
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import http from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';

const ROOT = resolve('build');
const PORT = Number(process.env.PORT ?? 4173);
const BACKEND = new URL(process.env.TODOCH_BACKEND ?? 'http://127.0.0.1:8000');

const TYPES = {
	'.html': 'text/html; charset=utf-8',
	'.js': 'text/javascript; charset=utf-8',
	'.css': 'text/css; charset=utf-8',
	'.svg': 'image/svg+xml',
	'.png': 'image/png',
	'.json': 'application/json',
	'.webmanifest': 'application/manifest+json',
	'.txt': 'text/plain; charset=utf-8'
};

const HEADERS = {
	'Content-Security-Policy': [
		"default-src 'self'",
		"script-src 'self'",
		"style-src 'self'",
		"img-src 'self' data: blob:",
		"font-src 'self'",
		"connect-src 'self'",
		"object-src 'none'",
		"base-uri 'none'",
		"form-action 'self'",
		"frame-ancestors 'none'",
		"manifest-src 'self'",
		"worker-src 'self'"
	].join('; '),
	'X-Content-Type-Options': 'nosniff',
	'X-Frame-Options': 'DENY',
	'Referrer-Policy': 'no-referrer',
	'Cross-Origin-Opener-Policy': 'same-origin',
	'Permissions-Policy':
		'camera=(), microphone=(), geolocation=(), payment=(), usb=(), publickey-credentials-get=(self), publickey-credentials-create=(self)'
};

function proxy(req, res) {
	const upstream = http.request(
		{
			hostname: BACKEND.hostname,
			port: BACKEND.port,
			path: req.url,
			method: req.method,
			headers: { ...req.headers, 'x-forwarded-for': req.socket.remoteAddress ?? '' }
		},
		(response) => {
			res.writeHead(response.statusCode ?? 502, response.headers);
			response.pipe(res);
		}
	);
	upstream.on('error', () => {
		res.writeHead(502, { 'Content-Type': 'application/json' });
		res.end('{"detail":"Backend nicht erreichbar"}');
	});
	req.pipe(upstream);
}

async function resolveFile(pathname) {
	const target = normalize(join(ROOT, decodeURIComponent(pathname)));
	if (target !== ROOT && !target.startsWith(ROOT + sep)) return null;
	try {
		const info = await stat(target);
		if (info.isFile()) return target;
	} catch {
		/* fällt auf index.html zurück */
	}
	return extname(pathname) ? null : join(ROOT, 'index.html');
}

http
	.createServer(async (req, res) => {
		const url = new URL(req.url ?? '/', 'http://localhost');
		if (url.pathname.startsWith('/api/')) return proxy(req, res);
		const file = await resolveFile(url.pathname);
		if (!file) {
			res.writeHead(404, HEADERS);
			return res.end('Not found');
		}
		const immutable = url.pathname.startsWith('/_app/immutable/');
		res.writeHead(200, {
			...HEADERS,
			'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream',
			'Cache-Control': immutable ? 'public, max-age=31536000, immutable' : 'no-cache'
		});
		createReadStream(file).pipe(res);
	})
	.listen(PORT, () => console.log(`Todoch-Vorschau auf http://localhost:${PORT}`));
