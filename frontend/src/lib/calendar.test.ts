import { describe, expect, it } from 'vitest';
import { formatAttendees, parseAttendees } from './attendees';
import {
	addMinutes,
	addMonths,
	durationMinutes,
	isoWeek,
	layoutDay,
	monthGrid,
	parseLocal,
	rangeFor,
	segmentFor,
	shift,
	startOfWeek
} from './calendar';

describe('calendar', () => {
	it('starts weeks on monday', () => {
		expect(startOfWeek('2026-09-11')).toBe('2026-09-07');
		expect(startOfWeek('2026-09-13')).toBe('2026-09-07');
		expect(startOfWeek('2026-09-14')).toBe('2026-09-14');
	});

	it('builds a six-week month grid', () => {
		const grid = monthGrid('2026-09-11');
		expect(grid).toHaveLength(42);
		expect(grid[0]).toBe('2026-08-31');
		expect(grid[41]).toBe('2026-10-11');
	});

	it('computes ranges and navigation', () => {
		expect(rangeFor('week', '2026-09-11')).toEqual({ from: '2026-09-07', to: '2026-09-14' });
		expect(rangeFor('day', '2026-09-11')).toEqual({ from: '2026-09-11', to: '2026-09-12' });
		expect(rangeFor('agenda', '2026-09-11').to).toBe('2026-10-11');
		expect(shift('month', '2026-01-31', 1)).toBe('2026-02-01');
		expect(shift('week', '2026-09-11', -1)).toBe('2026-09-04');
		expect(addMonths('2026-12-15', 1)).toBe('2027-01-01');
	});

	it('knows ISO week numbers', () => {
		expect(isoWeek('2026-09-11')).toBe(37);
		expect(isoWeek('2026-01-01')).toBe(1);
		expect(isoWeek('2026-12-31')).toBe(53);
		expect(isoWeek('2027-01-04')).toBe(1);
	});

	it('handles local times and durations', () => {
		expect(parseLocal('2026-09-11T14:30')).toEqual({ date: '2026-09-11', minutes: 870 });
		expect(parseLocal('2026-09-11')).toEqual({ date: '2026-09-11', minutes: 0 });
		expect(durationMinutes('2026-09-11T23:00', '2026-09-12T01:00')).toBe(120);
		expect(addMinutes('2026-09-11', 1500)).toEqual({ date: '2026-09-12', minutes: 60 });
	});

	it('splits events over midnight into day segments', () => {
		const occ = { all_day: false, start_local: '2026-09-11T23:00', end_local: '2026-09-12T01:00' };
		expect(segmentFor(occ, '2026-09-11')).toMatchObject({ start: 1380, end: 1440 });
		expect(segmentFor(occ, '2026-09-12')).toMatchObject({ start: 0, end: 60 });
		expect(segmentFor({ ...occ, end_local: '2026-09-12T00:00' }, '2026-09-12')).toBeNull();
		expect(segmentFor({ ...occ, all_day: true }, '2026-09-11')).toBeNull();
	});

	it('places overlapping events side by side', () => {
		const placed = layoutDay([
			{ item: 'a', start: 540, end: 600 },
			{ item: 'b', start: 570, end: 630 },
			{ item: 'c', start: 600, end: 660 },
			{ item: 'd', start: 700, end: 720 }
		]);
		const by = Object.fromEntries(placed.map((p) => [p.item, p]));
		expect(by.a).toMatchObject({ column: 0, columns: 2 });
		expect(by.b).toMatchObject({ column: 1, columns: 2 });
		expect(by.c).toMatchObject({ column: 0, columns: 2 });
		expect(by.d).toMatchObject({ column: 0, columns: 1 });
	});
});

describe('attendees', () => {
	it('parses one attendee per line', () => {
		expect(parseAttendees('Anna Berger <anna@firma.de>\nbob@example.org\n\nHerr Meier')).toEqual([
			{ name: 'Anna Berger', email: 'anna@firma.de' },
			{ name: '', email: 'bob@example.org' },
			{ name: 'Herr Meier', email: null }
		]);
	});

	it('formats attendees back to text', () => {
		const list = parseAttendees('Anna <anna@firma.de>\nbob@example.org\nMeier');
		expect(formatAttendees(list)).toBe('Anna <anna@firma.de>\nbob@example.org\nMeier');
	});
});
