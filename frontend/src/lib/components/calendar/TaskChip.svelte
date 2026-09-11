<script lang="ts">
	import { Check } from '@lucide/svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { Task } from '$lib/types';

	let { task }: { task: Task } = $props();
	const done = $derived(task.status === 'done');
</script>

<button
	type="button"
	class="flex w-full min-w-0 items-center gap-1 rounded px-1.5 py-0.5 text-left text-xs text-muted hover:bg-surface-2"
	onclick={() => (ui.editTaskId = task.id)}
	title={task.title}
>
	<span
		class="grid size-3 shrink-0 place-items-center rounded-sm border {done
			? 'border-muted bg-muted text-surface'
			: 'border-muted'}"
	>
		{#if done}<Check size={8} strokeWidth={3} aria-hidden="true" />{/if}
	</span>
	<span class="truncate {done ? 'line-through' : ''}">{task.title}</span>
</button>
