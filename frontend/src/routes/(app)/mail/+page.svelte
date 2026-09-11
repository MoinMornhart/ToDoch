<script lang="ts">
	import {
		ArrowLeft,
		CalendarCheck,
		CalendarPlus,
		ListPlus,
		ListTodo,
		MailOpen,
		Paperclip,
		RefreshCw,
		Search,
		Settings2,
		X
	} from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import MailAccounts from '$lib/components/MailAccounts.svelte';
	import MailRules from '$lib/components/MailRules.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import type { MailAccountInfo, MailMessage, MailMessageDetail, MailSuggestion } from '$lib/mail';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { EventWriteResult, Task } from '$lib/types';

	let accounts = $state<MailAccountInfo[]>([]);
	let messages = $state<MailMessage[]>([]);
	let suggestions = $state<MailMessage[]>([]);
	let deciding = $state<string | null>(null);
	let loaded = $state(false);
	let accountId = $state('');
	let query = $state('');
	let unreadOnly = $state(false);
	let selected = $state<MailMessageDetail | null>(null);
	let showAccounts = $state(false);
	let syncing = $state(false);
	let creating = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	const unread = $derived(accounts.reduce((sum, account) => sum + account.unread_count, 0));

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	async function loadAccounts() {
		accounts = await api<MailAccountInfo[]>('/mail/accounts');
	}

	async function loadMessages() {
		const params = new URLSearchParams({ limit: '100' });
		if (accountId) params.set('account_id', accountId);
		if (query.trim()) params.set('q', query.trim());
		if (unreadOnly) params.set('unread', 'true');
		messages = await api<MailMessage[]>(`/mail/messages?${params}`);
	}

	async function loadSuggestions() {
		suggestions = await api<MailMessage[]>('/mail/suggestions');
	}

	/** Status eines Vorschlags überall nachziehen (Liste, geöffnete Mail). */
	function markSuggestion(id: string, status: MailSuggestion['status'], eventId?: string) {
		for (const entry of [...messages, ...(selected ? [selected] : [])]) {
			if (entry.id !== id || !entry.suggestion) continue;
			entry.suggestion.status = status;
			if (eventId) entry.event_id = eventId;
		}
	}

	async function accept(message: MailMessage) {
		deciding = message.id;
		try {
			const result = await api<EventWriteResult>(`/mail/messages/${message.id}/suggestion/accept`, {
				method: 'POST',
				body: {}
			});
			markSuggestion(message.id, 'accepted', result.event.id);
			toasts.show(t('mail.accepted'));
			ui.changed();
			await loadSuggestions();
		} catch (error) {
			report(error);
		} finally {
			deciding = null;
		}
	}

	async function dismiss(message: MailMessage) {
		deciding = message.id;
		try {
			await api(`/mail/messages/${message.id}/suggestion/dismiss`, { method: 'POST' });
			markSuggestion(message.id, 'dismissed');
			toasts.show(t('mail.dismissed'));
			await loadSuggestions();
		} catch (error) {
			report(error);
		} finally {
			deciding = null;
		}
	}

	function openEvent(eventId: string | null) {
		if (eventId) ui.eventEditor = { mode: 'edit', eventId, occurrence: null };
	}

	function describe(suggestion: MailSuggestion): string {
		const day = new Intl.DateTimeFormat(i18n.locale, {
			weekday: 'short',
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		}).format(new Date(`${suggestion.start_date}T12:00:00`));
		if (suggestion.all_day || !suggestion.start_time) return `${day} · ${t('mail.allDay')}`;
		const end = suggestion.end_time ? `–${suggestion.end_time.slice(0, 5)}` : '';
		return `${day} · ${suggestion.start_time.slice(0, 5)}${end}`;
	}

	async function refresh() {
		try {
			await Promise.all([loadAccounts(), loadMessages(), loadSuggestions()]);
		} catch (error) {
			report(error);
		} finally {
			loaded = true;
		}
	}

	/** Suche und Filter: kurz warten, dann neu laden. */
	function reloadSoon() {
		clearTimeout(timer);
		timer = setTimeout(() => void loadMessages().catch(report), 250);
	}

	/** Rückmeldung nach „Mit Google/Microsoft verbinden“ (Rücksprung mit ?connected / ?oauth_error). */
	function oauthMessage(code: string): string {
		const messages: Record<string, string> = {
			denied: t('mail.oauthDenied'),
			expired: t('mail.oauthExpired'),
			noemail: t('mail.oauthNoEmail'),
			imap: t('mail.oauthImap'),
			limit: t('mail.oauthLimit')
		};
		return messages[code] ?? t('mail.oauthFailed');
	}

	onMount(() => {
		const params = page.url.searchParams;
		const connected = params.get('connected');
		const failure = params.get('oauth_error');
		if (connected) toasts.show(t('mail.connected'));
		if (failure) toasts.error(oauthMessage(failure));
		if (connected || failure) void goto('/mail', { replaceState: true });
		void refresh();
		return () => clearTimeout(timer);
	});

	async function syncAll() {
		syncing = true;
		try {
			const results = await Promise.all(
				accounts.map((account) =>
					api<MailAccountInfo>(`/mail/accounts/${account.id}/sync`, { method: 'POST' })
				)
			);
			const failed = results.find((result) => result.last_error);
			if (failed) toasts.error(`${failed.name}: ${failed.last_error}`);
			else toasts.show(t('mail.synced'));
			await refresh();
		} catch (error) {
			report(error);
		} finally {
			syncing = false;
		}
	}

	async function open(message: MailMessage) {
		try {
			selected = await api<MailMessageDetail>(`/mail/messages/${message.id}`);
			if (!message.is_read) {
				message.is_read = true;
				void loadAccounts().catch(() => undefined);
			}
		} catch (error) {
			report(error);
		}
	}

	async function markUnread() {
		if (!selected) return;
		const id = selected.id;
		try {
			await api(`/mail/messages/${id}`, { method: 'PATCH', body: { is_read: false } });
			const entry = messages.find((message) => message.id === id);
			if (entry) entry.is_read = false;
			selected = null;
			await loadAccounts();
		} catch (error) {
			report(error);
		}
	}

	/** Aufgabe mit Betreff und zitierter Mail – danach gleich im Editor öffnen (Datum setzen …). */
	async function makeTask() {
		if (!selected || creating) return;
		creating = true;
		const id = selected.id;
		try {
			const task = await api<Task>(`/mail/messages/${id}/task`, { method: 'POST', body: {} });
			if (selected?.id === id) selected.task_id = task.id;
			const entry = messages.find((message) => message.id === id);
			if (entry) entry.task_id = task.id;
			toasts.show(t('mail.taskCreated'));
			ui.changed();
			ui.editTaskId = task.id;
		} catch (error) {
			report(error);
		} finally {
			creating = false;
		}
	}

	function openTask() {
		if (selected?.task_id) ui.editTaskId = selected.task_id;
	}

	function sender(message: MailMessage): string {
		return message.from_name || message.from_address || '?';
	}

	function when(message: MailMessage, long = false): string {
		const value = new Date(message.sent_at ?? message.received_at);
		const sameDay = value.toDateString() === new Date().toDateString();
		const options: Intl.DateTimeFormatOptions = long
			? { dateStyle: 'full', timeStyle: 'short' }
			: sameDay
				? { timeStyle: 'short' }
				: { day: 'numeric', month: 'short' };
		return new Intl.DateTimeFormat(i18n.locale, options).format(value);
	}
</script>

<PageHeader
	title={t('nav.mail')}
	subtitle={accounts.length ? t('mail.subtitle', { count: unread }) : undefined}
/>

{#if loaded && accounts.length === 0}
	<p class="mb-5 max-w-2xl text-sm text-muted">{t('mail.intro')}</p>
	<MailAccounts {accounts} onchange={refresh} />
{:else if accounts.length}
	<div class="mb-4 flex flex-wrap items-center gap-2">
		<label class="relative min-w-0 flex-1 basis-48">
			<span class="sr-only">{t('mail.search')}</span>
			<Search
				size={15}
				class="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted"
				aria-hidden="true"
			/>
			<input
				type="search"
				class="input pl-9"
				placeholder={t('mail.search')}
				maxlength="100"
				bind:value={query}
				oninput={reloadSoon}
			/>
		</label>
		{#if accounts.length > 1}
			<select
				class="input w-auto"
				aria-label={t('mail.accounts')}
				bind:value={accountId}
				onchange={reloadSoon}
			>
				<option value="">{t('mail.allAccounts')}</option>
				{#each accounts as account (account.id)}
					<option value={account.id}>{account.name}</option>
				{/each}
			</select>
		{/if}
		<label class="flex items-center gap-2 text-sm">
			<input type="checkbox" bind:checked={unreadOnly} onchange={reloadSoon} />
			{t('mail.unreadOnly')}
		</label>
		<button type="button" class="btn btn-ghost" disabled={syncing} onclick={syncAll}>
			<RefreshCw size={14} aria-hidden="true" />{t('mail.syncAll')}
		</button>
		<button
			type="button"
			class="btn btn-ghost"
			aria-expanded={showAccounts}
			onclick={() => (showAccounts = !showAccounts)}
		>
			<Settings2 size={14} aria-hidden="true" />{t('mail.settings')}
		</button>
	</div>

	{#if showAccounts}
		<div class="mb-6 flex flex-col gap-8 rounded-xl border border-line p-4">
			<MailAccounts {accounts} onchange={refresh} />
			<MailRules {accounts} onchange={refresh} />
		</div>
	{/if}

	{#if suggestions.length}
		<section class="mb-6" aria-labelledby="mail-suggestions">
			<h2 id="mail-suggestions" class="mb-2 flex items-center gap-2 text-base font-semibold">
				<CalendarPlus size={16} aria-hidden="true" />{t('mail.suggestions')}
			</h2>
			<ul class="flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
				{#each suggestions as message (message.id)}
					{#if message.suggestion}
						<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
							<button type="button" class="min-w-0 text-left" onclick={() => open(message)}>
								<span class="block font-medium">{message.suggestion.title}</span>
								<span class="block text-xs text-muted">
									{describe(message.suggestion)} · {sender(message)}
								</span>
							</button>
							<div class="flex gap-1">
								<button
									type="button"
									class="btn btn-primary"
									disabled={deciding === message.id}
									onclick={() => accept(message)}
								>
									<CalendarCheck size={14} aria-hidden="true" />{t('mail.accept')}
								</button>
								<button
									type="button"
									class="btn btn-ghost"
									aria-label="{t('mail.dismiss')}: {message.suggestion.title}"
									disabled={deciding === message.id}
									onclick={() => dismiss(message)}
								>
									<X size={14} aria-hidden="true" />{t('mail.dismiss')}
								</button>
							</div>
						</li>
					{/if}
				{/each}
			</ul>
		</section>
	{/if}

	<div class="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
		<ul
			class="flex-col divide-y divide-line self-start overflow-hidden rounded-xl border border-line bg-raised {selected
				? 'hidden md:flex'
				: 'flex'}"
			aria-label={t('nav.mail')}
		>
			{#each messages as message (message.id)}
				<li>
					<button
						type="button"
						class="flex w-full flex-col gap-0.5 px-4 py-3 text-left text-sm hover:bg-surface-2 {selected?.id ===
						message.id
							? 'bg-surface-2'
							: ''}"
						aria-current={selected?.id === message.id ? 'true' : undefined}
						onclick={() => open(message)}
					>
						<span class="flex items-center gap-2">
							{#if !message.is_read}
								<span class="size-2 shrink-0 rounded-full bg-accent" aria-hidden="true"></span>
								<span class="sr-only">{t('mail.unread')}:</span>
							{/if}
							<span class="min-w-0 flex-1 truncate {message.is_read ? '' : 'font-semibold'}">
								{sender(message)}
							</span>
							{#if message.attachment_count}
								<Paperclip size={12} class="shrink-0 text-muted" aria-hidden="true" />
							{/if}
							{#if message.task_id}
								<ListTodo size={12} class="shrink-0 text-accent" aria-hidden="true" />
							{/if}
							<span class="shrink-0 text-xs text-muted">{when(message)}</span>
						</span>
						<span class="truncate {message.is_read ? '' : 'font-medium'}">
							{message.subject || t('mail.noSubject')}
						</span>
						<span class="truncate text-xs text-muted">{message.snippet}</span>
					</button>
				</li>
			{:else}
				<li class="px-4 py-6 text-center text-sm text-muted">{t('mail.empty')}</li>
			{/each}
		</ul>

		<article
			class="min-w-0 self-start rounded-xl border border-line bg-raised p-5 {selected
				? ''
				: 'hidden md:block'}"
			aria-label={t('mail.reader')}
		>
			{#if selected}
				<button
					type="button"
					class="btn btn-ghost mb-3 md:hidden"
					onclick={() => (selected = null)}
				>
					<ArrowLeft size={14} aria-hidden="true" />{t('mail.back')}
				</button>
				<h2 class="text-lg font-semibold break-words">{selected.subject || t('mail.noSubject')}</h2>
				<dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-sm">
					<dt class="text-muted">{t('mail.from')}</dt>
					<dd class="min-w-0 break-words">
						{selected.from_name}
						{#if selected.from_address}
							<span class="text-muted">&lt;{selected.from_address}&gt;</span>
						{/if}
					</dd>
					{#if selected.recipients}
						<dt class="text-muted">{t('mail.to')}</dt>
						<dd class="min-w-0 break-words">{selected.recipients}</dd>
					{/if}
					<dt class="text-muted">{t('mail.date')}</dt>
					<dd>{when(selected, true)}</dd>
				</dl>
				<div class="mt-4 flex flex-wrap gap-2">
					{#if selected.task_id}
						<button type="button" class="btn btn-primary" onclick={openTask}>
							<ListTodo size={14} aria-hidden="true" />{t('mail.openTask')}
						</button>
					{:else}
						<button type="button" class="btn btn-primary" disabled={creating} onclick={makeTask}>
							<ListPlus size={14} aria-hidden="true" />{t('mail.makeTask')}
						</button>
					{/if}
					<button type="button" class="btn btn-ghost" onclick={markUnread}>
						<MailOpen size={14} aria-hidden="true" />{t('mail.markUnread')}
					</button>
				</div>
				{#if selected.suggestion && selected.suggestion.status !== 'dismissed'}
					<div class="mt-4 rounded-lg bg-surface-2 px-4 py-3 text-sm">
						<p class="flex items-center gap-2 font-medium">
							<CalendarPlus size={14} aria-hidden="true" />
							{t('mail.suggestion')}: {selected.suggestion.title}
						</p>
						<p class="mt-0.5 text-xs text-muted">
							{describe(selected.suggestion)}
							{#if selected.suggestion.location}· {selected.suggestion.location}{/if}
							· {selected.suggestion.source === 'invite'
								? t('mail.fromInvite')
								: t('mail.fromText')}
						</p>
						<div class="mt-2 flex flex-wrap gap-2">
							{#if selected.suggestion.status === 'accepted'}
								<button
									type="button"
									class="btn btn-ghost"
									onclick={() => openEvent(selected?.event_id ?? null)}
								>
									<CalendarCheck size={14} aria-hidden="true" />{t('mail.openEvent')}
								</button>
							{:else}
								<button
									type="button"
									class="btn btn-primary"
									disabled={deciding === selected.id}
									onclick={() => selected && accept(selected)}
								>
									<CalendarCheck size={14} aria-hidden="true" />{t('mail.accept')}
								</button>
								<button
									type="button"
									class="btn btn-ghost"
									disabled={deciding === selected.id}
									onclick={() => selected && dismiss(selected)}
								>
									<X size={14} aria-hidden="true" />{t('mail.dismiss')}
								</button>
							{/if}
						</div>
					</div>
				{/if}
				{#if selected.has_html}
					<p class="mt-4 text-xs text-muted">{t('mail.htmlNote')}</p>
				{/if}
				{#if selected.attachment_count}
					<p class="mt-1 flex items-center gap-1 text-xs text-muted">
						<Paperclip size={12} aria-hidden="true" />
						{t('mail.attachments', { count: selected.attachment_count })}
					</p>
				{/if}
				<div
					class="mt-4 border-t border-line pt-4 text-sm leading-relaxed break-words whitespace-pre-wrap"
				>
					{selected.body_text}
				</div>
				{#if selected.truncated}
					<p class="mt-3 text-xs text-muted">{t('mail.truncated')}</p>
				{/if}
			{:else}
				<p class="text-sm text-muted">{t('mail.select')}</p>
			{/if}
		</article>
	</div>
{/if}
