// Macht den Build CSP-tauglich ohne 'unsafe-inline' und ohne Nonces:
//  1. SvelteKits Inline-Startskript wandert in eine eigene Datei (script-src 'self').
//  2. Das Inline-style des Screenreader-Ansagers (#svelte-announcer) wird entfernt –
//     dieselben Regeln stehen in src/app.css (style-src 'self').
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const BUILD = 'build';

function filesWith(dir, extension) {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return filesWith(path, extension);
		return path.endsWith(extension) ? [path] : [];
	});
}

let announcers = 0;
for (const file of filesWith(join(BUILD, '_app', 'immutable'), '.js')) {
	const code = readFileSync(file, 'utf8');
	const cleaned = code.replace(/(id="svelte-announcer"[^>]*?) style="[^"]*"/g, (_match, start) => {
		announcers++;
		return start;
	});
	if (cleaned !== code) writeFileSync(file, cleaned);
}
if (announcers === 0) console.warn('CSP: #svelte-announcer nicht gefunden – E2E-Test prüft das.');

let moved = 0;
for (const file of filesWith(BUILD, '.html')) {
	let html = readFileSync(file, 'utf8');
	html = html.replace(/<script>([\s\S]*?)<\/script>/g, (_match, code) => {
		const hash = createHash('sha256').update(code).digest('hex').slice(0, 16);
		const name = `_app/boot.${hash}.js`;
		writeFileSync(join(BUILD, name), code);
		moved++;
		return `<script src="/${name}"></script>`;
	});
	if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(html)) {
		throw new Error(`Inline-Skript in ${relative('.', file)} übrig`);
	}
	if (/\sstyle="/i.test(html)) throw new Error(`Inline-Style in ${relative('.', file)}`);
	writeFileSync(file, html);
}
console.log(`CSP: ${moved} Inline-Skript(e) ausgelagert, ${announcers} Inline-Style(s) entfernt.`);
