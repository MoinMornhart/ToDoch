<script lang="ts">
	import { ArrowLeftRight, RefreshCw, Trash, TriangleAlert } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import type { OAuthProviders } from '$lib/mail';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';

	interface Connection {
		id: string;
		provider: string;
		account_email: string;
		area_id: string;
		area_name: string;
		enabled: boolean;
		event_count: number;
		last_synced_at: string | null;
		last_success_at: string | null;
		last_error: string | null;
		created_at: string;
	}

	const uid = $props.id();
	let connections = $state<Connection[]>([]);
	let google = $state(false);
	let areaId = $state('');
	let busy = $state(false);
	let syncing = $state<string | null>(null);
	let confirmId = $state<string | null>(null);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
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
			google = (await api<OAuthProviders>('/mail/oauth/providers')).google;
		} catch {
			// ohne Knopf weiter
		}
	});

	/** Zu Google – der Rücksprung landet wieder hier auf „Bereiche“. */
	async function connect() {
		if (busy) return;
		busy = true;
		try {
			const { url } = await api<{ url: string }>('/calendar-sync/google/start', {
				method: 'POST',
				body: { area_id: areaId || undefined }
			});
			window.location.assign(url);
		} catch (error) {
			report(error);
			busy = false;
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
							Google Kalender
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
							aria-label="{t('sync.remove')}: {connection.area_name}"
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

	{#if google}
		<div class="flex flex-wrap items-end gap-3">
			<div>
				<label class="label" for="{uid}-area">{t('sync.area')}</label>
				<select id="{uid}-area" class="input" bind:value={areaId}>
					<option value="">{areas.list[0]?.name ?? ''}</option>
					{#each areas.list.slice(1) as area (area.id)}
						<option value={area.id}>{area.name}</option>
					{/each}
				</select>
			</div>
			<button type="button" class="btn btn-primary" disabled={busy} onclick={connect}>
				<ArrowLeftRight size={16} aria-hidden="true" />{t('sync.connectGoogle')}
			</button>
		</div>
	{:else if session.user?.is_admin}
		<p class="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">{t('sync.missing')}</p>
	{:else}
		<p class="text-sm text-muted">{t('sync.unavailable')}</p>
	{/if}
</section>
