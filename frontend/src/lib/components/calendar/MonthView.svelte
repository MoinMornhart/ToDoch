<script lang="ts">
	import { Plus } from '@lucide/svelte';
	import { coversDay } from '$lib/calendar';
	import { formatLongDate } from '$lib/dates';
	import { dragging } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import type { Occurrence, Task } from '$lib/types';
	import EventChip from './EventChip.svelte';
	import TaskChip from './TaskChip.svelte';

	let {
		days,
		month,
		today,
		occurrences,
		tasks,
		onopen,
		oncreate,
		onday,
		onmove
	}: {
		days: string[];
		month: string;
		today: string;
		occurrences: Occurrence[];
		tasks: Task[];
		onopen: (occ: Occurrence) => void;
		oncreate: (date: string) => void;
		onday: (date: string) => void;
		onmove: (occ: Occurrence, date: string) => void;
	} = $props();

	const MAX_ITEMS = 3;
	let dropDay = $state<string | null>(null);

	const weekdays = $derived(
		days
			.slice(0, 7)
			.map((day) =>
				new Intl.DateTimeFormat(i18n.locale, { weekday: 'short', timeZone: 'UTC' }).format(
					new Date(`${day}T00:00:00Z`)
				)
			)
	);

	function itemsFor(day: string) {
		const events = occurrences.filter((occ) => coversDay(occ, day));
		const dayTasks = tasks.filter((task) => task.due_date === day);
		return { events, tasks: dayTasks, total: events.length + dayTasks.length };
	}

	function drop(day: string) {
		dropDay = null;
		const occ = dragging.occ;
		dragging.occ = null;
		if (occ) onmove(occ, day);
	}
</script>

<div class="grid grid-cols-7 overflow-hidden rounded-xl border border-line bg-raised text-sm">
	{#each weekdays as name (name)}
		<div class="border-b border-line px-2 py-1.5 text-xs font-medium text-muted">{name}</div>
	{/each}
	{#each days as day, index (day)}
		{@const items = itemsFor(day)}
		{@const outside = day.slice(0, 7) !== month.slice(0, 7)}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="group min-h-24 border-line p-1 {index % 7 !== 6 ? 'border-r' : ''} {index < 35
				? 'border-b'
				: ''} {outside ? 'bg-surface-2/60' : ''} {dropDay === day ? 'bg-accent/10' : ''}"
			ondragover={(event) => {
				event.preventDefault();
				dropDay = day;
			}}
			ondragleave={() => (dropDay = dropDay === day ? null : dropDay)}
			ondrop={(event) => {
				event.preventDefault();
				drop(day);
			}}
		>
			<div class="flex items-center justify-between">
				<button
					type="button"
					class="grid size-6 place-items-center rounded-full text-xs {day === today
						? 'bg-accent font-semibold text-accent-fg'
						: outside
							? 'text-muted'
							: ''}"
					aria-label={formatLongDate(day, i18n.locale)}
					onclick={() => onday(day)}
				>
					{Number(day.slice(8))}
				</button>
				<button
					type="button"
					class="icon-btn size-6 opacity-0 group-hover:opacity-100 focus:opacity-100"
					aria-label={t('cal.newOn', { date: formatLongDate(day, i18n.locale) })}
					onclick={() => oncreate(day)}
				>
					<Plus size={14} aria-hidden="true" />
				</button>
			</div>
			<ul class="mt-0.5 flex flex-col gap-0.5">
				{#each items.events.slice(0, MAX_ITEMS) as occ (occ.key)}
					<li><EventChip {occ} {onopen} /></li>
				{/each}
				{#each items.tasks.slice(0, Math.max(0, MAX_ITEMS - items.events.length)) as task (task.id)}
					<li><TaskChip {task} /></li>
				{/each}
				{#if items.total > MAX_ITEMS}
					<li>
						<button
							type="button"
							class="px-1.5 text-xs text-muted hover:text-fg"
							onclick={() => onday(day)}
						>
							{t('cal.more', { count: items.total - MAX_ITEMS })}
						</button>
					</li>
				{/if}
			</ul>
		</div>
	{/each}
</div>
