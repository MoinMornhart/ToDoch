import type { Attendee } from '$lib/types';

/** „Anna Berger <anna@firma.de>“ je Zeile → Teilnehmerliste. */
export function parseAttendees(text: string): Attendee[] {
	const result: Attendee[] = [];
	for (const raw of text.split('\n')) {
		const line = raw.trim();
		if (!line) continue;
		const match = line.match(/^(.*?)\s*<([^<>\s]+@[^<>\s]+)>$/);
		if (match) result.push({ name: (match[1] ?? '').trim(), email: match[2] ?? null });
		else if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(line)) result.push({ name: '', email: line });
		else result.push({ name: line.slice(0, 200), email: null });
		if (result.length >= 50) break;
	}
	return result;
}

export function formatAttendees(attendees: Attendee[]): string {
	return attendees
		.map((a) => (a.email ? (a.name ? `${a.name} <${a.email}>` : a.email) : a.name))
		.join('\n');
}
