/** Datums-Hilfen. Alle Tage sind ISO-Strings (JJJJ-MM-TT) ohne Zeitzone. */

export interface DayLabels {
	today: string;
	tomorrow: string;
	yesterday: string;
}

function parts(iso: string): [number, number, number] {
	const [y, m, d] = iso.split('-').map(Number);
	return [y ?? 1970, m ?? 1, d ?? 1];
}

function utc(iso: string): number {
	const [y, m, d] = parts(iso);
	return Date.UTC(y, m - 1, d);
}

/** Heutiges Datum in der Zeitzone des Nutzers. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
	return new Intl.DateTimeFormat('en-CA', {
		timeZone,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit'
	}).format(now);
}

export function addDays(iso: string, days: number): string {
	return new Date(utc(iso) + days * 86_400_000).toISOString().slice(0, 10);
}

/** Tage von `from` bis `to` (positiv, wenn `to` später liegt). */
export function diffDays(from: string, to: string): number {
	return Math.round((utc(to) - utc(from)) / 86_400_000);
}

export function formatDay(iso: string, today: string, locale: string, labels: DayLabels): string {
	const diff = diffDays(today, iso);
	if (diff === 0) return labels.today;
	if (diff === 1) return labels.tomorrow;
	if (diff === -1) return labels.yesterday;
	const date = new Date(utc(iso));
	if (diff > 1 && diff < 7) {
		return new Intl.DateTimeFormat(locale, { weekday: 'long', timeZone: 'UTC' }).format(date);
	}
	const sameYear = iso.slice(0, 4) === today.slice(0, 4);
	return new Intl.DateTimeFormat(locale, {
		weekday: 'short',
		day: 'numeric',
		month: 'short',
		year: sameYear ? undefined : 'numeric',
		timeZone: 'UTC'
	}).format(date);
}

export function formatLongDate(iso: string, locale: string): string {
	return new Intl.DateTimeFormat(locale, {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		timeZone: 'UTC'
	}).format(new Date(utc(iso)));
}

export function formatTime(time: string | null): string {
	return time ? time.slice(0, 5) : '';
}

export function isValidIsoDate(value: string): boolean {
	if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
	const [y, m, d] = parts(value);
	const date = new Date(Date.UTC(y, m - 1, d));
	return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}
