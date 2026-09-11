import { describe, expect, it } from 'vitest';
import { guessImap } from './mail';

describe('guessImap', () => {
	it('kennt verbreitete Anbieter', () => {
		expect(guessImap(' Max@GMX.de ')).toEqual({
			host: 'imap.gmx.net',
			port: 993,
			security: 'ssl',
			hint: null,
			known: true
		});
		expect(guessImap('a@gmail.com')?.hint).toBe('app');
		expect(guessImap('a@hotmail.de')?.hint).toBe('oauth');
	});

	it('schlägt sonst imap.<domain> vor', () => {
		expect(guessImap('me@firma.example')).toMatchObject({
			host: 'imap.firma.example',
			known: false
		});
		expect(guessImap('kein-at')).toBeNull();
		expect(guessImap('a@')).toBeNull();
		expect(guessImap('a@localhost')).toBeNull();
	});
});
