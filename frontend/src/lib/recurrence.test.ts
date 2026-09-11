import { describe, expect, it } from 'vitest';
import { buildRule, describeRule, parseRule, weekdayName } from './recurrence';

const labels = {
	freq: { DAILY: 'Täglich', WEEKLY: 'Wöchentlich', MONTHLY: 'Monatlich', YEARLY: 'Jährlich' },
	every: 'Alle',
	units: { DAILY: 'Tage', WEEKLY: 'Wochen', MONTHLY: 'Monate', YEARLY: 'Jahre' },
	until: 'Bis'
};

describe('recurrence', () => {
	it('round-trips rules', () => {
		for (const rule of [
			'FREQ=DAILY',
			'FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH',
			'FREQ=MONTHLY;UNTIL=20261231',
			'FREQ=YEARLY'
		]) {
			expect(buildRule(parseRule(rule))).toBe(rule);
		}
	});

	it('handles empty and invalid rules', () => {
		expect(parseRule(null).freq).toBe('NONE');
		expect(parseRule('FREQ=HOURLY').freq).toBe('NONE');
		expect(buildRule({ freq: 'NONE', interval: 3, byday: [], until: '' })).toBeNull();
	});

	it('normalizes interval and weekday order', () => {
		expect(buildRule({ freq: 'WEEKLY', interval: 0, byday: ['FR', 'MO'], until: '' })).toBe(
			'FREQ=WEEKLY;BYDAY=MO,FR'
		);
		expect(buildRule({ freq: 'DAILY', interval: 999, byday: ['MO'], until: '' })).toBe(
			'FREQ=DAILY;INTERVAL=365'
		);
	});

	it('describes rules for humans', () => {
		expect(describeRule('FREQ=DAILY', 'de', labels)).toBe('Täglich');
		// Je nach ICU-Version „Mo“ oder „Mo.“
		expect(describeRule('FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH', 'de', labels)).toMatch(
			/^Alle 2 Wochen · Mo\.?, Do\.?$/
		);
		expect(describeRule(null, 'de', labels)).toBe('');
	});

	it('names weekdays', () => {
		expect(weekdayName('MO', 'de', 'long')).toBe('Montag');
		expect(weekdayName('SU', 'en', 'long')).toBe('Sunday');
	});
});
