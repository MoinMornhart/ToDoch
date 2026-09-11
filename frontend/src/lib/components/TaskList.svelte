<script lang="ts">
	import { tick } from 'svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { plainKey } from '$lib/keyboard';
	import { areas } from '$lib/stores/areas.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import { toggleTask } from '$lib/tasks.svelte';
	import type { TaskSection } from '$lib/types';
	import TaskRow from './TaskRow.svelte';

	let {
		sections,
		today,
		emptyText,
		loading,
		error
	}: {
		sections: TaskSection[];
		today: string;
		emptyText: string;
		loading: boolean;
		error: string | null;
	} = $props();

	let container: HTMLElement | undefined = $state();
	let pendingFocus: number | null = null;

	const flat = $derived(sections.flatMap((section) => section.tasks));
	const showArea = $derived(areas.selected === 'all' && areas.list.length > 1);

	function buttons(): HTMLElement[] {
		return container ? [...container.querySelectorAll<HTMLElement>('[data-task-button]')] : [];
	}

	function focusIndex(index: number) {
		const list = buttons();
		if (list.length === 0) return;
		list[Math.max(0, Math.min(index, list.length - 1))]?.focus();
	}

	// Nach dem Neuladen (z. B. nach dem Abhaken) den Fokus an derselben Stelle halten.
	$effect(() => {
		void flat;
		if (pendingFocus === null) return;
		const index = pendingFocus;
		pendingFocus = null;
		void tick().then(() => focusIndex(index));
	});

	function onKeydown(event: KeyboardEvent) {
		if (ui.dialogOpen) return;
		const key = plainKey(event);
		if (!key) return;
		const list = buttons();
		const index = list.indexOf(document.activeElement as HTMLElement);
		const inList = index >= 0;

		if (key === 'j' || (key === 'ArrowDown' && inList)) {
			event.preventDefault();
			focusIndex(inList ? index + 1 : 0);
		} else if (key === 'k' || (key === 'ArrowUp' && inList)) {
			event.preventDefault();
			focusIndex(inList ? index - 1 : list.length - 1);
		} else if (key === 'x' && inList) {
			const task = flat[index];
			if (task) {
				event.preventDefault();
				pendingFocus = index;
				void toggleTask(task);
			}
		} else if (key === 'e' && inList) {
			const task = flat[index];
			if (task) {
				event.preventDefault();
				ui.editTaskId = task.id;
			}
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div bind:this={container}>
	{#if error}
		<p class="my-4 text-sm text-danger" role="alert">{error}</p>
	{/if}
	{#if flat.length === 0 && !error}
		<p class="py-12 text-center text-sm text-muted">{loading ? t('app.loading') : emptyText}</p>
	{/if}
	{#each sections as section (section.key)}
		{#if section.tasks.length}
			<section class="mb-2" aria-label={section.title}>
				{#if section.title}
					<h2 class="mt-5 mb-1 flex items-baseline gap-2 px-2 text-sm font-semibold">
						{#if section.href}
							<a href={section.href} class="hover:underline">{section.title}</a>
						{:else}
							<span>{section.title}</span>
						{/if}
						<span class="text-xs font-normal text-muted">{section.tasks.length}</span>
					</h2>
				{/if}
				<ul class="flex flex-col">
					{#each section.tasks as task (task.id)}
						<TaskRow {task} {today} {showArea} />
					{/each}
				</ul>
			</section>
		{/if}
	{/each}
</div>
