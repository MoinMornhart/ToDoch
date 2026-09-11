<script lang="ts">
	import { CalendarPlus, ChevronLeft, ChevronRight } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AgendaView from '$lib/components/calendar/AgendaView.svelte';
	import MonthView from '$lib/components/calendar/MonthView.svelte';
	import TimeGrid from '$lib/components/calendar/TimeGrid.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import {
		filterDays,
		shapeFor,
		isoWeek,
		minutesToTime,
		rangeFor,
		shift,
		visibleDays,
		VIEWS,
		type CalendarView
	} from '$lib/calendar';
	import { formatLongDate, isValidIsoDate, todayIn } from '$lib/dates';
	import { calendarQuery, moveOccurrence, targetOf } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { plainKey } from '$lib/keyboard';
	import { session } from '$lib/stores/session.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { Occurrence } from '$lib/types';

	const KEY_VIEWS: Record<string, CalendarView> = { m: 'month', w: 'week', d: 'day', a: 'agenda' };

	const timezone = $derived(session.user?.timezone ?? 'UTC');
	const today = $derived(todayIn(timezone));
	let fallbackView = $state<CalendarView>('week');
	let nowMinutes = $state(0);

	const view = $derived.by((): CalendarView => {
		const requested = page.url.searchParams.get('view') ?? '';
		return (VIEWS as string[]).includes(requested) ? (requested as CalendarView) : fallbackView;
	});
	const date = $derived.by(() => {
		const requested = page.url.searchParams.get('date') ?? '';
		return isValidIsoDate(requested) ? requested : today;
	});
	// Kalenderform des gewählten Bereichs (z. B. Arbeit: Mo–Fr, 8–18 Uhr)
	const shape = $derived(shapeFor(areas.current ? [areas.current] : areas.list));
	const days = $derived(
		view === 'week' || view === 'month'
			? filterDays(visibleDays(view, date), shape.weekdays)
			: visibleDays(view, date)
	);
	const data = calendarQuery(() => rangeFor(view, date));

	function format(day: string, options: Intl.DateTimeFormatOptions): string {
		return new Intl.DateTimeFormat(i18n.locale, { ...options, timeZone: 'UTC' }).format(
			new Date(`${day}T00:00:00Z`)
		);
	}

	const title = $derived.by(() => {
		if (view === 'month') return format(date, { month: 'long', year: 'numeric' });
		if (view === 'day') return formatLongDate(date, i18n.locale);
		if (view === 'agenda')
			return t('cal.agendaFrom', { date: format(date, { day: 'numeric', month: 'long' }) });
		const first = days[0] ?? date;
		const last = days[days.length - 1] ?? date;
		return `${format(first, { day: 'numeric', month: 'short' })} – ${format(last, {
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		})}`;
	});
	const subtitle = $derived(view === 'week' ? t('cal.weekNumber', { week: isoWeek(date) }) : '');

	function updateNow() {
		const parts = new Intl.DateTimeFormat('en-GB', {
			timeZone: timezone,
			hour: '2-digit',
			minute: '2-digit',
			hourCycle: 'h23'
		}).formatToParts(new Date());
		const value = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
		nowMinutes = value('hour') * 60 + value('minute');
	}

	onMount(() => {
		if (matchMedia('(max-width: 640px)').matches) fallbackView = 'agenda';
		updateNow();
		const timer = setInterval(updateNow, 60_000);
		return () => clearInterval(timer);
	});

	function go(nextView: CalendarView, nextDate: string) {
		void goto(`/calendar?view=${nextView}&date=${nextDate}`, { keepFocus: true, noScroll: true });
	}

	function openOccurrence(occ: Occurrence) {
		const target = targetOf(occ);
		ui.eventEditor = { mode: 'edit', eventId: target.id, occurrence: target.occurrence ?? null };
	}

	function create(day: string, minutes: number | null = null) {
		ui.eventEditor = {
			mode: 'new',
			date: day,
			time: minutes === null ? undefined : minutesToTime(minutes)
		};
	}

	function onKeydown(event: KeyboardEvent) {
		if (ui.dialogOpen) return;
		const key = plainKey(event);
		if (!key) return;
		if (key === 'ArrowLeft' || key === 'ArrowRight') {
			event.preventDefault();
			go(view, shift(view, date, key === 'ArrowLeft' ? -1 : 1));
		} else if (KEY_VIEWS[key]) {
			event.preventDefault();
			go(KEY_VIEWS[key], date);
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />
<svelte:head><title>{t('nav.calendar')} · Todoch</title></svelte:head>

<header class="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2">
	<div class="mr-auto">
		<h1 class="text-2xl font-semibold tracking-tight">{title}</h1>
		{#if subtitle}<p class="text-sm text-muted">{subtitle}</p>{/if}
	</div>
	<div class="flex items-center gap-1">
		<button type="button" class="btn py-1.5" onclick={() => go(view, today)}
			>{t('cal.today')}</button
		>
		<button
			type="button"
			class="icon-btn"
			aria-label={t('cal.prev')}
			onclick={() => go(view, shift(view, date, -1))}
		>
			<ChevronLeft size={18} aria-hidden="true" />
		</button>
		<button
			type="button"
			class="icon-btn"
			aria-label={t('cal.next')}
			onclick={() => go(view, shift(view, date, 1))}
		>
			<ChevronRight size={18} aria-hidden="true" />
		</button>
	</div>
	<div
		role="group"
		aria-label={t('cal.view')}
		class="flex rounded-lg border border-line bg-raised p-0.5"
	>
		{#each VIEWS as option (option)}
			<button
				type="button"
				aria-pressed={view === option}
				class="rounded-md px-2.5 py-1 text-sm {view === option
					? 'bg-surface-2 font-medium'
					: 'text-muted hover:text-fg'}"
				onclick={() => go(option, date)}
			>
				{t(`cal.${option}`)}
			</button>
		{/each}
	</div>
	<button type="button" class="btn btn-primary py-1.5" onclick={() => create(date)}>
		<CalendarPlus size={16} aria-hidden="true" />{t('cal.newEvent')}
	</button>
</header>

{#if data.error}<p class="mb-3 text-sm text-danger" role="alert">{data.error}</p>{/if}

{#if view === 'month'}
	<MonthView
		{days}
		columns={shape.weekdays.length}
		month={date}
		{today}
		occurrences={data.occurrences}
		tasks={data.tasks}
		onopen={openOccurrence}
		oncreate={(day) => create(day)}
		onday={(day) => go('day', day)}
		onmove={(occ, day) => moveOccurrence(occ, { date: day, minutes: null })}
	/>
{:else if view === 'agenda'}
	<AgendaView
		{days}
		{today}
		occurrences={data.occurrences}
		tasks={data.tasks}
		loading={data.loading}
		onopen={openOccurrence}
	/>
{:else}
	<TimeGrid
		{days}
		{today}
		{nowMinutes}
		startHour={shape.startHour}
		endHour={shape.endHour}
		occurrences={data.occurrences}
		tasks={data.tasks}
		onopen={openOccurrence}
		oncreate={create}
		onday={(day) => go('day', day)}
		onmove={moveOccurrence}
	/>
{/if}
