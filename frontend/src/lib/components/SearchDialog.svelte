<script lang="ts">
	import { CalendarDays, Search } from '@lucide/svelte';
	import { tick } from 'svelte';
	import { api } from '$lib/api';
	import { formatDay, formatTime, todayIn } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels } from '$lib/labels';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { EventSearchResult, SearchResult, Task } from '$lib/types';
	import Dialog from './Dialog.svelte';

	type Hit = { kind: 'task'; task: Task } | { kind: 'event'; event: EventSearchResult };

	const uid = $props.id();
	let query = $state('');
	let results = $state<Hit[]>([]);
	let active = $state(0);
	let searched = $state(false);
	let input: HTMLInputElement | undefined = $state();
	let timer: ReturnType<typeof setTimeout> | undefined;
	let sequence = 0;

	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));

	$effect(() => {
		if (ui.searchOpen) {
			query = '';
			results = [];
			searched = false;
			active = 0;
			void tick().then(() => input?.focus());
		}
	});

	function onInput() {
		clearTimeout(timer);
		const q = query.trim();
		const mine = ++sequence;
		if (!q) {
			results = [];
			searched = false;
			return;
		}
		timer = setTimeout(async () => {
			try {
				const found = await api<SearchResult>('/search', { query: { q, area_id: areas.filterId } });
				if (mine === sequence) {
					results = [
						...found.events.map((event): Hit => ({ kind: 'event', event })),
						...found.tasks.map((task): Hit => ({ kind: 'task', task }))
					];
					active = 0;
					searched = true;
				}
			} catch {
				if (mine === sequence) results = [];
			}
		}, 180);
	}

	function openHit(hit: Hit) {
		ui.searchOpen = false;
		if (hit.kind === 'task') ui.editTaskId = hit.task.id;
		else ui.eventEditor = { mode: 'edit', eventId: hit.event.id, occurrence: null };
	}

	function keyOf(hit: Hit): string {
		return hit.kind === 'task' ? `t:${hit.task.id}` : `e:${hit.event.id}`;
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			active = Math.min(active + 1, results.length - 1);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			active = Math.max(active - 1, 0);
		} else if (event.key === 'Enter') {
			event.preventDefault();
			const hit = results[active];
			if (hit) openHit(hit);
		}
	}
</script>

<Dialog bind:open={ui.searchOpen} title={t('search.label')}>
	<div
		class="flex items-center gap-2 rounded-lg border border-line px-3 focus-within:border-accent"
	>
		<Search size={16} class="text-muted" aria-hidden="true" />
		<input
			bind:this={input}
			bind:value={query}
			oninput={onInput}
			onkeydown={onKeydown}
			role="combobox"
			aria-label={t('search.label')}
			aria-expanded={results.length > 0}
			aria-controls="{uid}-results"
			aria-activedescendant={results.length ? `${uid}-option-${active}` : undefined}
			aria-autocomplete="list"
			placeholder={t('search.placeholder')}
			class="h-10 w-full bg-transparent outline-none placeholder:text-muted"
			autocomplete="off"
			maxlength="200"
		/>
	</div>
	<ul id="{uid}-results" role="listbox" aria-label={t('search.label')} class="mt-3 flex flex-col">
		{#each results as hit, index (keyOf(hit))}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<li
				id="{uid}-option-{index}"
				role="option"
				aria-selected={index === active}
				class="flex cursor-pointer items-baseline justify-between gap-3 rounded-lg px-3 py-2 {index ===
				active
					? 'bg-surface-2'
					: ''}"
				onclick={() => openHit(hit)}
				onmousemove={() => (active = index)}
			>
				{#if hit.kind === 'event'}
					<span class="flex min-w-0 items-center gap-2">
						<CalendarDays size={14} class="shrink-0 text-muted" aria-label={t('search.event')} />
						<span class="truncate">{hit.event.title}</span>
					</span>
					<span class="shrink-0 text-xs text-muted">
						{formatDay(hit.event.start_local.slice(0, 10), today, i18n.locale, dayLabels())}
						{#if !hit.event.all_day}{formatTime(hit.event.start_local.slice(11))}{/if}
					</span>
				{:else}
					<span class={hit.task.status === 'done' ? 'text-muted line-through' : ''}>
						{hit.task.title}
					</span>
					{#if hit.task.due_date}
						<span class="shrink-0 text-xs text-muted">
							{formatDay(hit.task.due_date, today, i18n.locale, dayLabels())}
						</span>
					{/if}
				{/if}
			</li>
		{/each}
	</ul>
	{#if searched && results.length === 0}
		<p class="py-6 text-center text-sm text-muted">{t('empty.search')}</p>
	{/if}
</Dialog>
