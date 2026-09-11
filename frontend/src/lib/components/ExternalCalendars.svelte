<script lang="ts">
	import { CalendarPlus, RefreshCw, Trash, TriangleAlert } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { ExternalCalendarInfo } from '$lib/types';

	const INTERVALS = [15, 60, 360, 1440];
	const uid = $props.id();

	let calendars = $state<ExternalCalendarInfo[]>([]);
	let name = $state('');
	let url = $state('');
	let areaId = $state('');
	let refresh = $state(60);
	let busy = $state(false);
	let syncing = $state<string | null>(null);
	let confirmId = $state<string | null>(null);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function intervalLabel(minutes: number): string {
		if (minutes < 60) return t('calendars.everyMinutes', { n: minutes });
		if (minutes < 1440) return t('calendars.everyHours', { n: minutes / 60 });
		return t('calendars.daily');
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
	}

	async function load() {
		try {
			calendars = await api<ExternalCalendarInfo[]>('/calendars');
		} catch (error) {
			report(error);
		}
	}

	onMount(() => {
		areaId = areas.list.find((a) => a.name.toLowerCase() === 'streamo')?.id ?? '';
		void load();
	});

	async function add(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		try {
			const created = await api<ExternalCalendarInfo>('/calendars', {
				method: 'POST',
				body: {
					name: name.trim(),
					url: url.trim(),
					area_id: areaId || undefined,
					refresh_minutes: refresh
				}
			});
			name = '';
			url = '';
			if (created.last_error) toasts.error(created.last_error);
			else toasts.show(t('calendars.added', { count: created.event_count }));
			ui.changed();
			await load();
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	async function sync(calendar: ExternalCalendarInfo) {
		syncing = calendar.id;
		try {
			const result = await api<ExternalCalendarInfo>(`/calendars/${calendar.id}/sync`, {
				method: 'POST'
			});
			if (result.last_error) toasts.error(result.last_error);
			else toasts.show(t('calendars.synced', { count: result.event_count }));
			ui.changed();
			await load();
		} catch (error) {
			report(error);
		} finally {
			syncing = null;
		}
	}

	async function update(calendar: ExternalCalendarInfo, body: Record<string, unknown>) {
		try {
			await api(`/calendars/${calendar.id}`, { method: 'PATCH', body });
			ui.changed();
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function remove(calendar: ExternalCalendarInfo) {
		if (confirmId !== calendar.id) {
			confirmId = calendar.id;
			return;
		}
		try {
			await api(`/calendars/${calendar.id}`, { method: 'DELETE' });
			confirmId = null;
			toasts.show(t('calendars.removed'));
			ui.changed();
			await load();
		} catch (error) {
			report(error);
		}
	}
</script>

<section class="mt-10" aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<CalendarPlus size={16} aria-hidden="true" />{t('calendars.title')}
	</h2>
	<p class="mb-2 text-sm text-muted">{t('calendars.intro')}</p>
	<p class="mb-4 rounded-lg bg-surface-2 px-3 py-2 text-sm">
		<strong>Streamo × ToDoch:</strong>
		{t('calendars.streamoHint')}
	</p>

	{#if calendars.length}
		<ul class="mb-4 flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each calendars as calendar (calendar.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					<div class="min-w-0">
						<p class="font-medium">
							{calendar.name}
							<span class="font-normal text-muted">· {calendar.host}</span>
						</p>
						<p class="text-xs text-muted">
							{calendar.area_name} · {intervalLabel(calendar.refresh_minutes)} ·
							{t('calendars.count', { count: calendar.event_count })}
							{#if calendar.last_success_at}
								· {t('calendars.lastSync', { date: formatDate(calendar.last_success_at) })}
							{/if}
						</p>
						{#if calendar.last_error}
							<p class="mt-1 flex items-center gap-1 text-xs text-danger" role="alert">
								<TriangleAlert size={12} aria-hidden="true" />{calendar.last_error}
							</p>
						{/if}
					</div>
					<div class="flex flex-wrap items-center gap-1">
						<select
							class="input w-auto py-1 text-xs"
							aria-label="{t('feeds.area')}: {calendar.name}"
							value={calendar.area_id}
							onchange={(event) => update(calendar, { area_id: event.currentTarget.value })}
						>
							{#each areas.list as area (area.id)}<option value={area.id}>{area.name}</option
								>{/each}
						</select>
						<button
							type="button"
							class="btn btn-ghost"
							disabled={syncing === calendar.id}
							onclick={() => sync(calendar)}
						>
							<RefreshCw size={14} aria-hidden="true" />{t('calendars.syncNow')}
						</button>
						<button
							type="button"
							class="btn btn-ghost btn-danger"
							aria-label="{t('calendars.remove')}: {calendar.name}"
							onclick={() => remove(calendar)}
						>
							<Trash size={14} aria-hidden="true" />
							{confirmId === calendar.id ? t('calendars.removeConfirm') : t('calendars.remove')}
						</button>
					</div>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="mb-4 text-sm text-muted">{t('calendars.none')}</p>
	{/if}

	<form class="grid gap-3 sm:grid-cols-2" onsubmit={add}>
		<div>
			<label class="label" for="{uid}-name">{t('calendars.name')}</label>
			<input
				id="{uid}-name"
				class="input"
				maxlength="100"
				required
				placeholder={t('calendars.namePlaceholder')}
				bind:value={name}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-area">{t('feeds.area')}</label>
			<select id="{uid}-area" class="input" bind:value={areaId}>
				<option value="">{areas.list[0]?.name ?? ''}</option>
				{#each areas.list.slice(1) as area (area.id)}<option value={area.id}>{area.name}</option
					>{/each}
			</select>
		</div>
		<div class="sm:col-span-2">
			<label class="label" for="{uid}-url">{t('calendars.url')}</label>
			<input
				id="{uid}-url"
				class="input font-mono text-xs"
				maxlength="2000"
				required
				autocomplete="off"
				placeholder="https://…/calendar.ics"
				bind:value={url}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-refresh">{t('calendars.refresh')}</label>
			<select id="{uid}-refresh" class="input" bind:value={refresh}>
				{#each INTERVALS as minutes (minutes)}
					<option value={minutes}>{intervalLabel(minutes)}</option>
				{/each}
			</select>
		</div>
		<div class="flex items-end">
			<button type="submit" class="btn btn-primary" disabled={busy}>
				<CalendarPlus size={16} aria-hidden="true" />{t('calendars.add')}
			</button>
		</div>
	</form>
</section>
