<script lang="ts">
	import { MapPin } from '@lucide/svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import QuickAdd from '$lib/components/QuickAdd.svelte';
	import TaskList from '$lib/components/TaskList.svelte';
	import { minutesToTime, parseLocal } from '$lib/calendar';
	import { addDays, formatLongDate, todayIn } from '$lib/dates';
	import { calendarQuery, targetOf } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import { taskQuery } from '$lib/tasks.svelte';
	import type { Occurrence, TaskSection } from '$lib/types';

	const query = taskQuery(() => ({ view: 'today' }));
	const today = $derived(todayIn(session.user?.timezone ?? 'UTC'));
	const calendar = calendarQuery(() => ({ from: today, to: addDays(today, 1) }));

	const sections = $derived.by((): TaskSection[] => {
		const overdue = query.tasks.filter((task) => task.due_date !== null && task.due_date < today);
		const due = query.tasks.filter((task) => !(task.due_date !== null && task.due_date < today));
		return [
			{ key: 'overdue', title: t('date.overdue'), tasks: overdue },
			{ key: 'today', title: overdue.length ? t('date.today') : undefined, tasks: due }
		];
	});

	function timeLabel(occ: Occurrence): string {
		if (occ.all_day) return t('cal.allDay');
		const start = parseLocal(occ.start_local);
		const end = parseLocal(occ.end_local);
		const startText = start.date < today ? '' : minutesToTime(start.minutes);
		const endText = end.date > today ? '' : minutesToTime(end.minutes);
		return `${startText}–${endText}`;
	}

	function open(occ: Occurrence) {
		const target = targetOf(occ);
		ui.eventEditor = { mode: 'edit', eventId: target.id, occurrence: target.occurrence ?? null };
	}
</script>

<PageHeader title={t('nav.today')} subtitle={formatLongDate(today, i18n.locale)} />
<QuickAdd />

{#if calendar.occurrences.length}
	<section class="mt-4 mb-2" aria-label={t('cal.todayEvents')}>
		<h2 class="mb-1 flex items-baseline gap-2 px-2 text-sm font-semibold">
			<a href="/calendar?view=day&date={today}" class="hover:underline">{t('cal.todayEvents')}</a>
			<span class="text-xs font-normal text-muted">{calendar.occurrences.length}</span>
		</h2>
		<ul class="flex flex-col">
			{#each calendar.occurrences as occ (occ.key)}
				<li>
					<button
						type="button"
						class="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-surface-2"
						onclick={() => open(occ)}
					>
						<span
							class="size-2.5 shrink-0 rounded-full"
							style:background-color={areas.byId(occ.area_id)?.color ?? '#6b7280'}
						></span>
						<span class="w-24 shrink-0 text-xs text-muted tabular-nums">{timeLabel(occ)}</span>
						<span
							class="min-w-0 flex-1 truncate {occ.status === 'cancelled'
								? 'text-muted line-through'
								: ''}"
						>
							{occ.title}
						</span>
						{#if occ.location}
							<span class="hidden items-center gap-1 text-xs text-muted sm:inline-flex">
								<MapPin size={11} aria-hidden="true" />{occ.location}
							</span>
						{/if}
					</button>
				</li>
			{/each}
		</ul>
	</section>
{/if}

<TaskList
	{sections}
	{today}
	emptyText={t('empty.today')}
	loading={query.loading}
	error={query.error}
/>
