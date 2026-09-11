import type { Locale } from '$lib/types';
import { de, type MessageKey } from './de';
import { en } from './en';

const dictionaries: Record<Locale, Record<MessageKey, string>> = { de, en };

let current = $state<Locale>('de');

export const i18n = {
	get locale(): Locale {
		return current;
	},
	set locale(value: Locale) {
		current = value;
		if (typeof document !== 'undefined') document.documentElement.lang = value;
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
