// Setzt das Farbschema vor dem ersten Rendern, damit nichts aufblitzt.
// Eigene Datei statt Inline-Skript wegen der CSP (script-src 'self').
// Gleiche Logik wie src/lib/stores/theme.svelte.ts.
(function () {
	var mode = 'system';
	try {
		mode = localStorage.getItem('todoch-theme') || 'system';
	} catch (e) {
		/* Speicher gesperrt – Systemeinstellung verwenden */
	}
	var dark =
		mode === 'dark' || (mode !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
	document.documentElement.dataset.theme = dark ? 'dark' : 'light';
	var meta = document.querySelector('meta[name="theme-color"]');
	if (meta) meta.setAttribute('content', dark ? '#161615' : '#fafaf9');
})();
