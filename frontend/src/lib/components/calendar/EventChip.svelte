<script lang="ts">
	import { Lock, Repeat } from '@lucide/svelte';
	import { parseLocal, minutesToTime } from '$lib/calendar';
	import { dragging } from '$lib/events.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import type { Occurrence } from '$lib/types';

	let {
		occ,
		onopen,
		showTime = true
	}: { occ: Occurrence; onopen: (occ: Occurrence) => void; showTime?: boolean } = $props();

	const color = $derived(areas.byId(occ.area_id)?.color ?? '#6b7280');
	const time = $derived(occ.all_day ? '' : minutesToTime(parseLocal(occ.start_local).minutes));
</script>

<button
	type="button"
	draggable="true"
	ondragstart={(event) => {
		dragging.occ = occ;
		dragging.grabMinutes = 0;
		event.dataTransfer?.setData('text/plain', occ.key);
	}}
	ondragend={() => (dragging.occ = null)}
	onclick={() => onopen(occ)}
	class="flex w-full min-w-0 items-center gap-1 rounded px-1.5 py-0.5 text-left text-xs hover:brightness-95 {occ.status ===
	'cancelled'
		? 'line-through opacity-60'
		: ''} {occ.status === 'tentative' ? 'italic' : ''}"
	style:background-color={occ.all_day ? `color-mix(in srgb, ${color} 18%, transparent)` : undefined}
	title={occ.title}
>
	{#if !occ.all_day}
		<span class="size-1.5 shrink-0 rounded-full" style:background-color={color}></span>
		{#if showTime}<span class="shrink-0 text-muted tabular-nums">{time}</span>{/if}
	{/if}
	<span class="truncate">{occ.title}</span>
	{#if occ.is_fixed}<Lock size={10} class="shrink-0" aria-label={t('event.fixed')} />{/if}
	{#if occ.recurring}<Repeat size={10} class="shrink-0 text-muted" aria-hidden="true" />{/if}
</button>
