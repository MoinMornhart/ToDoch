/** Kalender-Hilfen: Raster, Zeiträume, Blättern und Anordnung überlappender Termine. */

import { addDays, diffDays } from '$lib/dates';

export type CalendarView = 'month' | 'week' | 'day' | 'agenda';
export const VIEWS: CalendarView[] = ['month', 'week', 'day', 'agenda'];
export const AGENDA_DAYS = 30;

function weekday(iso: string): number {
	return new Date(`${iso}T00:00:00Z`).getUTCDay(); // 0 = Sonntag
}

/** Montag der Woche. */
export function startOfWeek(iso: string): string {
	return addDays(iso, -((weekday(iso) + 6) % 7));
}

export function firstOfMonth(iso: string): string {
	return `${iso.slice(0, 7)}-01`;
}

export function addMonths(iso: string, months: number): string {
	const [y, m] = iso.split('-').map(Number);
	return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1 + months, 1)).toISOString().slice(0, 10);
}

/** 6 Wochen × 7 Tage, beginnend am Montag vor dem Monatsersten. */
export function monthGrid(iso: string): string[] {
	const start = startOfWeek(firstOfMonth(iso));
	return Array.from({ length: 42 }, (_, i) => addDays(start, i));
}

export function visibleDays(view: CalendarView, iso: string): string[] {
	if (view === 'month') return monthGrid(iso);
	if (view === 'week') return Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(iso), i));
	if (view === 'day') return [iso];
	return Array.from({ length: AGENDA_DAYS }, (_, i) => addDays(iso, i));
}

/** Zeitraum für die API (``to`` exklusiv). */
export function rangeFor(view: CalendarView, iso: string): { from: string; to: string } {
	const days = visibleDays(view, iso);
	return { from: days[0] ?? iso, to: addDays(days[days.length - 1] ?? iso, 1) };
}

export function shift(view: CalendarView, iso: string, direction: 1 | -1): string {
	if (view === 'month') return addMonths(firstOfMonth(iso), direction);
	if (view === 'week') return addDays(iso, 7 * direction);
	if (view === 'day') return addDays(iso, direction);
	return addDays(iso, AGENDA_DAYS * direction);
}

/** Kalenderwoche nach ISO 8601. */
export function isoWeek(iso: string): number {
	const date = new Date(`${iso}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() + 3 - ((date.getUTCDay() + 6) % 7));
	const firstThursday = new Date(Date.UTC(date.getUTCFullYear(), 0, 4));
	firstThursday.setUTCDate(firstThursday.getUTCDate() + 3 - ((firstThursday.getUTCDay() + 6) % 7));
	return 1 + Math.round((date.getTime() - firstThursday.getTime()) / (7 * 86_400_000));
}

/** „JJJJ-MM-TTTHH:MM“ oder „JJJJ-MM-TT“ → Tag und Minuten seit Mitternacht. */
export function parseLocal(value: string): { date: string; minutes: number } {
	const date = value.slice(0, 10);
	if (value.length < 16) return { date, minutes: 0 };
	return { date, minutes: Number(value.slice(11, 13)) * 60 + Number(value.slice(14, 16)) };
}

export function minutesToTime(minutes: number): string {
	const m = Math.max(0, Math.min(24 * 60 - 1, Math.round(minutes)));
	return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

export function snap(minutes: number, step = 15): number {
	return Math.round(minutes / step) * step;
}

export function durationMinutes(startLocal: string, endLocal: string): number {
	const a = parseLocal(startLocal);
	const b = parseLocal(endLocal);
	return diffDays(a.date, b.date) * 1440 + b.minutes - a.minutes;
}

/** Minuten auf einen Tag addieren (mit Tagesüberlauf). */
export function addMinutes(date: string, minutes: number): { date: string; minutes: number } {
	const days = Math.floor(minutes / 1440);
	return { date: addDays(date, days), minutes: minutes - days * 1440 };
}

interface Timed {
	all_day: boolean;
	start_local: string;
	end_local: string;
}

export function coversDay(item: Timed, day: string): boolean {
	if (item.all_day) return item.start_local <= day && day < item.end_local;
	const start = item.start_local.slice(0, 10);
	return start === day;
}

export interface DaySegment<T> {
	item: T;
	start: number;
	end: number;
}

/** Anteil eines zeitgebundenen Termins an einem Tag (auch über Mitternacht). */
export function segmentFor<T extends Timed>(item: T, day: string): DaySegment<T> | null {
	if (item.all_day) return null;
	const s = parseLocal(item.start_local);
	const e = parseLocal(item.end_local);
	if (s.date > day || e.date < day) return null;
	if (e.date === day && s.date < day && e.minutes === 0) return null; // endet um Mitternacht
	const start = s.date === day ? s.minutes : 0;
	const end = e.date === day ? e.minutes : 1440;
	return { item, start, end: Math.max(end, start) };
}

export interface Placed<T> extends DaySegment<T> {
	column: number;
	columns: number;
}

/** Überlappende Termine nebeneinander anordnen (Spalten je Überlappungsgruppe). */
export function layoutDay<T>(segments: DaySegment<T>[], minLength = 20): Placed<T>[] {
	const sorted = [...segments].sort((a, b) => a.start - b.start || b.end - a.end);
	const placed: Placed<T>[] = [];
	let group: Placed<T>[] = [];
	let columnEnds: number[] = [];
	let groupEnd = -1;

	const closeGroup = () => {
		for (const entry of group) entry.columns = columnEnds.length;
		group = [];
		columnEnds = [];
	};

	for (const segment of sorted) {
		const end = Math.max(segment.end, segment.start + minLength);
		if (segment.start >= groupEnd) {
			closeGroup();
			groupEnd = -1;
		}
		let column = columnEnds.findIndex((columnEnd) => columnEnd <= segment.start);
		if (column === -1) {
			column = columnEnds.length;
			columnEnds.push(end);
		} else {
			columnEnds[column] = end;
		}
		const entry: Placed<T> = { ...segment, column, columns: 1 };
		group.push(entry);
		placed.push(entry);
		groupEnd = Math.max(groupEnd, end);
	}
	closeGroup();
	return placed;
}
