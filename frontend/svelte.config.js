import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// Reine Single-Page-App: Caddy liefert index.html für alle Pfade aus.
		adapter: adapter({ fallback: 'index.html', strict: true }),
		// Absolute Pfade, damit die SPA-Fallback-Seite auch unter /day/… funktioniert.
		paths: { relative: false },
		version: { pollInterval: 0 }
	}
};

export default config;
