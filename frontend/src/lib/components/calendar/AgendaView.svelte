<script lang="ts">
	import { Lock, MapPin, Repeat } from '@lucide/svelte';
	import { coversDay, minutesToTime, parseLocal } from '$lib/calendar';
	import { formatDay, formatLongDate } from '$lib/dates';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels } from '$lib/labels';
	import { areas } from '$lib/stores/areas.svelte';
	import type { Occurrence, Task } from '$lib/types';
	import TaskChip from './TaskChip.svelte';

	let {
		days,
		today,
		occurrences,
		tasks,
		loading,
		onopen
	}: {
		days: string[];
		today: string;
		occurrences: Occurrence[];
		tasks: Task[];
		loading: boolean;
		onopen: (occ: Occurrence) => void;
	} = $props();

	const groups = $derived(
		days
			.map((day) => ({
				day,
				events: occurrences.filter((occ) =>
					occ.all_day ? coversDay(occ, day) : parseLocal(occ.start_local).date === day
				),
				tasks: tasks.filter((task) => task.due_date === day)
			}))
			.filter((group) => group.events.length || group.tasks.length)
	);

	function timeLabel(occ: Occurrence): string {
		if (occ.all_day) return t('cal.allDay');
		const start = parseLocal(occ.start_local);
		const end = parseLocal(occ.end_local);
		return `${minutesToTime(start.minutes)}–${minutesToTime(end.minutes)}`;
	}
</script>

{#if groups.length === 0}
	<p class="py-12 text-center text-sm text-muted">{loading ? t('app.loading') : t('cal.empty')}</p>
{/if}
<div class="flex flex-col gap-5">
	{#each groups as group (group.day)}
		<section aria-label={formatLongDate(group.day, i18n.locale)}>
			<h2 class="mb-1 flex items-baseline gap-2 px-2 text-sm font-semibold">
				{formatDay(group.day, today, i18n.locale, dayLabels())}
				<span class="text-xs font-normal text-muted">{formatLongDate(group.day, i18n.locale)}</span>
			</h2>
			<ul class="flex flex-col">
				{#each group.events as occ (occ.key)}
					<li>
						<button
							type="button"
							class="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left hover:bg-surface-2"
							onclick={() => onopen(occ)}
						>
							<span
								class="mt-1.5 size-2.5 shrink-0 rounded-full"
								style:background-color={areas.byId(occ.area_id)?.color ?? '#6b7280'}
							></span>
							<span class="w-24 shrink-0 pt-px text-xs text-muted tabular-nums"
								>{timeLabel(occ)}</span
							>
							<span class="min-w-0 flex-1">
								<span
									class="block {occ.status === 'cancelled'
										? 'text-muted line-through'
										: ''} {occ.status === 'tentative' ? 'italic' : ''}">{occ.title}</span
								>
								<span class="flex flex-wrap items-center gap-x-3 text-xs text-muted">
									{#if occ.location}
										<span class="inline-flex items-center gap-1">
											<MapPin size={11} aria-hidden="true" />{occ.location}
										</span>
									{/if}
									{#if occ.recurring}<Repeat size={11} aria-label={t('task.recurrence')} />{/if}
									{#if occ.is_fixed}<Lock size={11} aria-label={t('event.fixed')} />{/if}
								</span>
							</span>
						</button>
					</li>
				{/each}
				{#each group.tasks as task (task.id)}
					<li class="px-1"><TaskChip {task} /></li>
				{/each}
			</ul>
		</section>
	{/each}
</div>
