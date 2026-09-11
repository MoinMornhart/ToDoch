<script lang="ts">
	import { CalendarPlus, MapPin, Plus } from '@lucide/svelte';
	import { goto } from '$app/navigation';
	import DashboardCard from '$lib/components/DashboardCard.svelte';
	import TaskRow from '$lib/components/TaskRow.svelte';
	import { minutesToTime, parseLocal } from '$lib/calendar';
	import { addDays, formatDay, formatLongDate, todayIn } from '$lib/dates';
	import { calendarQuery, targetOf } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { dayLabels } from '$lib/labels';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import { taskQuery } from '$lib/tasks.svelte';
	import type { Occurrence } from '$lib/types';

	const timezone = $derived(session.user?.timezone ?? 'UTC');
	const today = $derived(todayIn(timezone));

	const todayTasks = taskQuery(() => ({ view: 'today' }));
	const upcoming = taskQuery(() => ({ view: 'upcoming' }));
	const done = taskQuery(() => ({ view: 'done', limit: '200' }));
	const week = calendarQuery(() => ({ from: today, to: addDays(today, 7) }));

	const overdue = $derived(
		todayTasks.tasks.filter((task) => task.due_date !== null && task.due_date < today)
	);
	const dueToday = $derived(
		todayTasks.tasks.filter((task) => !(task.due_date !== null && task.due_date < today))
	);
	const nextEvents = $derived(
		week.occurrences.filter((occ) => Date.parse(occ.end) > Date.now()).slice(0, 6)
	);
	const eventsToday = $derived(
		week.occurrences.filter((occ) =>
			occ.all_day
				? occ.start_local <= today && today < occ.end_local
				: occ.start_local.startsWith(today)
		)
	);
	const doneThisWeek = $derived(
		done.tasks.filter(
			(task) => task.completed_at && Date.parse(task.completed_at) > Date.now() - 7 * 86_400_000
		).length
	);
	const showArea = $derived(areas.selected === 'all' && areas.list.length > 1);

	const greeting = $derived.by(() => {
		const hour = Number(
			new Intl.DateTimeFormat('en-GB', {
				timeZone: timezone,
				hour: '2-digit',
				hourCycle: 'h23'
			}).format(new Date())
		);
		if (hour < 11) return t('dash.morning');
		if (hour < 18) return t('dash.day');
		return t('dash.evening');
	});

	const stats = $derived([
		{ label: t('dash.dueToday'), value: dueToday.length, href: '/today', danger: false },
		{ label: t('dash.overdue'), value: overdue.length, href: '/today', danger: overdue.length > 0 },
		{
			label: t('dash.eventsToday'),
			value: eventsToday.length,
			href: `/calendar?view=day&date=${today}`,
			danger: false
		},
		{ label: t('dash.doneWeek'), value: doneThisWeek, href: '/done', danger: false }
	]);

	function eventWhen(occ: Occurrence): string {
		const start = parseLocal(occ.start_local);
		const day = formatDay(start.date, today, i18n.locale, dayLabels());
		return occ.all_day ? `${day} · ${t('cal.allDay')}` : `${day} · ${minutesToTime(start.minutes)}`;
	}

	function openEvent(occ: Occurrence) {
		const target = targetOf(occ);
		ui.eventEditor = { mode: 'edit', eventId: target.id, occurrence: target.occurrence ?? null };
	}

	function openArea(id: string) {
		areas.select(id);
		void goto('/open');
	}
</script>

<svelte:head><title>{t('nav.dashboard')} · Todoch</title></svelte:head>

<header class="mb-6">
	<p class="text-sm text-muted">{formatLongDate(today, i18n.locale)}</p>
	<h1 tabindex="-1" class="text-2xl font-semibold tracking-tight focus:outline-none">
		{greeting}, {session.user?.display_name}
	</h1>
	<p class="mt-1 text-sm text-muted">
		{t('dash.summary', { tasks: dueToday.length, events: eventsToday.length })}
	</p>
	<div class="mt-4 flex flex-wrap gap-2">
		<button type="button" class="btn btn-primary" onclick={() => (ui.newTask = {})}>
			<Plus size={16} aria-hidden="true" />{t('new.task')}
		</button>
		<button
			type="button"
			class="btn"
			onclick={() => (ui.eventEditor = { mode: 'new', date: today })}
		>
			<CalendarPlus size={16} aria-hidden="true" />{t('new.event')}
		</button>
	</div>
</header>

<ul class="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4" aria-label={t('nav.dashboard')}>
	{#each stats as stat (stat.label)}
		<li>
			<a
				href={stat.href}
				class="block rounded-xl border border-line bg-raised px-4 py-3 hover:bg-surface-2"
			>
				<span class="block text-2xl font-semibold tabular-nums {stat.danger ? 'text-danger' : ''}">
					{stat.value}
				</span>
				<span class="text-xs text-muted">{stat.label}</span>
			</a>
		</li>
	{/each}
</ul>

<div class="grid items-start gap-4 lg:grid-cols-2">
	{#if overdue.length}
		<DashboardCard title={t('dash.overdue')} count={overdue.length} href="/today" tone="danger">
			<ul class="flex flex-col">
				{#each overdue.slice(0, 5) as task (task.id)}<TaskRow {task} {today} {showArea} />{/each}
			</ul>
		</DashboardCard>
	{/if}

	<DashboardCard title={t('dash.today')} count={dueToday.length} href="/today">
		{#if dueToday.length}
			<ul class="flex flex-col">
				{#each dueToday.slice(0, 6) as task (task.id)}<TaskRow {task} {today} {showArea} />{/each}
			</ul>
		{:else}
			<p class="py-3 text-sm text-muted">{t('dash.nothingToday')}</p>
		{/if}
	</DashboardCard>

	<DashboardCard title={t('dash.events')} count={nextEvents.length} href="/calendar">
		{#if nextEvents.length}
			<ul class="flex flex-col">
				{#each nextEvents as occ (occ.key)}
					<li>
						<button
							type="button"
							class="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left hover:bg-surface-2"
							onclick={() => openEvent(occ)}
						>
							<span
								class="mt-1.5 size-2.5 shrink-0 rounded-full"
								style:background-color={areas.byId(occ.area_id)?.color ?? '#6b7280'}
							></span>
							<span class="min-w-0 flex-1">
								<span class="block truncate">{occ.title}</span>
								<span class="flex flex-wrap gap-x-3 text-xs text-muted">
									{eventWhen(occ)}
									{#if occ.location}
										<span class="inline-flex items-center gap-1">
											<MapPin size={11} aria-hidden="true" />{occ.location}
										</span>
									{/if}
								</span>
							</span>
						</button>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="py-3 text-sm text-muted">{t('dash.noEvents')}</p>
		{/if}
	</DashboardCard>

	<DashboardCard title={t('dash.upcoming')} count={upcoming.tasks.length} href="/upcoming">
		{#if upcoming.tasks.length}
			<ul class="flex flex-col">
				{#each upcoming.tasks.slice(0, 6) as task (task.id)}<TaskRow
						{task}
						{today}
						{showArea}
					/>{/each}
			</ul>
		{:else}
			<p class="py-3 text-sm text-muted">{t('dash.noUpcoming')}</p>
		{/if}
	</DashboardCard>

	<DashboardCard title={t('dash.areas')} href="/areas">
		<ul class="flex flex-col">
			{#each areas.list as area (area.id)}
				<li>
					<button
						type="button"
						class="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm hover:bg-surface-2"
						onclick={() => openArea(area.id)}
					>
						<span class="size-2.5 shrink-0 rounded-full" style:background-color={area.color}></span>
						<span class="flex-1">{area.name}</span>
						<span class="text-xs text-muted">{t('areas.open', { count: area.open_count })}</span>
					</button>
				</li>
			{/each}
		</ul>
	</DashboardCard>
</div>
