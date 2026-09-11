<script lang="ts">
	import { X } from '@lucide/svelte';
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n/index.svelte';

	let {
		open = $bindable(false),
		title,
		onclose,
		children,
		size = 'md'
	}: {
		open?: boolean;
		title: string;
		onclose?: () => void;
		children: Snippet;
		size?: 'md' | 'lg';
	} = $props();

	const uid = $props.id();
	let dialog: HTMLDialogElement | undefined = $state();

	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) dialog.showModal();
		else if (!open && dialog.open) dialog.close();
	});

	function handleClose() {
		open = false;
		onclose?.();
	}

	function handleBackdrop(event: MouseEvent) {
		if (event.target === dialog) dialog?.close();
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog
	bind:this={dialog}
	aria-labelledby="{uid}-title"
	onclose={handleClose}
	onclick={handleBackdrop}
	class="m-auto max-h-[calc(100dvh-2rem)] rounded-xl border border-line bg-raised p-0 text-fg shadow-2xl {size ===
	'lg'
		? 'w-[min(44rem,calc(100vw-1.5rem))]'
		: 'w-[min(30rem,calc(100vw-1.5rem))]'}"
>
	<div class="flex max-h-[calc(100dvh-2rem)] flex-col">
		<div class="flex items-center justify-between gap-4 border-b border-line px-5 py-3">
			<h2 id="{uid}-title" class="text-base font-semibold">{title}</h2>
			<button
				type="button"
				class="icon-btn -mr-2"
				aria-label={t('help.close')}
				onclick={() => dialog?.close()}
			>
				<X size={18} aria-hidden="true" />
			</button>
		</div>
		<div class="overflow-y-auto px-5 py-4">
			{@render children()}
		</div>
	</div>
</dialog>
