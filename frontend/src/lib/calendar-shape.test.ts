import { describe, expect, it } from 'vitest';
import { filterDays, FULL_SHAPE, monthGrid, shapeFor, weekdayIndex } from './calendar';

describe('calendar shape', () => {
	it('uses the settings of one area', () => {
		expect(shapeFor([{ week_days: 31, day_start: 8, day_end: 18 }])).toEqual({
			weekdays: [0, 1, 2, 3, 4],
			startHour: 8,
			endHour: 18
		});
	});

	it('combines several areas', () => {
		const shape = shapeFor([
			{ week_days: 31, day_start: 8, day_end: 18 },
			{ week_days: 96, day_start: 10, day_end: 22 }
		]);
		expect(shape).toEqual({ weekdays: [0, 1, 2, 3, 4, 5, 6], startHour: 8, endHour: 22 });
		expect(shapeFor([])).toEqual(FULL_SHAPE);
	});

	it('filters days by weekday', () => {
		expect(weekdayIndex('2026-09-14')).toBe(0);
		expect(weekdayIndex('2026-09-13')).toBe(6);
		const workdays = filterDays(monthGrid('2026-09-11'), [0, 1, 2, 3, 4]);
		expect(workdays).toHaveLength(30);
		expect(workdays.every((day) => weekdayIndex(day) < 5)).toBe(true);
		expect(filterDays(['2026-09-13'], [0])).toEqual(['2026-09-13']);
	});
});
