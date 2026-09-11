/** Termine laden, verschieben und Serien-Rückfragen. */

import { api, ApiError } from '$lib/api';
import { addMinutes, durationMinutes, minutesToTime, parseLocal } from '$lib/calendar';
import { addDays, diffDays } from '$lib/dates';
import { t } from '$lib/i18n/index.svelte';
import { areas } from '$lib/stores/areas.svelte';
import { choice } from '$lib/stores/choice.svelte';
import { toasts } from '$lib/stores/toasts.svelte';
import { ui } from '$lib/stores/ui.svelte';
import type { Conflict, EventScope, EventWriteResult, Occurrence, Task } from '$lib/types';

/** Reaktive Abfrage von Terminen und fälligen Aufgaben in einem Zeitraum. */
export function calendarQuery(range: () => { from: string; to: string }) {
	const state = $state({
		occurrences: [] as Occurrence[],
		tasks: [] as Task[],
		loading: true,
		error: null as string | null
	});
	let sequence = 0;

	$effect(() => {
		const { from, to } = range();
		const area_id = areas.filterId;
		void ui.version;
		const mine = ++sequence;
		state.loading = true;
		Promise.all([
			api<Occurrence[]>('/events', { query: { from, to, area_id } }),
			api<Task[]>('/tasks', { query: { view: 'all', from, to, area_id } })
		])
			.then(([occurrences, tasks]) => {
				if (mine !== sequence) return;
				state.occurrences = occurrences;
				state.tasks = tasks;
				state.error = null;
			})
			.catch((error: unknown) => {
				if (mine === sequence)
					state.error = error instanceof ApiError ? error.message : t('error.generic');
			})
			.finally(() => {
				if (mine === sequence) state.loading = false;
			});
	});

	return state;
}

/** Welche Zeile ist gemeint? Serienvorkommen gehen über die Serie plus Vorkommen. */
export function targetOf(occ: Occurrence): { id: string; occurrence?: string } {
	if (occ.recurring && occ.series_id && occ.event_id === occ.series_id && occ.recurrence_id) {
		return { id: occ.series_id, occurrence: occ.recurrence_id };
	}
	return { id: occ.event_id };
}

export async function askScope(deleting = false): Promise<EventScope | null> {
	const answer = await choice.ask(
		t('scope.title'),
		deleting ? t('scope.deleteQuestion') : t('scope.question'),
		[
			{ value: 'this', label: t('scope.this'), primary: true },
			{ value: 'following', label: t('scope.following') },
			{ value: 'all', label: t('scope.all'), danger: deleting }
		]
	);
	return answer as EventScope | null;
}

export function reportConflicts(conflicts: Conflict[]): void {
	if (conflicts.length === 0) return;
	toasts.show(t('event.conflict', { titles: conflicts.map((c) => c.title).join(', ') }));
}

/** Termin per Drag & Drop verschieben. ``minutes`` null = Zeit behalten bzw. ganztägig. */
export async function moveOccurrence(
	occ: Occurrence,
	target: { date: string; minutes: number | null; allDay?: boolean }
): Promise<void> {
	const start = parseLocal(occ.start_local);
	let body: Record<string, unknown>;
	if (occ.all_day || target.allDay) {
		const span = occ.all_day ? Math.max(1, diffDays(occ.start_local, occ.end_local)) : 1;
		body = {
			all_day: true,
			start_date: target.date,
			end_date: addDays(target.date, span - 1),
			start_time: null,
			end_time: null
		};
	} else {
		const minutes = target.minutes ?? start.minutes;
		const end = addMinutes(target.date, minutes + durationMinutes(occ.start_local, occ.end_local));
		body = {
			all_day: false,
			start_date: target.date,
			start_time: minutesToTime(minutes),
			end_date: end.date,
			end_time: minutesToTime(end.minutes)
		};
	}
	if (body.start_date === start.date && body.start_time === minutesToTime(start.minutes)) return;

	if (occ.is_fixed) {
		const sure = await choice.ask(t('event.fixed'), t('event.fixedConfirm', { title: occ.title }), [
			{ value: 'yes', label: t('event.move'), primary: true }
		]);
		if (!sure) return;
	}
	let scope: EventScope = 'all';
	if (occ.recurring) {
		const answer = await askScope();
		if (!answer) return;
		scope = answer;
	}
	const target_ = targetOf(occ);
	try {
		const result = await api<EventWriteResult>(`/events/${target_.id}`, {
			method: 'PATCH',
			query: { scope, occurrence: target_.occurrence },
			body
		});
		ui.changed();
		toasts.show(t('event.moved'));
		reportConflicts(result.conflicts);
	} catch (error) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}
}

/** Gezogenes Element (HTML-Drag-and-Drop liefert keine Objekte). */
export const dragging = $state({
	occ: null as Occurrence | null,
	/** Abstand vom oberen Rand des Termins in Minuten – damit er nicht „springt“. */
	grabMinutes: 0
});

export function reminderLabel(minutes: number): string {
	if (minutes === 0) return t('rem.start');
	if (minutes % 10080 === 0) return t('rem.weeks', { n: minutes / 10080 });
	if (minutes % 1440 === 0) return t('rem.days', { n: minutes / 1440 });
	if (minutes % 60 === 0) return t('rem.hours', { n: minutes / 60 });
	return t('rem.minutes', { n: minutes });
}

export const REMINDER_PRESETS = [0, 10, 30, 60, 120, 1440, 2880, 10080];
