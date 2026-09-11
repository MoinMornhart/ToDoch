import { describe, expect, it } from 'vitest';
import { describeAgent } from './agent';
import { de } from './i18n/de';
import { en } from './i18n/en';
import { isTypingTarget, plainKey } from './keyboard';
import { parseTags } from './tags';

function element(tagName: string, extra: Record<string, unknown> = {}) {
	return { tagName, isContentEditable: false, ...extra } as unknown as HTMLElement;
}

function keyEvent(key: string, extra: Partial<KeyboardEvent> = {}): KeyboardEvent {
	return {
		key,
		ctrlKey: false,
		metaKey: false,
		altKey: false,
		isComposing: false,
		defaultPrevented: false,
		target: element('BODY'),
		...extra
	} as unknown as KeyboardEvent;
}

describe('keyboard', () => {
	it('detects typing targets', () => {
		expect(isTypingTarget(element('INPUT', { type: 'text' }))).toBe(true);
		expect(isTypingTarget(element('INPUT', { type: 'checkbox' }))).toBe(false);
		expect(isTypingTarget(element('TEXTAREA'))).toBe(true);
		expect(isTypingTarget(element('DIV', { isContentEditable: true }))).toBe(true);
		expect(isTypingTarget(element('BUTTON'))).toBe(false);
		expect(isTypingTarget(null)).toBe(false);
	});

	it('ignores shortcuts with modifiers or while typing', () => {
		expect(plainKey(keyEvent('n'))).toBe('n');
		expect(plainKey(keyEvent('n', { ctrlKey: true }))).toBeNull();
		expect(plainKey(keyEvent('n', { target: element('INPUT', { type: 'text' }) }))).toBeNull();
	});
});

describe('tags', () => {
	it('parses free text', () => {
		expect(parseTags('#Haushalt, finanzen amt  haushalt')).toEqual(['haushalt', 'finanzen', 'amt']);
		expect(parseTags('böse<script> ok_1 a-b')).toEqual(['ok_1', 'a-b']);
		expect(parseTags('')).toEqual([]);
	});
});

describe('agent', () => {
	it('summarizes user agents', () => {
		expect(
			describeAgent(
				'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
			)
		).toBe('Chrome · Windows');
		expect(
			describeAgent(
				'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'
			)
		).toBe('Safari · iOS');
		expect(describeAgent(null)).toBe('–');
	});
});

describe('i18n', () => {
	it('uses the same placeholders in all languages', () => {
		const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
		for (const key of Object.keys(de) as (keyof typeof de)[]) {
			expect(placeholders(en[key]), key).toEqual(placeholders(de[key]));
		}
	});
});
