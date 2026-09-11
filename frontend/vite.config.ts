import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

const backend = process.env.TODOCH_BACKEND ?? 'http://127.0.0.1:8000';
const proxy = { '/api': { target: backend, changeOrigin: false } };

// Dieselbe CSP wie in Caddy – so fallen Verstöße schon in den E2E-Tests auf.
const csp = [
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
].join('; ');

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: { port: 5173, strictPort: true, proxy },
	preview: {
		port: 4173,
		strictPort: true,
		proxy,
		headers: { 'Content-Security-Policy': csp, 'X-Content-Type-Options': 'nosniff' }
	},
	test: { include: ['src/**/*.test.ts'] }
});
