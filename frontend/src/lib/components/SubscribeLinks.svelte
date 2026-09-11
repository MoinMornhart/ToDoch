<script lang="ts">
	import { CalendarPlus, ExternalLink, Link } from '@lucide/svelte';
	import { api, ApiError } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { FeedCreated } from '$lib/types';

	/** Ohne App-Registrierung: ToDoch → Google/Outlook per Abo, Google/Outlook → ToDoch per ICS-Link. */
	const uid = $props.id();
	let areaId = $state('');
	let busy = $state(false);
	let created = $state<FeedCreated | null>(null);

	const googleUrl = $derived(
		created
			? `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(created.webcal_url)}`
			: ''
	);
	const outlookUrl = $derived(
		created
			? `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(created.url)}&name=ToDoch`
			: ''
	);

	async function create() {
		if (busy) return;
		busy = true;
		try {
			created = await api<FeedCreated>('/feeds', {
				method: 'POST',
				body: { name: 'Google & Outlook', area_id: areaId || undefined, detail: 'full' }
			});
			toasts.show(t('subscribe.created'));
		} catch (error) {
			toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
		} finally {
			busy = false;
		}
	}
</script>

<section class="mt-10" aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<Link size={16} aria-hidden="true" />{t('subscribe.title')}
	</h2>
	<p class="mb-4 text-sm text-muted">{t('subscribe.intro')}</p>

	<h3 class="mb-2 text-sm font-medium">{t('subscribe.step1')}</h3>
	<div class="mb-5 flex flex-wrap items-end gap-3">
		<div>
			<label class="label" for="{uid}-area">{t('subscribe.area')}</label>
			<select id="{uid}-area" class="input" bind:value={areaId} onchange={() => (created = null)}>
				<option value="">{t('feeds.allAreas')}</option>
				{#each areas.list as area (area.id)}
					<option value={area.id}>{area.name}</option>
				{/each}
			</select>
		</div>
		{#if created}
			<a class="btn btn-primary" href={googleUrl} target="_blank" rel="noopener noreferrer">
				<CalendarPlus size={16} aria-hidden="true" />{t('subscribe.google')}
			</a>
			<a class="btn btn-primary" href={outlookUrl} target="_blank" rel="noopener noreferrer">
				<CalendarPlus size={16} aria-hidden="true" />{t('subscribe.outlook')}
			</a>
			<a class="btn btn-ghost" href={created.webcal_url}>
				<CalendarPlus size={16} aria-hidden="true" />{t('subscribe.apple')}
			</a>
		{:else}
			<button type="button" class="btn btn-primary" disabled={busy} onclick={create}>
				<Link size={16} aria-hidden="true" />{t('subscribe.create')}
			</button>
		{/if}
	</div>

	<h3 class="mb-2 text-sm font-medium">{t('subscribe.step2')}</h3>
	<ul class="flex flex-col gap-1 text-sm">
		<li>
			{t('subscribe.googleHow')} ·
			<a
				class="inline-flex items-center gap-1 text-accent underline"
				href="https://calendar.google.com/calendar/r/settings"
				target="_blank"
				rel="noopener noreferrer"
				>{t('subscribe.open')}<ExternalLink size={12} aria-hidden="true" /></a
			>
		</li>
		<li>
			{t('subscribe.outlookHow')} ·
			<a
				class="inline-flex items-center gap-1 text-accent underline"
				href="https://outlook.live.com/calendar/0/options/calendar/SharedCalendars"
				target="_blank"
				rel="noopener noreferrer"
				>{t('subscribe.open')}<ExternalLink size={12} aria-hidden="true" /></a
			>
		</li>
		<li class="text-muted">{t('subscribe.paste')}</li>
	</ul>
</section>
