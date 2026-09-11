/** Wiederholungsregeln (RRULE-Untermenge, wie im Backend) für den Editor. */

export const FREQUENCIES = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'] as const;
export const WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'] as const;

export type Frequency = (typeof FREQUENCIES)[number];
export type Weekday = (typeof WEEKDAYS)[number];

export interface RecurrenceForm {
	freq: Frequency | 'NONE';
	interval: number;
	byday: Weekday[];
	until: string;
}

export const EMPTY_RECURRENCE: RecurrenceForm = { freq: 'NONE', interval: 1, byday: [], until: '' };

export function parseRule(rule: string | null): RecurrenceForm {
	if (!rule) return { ...EMPTY_RECURRENCE, byday: [] };
	const fields = new Map<string, string>();
	for (const part of rule.replace(/^RRULE:/i, '').split(';')) {
		const [key, value] = part.split('=');
		if (key && value) fields.set(key.toUpperCase(), value.toUpperCase());
	}
	const freq = fields.get('FREQ');
	if (!freq || !(FREQUENCIES as readonly string[]).includes(freq)) return { ...EMPTY_RECURRENCE };
	const until = fields.get('UNTIL');
	return {
		freq: freq as Frequency,
		interval: Math.max(1, Number(fields.get('INTERVAL') ?? 1) || 1),
		byday: (fields.get('BYDAY') ?? '')
			.split(',')
			.filter((d): d is Weekday => (WEEKDAYS as readonly string[]).includes(d)),
		until: until ? `${until.slice(0, 4)}-${until.slice(4, 6)}-${until.slice(6, 8)}` : ''
	};
}

export function buildRule(form: RecurrenceForm): string | null {
	if (form.freq === 'NONE') return null;
	const parts = [`FREQ=${form.freq}`];
	const interval = Math.min(365, Math.max(1, Math.round(form.interval || 1)));
	if (interval > 1) parts.push(`INTERVAL=${interval}`);
	if (form.freq === 'WEEKLY' && form.byday.length > 0) {
		parts.push('BYDAY=' + WEEKDAYS.filter((d) => form.byday.includes(d)).join(','));
	}
	if (form.until) parts.push('UNTIL=' + form.until.replaceAll('-', ''));
	return parts.join(';');
}

const WEEKDAY_INDEX: Record<Weekday, number> = { MO: 1, TU: 2, WE: 3, TH: 4, FR: 5, SA: 6, SU: 0 };

export function weekdayName(
	day: Weekday,
	locale: string,
	style: 'short' | 'long' = 'short'
): string {
	// 2023-01-01 war ein Sonntag.
	const date = new Date(Date.UTC(2023, 0, 1 + WEEKDAY_INDEX[day]));
	return new Intl.DateTimeFormat(locale, { weekday: style, timeZone: 'UTC' }).format(date);
}

export interface RuleLabels {
	freq: Record<Frequency, string>;
	every: string;
	units: Record<Frequency, string>;
	until: string;
}

export function describeRule(rule: string | null, locale: string, labels: RuleLabels): string {
	const form = parseRule(rule);
	if (form.freq === 'NONE') return '';
	let text =
		form.interval > 1
			? `${labels.every} ${form.interval} ${labels.units[form.freq]}`
			: labels.freq[form.freq];
	if (form.byday.length > 0)
		text += ` · ${form.byday.map((d) => weekdayName(d, locale)).join(', ')}`;
	if (form.until) {
		const until = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(
			new Date(`${form.until}T00:00:00Z`)
		);
		text += ` · ${labels.until} ${until}`;
	}
	return text;
}
