import type { Locale } from '$lib/types';
import { de, type MessageKey } from './de';
import { en } from './en';

const dictionaries: Record<Locale, Record<MessageKey, string>> = { de, en };
const STORAGE_KEY = 'todoch-locale';

/**
 * Sprache vor der Anmeldung: zuletzt gewählte, sonst die des Browsers, sonst Deutsch.
 * Nach der Anmeldung gilt die Sprache aus dem Profil.
 */
export function detectLocale(stored: string | null, languages: readonly string[]): Locale {
	if (stored === 'de' || stored === 'en') return stored;
	for (const language of languages) {
		const tag = language.toLowerCase();
		if (tag.startsWith('de')) return 'de';
		if (tag.startsWith('en')) return 'en';
	}
	return 'de';
}

function initialLocale(): Locale {
	if (typeof navigator === 'undefined' || import.meta.env.MODE === 'test') return 'de';
	let stored: string | null = null;
	try {
		stored = localStorage.getItem(STORAGE_KEY);
	} catch {
		// Speicher gesperrt – dann nach Browser
	}
	return detectLocale(
		stored,
		navigator.languages?.length ? navigator.languages : [navigator.language]
	);
}

let current = $state<Locale>(initialLocale());
if (typeof document !== 'undefined') document.documentElement.lang = current;

export const i18n = {
	get locale(): Locale {
		return current;
	},
	set locale(value: Locale) {
		current = value;
		if (typeof document !== 'undefined') document.documentElement.lang = value;
		try {
			localStorage.setItem(STORAGE_KEY, value);
		} catch {
			// nur für diese Sitzung
		}
	}
};

export function t(key: MessageKey, vars?: Record<string, string | number>): string {
	let text: string = dictionaries[current][key] ?? de[key] ?? key;
	if (vars) {
		for (const [name, value] of Object.entries(vars))
			text = text.replaceAll(`{${name}}`, String(value));
	}
	return text;
}

export type { MessageKey };
