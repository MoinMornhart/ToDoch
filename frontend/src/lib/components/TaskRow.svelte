<script lang="ts">
	import { CalendarDays, Check, ListChecks, Repeat } from '@lucide/svelte';
	import { formatDay, formatTime } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels } from '$lib/labels';
	import { areas } from '$lib/stores/areas.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import { toggleTask } from '$lib/tasks.svelte';
	import type { Task } from '$lib/types';

	let { task, today, showArea }: { task: Task; today: string; showArea: boolean } = $props();

	const area = $derived(areas.byId(task.area_id));
	const done = $derived(task.status === 'done');
	const overdue = $derived(!done && task.due_date !== null && task.due_date < today);
	const checked = $derived(task.checklist.filter((item) => item.done).length);
	const ring = $derived(
		done
			? 'border-muted bg-muted text-surface'
			: ['border-muted', 'border-accent', 'border-warn', 'border-danger'][task.priority]
	);
	const hasMeta = $derived(
		Boolean(
			task.due_date || task.recurrence || task.tags.length || task.checklist.length || showArea
		)
	);
</script>

<li
	class="flex items-start gap-3 rounded-lg px-2 py-2 focus-within:bg-surface-2 hover:bg-surface-2"
>
	<button
		type="button"
		role="checkbox"
		aria-checked={done}
		aria-label="{done ? t('task.reopen') : t('task.complete')}: {task.title}"
		onclick={() => toggleTask(task)}
		class="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border-2 {ring}"
	>
		{#if done}<Check size={12} strokeWidth={3} aria-hidden="true" />{/if}
	</button>
	<button
		type="button"
		data-task-button
		class="min-w-0 flex-1 text-left"
		onclick={() => (ui.editTaskId = task.id)}
	>
		<span class="block leading-snug break-words {done ? 'text-muted line-through' : ''}">
			{task.title}
		</span>
		{#if hasMeta}
			<span class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted">
				{#if task.due_date}
					<span class="inline-flex items-center gap-1 {overdue ? 'font-medium text-danger' : ''}">
						<CalendarDays size={12} aria-hidden="true" />
						{formatDay(task.due_date, today, i18n.locale, dayLabels())}
						{#if task.due_time}{formatTime(task.due_time)}{/if}
						{#if overdue}<span class="sr-only">({t('task.overdue')})</span>{/if}
					</span>
				{/if}
				{#if task.recurrence}
					<Repeat size={12} aria-label={t('task.recurrence')} />
				{/if}
				{#if task.checklist.length}
					<span class="inline-flex items-center gap-1">
						<ListChecks size={12} aria-hidden="true" />{checked}/{task.checklist.length}
					</span>
				{/if}
				{#each task.tags as tag (tag)}<span>#{tag}</span>{/each}
				{#if showArea && area}
					<span class="inline-flex items-center gap-1">
						<span class="size-2 rounded-full" style:background-color={area.color}></span>
						{area.name}
					</span>
				{/if}
			</span>
		{/if}
	</button>
</li>
