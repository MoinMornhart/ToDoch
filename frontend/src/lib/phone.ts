/**
 * Formular „Telefontermin“: Entwurf, lokale Zwischenspeicherung und Umwandlung in die
 * Anfrage an POST /api/appointments. Reine Funktionen – getestet in phone.test.ts.
 */

import { addMinutes, minutesToTime, parseLocal } from '$lib/calendar';
import { parseTags } from '$lib/tags';
import type { Channel, Contact, Priority } from '$lib/types';

export type PlaceKind = 'phone' | 'onsite' | 'video' | 'other';

export const CHANNELS: Channel[] = ['phone', 'in_person', 'mail', 'other'];
export const PLACE_KINDS: PlaceKind[] = ['phone', 'onsite', 'video', 'other'];
export const DURATIONS = [15, 30, 45, 60, 90, 120, 180];

export interface PhoneDraft {
	contactId: string | null;
	name: string;
	company: string;
	phone: string;
	email: string;
	address: string;
	title: string;
	date: string;
	time: string;
	duration: number;
	allDay: boolean;
	placeKind: PlaceKind;
	place: string;
	url: string;
	tzid: string;
	channel: Channel;
	agreedOn: string;
	agreedWith: string;
	notes: string;
	areaId: string;
	tags: string;
	priority: Priority;
	reminders: number[];
	followUp: boolean;
	followUpTitle: string;
	followUpDays: number;
}

export type ContactFields = Pick<
	PhoneDraft,
	'contactId' | 'name' | 'company' | 'phone' | 'email' | 'address'
>;

export function blankDraft(
	today: string,
	tzid: string,
	areaId: string,
	followUpTitle: string
): PhoneDraft {
	return {
		contactId: null,
		name: '',
		company: '',
		phone: '',
		email: '',
		address: '',
		title: '',
		date: today,
		time: '09:00',
		duration: 30,
		allDay: false,
		// Meist ein Termin vor Ort (z. B. Arzt), der nur am Telefon ausgemacht wurde
		placeKind: 'onsite',
		place: '',
		url: '',
		tzid,
		channel: 'phone',
		agreedOn: today,
		agreedWith: '',
		notes: '',
		areaId,
		tags: '',
		priority: 0,
		reminders: [30],
		followUp: false,
		followUpTitle,
		followUpDays: 1
	};
}

export function contactFields(contact: Contact): ContactFields {
	return {
		contactId: contact.id,
		name: contact.name,
		company: contact.company,
		phone: contact.phone,
		email: contact.email,
		address: contact.address
	};
}

export const EMPTY_CONTACT: ContactFields = {
	contactId: null,
	name: '',
	company: '',
	phone: '',
	email: '',
	address: ''
};

/** Noch nichts Eigenes eingetragen – dann lohnt kein Entwurf. */
export function isDraftEmpty(draft: PhoneDraft): boolean {
	return [
		draft.name,
		draft.company,
		draft.phone,
		draft.email,
		draft.address,
		draft.title,
		draft.notes
	].every((value) => !value.trim());
}

// --- Entwurf im Browser (pro Nutzer) ---------------------------------------------------------

const DRAFT_KEY = 'todoch-phone-draft';

type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;

function storage(): Storage | null {
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

export function loadDraft(
	userId: string,
	fallback: PhoneDraft,
	store: Storage | null = storage()
): PhoneDraft | null {
	try {
		const raw = store?.getItem(`${DRAFT_KEY}:${userId}`);
		if (!raw) return null;
		const data: unknown = JSON.parse(raw);
		if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
		return { ...fallback, ...(data as Partial<PhoneDraft>) };
	} catch {
		return null;
	}
}

export function saveDraft(userId: string, draft: PhoneDraft, store: Storage | null = storage()) {
	try {
		store?.setItem(`${DRAFT_KEY}:${userId}`, JSON.stringify(draft));
	} catch {
		// Speicher voll oder gesperrt – dann eben ohne Entwurf
	}
}

export function clearDraft(userId: string, store: Storage | null = storage()) {
	try {
		store?.removeItem(`${DRAFT_KEY}:${userId}`);
	} catch {
		// nichts zu tun
	}
}

// --- Anfrage ---------------------------------------------------------------------------------

export function locationFor(draft: PhoneDraft, labels: Record<PlaceKind, string>): string {
	const place = draft.place.trim();
	switch (draft.placeKind) {
		case 'phone':
			return draft.phone.trim() ? `${labels.phone}: ${draft.phone.trim()}` : labels.phone;
		case 'onsite':
			return place || labels.onsite;
		case 'video':
			return labels.video;
		default:
			return place;
	}
}

export function titleFor(draft: PhoneDraft, defaultTitle: string): string {
	const name = draft.name.trim();
	const company = draft.company.trim();
	if (draft.title.trim()) return draft.title.trim();
	if (!name) return '';
	return company ? `${defaultTitle} ${name} (${company})` : `${defaultTitle} ${name}`;
}

export function appointmentPayload(
	draft: PhoneDraft,
	defaultTitle: string,
	placeLabels: Record<PlaceKind, string>
) {
	const start = parseLocal(`${draft.date}T${draft.time}`).minutes;
	const end = addMinutes(draft.date, start + draft.duration);
	const name = draft.name.trim();
	return {
		contact_id: draft.contactId,
		contact: name
			? {
					name,
					company: draft.company.trim(),
					phone: draft.phone.trim(),
					email: draft.email.trim() || null,
					address: draft.address.trim()
				}
			: null,
		event: {
			title: titleFor(draft, defaultTitle),
			all_day: draft.allDay,
			start_date: draft.date,
			start_time: draft.allDay ? null : draft.time,
			end_date: draft.allDay ? draft.date : end.date,
			end_time: draft.allDay ? null : minutesToTime(end.minutes),
			location: locationFor(draft, placeLabels),
			url: draft.placeKind === 'video' ? draft.url.trim() : '',
			description: draft.notes,
			tzid: draft.tzid,
			channel: draft.channel,
			agreed_on: draft.agreedOn || null,
			agreed_with: draft.agreedWith.trim(),
			priority: draft.priority,
			tags: parseTags(draft.tags),
			reminders: draft.reminders,
			...(draft.areaId ? { area_id: draft.areaId } : {})
		},
		follow_up:
			draft.followUp && draft.followUpTitle.trim()
				? {
						title: draft.followUpTitle.trim(),
						days_before: draft.followUpDays,
						priority: draft.priority
					}
				: null
	};
}

export function mailtoLink(to: string, subject: string, body: string): string {
	return `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
