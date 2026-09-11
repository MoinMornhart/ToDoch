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
	const hours = Array.from({ length: 24 }, (_, h) => h);
	let scroller: HTMLDivElement | undefined = $state();
	let dropTarget = $state<string | null>(null);

	onMount(() => {
		if (scroller) scroller.scrollTop = 7 * HOUR - 8;
	});

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
		return (event.clientY - rect.top) / PX;
	}

	function colorOf(occ: Occurrence): string {
		return areas.byId(occ.area_id)?.color ?? '#6b7280';
	}
</script>

<div class="overflow-hidden rounded-xl border border-line bg-raised text-sm">
	<!-- Kopfzeile und ganztägige Termine -->
	<div
		class="grid border-b border-line"
		style:grid-template-columns={`3.5rem repeat(${days.length}, minmax(0, 1fr))`}
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
				class="flex min-h-8 flex-col gap-0.5 border-l border-t border-line p-0.5 {dropTarget ===
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

	<!-- Zeitraster -->
	<div bind:this={scroller} class="max-h-[calc(100dvh-15rem)] overflow-y-auto">
		<div
			class="relative grid"
			style:grid-template-columns={`3.5rem repeat(${days.length}, minmax(0, 1fr))`}
			style:height={`${24 * HOUR}px`}
		>
			<div class="relative">
				{#each hours as hour (hour)}
					<span
						class="absolute right-2 -translate-y-1/2 text-[10px] text-muted tabular-nums"
						style:top={`${hour * HOUR}px`}
					>
						{hour === 0 ? '' : `${String(hour).padStart(2, '0')}:00`}
					</span>
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
							oncreate(column.day, snap(minutesAt(event, event.currentTarget), 30));
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
						onmove(occ, { date: column.day, minutes: Math.max(0, Math.min(1425, minutes)) });
					}}
				>
					{#if column.day === today}
						<div
							class="pointer-events-none absolute inset-x-0 z-10 border-t-2 border-danger"
							style:top={`${nowMinutes * PX}px`}
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
							style:top={`${placed.start * PX}px`}
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
