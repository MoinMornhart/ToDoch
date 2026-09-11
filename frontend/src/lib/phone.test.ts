import { describe, expect, it } from 'vitest';
import {
	appointmentPayload,
	blankDraft,
	clearDraft,
	isDraftEmpty,
	loadDraft,
	locationFor,
	mailtoLink,
	saveDraft,
	titleFor,
	type PhoneDraft
} from './phone';

const LABELS = { phone: 'Telefonisch', onsite: 'Vor Ort', video: 'Video', other: 'Sonstiges' };

function draft(changes: Partial<PhoneDraft> = {}): PhoneDraft {
	return { ...blankDraft('2026-09-14', 'Europe/Berlin', 'area-1', 'Vorbereiten'), ...changes };
}

function memoryStore() {
	const data = new Map<string, string>();
	return {
		getItem: (key: string) => data.get(key) ?? null,
		setItem: (key: string, value: string) => void data.set(key, value),
		removeItem: (key: string) => void data.delete(key),
		data
	};
}

describe('Telefontermin', () => {
	it('beginnt leer mit sinnvollen Vorgaben', () => {
		const d = draft();
		expect(isDraftEmpty(d)).toBe(true);
		expect(d.agreedOn).toBe('2026-09-14');
		expect(d.channel).toBe('phone');
		expect(isDraftEmpty(draft({ notes: 'Rückruf' }))).toBe(false);
		expect(isDraftEmpty(draft({ name: '  ' }))).toBe(true);
	});

	it('berechnet das Ende aus der Dauer, auch über Mitternacht', () => {
		const body = appointmentPayload(draft({ time: '10:00', duration: 30 }), 'Termin mit', LABELS);
		expect(body.event.end_date).toBe('2026-09-14');
		expect(body.event.end_time).toBe('10:30');
		const late = appointmentPayload(draft({ time: '23:45', duration: 30 }), 'Termin mit', LABELS);
		expect(late.event.end_date).toBe('2026-09-15');
		expect(late.event.end_time).toBe('00:15');
	});

	it('ganztägig ohne Uhrzeit', () => {
		const body = appointmentPayload(draft({ allDay: true }), 'Termin mit', LABELS);
		expect(body.event).toMatchObject({ all_day: true, start_time: null, end_time: null });
		expect(body.event.end_date).toBe('2026-09-14');
	});

	it('bildet den Titel aus Name und Firma, wenn keiner eingetragen ist', () => {
		expect(titleFor(draft({ name: 'Anna' }), 'Termin mit')).toBe('Termin mit Anna');
		expect(titleFor(draft({ name: 'Anna', company: 'ACME' }), 'Termin mit')).toBe(
			'Termin mit Anna (ACME)'
		);
		expect(titleFor(draft({ name: 'Anna', title: ' Beratung ' }), 'Termin mit')).toBe('Beratung');
		expect(titleFor(draft(), 'Termin mit')).toBe('');
	});

	it('schickt Kontakt und Folgeaufgabe nur, wenn ausgefüllt', () => {
		const empty = appointmentPayload(draft(), 'Termin mit', LABELS);
		expect(empty.contact).toBeNull();
		expect(empty.follow_up).toBeNull();

		const full = appointmentPayload(
			draft({
				name: ' Anna ',
				email: ' ',
				followUp: true,
				followUpTitle: 'Akte holen',
				followUpDays: 3,
				priority: 2,
				tags: '#kunde, wichtig'
			}),
			'Termin mit',
			LABELS
		);
		expect(full.contact).toMatchObject({ name: 'Anna', email: null });
		expect(full.follow_up).toEqual({ title: 'Akte holen', days_before: 3, priority: 2 });
		expect(full.event.tags).toEqual(['kunde', 'wichtig']);
		expect(full.event.area_id).toBe('area-1');
	});

	it('beschreibt den Ort je nach Art', () => {
		expect(locationFor(draft(), LABELS)).toBe('Vor Ort');
		const byPhone = draft({ placeKind: 'phone', phone: '030 1' });
		expect(locationFor(byPhone, LABELS)).toBe('Telefonisch: 030 1');
		expect(locationFor(draft({ placeKind: 'phone' }), LABELS)).toBe('Telefonisch');
		expect(locationFor(draft({ placeKind: 'onsite' }), LABELS)).toBe('Vor Ort');
		expect(locationFor(draft({ placeKind: 'onsite', place: 'Büro 3' }), LABELS)).toBe('Büro 3');
		const video = draft({ placeKind: 'video', url: ' https://meet.example/x ' });
		expect(locationFor(video, LABELS)).toBe('Video');
		expect(appointmentPayload(video, 'x', LABELS).event.url).toBe('https://meet.example/x');
		expect(appointmentPayload(draft({ url: 'https://x' }), 'x', LABELS).event.url).toBe('');
	});

	it('speichert den Entwurf pro Nutzer und ergänzt fehlende Felder', () => {
		const store = memoryStore();
		saveDraft('u1', draft({ name: 'Anna' }), store);
		expect(loadDraft('u2', draft(), store)).toBeNull();
		expect(loadDraft('u1', draft(), store)?.name).toBe('Anna');

		store.setItem('todoch-phone-draft:u1', JSON.stringify({ name: 'Alt' }));
		const merged = loadDraft('u1', draft(), store);
		expect(merged?.name).toBe('Alt');
		expect(merged?.duration).toBe(30);

		store.setItem('todoch-phone-draft:u1', '{kaputt');
		expect(loadDraft('u1', draft(), store)).toBeNull();
		clearDraft('u1', store);
		expect(store.data.size).toBe(0);
	});

	it('baut mailto-Links sicher zusammen', () => {
		expect(mailtoLink('a@b.de', 'Termin & Co', 'Zeile 1\nZeile 2')).toBe(
			'mailto:a%40b.de?subject=Termin%20%26%20Co&body=Zeile%201%0AZeile%202'
		);
	});
});
