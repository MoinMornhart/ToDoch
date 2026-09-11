<script lang="ts">
	import { CalendarDays, Check, Download, Mail, UserRound, X } from '@lucide/svelte';
	import { tick, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { formatLongDate, todayIn } from '$lib/dates';
	import { REMINDER_PRESETS, reminderLabel, reportConflicts } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import {
		appointmentPayload,
		blankDraft,
		CHANNELS,
		clearDraft,
		contactFields,
		DURATIONS,
		EMPTY_CONTACT,
		isDraftEmpty,
		loadDraft,
		mailtoLink,
		PLACE_KINDS,
		saveDraft,
		titleFor,
		type PhoneDraft,
		type PlaceKind
	} from '$lib/phone';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { AppointmentResult, Contact, Priority } from '$lib/types';
	import Dialog from './Dialog.svelte';

	const uid = $props.id();
	const PRIORITIES: Priority[] = [0, 1, 2, 3];
	const allZones =
		typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];

	let open = $state(false);
	let draft = $state<PhoneDraft | null>(null);
	let restored = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let result = $state<AppointmentResult | null>(null);
	let suggestions = $state<Contact[]>([]);
	let active = $state(-1);
	let nameInput: HTMLInputElement | undefined = $state();
	let controller: AbortController | null = null;
	let timer: ReturnType<typeof setTimeout> | undefined;

	const userId = $derived(session.user?.id ?? '');
	const timezone = $derived(session.user?.timezone ?? 'Europe/Berlin');
	const zones = $derived(Array.from(new Set([timezone, ...allZones])).sort());
	const placeLabels = $derived<Record<PlaceKind, string>>({
		phone: t('phone.place.phone'),
		onsite: t('phone.place.onsite'),
		video: t('phone.place.video'),
		other: t('phone.place.other')
	});

	function message(err: unknown): string {
		return err instanceof ApiError ? err.message : t('error.generic');
	}

	function fresh(): PhoneDraft {
		return blankDraft(
			todayIn(timezone),
			timezone,
			areas.filterId ?? areas.list[0]?.id ?? '',
			t('phone.followUpDefault')
		);
	}

	function durationLabel(minutes: number): string {
		return minutes < 60 || minutes % 60
			? t('phone.minutes', { n: minutes })
			: t('phone.hours', { n: minutes / 60 });
	}

	async function start(request: { contactId?: string }) {
		error = null;
		result = null;
		suggestions = [];
		restored = false;
		if (request.contactId) {
			try {
				const contact = await api<Contact>(`/contacts/${request.contactId}`);
				draft = { ...fresh(), ...contactFields(contact) };
			} catch (err) {
				toasts.error(message(err));
				ui.phoneForm = null;
				return;
			}
		} else {
			const saved = loadDraft(userId, fresh());
			restored = saved !== null && !isDraftEmpty(saved);
			draft = restored && saved ? saved : fresh();
		}
		open = true;
		await tick();
		nameInput?.focus();
	}

	$effect(() => {
		const request = ui.phoneForm;
		// Nur auf das Öffnen reagieren – nicht auf Bereiche, Sprache usw., die start() liest
		if (request) untrack(() => void start(request));
	});

	// Entwurf laufend auf diesem Gerät sichern – kein Datenverlust beim Neuladen
	$effect(() => {
		if (!open || !draft || result) return;
		const snapshot = $state.snapshot(draft) as PhoneDraft;
		if (isDraftEmpty(snapshot)) clearDraft(userId);
		else saveDraft(userId, snapshot);
	});

	// --- Kontaktvorschläge ---

	function onNameInput() {
		if (!draft) return;
		// Name geleert: Verknüpfung zum gespeicherten Kontakt lösen, neu suchen
		if (draft.contactId && !draft.name.trim()) Object.assign(draft, EMPTY_CONTACT);
		if (draft.contactId) return;
		clearTimeout(timer);
		const query = draft.name.trim();
		if (query.length < 2) {
			suggestions = [];
			return;
		}
		timer = setTimeout(() => void suggest(query), 200);
	}

	async function suggest(query: string) {
		controller?.abort();
		controller = new AbortController();
		try {
			suggestions = await api<Contact[]>('/contacts', {
				query: { q: query, limit: 6 },
				signal: controller.signal
			});
			active = -1;
		} catch {
			// abgebrochen oder offline – dann ohne Vorschläge
		}
	}

	function pick(contact: Contact) {
		if (!draft) return;
		Object.assign(draft, contactFields(contact));
		suggestions = [];
	}

	async function otherContact() {
		if (!draft) return;
		Object.assign(draft, EMPTY_CONTACT);
		await tick();
		nameInput?.focus();
	}

	function onNameKeydown(event: KeyboardEvent) {
		if (!suggestions.length) return;
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			active = (active + 1) % suggestions.length;
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			active = (active - 1 + suggestions.length) % suggestions.length;
		} else if (event.key === 'Enter' && active >= 0) {
			event.preventDefault();
			pick(suggestions[active]!);
		} else if (event.key === 'Escape') {
			event.preventDefault();
			suggestions = [];
		}
	}

	// --- Speichern und danach ---

	async function save(event?: Event) {
		event?.preventDefault();
		if (!draft || saving) return;
		const body = appointmentPayload(draft, t('phone.defaultTitle'), placeLabels);
		if (!body.event.title) {
			error = t('phone.nameOrTitle');
			return;
		}
		saving = true;
		error = null;
		try {
			result = await api<AppointmentResult>('/appointments', { method: 'POST', body });
			clearDraft(userId);
			restored = false;
			ui.changed();
			void areas.refresh();
			toasts.show(t('phone.saved'));
			reportConflicts(result.conflicts);
		} catch (err) {
			error = message(err);
		} finally {
			saving = false;
		}
	}

	function discard() {
		clearDraft(userId);
		restored = false;
		draft = fresh();
		nameInput?.focus();
	}

	async function another() {
		const contact = result?.contact;
		result = null;
		draft = { ...fresh(), ...(contact ? contactFields(contact) : EMPTY_CONTACT) };
		await tick();
		nameInput?.focus();
	}

	function when(r: AppointmentResult): string {
		const day = formatLongDate(r.event.start_date, i18n.locale);
		if (r.event.all_day) return `${day} · ${t('cal.allDay')}`;
		return `${day} · ${r.event.start_time?.slice(0, 5)}–${r.event.end_time?.slice(0, 5)}`;
	}

	function mailLink(r: AppointmentResult): string {
		const lines = [r.event.title, when(r)];
		if (r.event.location) lines.push(r.event.location);
		if (r.event.url) lines.push(r.event.url);
		return mailtoLink(r.contact?.email ?? '', r.event.title, lines.join('\n'));
	}

	async function showInCalendar(r: AppointmentResult) {
		open = false;
		await goto(`/calendar?view=day&date=${r.event.start_date}`);
	}

	function onKeydown(event: KeyboardEvent) {
		if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
			event.preventDefault();
			void save();
		}
	}

	function onClose() {
		ui.phoneForm = null;
		draft = null;
		result = null;
		suggestions = [];
		controller?.abort();
	}
</script>

<Dialog bind:open title={t('phone.title')} size="lg" onclose={onClose}>
	{#if result}
		<div class="flex flex-col gap-4" role="status">
			<div class="flex items-start gap-3">
				<span class="grid size-9 shrink-0 place-items-center rounded-full bg-ok/15 text-ok">
					<Check size={18} aria-hidden="true" />
				</span>
				<div>
					<p class="font-semibold">{t('phone.done')}: {result.event.title}</p>
					<p class="text-sm text-muted">{when(result)}</p>
					{#if result.task}
						<p class="mt-1 text-sm text-muted">
							{t('phone.withTask', {
								title: result.task.title,
								date: formatLongDate(result.task.due_date ?? '', i18n.locale)
							})}
						</p>
					{/if}
				</div>
			</div>
			<div class="flex flex-wrap gap-2">
				<a class="btn" href="/api/events/{result.event.id}/ics" download="termin.ics">
					<Download size={16} aria-hidden="true" />{t('phone.ics')}
				</a>
				{#if result.contact?.email}
					<a class="btn" href={mailLink(result)}>
						<Mail size={16} aria-hidden="true" />{t('phone.sendMail')}
					</a>
				{/if}
				<button type="button" class="btn" onclick={() => result && showInCalendar(result)}>
					<CalendarDays size={16} aria-hidden="true" />{t('phone.openCalendar')}
				</button>
			</div>
			{#if result.contact?.email}
				<p class="text-xs text-muted">{t('phone.mailHint')}</p>
			{/if}
			<div class="flex flex-wrap justify-end gap-2 border-t border-line pt-4">
				<button type="button" class="btn" onclick={another}>
					{result.contact
						? t('phone.another', { name: result.contact.name })
						: t('phone.anotherPlain')}
				</button>
				<button type="button" class="btn btn-primary" onclick={() => (open = false)}>
					{t('phone.close')}
				</button>
			</div>
		</div>
	{:else if draft}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<form class="flex flex-col gap-6" onsubmit={save} onkeydown={onKeydown}>
			<p class="-mb-2 text-sm text-muted">{t('phone.intro')}</p>
			{#if error}<p role="alert" class="text-sm text-danger">{error}</p>{/if}
			{#if restored}
				<p
					class="flex items-center justify-between gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm"
				>
					{t('phone.draftRestored')}
					<button type="button" class="btn btn-ghost px-2 py-1 text-xs" onclick={discard}>
						{t('phone.discard')}
					</button>
				</p>
			{/if}

			<fieldset class="flex flex-col gap-3">
				<legend class="mb-2 flex w-full items-center justify-between text-sm font-semibold">
					{t('phone.contact')}
				</legend>
				{#if draft.contactId}
					<p class="flex items-center justify-between gap-2 text-xs text-muted">
						<span class="inline-flex items-center gap-1">
							<UserRound size={14} aria-hidden="true" />{t('phone.savedContact')}
						</span>
						<button type="button" class="btn btn-ghost px-2 py-1 text-xs" onclick={otherContact}>
							<X size={14} aria-hidden="true" />{t('phone.newContact')}
						</button>
					</p>
				{/if}
				<div class="grid gap-3 sm:grid-cols-2">
					<div class="relative">
						<label class="label" for="{uid}-name">{t('phone.name')}</label>
						<input
							id="{uid}-name"
							bind:this={nameInput}
							class="input"
							role="combobox"
							autocomplete="off"
							aria-autocomplete="list"
							aria-expanded={suggestions.length > 0}
							aria-controls="{uid}-suggestions"
							aria-activedescendant={active >= 0 ? `${uid}-option-${active}` : undefined}
							maxlength="200"
							bind:value={draft.name}
							oninput={onNameInput}
							onkeydown={onNameKeydown}
							onblur={() => setTimeout(() => (suggestions = []), 150)}
						/>
						{#if suggestions.length}
							<ul
								id="{uid}-suggestions"
								role="listbox"
								aria-label={t('phone.suggestions')}
								class="absolute inset-x-0 top-full z-10 mt-1 overflow-hidden rounded-lg border border-line bg-raised shadow-lg"
							>
								{#each suggestions as contact, index (contact.id)}
									<li
										id="{uid}-option-{index}"
										role="option"
										aria-selected={index === active}
										class="cursor-pointer px-3 py-2 text-sm {index === active
											? 'bg-surface-2'
											: 'hover:bg-surface-2'}"
										onmousedown={(event) => {
											event.preventDefault();
											pick(contact);
										}}
									>
										<span class="block">{contact.name}</span>
										<span class="block text-xs text-muted">
											{[contact.company, contact.phone, contact.email].filter(Boolean).join(' · ')}
										</span>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
					<div>
						<label class="label" for="{uid}-company">{t('phone.company')}</label>
						<input id="{uid}-company" class="input" maxlength="200" bind:value={draft.company} />
					</div>
					<div>
						<label class="label" for="{uid}-phone">{t('phone.phone')}</label>
						<input
							id="{uid}-phone"
							type="tel"
							class="input"
							maxlength="50"
							autocomplete="off"
							bind:value={draft.phone}
						/>
					</div>
					<div>
						<label class="label" for="{uid}-email">{t('phone.email')}</label>
						<input
							id="{uid}-email"
							type="email"
							class="input"
							maxlength="254"
							autocomplete="off"
							bind:value={draft.email}
						/>
					</div>
					<div class="sm:col-span-2">
						<label class="label" for="{uid}-address">{t('phone.address')}</label>
						<textarea
							id="{uid}-address"
							class="input min-h-16"
							maxlength="1000"
							bind:value={draft.address}></textarea>
					</div>
				</div>
			</fieldset>

			<fieldset class="flex flex-col gap-3">
				<legend class="mb-2 text-sm font-semibold">{t('phone.appointment')}</legend>
				<div>
					<label class="label" for="{uid}-title">{t('phone.subject')}</label>
					<input
						id="{uid}-title"
						class="input"
						maxlength="300"
						placeholder={titleFor(draft, t('phone.defaultTitle')) || t('phone.subjectHint')}
						bind:value={draft.title}
					/>
				</div>
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
					<div class="col-span-2 sm:col-span-1">
						<label class="label" for="{uid}-date">{t('phone.date')}</label>
						<input id="{uid}-date" type="date" class="input" required bind:value={draft.date} />
					</div>
					{#if !draft.allDay}
						<div>
							<label class="label" for="{uid}-time">{t('phone.time')}</label>
							<input id="{uid}-time" type="time" class="input" required bind:value={draft.time} />
						</div>
						<div>
							<label class="label" for="{uid}-duration">{t('phone.duration')}</label>
							<select id="{uid}-duration" class="input" bind:value={draft.duration}>
								{#each DURATIONS as minutes (minutes)}
									<option value={minutes}>{durationLabel(minutes)}</option>
								{/each}
							</select>
						</div>
					{/if}
					<label class="flex items-end gap-2 pb-2.5 text-sm">
						<input type="checkbox" class="size-4 accent-accent" bind:checked={draft.allDay} />
						{t('event.allDay')}
					</label>
				</div>

				<div>
					<span class="label" id="{uid}-place-label">{t('phone.place')}</span>
					<div class="flex flex-wrap gap-1.5" role="group" aria-labelledby="{uid}-place-label">
						{#each PLACE_KINDS as kind (kind)}
							<button
								type="button"
								class="btn px-3 py-1.5 {draft.placeKind === kind
									? 'border-accent text-accent'
									: ''}"
								aria-pressed={draft.placeKind === kind}
								onclick={() => draft && (draft.placeKind = kind)}
							>
								{placeLabels[kind]}
							</button>
						{/each}
					</div>
					{#if draft.placeKind === 'video'}
						<input
							type="url"
							class="input mt-2"
							aria-label={t('phone.placeLink')}
							placeholder="https://"
							maxlength="1000"
							bind:value={draft.url}
						/>
					{:else if draft.placeKind === 'onsite' || draft.placeKind === 'other'}
						<input
							class="input mt-2"
							aria-label={draft.placeKind === 'onsite'
								? t('phone.placeAddress')
								: t('phone.placeText')}
							placeholder={draft.placeKind === 'onsite' ? t('phone.placeAddress') : ''}
							maxlength="500"
							bind:value={draft.place}
						/>
					{/if}
				</div>

				<div>
					<label class="label" for="{uid}-zone">{t('phone.timezone')}</label>
					<select id="{uid}-zone" class="input" bind:value={draft.tzid}>
						{#each zones as zone (zone)}<option value={zone}>{zone}</option>{/each}
					</select>
				</div>
			</fieldset>

			<fieldset class="flex flex-col gap-3">
				<legend class="mb-2 text-sm font-semibold">{t('phone.context')}</legend>
				<div class="grid gap-3 sm:grid-cols-3">
					<div>
						<label class="label" for="{uid}-channel">{t('phone.channel')}</label>
						<select id="{uid}-channel" class="input" bind:value={draft.channel}>
							{#each CHANNELS as channel (channel)}
								<option value={channel}>{t(`phone.channel.${channel}`)}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="label" for="{uid}-agreed-on">{t('phone.agreedOn')}</label>
						<input id="{uid}-agreed-on" type="date" class="input" bind:value={draft.agreedOn} />
					</div>
					<div>
						<label class="label" for="{uid}-agreed-with">{t('phone.agreedWith')}</label>
						<input
							id="{uid}-agreed-with"
							class="input"
							maxlength="200"
							bind:value={draft.agreedWith}
						/>
					</div>
				</div>
				<div>
					<label class="label" for="{uid}-notes">{t('phone.notes')}</label>
					<textarea
						id="{uid}-notes"
						class="input min-h-40"
						maxlength="50000"
						aria-describedby="{uid}-notes-hint"
						bind:value={draft.notes}></textarea>
					<p id="{uid}-notes-hint" class="mt-1 text-xs text-muted">{t('phone.notesHint')}</p>
				</div>
			</fieldset>

			<fieldset class="flex flex-col gap-3">
				<legend class="mb-2 text-sm font-semibold">{t('phone.organisation')}</legend>
				<div class="grid gap-3 sm:grid-cols-2">
					<div>
						<label class="label" for="{uid}-area">{t('task.area')}</label>
						<select id="{uid}-area" class="input" bind:value={draft.areaId}>
							{#each areas.list as area (area.id)}
								<option value={area.id}>{area.name}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="label" for="{uid}-tags">{t('task.tags')}</label>
						<input id="{uid}-tags" class="input" autocomplete="off" bind:value={draft.tags} />
					</div>
				</div>
				<div>
					<span class="label" id="{uid}-priority-label">{t('task.priority')}</span>
					<div class="flex flex-wrap gap-1.5" role="group" aria-labelledby="{uid}-priority-label">
						{#each PRIORITIES as priority (priority)}
							<button
								type="button"
								class="btn px-3 py-1.5 {draft.priority === priority
									? 'border-accent text-accent'
									: ''}"
								aria-pressed={draft.priority === priority}
								onclick={() => draft && (draft.priority = priority)}
							>
								{t(`priority.${priority}`)}
							</button>
						{/each}
					</div>
				</div>
				<div>
					<span class="label" id="{uid}-reminders-label">{t('event.reminders')}</span>
					<div class="flex flex-wrap gap-1.5" role="group" aria-labelledby="{uid}-reminders-label">
						{#each REMINDER_PRESETS as minutes (minutes)}
							<button
								type="button"
								class="btn px-2.5 py-1 text-xs {draft.reminders.includes(minutes)
									? 'border-accent text-accent'
									: ''}"
								aria-pressed={draft.reminders.includes(minutes)}
								onclick={() => {
									if (!draft) return;
									draft.reminders = draft.reminders.includes(minutes)
										? draft.reminders.filter((m) => m !== minutes)
										: [...draft.reminders, minutes].sort((a, b) => a - b);
								}}
							>
								{reminderLabel(minutes)}
							</button>
						{/each}
					</div>
				</div>
				<label class="flex items-center gap-2 text-sm">
					<input type="checkbox" class="size-4 accent-accent" bind:checked={draft.followUp} />
					{t('phone.followUp')}
				</label>
				{#if draft.followUp}
					<div class="grid grid-cols-[1fr_auto] gap-3">
						<div>
							<label class="label" for="{uid}-follow-title">{t('phone.followUpTitle')}</label>
							<input
								id="{uid}-follow-title"
								class="input"
								maxlength="300"
								bind:value={draft.followUpTitle}
							/>
						</div>
						<div class="w-32">
							<label class="label" for="{uid}-follow-days">{t('phone.followUpDays')}</label>
							<input
								id="{uid}-follow-days"
								type="number"
								min="0"
								max="365"
								class="input"
								bind:value={draft.followUpDays}
							/>
						</div>
					</div>
				{/if}
			</fieldset>

			<div class="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
				<p class="text-xs text-muted">{t('phone.draftHint')}</p>
				<div class="flex gap-2">
					<button type="button" class="btn" onclick={() => (open = false)}>
						{t('task.cancel')}
					</button>
					<button type="submit" class="btn btn-primary" disabled={saving}>{t('task.save')}</button>
				</div>
			</div>
		</form>
	{/if}
</Dialog>
