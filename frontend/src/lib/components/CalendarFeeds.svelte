<script lang="ts">
	import { Copy, ExternalLink, Rss, Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { FeedCreated, FeedDetail, FeedInfo } from '$lib/types';

	const DETAILS: FeedDetail[] = ['full', 'title', 'busy'];
	const uid = $props.id();

	let feeds = $state<FeedInfo[]>([]);
	let name = $state('');
	let areaId = $state('');
	let detail = $state<FeedDetail>('full');
	let created = $state<FeedCreated | null>(null);
	let confirmId = $state<string | null>(null);
	let busy = $state(false);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	async function load() {
		try {
			feeds = await api<FeedInfo[]>('/feeds');
		} catch (error) {
			report(error);
		}
	}

	onMount(load);

	async function create(event: SubmitEvent) {
		event.preventDefault();
		if (!name.trim() || busy) return;
		busy = true;
		try {
			created = await api<FeedCreated>('/feeds', {
				method: 'POST',
				body: { name: name.trim(), area_id: areaId || null, detail }
			});
			name = '';
			await load();
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	async function revoke(feed: FeedInfo) {
		if (confirmId !== feed.id) {
			confirmId = feed.id;
			return;
		}
		try {
			await api(`/feeds/${feed.id}`, { method: 'DELETE' });
			confirmId = null;
			if (created?.feed.id === feed.id) created = null;
			toasts.show(t('feeds.revoked'));
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function copy(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			toasts.show(t('feeds.copied'));
		} catch {
			toasts.error(t('error.generic'));
		}
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
	}

	const googleUrl = $derived(
		created
			? `https://calendar.google.com/calendar/render?cid=${encodeURIComponent(created.webcal_url)}`
			: ''
	);
	const outlookUrl = $derived(
		created
			? `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(created.url)}&name=${encodeURIComponent(created.feed.name)}`
			: ''
	);
</script>

<section class="mt-10" aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<Rss size={16} aria-hidden="true" />{t('feeds.title')}
	</h2>
	<p class="mb-4 text-sm text-muted">{t('feeds.intro')}</p>

	{#if created}
		<div class="mb-4 rounded-xl border border-accent bg-raised p-4" role="status">
			<p class="text-sm font-semibold">{t('feeds.createdTitle')}</p>
			<p class="mb-3 text-xs text-muted">{t('feeds.createdHint')}</p>
			<div class="flex gap-2">
				<input
					class="input font-mono text-xs"
					value={created.url}
					readonly
					aria-label={t('feeds.createdTitle')}
					onfocus={(event) => event.currentTarget.select()}
				/>
				<button type="button" class="btn shrink-0" onclick={() => created && copy(created.url)}>
					<Copy size={14} aria-hidden="true" />{t('feeds.copy')}
				</button>
			</div>
			<div class="mt-3 flex flex-wrap gap-2 text-sm">
				<a class="btn py-1" href={created.webcal_url}>
					<ExternalLink size={14} aria-hidden="true" />{t('feeds.openApple')}
				</a>
				<a class="btn py-1" href={googleUrl} target="_blank" rel="noopener noreferrer">
					<ExternalLink size={14} aria-hidden="true" />{t('feeds.openGoogle')}
				</a>
				<a class="btn py-1" href={outlookUrl} target="_blank" rel="noopener noreferrer">
					<ExternalLink size={14} aria-hidden="true" />{t('feeds.openOutlook')}
				</a>
			</div>
		</div>
	{/if}

	{#if feeds.length}
		<ul class="mb-4 flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each feeds as feed (feed.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					<div>
						<p class="font-medium">{feed.name}</p>
						<p class="text-xs text-muted">
							{feed.area_name ?? t('feeds.allAreas')} · {t(`feeds.detail.${feed.detail}`)} ·
							{feed.last_used_at
								? t('feeds.lastUsed', { date: formatDate(feed.last_used_at) })
								: t('feeds.neverUsed')}
						</p>
					</div>
					<button type="button" class="btn btn-ghost btn-danger" onclick={() => revoke(feed)}>
						<Trash size={14} aria-hidden="true" />
						{confirmId === feed.id ? t('feeds.revokeConfirm') : t('feeds.revoke')}
					</button>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="mb-4 text-sm text-muted">{t('feeds.none')}</p>
	{/if}

	<form class="flex flex-wrap items-end gap-2" onsubmit={create}>
		<div class="min-w-40 flex-1">
			<label class="label" for="{uid}-name">{t('feeds.name')}</label>
			<input
				id="{uid}-name"
				class="input"
				maxlength="100"
				required
				placeholder={t('feeds.namePlaceholder')}
				bind:value={name}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-area">{t('feeds.area')}</label>
			<select id="{uid}-area" class="input w-auto" bind:value={areaId}>
				<option value="">{t('feeds.allAreas')}</option>
				{#each areas.list as area (area.id)}<option value={area.id}>{area.name}</option>{/each}
			</select>
		</div>
		<div>
			<label class="label" for="{uid}-detail">{t('feeds.detail')}</label>
			<select id="{uid}-detail" class="input w-auto" bind:value={detail}>
				{#each DETAILS as option (option)}
					<option value={option}>{t(`feeds.detail.${option}`)}</option>
				{/each}
			</select>
		</div>
		<button type="submit" class="btn btn-primary" disabled={busy}>{t('feeds.create')}</button>
	</form>
</section>
