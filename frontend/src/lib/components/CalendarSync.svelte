<script lang="ts">
	import { ArrowLeftRight, RefreshCw, Search, Trash, TriangleAlert } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import type { OAuthProvider, OAuthProviders } from '$lib/mail';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';

	interface Connection {
		id: string;
		provider: OAuthProvider | 'caldav';
		account_email: string;
		server: string | null;
		area_id: string;
		area_name: string;
		enabled: boolean;
		event_count: number;
		last_synced_at: string | null;
		last_success_at: string | null;
		last_error: string | null;
		created_at: string;
	}

	interface FoundCalendar {
		url: string;
		name: string;
	}

	/** CalDAV-Anbieter mit bekannter Adresse – bei Nextcloud genügt der eigene Server. */
	const PRESETS: { id: string; name: string; url: string; appPassword?: string }[] = [
		{ id: 'nextcloud', name: 'Nextcloud', url: 'https://' },
		{
			id: 'icloud',
			name: 'iCloud',
			url: 'https://caldav.icloud.com',
			appPassword: 'https://account.apple.com/account/manage'
		},
		{ id: 'mailbox', name: 'mailbox.org', url: 'https://dav.mailbox.org' },
		{ id: 'posteo', name: 'Posteo', url: 'https://posteo.de:8443' },
		{ id: 'gmx', name: 'GMX', url: 'https://caldav.gmx.net' },
		{ id: 'webde', name: 'WEB.DE', url: 'https://caldav.web.de' },
		{ id: 'other', name: '', url: 'https://' }
	];

	const uid = $props.id();
	let connections = $state<Connection[]>([]);
	let providers = $state<OAuthProviders>({ google: false, microsoft: false });
	let areaId = $state('');
	let busy = $state(false);
	let syncing = $state<string | null>(null);
	let confirmId = $state<string | null>(null);
	const available = $derived(providers.google || providers.microsoft);

	let preset = $state('nextcloud');
	let davUrl = $state('https://');
	let username = $state('');
	let password = $state('');
	let found = $state<FoundCalendar[] | null>(null);
	let chosen = $state('');
	let davBusy = $state(false);
	const presetInfo = $derived(PRESETS.find((p) => p.id === preset));

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
	}

	function label(connection: Connection): string {
		if (connection.provider === 'caldav') return connection.server ?? 'CalDAV';
		return connection.provider === 'microsoft' ? t('sync.microsoft') : t('sync.google');
	}

	async function load() {
		try {
			connections = await api<Connection[]>('/calendar-sync');
		} catch (error) {
			report(error);
		}
	}

	onMount(async () => {
		void load();
		try {
			providers = await api<OAuthProviders>('/mail/oauth/providers');
		} catch {
			// ohne Knöpfe weiter
		}
	});

	/** Zum Anbieter – der Rücksprung landet wieder hier auf „Bereiche“. */
	async function connect(provider: OAuthProvider) {
		if (busy) return;
		busy = true;
		try {
			const { url } = await api<{ url: string }>(`/calendar-sync/${provider}/start`, {
				method: 'POST',
				body: { area_id: areaId || undefined }
			});
			window.location.assign(url);
		} catch (error) {
			report(error);
			busy = false;
		}
	}

	function choosePreset(id: string) {
		preset = id;
		davUrl = PRESETS.find((p) => p.id === id)?.url ?? 'https://';
		found = null;
	}

	async function searchCalendars(event: SubmitEvent) {
		event.preventDefault();
		if (davBusy) return;
		davBusy = true;
		try {
			found = await api<FoundCalendar[]>('/calendar-sync/caldav/discover', {
				method: 'POST',
				body: { url: davUrl.trim(), username: username.trim(), password }
			});
			chosen = found[0]?.url ?? '';
		} catch (error) {
			report(error);
		} finally {
			davBusy = false;
		}
	}

	async function connectCaldav() {
		if (davBusy || !chosen) return;
		davBusy = true;
		try {
			const created = await api<Connection>('/calendar-sync/caldav', {
				method: 'POST',
				body: {
					url: davUrl.trim(),
					username: username.trim(),
					password,
					calendar_url: chosen,
					area_id: areaId || undefined
				}
			});
			password = '';
			found = null;
			if (created.last_error) toasts.error(created.last_error);
			else toasts.show(t('caldav.connected'));
			ui.changed();
			await load();
		} catch (error) {
			report(error);
		} finally {
			davBusy = false;
		}
	}

	async function sync(connection: Connection) {
		syncing = connection.id;
		try {
			const result = await api<Connection>(`/calendar-sync/${connection.id}/sync`, {
				method: 'POST'
			});
			if (result.last_error) toasts.error(result.last_error);
			else toasts.show(t('sync.synced'));
			ui.changed();
			await load();
		} catch (error) {
			report(error);
		} finally {
			syncing = null;
		}
	}

	async function remove(connection: Connection) {
		if (confirmId !== connection.id) {
			confirmId = connection.id;
			return;
		}
		try {
			await api(`/calendar-sync/${connection.id}`, { method: 'DELETE' });
			confirmId = null;
			toasts.show(t('sync.removed'));
			await load();
		} catch (error) {
			report(error);
		}
	}
</script>

<section class="mt-10" aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<ArrowLeftRight size={16} aria-hidden="true" />{t('sync.title')}
	</h2>
	<p class="mb-4 text-sm text-muted">{t('sync.intro')}</p>

	{#if connections.length}
		<ul class="mb-4 flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each connections as connection (connection.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					<div class="min-w-0">
						<p class="font-medium">
							{label(connection)}
							<span class="font-normal text-muted">
								· {connection.account_email} ⇄ {connection.area_name}</span
							>
						</p>
						<p class="text-xs text-muted">
							{t('sync.count', { count: connection.event_count })}
							{#if connection.last_success_at}
								· {t('sync.lastSync', { date: formatDate(connection.last_success_at) })}
							{/if}
						</p>
						{#if connection.last_error}
							<p class="mt-1 flex items-center gap-1 text-xs text-danger" role="alert">
								<TriangleAlert size={12} aria-hidden="true" />{connection.last_error}
							</p>
						{/if}
					</div>
					<div class="flex flex-wrap items-center gap-1">
						<button
							type="button"
							class="btn btn-ghost"
							disabled={syncing === connection.id}
							onclick={() => sync(connection)}
						>
							<RefreshCw size={14} aria-hidden="true" />{t('sync.syncNow')}
						</button>
						<button
							type="button"
							class="btn btn-ghost btn-danger"
							aria-label="{t('sync.remove')}: {label(connection)} {connection.area_name}"
							onclick={() => remove(connection)}
						>
							<Trash size={14} aria-hidden="true" />
							{confirmId === connection.id ? t('sync.removeConfirm') : t('sync.remove')}
						</button>
					</div>
				</li>
			{/each}
		</ul>
	{/if}

	<div class="mb-6">
		<label class="label" for="{uid}-area">{t('sync.area')}</label>
		<select id="{uid}-area" class="input w-auto" bind:value={areaId}>
			<option value="">{areas.list[0]?.name ?? ''}</option>
			{#each areas.list.slice(1) as area (area.id)}
				<option value={area.id}>{area.name}</option>
			{/each}
		</select>
	</div>

	<h3 class="mb-1 text-sm font-medium">{t('caldav.title')}</h3>
	<p class="mb-3 text-sm text-muted">{t('caldav.intro')}</p>
	<form class="mb-6 grid gap-3 sm:grid-cols-2" onsubmit={searchCalendars}>
		<div>
			<label class="label" for="{uid}-preset">{t('caldav.provider')}</label>
			<select
				id="{uid}-preset"
				class="input"
				value={preset}
				onchange={(event) => choosePreset(event.currentTarget.value)}
			>
				{#each PRESETS as option (option.id)}
					<option value={option.id}>{option.name || t('caldav.other')}</option>
				{/each}
			</select>
		</div>
		<div>
			<label class="label" for="{uid}-url">{t('caldav.url')}</label>
			<input
				id="{uid}-url"
				class="input font-mono text-xs"
				required
				maxlength="2000"
				autocomplete="off"
				bind:value={davUrl}
				oninput={() => (found = null)}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-user">{t('caldav.username')}</label>
			<input
				id="{uid}-user"
				class="input"
				required
				maxlength="320"
				autocomplete="off"
				bind:value={username}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-password">{t('caldav.password')}</label>
			<input
				id="{uid}-password"
				class="input"
				type="password"
				required
				maxlength="500"
				autocomplete="new-password"
				bind:value={password}
			/>
			<p class="mt-1 text-xs text-muted">
				{t('caldav.passwordHint')}
				{#if presetInfo?.appPassword}
					<a
						class="text-accent underline"
						href={presetInfo.appPassword}
						target="_blank"
						rel="noopener noreferrer">{t('caldav.appPassword')}</a
					>
				{/if}
			</p>
		</div>
		{#if found}
			<div class="sm:col-span-2">
				{#if found.length}
					<label class="label" for="{uid}-calendar">{t('caldav.choose')}</label>
					<div class="flex flex-wrap items-center gap-2">
						<select id="{uid}-calendar" class="input w-auto" bind:value={chosen}>
							{#each found as calendar (calendar.url)}
								<option value={calendar.url}>{calendar.name}</option>
							{/each}
						</select>
						<button
							type="button"
							class="btn btn-primary"
							disabled={davBusy}
							onclick={connectCaldav}
						>
							<ArrowLeftRight size={16} aria-hidden="true" />{t('caldav.connect')}
						</button>
					</div>
				{:else}
					<p class="text-sm text-muted">{t('caldav.none')}</p>
				{/if}
			</div>
		{:else}
			<div>
				<button type="submit" class="btn btn-primary" disabled={davBusy}>
					<Search size={16} aria-hidden="true" />{t('caldav.search')}
				</button>
			</div>
		{/if}
	</form>

	{#if available}
		<h3 class="mb-2 text-sm font-medium">{t('sync.oauthTitle')}</h3>
		<div class="flex flex-wrap items-end gap-3">
			{#if providers.google}
				<button
					type="button"
					class="btn btn-primary"
					disabled={busy}
					onclick={() => connect('google')}
				>
					<ArrowLeftRight size={16} aria-hidden="true" />{t('sync.connectGoogle')}
				</button>
			{/if}
			{#if providers.microsoft}
				<button
					type="button"
					class="btn btn-primary"
					disabled={busy}
					onclick={() => connect('microsoft')}
				>
					<ArrowLeftRight size={16} aria-hidden="true" />{t('sync.connectMicrosoft')}
				</button>
			{/if}
		</div>
	{:else if session.user?.is_admin}
		<p class="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">{t('sync.missing')}</p>
	{/if}
</section>
