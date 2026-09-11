import { describe, expect, it } from 'vitest';
import { addDays, diffDays, formatDay, formatTime, isValidIsoDate, todayIn } from './dates';

const labels = { today: 'Heute', tomorrow: 'Morgen', yesterday: 'Gestern' };
const TODAY = '2026-09-11'; // Freitag

describe('dates', () => {
	it('adds days across months, years and DST', () => {
		expect(addDays('2026-03-28', 2)).toBe('2026-03-30');
		expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
		expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
		expect(addDays('2026-10-24', 2)).toBe('2026-10-26');
	});

	it('computes day differences', () => {
		expect(diffDays(TODAY, '2026-09-14')).toBe(3);
		expect(diffDays(TODAY, '2026-09-10')).toBe(-1);
	});

	it('formats relative days', () => {
		expect(formatDay(TODAY, TODAY, 'de', labels)).toBe('Heute');
		expect(formatDay('2026-09-12', TODAY, 'de', labels)).toBe('Morgen');
		expect(formatDay('2026-09-10', TODAY, 'de', labels)).toBe('Gestern');
		expect(formatDay('2026-09-14', TODAY, 'de', labels)).toBe('Montag');
		expect(formatDay('2026-10-15', TODAY, 'de', labels)).toMatch(/15\. Okt/);
		expect(formatDay('2027-01-05', TODAY, 'de', labels)).toContain('2027');
	});

	it('uses the user time zone for today', () => {
		const now = new Date('2026-09-11T23:30:00Z');
		expect(todayIn('Europe/Berlin', now)).toBe('2026-09-12');
		expect(todayIn('America/New_York', now)).toBe('2026-09-11');
	});

	it('validates ISO dates and formats times', () => {
		expect(isValidIsoDate('2026-02-28')).toBe(true);
		expect(isValidIsoDate('2026-02-30')).toBe(false);
		expect(isValidIsoDate('../etc')).toBe(false);
		expect(formatTime('14:05:00')).toBe('14:05');
		expect(formatTime(null)).toBe('');
	});
});
