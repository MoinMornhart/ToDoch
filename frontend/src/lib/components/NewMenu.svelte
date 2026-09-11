<script lang="ts">
	import { CalendarPlus, ListTodo, Phone, Plus } from '@lucide/svelte';
	import { todayIn } from '$lib/dates';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { ui } from '$lib/stores/ui.svelte';

	let { variant = 'sidebar' }: { variant?: 'sidebar' | 'fab' } = $props();

	const uid = $props.id();
	let open = $state(false);
	let root: HTMLDivElement | undefined = $state();

	function choose(kind: 'task' | 'event' | 'phone') {
		open = false;
		if (kind === 'task') ui.newTask = {};
		else if (kind === 'phone') ui.phoneForm = {};
		else ui.eventEditor = { mode: 'new', date: todayIn(session.user?.timezone ?? 'UTC') };
	}

	function onWindowClick(event: MouseEvent) {
		if (open && root && !root.contains(event.target as Node)) open = false;
	}

	function onWindowKey(event: KeyboardEvent) {
		if (open && event.key === 'Escape') open = false;
	}
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

<div bind:this={root} class="relative">
	{#if variant === 'fab'}
		<button
			type="button"
			class="grid size-14 place-items-center rounded-full bg-accent text-accent-fg shadow-lg"
			aria-label={t('new.label')}
			aria-haspopup="menu"
			aria-expanded={open}
			aria-controls="{uid}-menu"
			onclick={() => (open = !open)}
		>
			<Plus size={24} aria-hidden="true" />
		</button>
	{:else}
		<button
			type="button"
			class="btn btn-primary w-full justify-start"
			aria-haspopup="menu"
			aria-expanded={open}
			aria-controls="{uid}-menu"
			onclick={() => (open = !open)}
		>
			<Plus size={16} aria-hidden="true" />{t('new.label')}
		</button>
	{/if}
	{#if open}
		<div
			id="{uid}-menu"
			role="menu"
			class="absolute z-40 w-60 rounded-lg border border-line bg-raised p-1 shadow-lg {variant ===
			'fab'
				? 'right-0 bottom-full mb-2'
				: 'top-full left-0 mt-1'}"
		>
			<button
				type="button"
				role="menuitem"
				class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-surface-2"
				onclick={() => choose('task')}
			>
				<ListTodo size={16} aria-hidden="true" />{t('new.task')}
				<span class="ml-auto text-xs text-muted">{t('new.taskHint')}</span>
			</button>
			<button
				type="button"
				role="menuitem"
				class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-surface-2"
				onclick={() => choose('event')}
			>
				<CalendarPlus size={16} aria-hidden="true" />{t('new.event')}
				<span class="ml-auto text-xs text-muted"><kbd>c</kbd></span>
			</button>
			<button
				type="button"
				role="menuitem"
				class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-surface-2"
				onclick={() => choose('phone')}
			>
				<Phone size={16} aria-hidden="true" />{t('new.phone')}
				<span class="ml-auto text-xs text-muted"><kbd>t</kbd></span>
			</button>
		</div>
	{/if}
</div>
