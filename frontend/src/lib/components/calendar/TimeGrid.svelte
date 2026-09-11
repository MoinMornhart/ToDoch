<script lang="ts">
	import { onMount } from 'svelte';
	import { coversDay, layoutDay, minutesToTime, segmentFor, snap } from '$lib/calendar';
	import { formatLongDate } from '$lib/dates';
	import { dragging } from '$lib/events.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import type { Occurrence, Task } from '$lib/types';
	import EventChip from './EventChip.svelte';
	import TaskChip from './TaskChip.svelte';

	let {
		days,
		today,
		nowMinutes,
		startHour = 0,
		endHour = 24,
		occurrences,
		tasks,
		onopen,
		oncreate,
		onday,
		onmove
	}: {
		days: string[];
		today: string;
		nowMinutes: number;
		startHour?: number;
		endHour?: number;
		occurrences: Occurrence[];
		tasks: Task[];
		onopen: (occ: Occurrence) => void;
		oncreate: (date: string, minutes: number | null) => void;
		onday: (date: string) => void;
		onmove: (
			occ: Occurrence,
			target: { date: string; minutes: number | null; allDay?: boolean }
		) => void;
	} = $props();

	const HOUR = 48;
	const PX = HOUR / 60;
	let scroller: HTMLDivElement | undefined = $state();
	let dropTarget = $state<string | null>(null);

	const columns = $derived(
		days.map((day) => ({
			day,
			allDay: occurrences.filter((occ) => occ.all_day && coversDay(occ, day)),
			tasks: tasks.filter((task) => task.due_date === day),
			placed: layoutDay(
				occurrences.map((occ) => segmentFor(occ, day)).filter((segment) => segment !== null),
				30
			)
		}))
	);

	// Sichtbarer Zeitraum: Einstellung des Bereichs, bei Bedarf erweitert, damit kein Termin fehlt.
	const bounds = $derived.by(() => {
		let start = startHour * 60;
		let end = endHour * 60;
		for (const column of columns) {
			for (const placed of column.placed) {
				start = Math.min(start, placed.start);
				end = Math.max(end, placed.end);
			}
		}
		return { start: Math.floor(start / 60) * 60, end: Math.min(1440, Math.ceil(end / 60) * 60) };
	});
	const hours = $derived(
		Array.from({ length: (bounds.end - bounds.start) / 60 }, (_, i) => bounds.start / 60 + i)
	);
	const template = $derived(`3.5rem repeat(${days.length}, minmax(0, 1fr))`);

	onMount(() => {
		if (scroller && bounds.start === 0 && bounds.end === 1440) scroller.scrollTop = 7 * HOUR;
	});

	function header(day: string) {
		const date = new Date(`${day}T00:00:00Z`);
		return {
			weekday: new Intl.DateTimeFormat(i18n.locale, { weekday: 'short', timeZone: 'UTC' }).format(
				date
			),
			number: date.getUTCDate()
		};
	}

	function minutesAt(event: MouseEvent, element: HTMLElement): number {
		const rect = element.getBoundingClientRect();
		return bounds.start + (event.clientY - rect.top) / PX;
	}

	function clamp(minutes: number): number {
		return Math.max(bounds.start, Math.min(bounds.end - 15, minutes));
	}

	function colorOf(occ: Occurrence): string {
		return areas.byId(occ.area_id)?.color ?? '#6b7280';
	}
</script>

<!-- Kopf und Raster liegen im selben Scrollbereich – so sind die Spalten immer gleich breit. -->
<div class="overflow-hidden rounded-xl border border-line bg-raised text-sm">
	<div bind:this={scroller} class="max-h-[calc(100dvh-13rem)] overflow-y-auto">
		<div
			class="sticky top-0 z-20 grid border-b border-line bg-raised"
			style:grid-template-columns={template}
		>
			<div></div>
			{#each days as day (day)}
				{@const h = header(day)}
				<button
					type="button"
					class="flex items-baseline justify-center gap-1.5 border-l border-line py-1.5 text-xs {day ===
					today
						? 'font-semibold text-accent'
						: 'text-muted'}"
					aria-label={formatLongDate(day, i18n.locale)}
					onclick={() => onday(day)}
				>
					{h.weekday}
					<span class="text-base {day === today ? '' : 'text-fg'}">{h.number}</span>
				</button>
			{/each}
			<div class="self-center px-1 text-right text-[10px] text-muted">{t('cal.allDay')}</div>
			{#each columns as column (column.day)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="flex min-h-8 flex-col gap-0.5 border-t border-l border-line p-0.5 {dropTarget ===
					`all:${column.day}`
						? 'bg-accent/10'
						: ''}"
					ondragover={(event) => {
						event.preventDefault();
						dropTarget = `all:${column.day}`;
					}}
					ondrop={(event) => {
						event.preventDefault();
						dropTarget = null;
						const occ = dragging.occ;
						dragging.occ = null;
						if (occ) onmove(occ, { date: column.day, minutes: null, allDay: true });
					}}
				>
					{#each column.allDay as occ (occ.key)}<EventChip {occ} {onopen} />{/each}
					{#each column.tasks as task (task.id)}<TaskChip {task} />{/each}
				</div>
			{/each}
		</div>

		<div
			class="relative grid"
			style:grid-template-columns={template}
			style:height={`${hours.length * HOUR}px`}
		>
			<div class="relative">
				{#each hours as hour, index (hour)}
					{#if index > 0}
						<span
							class="absolute right-2 -translate-y-1/2 text-[10px] text-muted tabular-nums"
							style:top={`${index * HOUR}px`}
						>
							{String(hour).padStart(2, '0')}:00
						</span>
					{/if}
				{/each}
			</div>
			{#each columns as column (column.day)}
				<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
				<div
					class="hour-lines relative border-l border-line {dropTarget === column.day
						? 'bg-accent/5'
						: ''}"
					onclick={(event) => {
						if (event.target === event.currentTarget)
							oncreate(column.day, clamp(snap(minutesAt(event, event.currentTarget), 30)));
					}}
					ondragover={(event) => {
						event.preventDefault();
						dropTarget = column.day;
					}}
					ondragleave={() => (dropTarget = dropTarget === column.day ? null : dropTarget)}
					ondrop={(event) => {
						event.preventDefault();
						dropTarget = null;
						const occ = dragging.occ;
						dragging.occ = null;
						if (!occ) return;
						const minutes = snap(minutesAt(event, event.currentTarget) - dragging.grabMinutes, 15);
						onmove(occ, { date: column.day, minutes: clamp(minutes) });
					}}
				>
					{#if column.day === today && nowMinutes >= bounds.start && nowMinutes < bounds.end}
						<div
							class="pointer-events-none absolute inset-x-0 z-10 border-t-2 border-danger"
							style:top={`${(nowMinutes - bounds.start) * PX}px`}
						></div>
					{/if}
					{#each column.placed as placed (placed.item.key)}
						{@const occ = placed.item}
						{@const color = colorOf(occ)}
						<button
							type="button"
							draggable="true"
							ondragstart={(event) => {
								dragging.occ = occ;
								dragging.grabMinutes = event.offsetY / PX;
								event.dataTransfer?.setData('text/plain', occ.key);
							}}
							ondragend={() => (dragging.occ = null)}
							onclick={() => onopen(occ)}
							class="absolute overflow-hidden rounded-md border-l-[3px] px-1.5 py-0.5 text-left text-xs leading-tight hover:brightness-95 {occ.status ===
							'cancelled'
								? 'line-through opacity-60'
								: ''} {occ.status === 'tentative' ? 'italic' : ''}"
							style:top={`${(placed.start - bounds.start) * PX}px`}
							style:height={`${Math.max((placed.end - placed.start) * PX, 18)}px`}
							style:left={`calc(${(placed.column / placed.columns) * 100}% + 2px)`}
							style:width={`calc(${100 / placed.columns}% - 4px)`}
							style:border-color={color}
							style:background-color={`color-mix(in srgb, ${color} 16%, var(--raised))`}
						>
							<span class="block truncate font-medium">{occ.title}</span>
							<span class="block truncate text-muted tabular-nums">
								{minutesToTime(placed.start)}–{placed.end >= 1440
									? '24:00'
									: minutesToTime(placed.end)}
								{#if occ.location}· {occ.location}{/if}
							</span>
						</button>
					{/each}
				</div>
			{/each}
		</div>
	</div>
</div>
