<script lang="ts">
	import { Download, Mail, Phone, Trash, UserRound } from '@lucide/svelte';
	import { formatLongDate } from '$lib/dates';
	import { tick } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { formatAttendees, parseAttendees } from '$lib/attendees';
	import { addMinutes, minutesToTime, parseLocal } from '$lib/calendar';
	import { askScope, REMINDER_PRESETS, reminderLabel, reportConflicts } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import {
		buildRule,
		FREQUENCIES,
		parseRule,
		weekdayName,
		WEEKDAYS,
		type RecurrenceForm,
		type Weekday
	} from '$lib/recurrence';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import { parseTags } from '$lib/tags';
	import type {
		EventDetail,
		EventEditorRequest,
		EventScope,
		EventStatus,
		EventWriteResult
	} from '$lib/types';
	import Dialog from './Dialog.svelte';

	interface Form {
		title: string;
		all_day: boolean;
		start_date: string;
		start_time: string;
		end_date: string;
		end_time: string;
		area_id: string;
		location: string;
		url: string;
		description: string;
		recurrence: RecurrenceForm;
		recurrenceDirty: boolean;
		reminders: number[];
		status: EventStatus;
		is_fixed: boolean;
		free: boolean;
		attendees: string;
		tags: string;
	}

	const STATUSES: EventStatus[] = ['confirmed', 'tentative', 'cancelled'];
	const uid = $props.id();
	let open = $state(false);
	let request = $state<EventEditorRequest | null>(null);
	let detail = $state<EventDetail | null>(null);
	let form = $state<Form | null>(null);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let confirmDelete = $state(false);
	let titleInput: HTMLInputElement | undefined = $state();

	const recurring = $derived(
		detail !== null && (detail.rrule !== null || detail.series_id !== null)
	);
	const isOverride = $derived(detail?.series_id != null);

	function message(err: unknown): string {
		return err instanceof ApiError ? err.message : t('error.generic');
	}

	function blank(date: string, time?: string, allDay?: boolean): Form {
		const start = parseLocal(`${date}T${time ?? '09:00'}`).minutes;
		const end = addMinutes(date, start + 60);
		return {
			title: '',
			all_day: allDay ?? false,
			start_date: date,
			start_time: minutesToTime(start),
			end_date: allDay ? date : end.date,
			end_time: minutesToTime(end.minutes),
			area_id: areas.filterId ?? areas.list[0]?.id ?? '',
			location: '',
			url: '',
			description: '',
			recurrence: parseRule(null),
			recurrenceDirty: false,
			reminders: [],
			status: 'confirmed',
			is_fixed: false,
			free: false,
			attendees: '',
			tags: ''
		};
	}

	function fromDetail(d: EventDetail): Form {
		return {
			title: d.title,
			all_day: d.all_day,
			start_date: d.start_date,
			start_time: d.start_time?.slice(0, 5) ?? '09:00',
			end_date: d.end_date,
			end_time: d.end_time?.slice(0, 5) ?? '10:00',
			area_id: d.area_id,
			location: d.location,
			url: d.url,
			description: d.description,
			recurrence: parseRule(d.rrule),
			recurrenceDirty: false,
			reminders: [...d.reminders],
			status: d.status,
			is_fixed: d.is_fixed,
			free: d.transparency === 'transparent',
			attendees: formatAttendees(d.attendees),
			tags: d.tags.join(' ')
		};
	}

	async function load(req: EventEditorRequest) {
		error = null;
		confirmDelete = false;
		request = req;
		if (req.mode === 'new') {
			detail = null;
			form = blank(req.date, req.time, req.allDay);
		} else {
			try {
				const loaded = await api<EventDetail>(`/events/${req.eventId}`, {
					query: { occurrence: req.occurrence ?? undefined }
				});
				if (ui.eventEditor !== req) return;
				detail = loaded;
				form = fromDetail(loaded);
			} catch (err) {
				toasts.error(message(err));
				ui.eventEditor = null;
				return;
			}
		}
		open = true;
		await tick();
		titleInput?.focus();
	}

	$effect(() => {
		const req = ui.eventEditor;
		if (req) void load(req);
	});

	function payload(f: Form): Record<string, unknown> {
		const body: Record<string, unknown> = {
			title: f.title.trim(),
			all_day: f.all_day,
			start_date: f.start_date,
			start_time: f.all_day ? null : f.start_time,
			end_date: f.end_date || f.start_date,
			end_time: f.all_day ? null : f.end_time,
			location: f.location,
			url: f.url.trim(),
			description: f.description,
			status: f.status,
			transparency: f.free ? 'transparent' : 'opaque',
			is_fixed: f.is_fixed,
			reminders: f.reminders,
			attendees: parseAttendees(f.attendees),
			tags: parseTags(f.tags)
		};
		if (f.area_id) body.area_id = f.area_id;
		if (!detail || f.recurrenceDirty) body.rrule = buildRule(f.recurrence);
		return body;
	}

	async function save(event?: Event) {
		event?.preventDefault();
		if (!form || !request || saving) return;
		if (!form.title.trim()) {
			error = t('task.titleRequired');
			return;
		}
		saving = true;
		error = null;
		try {
			let result: EventWriteResult;
			if (request.mode === 'new') {
				result = await api<EventWriteResult>('/events', { method: 'POST', body: payload(form) });
			} else {
				let scope: EventScope = 'all';
				if (recurring) {
					const answer = await askScope();
					if (!answer) return;
					scope = answer;
				}
				result = await api<EventWriteResult>(`/events/${request.eventId}`, {
					method: 'PATCH',
					query: { scope, occurrence: request.occurrence ?? undefined },
					body: payload(form)
				});
			}
			ui.changed();
			toasts.show(t('event.saved'));
			reportConflicts(result.conflicts);
			open = false;
		} catch (err) {
			error = message(err);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (!request || request.mode !== 'edit') return;
		let scope: EventScope = 'all';
		if (recurring) {
			const answer = await askScope(true);
			if (!answer) return;
			scope = answer;
		} else if (!confirmDelete) {
			confirmDelete = true;
			return;
		}
		try {
			await api(`/events/${request.eventId}`, {
				method: 'DELETE',
				query: { scope, occurrence: request.occurrence ?? undefined }
			});
			ui.changed();
			toasts.show(t('event.deleted'));
			open = false;
		} catch (err) {
			error = message(err);
		}
	}

	function keepEndAfterStart() {
		if (!form) return;
		if (form.end_date < form.start_date) form.end_date = form.start_date;
		if (!form.all_day && form.end_date === form.start_date && form.end_time <= form.start_time) {
			const end = addMinutes(
				form.start_date,
				parseLocal(`${form.start_date}T${form.start_time}`).minutes + 60
			);
			form.end_date = end.date;
			form.end_time = minutesToTime(end.minutes);
		}
	}

	function toggleReminder(minutes: number) {
		if (!form) return;
		form.reminders = form.reminders.includes(minutes)
			? form.reminders.filter((m) => m !== minutes)
			: [...form.reminders, minutes].sort((a, b) => a - b);
	}

	function toggleWeekday(day: Weekday) {
		if (!form) return;
		const days = form.recurrence.byday;
		form.recurrence.byday = days.includes(day) ? days.filter((d) => d !== day) : [...days, day];
		form.recurrenceDirty = true;
	}

	function onKeydown(event: KeyboardEvent) {
		if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
			event.preventDefault();
			void save();
		}
	}

	const agreement = $derived.by(() => {
		if (!detail?.channel) return '';
		const parts = [t('event.agreed', { channel: t(`phone.channel.${detail.channel}`) })];
		if (detail.agreed_on) {
			parts.push(t('event.agreedOn', { date: formatLongDate(detail.agreed_on, i18n.locale) }));
		}
		if (detail.agreed_with) parts.push(t('event.agreedWith', { name: detail.agreed_with }));
		return parts.join(' ');
	});

	function openTask(id: string) {
		open = false;
		ui.editTaskId = id;
	}

	function anotherAppointment(contactId: string) {
		open = false;
		ui.phoneForm = { contactId };
	}

	function onClose() {
		ui.eventEditor = null;
		request = null;
		detail = null;
		form = null;
	}
</script>

<Dialog
	bind:open
	title={request?.mode === 'new' ? t('event.new') : t('event.edit')}
	size="lg"
	onclose={onClose}
>
	{#if form}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<form class="flex flex-col gap-4" onsubmit={save} onkeydown={onKeydown}>
			{#if error}<p role="alert" class="text-sm text-danger">{error}</p>{/if}
			{#if detail?.read_only}
				<p class="rounded-lg bg-surface-2 px-3 py-2 text-sm">
					{t('event.readOnly', { name: detail.calendar_name ?? '' })}
				</p>
			{/if}
			<fieldset class="contents" disabled={detail?.read_only ?? false}>
				{#if detail && (detail.contact || agreement || detail.tasks.length)}
					<section
						aria-label={t('event.contact')}
						class="flex flex-col gap-2 rounded-lg border border-line bg-surface-2/60 p-3 text-sm"
					>
						{#if detail.contact}
							{@const contact = detail.contact}
							<div class="flex flex-wrap items-start justify-between gap-2">
								<div class="min-w-0">
									<p class="flex items-center gap-1.5 font-medium">
										<UserRound size={15} aria-hidden="true" />{contact.name}
										{#if contact.company}<span class="font-normal text-muted"
												>· {contact.company}</span
											>{/if}
									</p>
									<p class="mt-1 flex flex-wrap gap-x-4 gap-y-1">
										{#if contact.phone}
											<a
												class="inline-flex items-center gap-1 text-accent"
												href="tel:{contact.phone}"
											>
												<Phone size={13} aria-hidden="true" />{contact.phone}
											</a>
										{/if}
										{#if contact.email}
											<a
												class="inline-flex items-center gap-1 text-accent"
												href="mailto:{contact.email}"
											>
												<Mail size={13} aria-hidden="true" />{contact.email}
											</a>
										{/if}
									</p>
									{#if contact.address}
										<p class="mt-1 whitespace-pre-line text-muted">{contact.address}</p>
									{/if}
								</div>
								<button
									type="button"
									class="btn px-2.5 py-1 text-xs"
									onclick={() => anotherAppointment(contact.id)}
								>
									{t('event.another')}
								</button>
							</div>
						{/if}
						{#if agreement}<p class="text-muted">{agreement}</p>{/if}
						{#if detail.tasks.length}
							<div>
								<p class="text-xs font-medium text-muted">{t('event.tasks')}</p>
								<ul class="mt-1 flex flex-col gap-0.5">
									{#each detail.tasks as linked (linked.id)}
										<li>
											<button
												type="button"
												class="text-left {linked.status === 'done'
													? 'text-muted line-through'
													: 'text-accent'}"
												onclick={() => openTask(linked.id)}
											>
												{linked.title}{#if linked.due_date}
													<span class="text-muted">
														· {formatLongDate(linked.due_date, i18n.locale)}</span
													>{/if}
											</button>
										</li>
									{/each}
								</ul>
							</div>
						{/if}
					</section>
				{/if}

				<div>
					<label class="label" for="{uid}-title">{t('event.title')}</label>
					<input
						id="{uid}-title"
						bind:this={titleInput}
						class="input"
						bind:value={form.title}
						maxlength="300"
						required
					/>
				</div>

				<label class="flex items-center gap-2 text-sm">
					<input type="checkbox" class="size-4 accent-accent" bind:checked={form.all_day} />
					{t('event.allDay')}
				</label>

				<div class="grid gap-3 sm:grid-cols-2">
					<div class="flex gap-2">
						<div class="flex-1">
							<label class="label" for="{uid}-start">{t('event.start')}</label>
							<input
								id="{uid}-start"
								type="date"
								class="input"
								bind:value={form.start_date}
								onchange={keepEndAfterStart}
								required
							/>
						</div>
						{#if !form.all_day}
							<div class="w-28">
								<label class="label" for="{uid}-start-time">{t('event.time')}</label>
								<input
									id="{uid}-start-time"
									type="time"
									class="input"
									aria-label={t('event.startTime')}
									bind:value={form.start_time}
									onchange={keepEndAfterStart}
									required
								/>
							</div>
						{/if}
					</div>
					<div class="flex gap-2">
						<div class="flex-1">
							<label class="label" for="{uid}-end">{t('event.end')}</label>
							<input
								id="{uid}-end"
								type="date"
								class="input"
								bind:value={form.end_date}
								min={form.start_date}
							/>
						</div>
						{#if !form.all_day}
							<div class="w-28">
								<label class="label" for="{uid}-end-time">{t('event.time')}</label>
								<input
									id="{uid}-end-time"
									type="time"
									class="input"
									aria-label={t('event.endTime')}
									bind:value={form.end_time}
								/>
							</div>
						{/if}
					</div>
				</div>

				<div class="grid gap-3 sm:grid-cols-2">
					<div>
						<label class="label" for="{uid}-area">{t('task.area')}</label>
						<select id="{uid}-area" class="input" bind:value={form.area_id}>
							{#each areas.list as area (area.id)}
								<option value={area.id}>{area.name}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="label" for="{uid}-location">{t('event.location')}</label>
						<input id="{uid}-location" class="input" bind:value={form.location} maxlength="500" />
					</div>
				</div>

				{#if !isOverride}
					<fieldset>
						<legend class="label">{t('task.recurrence')}</legend>
						<div class="flex flex-wrap items-center gap-3">
							<select
								aria-label={t('task.recurrence')}
								class="input w-auto"
								bind:value={form.recurrence.freq}
								onchange={() => form && (form.recurrenceDirty = true)}
							>
								<option value="NONE">{t('rec.none')}</option>
								{#each FREQUENCIES as freq (freq)}
									<option value={freq}>{t(`rec.${freq}`)}</option>
								{/each}
							</select>
							{#if form.recurrence.freq !== 'NONE'}
								<label class="flex items-center gap-2 text-sm">
									{t('rec.every')}
									<input
										type="number"
										min="1"
										max="365"
										class="input w-20"
										bind:value={form.recurrence.interval}
										oninput={() => form && (form.recurrenceDirty = true)}
									/>
									{t(`rec.unit.${form.recurrence.freq}`)}
								</label>
								<label class="flex items-center gap-2 text-sm">
									{t('rec.until')}
									<input
										type="date"
										class="input w-auto"
										bind:value={form.recurrence.until}
										onchange={() => form && (form.recurrenceDirty = true)}
									/>
								</label>
							{/if}
						</div>
						{#if form.recurrence.freq === 'WEEKLY'}
							<div class="mt-2 flex flex-wrap gap-1" role="group" aria-label={t('rec.weekdays')}>
								{#each WEEKDAYS as day (day)}
									<button
										type="button"
										class="btn px-2.5 py-1 {form.recurrence.byday.includes(day)
											? 'border-accent text-accent'
											: ''}"
										aria-pressed={form.recurrence.byday.includes(day)}
										onclick={() => toggleWeekday(day)}
									>
										{weekdayName(day, i18n.locale)}
									</button>
								{/each}
							</div>
						{/if}
					</fieldset>
				{/if}

				<fieldset>
					<legend class="label">{t('event.reminders')}</legend>
					<div class="flex flex-wrap gap-1.5">
						{#each REMINDER_PRESETS as minutes (minutes)}
							<button
								type="button"
								class="btn px-2.5 py-1 text-xs {form.reminders.includes(minutes)
									? 'border-accent text-accent'
									: ''}"
								aria-pressed={form.reminders.includes(minutes)}
								onclick={() => toggleReminder(minutes)}
							>
								{reminderLabel(minutes)}
							</button>
						{/each}
					</div>
				</fieldset>

				<div class="grid gap-3 sm:grid-cols-2">
					<div>
						<label class="label" for="{uid}-status">{t('event.status')}</label>
						<select id="{uid}-status" class="input" bind:value={form.status}>
							{#each STATUSES as status (status)}
								<option value={status}>{t(`event.status.${status}`)}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="label" for="{uid}-url">{t('event.url')}</label>
						<input
							id="{uid}-url"
							type="url"
							class="input"
							bind:value={form.url}
							placeholder="https://"
							maxlength="1000"
						/>
					</div>
				</div>

				<div class="flex flex-col gap-2 text-sm">
					<label class="flex items-start gap-2">
						<input
							type="checkbox"
							class="mt-0.5 size-4 accent-accent"
							bind:checked={form.is_fixed}
						/>
						<span>{t('event.fixed')} <span class="text-muted">– {t('event.fixedHint')}</span></span>
					</label>
					<label class="flex items-center gap-2">
						<input type="checkbox" class="size-4 accent-accent" bind:checked={form.free} />
						{t('event.free')}
					</label>
				</div>

				<div>
					<label class="label" for="{uid}-attendees">{t('event.attendees')}</label>
					<textarea
						id="{uid}-attendees"
						class="input min-h-16"
						bind:value={form.attendees}
						aria-describedby="{uid}-attendees-hint"></textarea>
					<p id="{uid}-attendees-hint" class="mt-1 text-xs text-muted">
						{t('event.attendeesHint')}
					</p>
				</div>

				<div>
					<label class="label" for="{uid}-description">{t('event.description')}</label>
					<textarea
						id="{uid}-description"
						class="input min-h-24"
						bind:value={form.description}
						maxlength="50000"></textarea>
				</div>

				<div>
					<label class="label" for="{uid}-tags">{t('task.tags')}</label>
					<input id="{uid}-tags" class="input" bind:value={form.tags} autocomplete="off" />
				</div>
			</fieldset>

			<div class="flex items-center justify-between gap-2 border-t border-line pt-4">
				{#if request?.mode === 'edit'}
					<div class="flex flex-wrap gap-1">
						{#if !detail?.read_only}
							<button type="button" class="btn btn-ghost btn-danger" onclick={remove}>
								<Trash size={16} aria-hidden="true" />
								{confirmDelete ? t('task.deleteConfirm') : t('task.delete')}
							</button>
						{/if}
						<a
							class="btn btn-ghost"
							href="/api/events/{request.eventId}/ics"
							download="termin.ics"
							title={t('event.ics')}
						>
							<Download size={16} aria-hidden="true" /><span class="sr-only sm:not-sr-only"
								>{t('event.ics')}</span
							>
						</a>
					</div>
				{:else}
					<span></span>
				{/if}
				<div class="flex gap-2">
					<button type="button" class="btn" onclick={() => (open = false)}
						>{t('task.cancel')}</button
					>
					{#if !detail?.read_only}
						<button type="submit" class="btn btn-primary" disabled={saving}>{t('task.save')}</button
						>
					{/if}
				</div>
			</div>
		</form>
	{/if}
</Dialog>
