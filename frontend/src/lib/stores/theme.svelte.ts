// Farbschema je Gerät: System, Hell oder Dunkel. Den Startwert setzt static/theme.js
// schon vor dem ersten Rendern; dieser Store hält ihn danach aktuell.
export type ThemeMode = 'system' | 'light' | 'dark';

const STORAGE_KEY = 'todoch-theme';
const THEME_COLORS = { light: '#fafaf9', dark: '#161615' } as const;

function stored(): ThemeMode {
	try {
		const value = localStorage.getItem(STORAGE_KEY);
		return value === 'light' || value === 'dark' ? value : 'system';
	} catch {
		return 'system';
	}
}

class ThemeStore {
	#media = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;
	mode = $state<ThemeMode>(stored());
	systemDark = $state(this.#media?.matches ?? false);
	resolved = $derived<'light' | 'dark'>(
		this.mode === 'system' ? (this.systemDark ? 'dark' : 'light') : this.mode
	);

	constructor() {
		this.#media?.addEventListener('change', (event) => {
			this.systemDark = event.matches;
			this.apply();
		});
	}

	set(mode: ThemeMode) {
		this.mode = mode;
		try {
			if (mode === 'system') localStorage.removeItem(STORAGE_KEY);
			else localStorage.setItem(STORAGE_KEY, mode);
		} catch {
			// Nur für diese Sitzung
		}
		this.apply();
	}

	toggle() {
		this.set(this.resolved === 'dark' ? 'light' : 'dark');
	}

	apply() {
		if (typeof document === 'undefined') return;
		document.documentElement.dataset.theme = this.resolved;
		document
			.querySelector('meta[name="theme-color"]')
			?.setAttribute('content', THEME_COLORS[this.resolved]);
	}
}

export const theme = new ThemeStore();
