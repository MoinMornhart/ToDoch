<script lang="ts">
	import { toasts } from '$lib/stores/toasts.svelte';
</script>

<div
	class="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6"
	role="status"
	aria-live="polite"
>
	{#each toasts.items as toast (toast.id)}
		<div
			class="pointer-events-auto flex items-center gap-4 rounded-lg px-4 py-2.5 text-sm shadow-lg {toast.kind ===
			'error'
				? 'bg-danger text-surface'
				: 'bg-fg text-surface'}"
		>
			<span>{toast.message}</span>
			{#if toast.action}
				<button
					type="button"
					class="font-semibold underline underline-offset-2"
					onclick={() => {
						void toast.action?.run();
						toasts.dismiss(toast.id);
					}}
				>
					{toast.action.label}
				</button>
			{/if}
		</div>
	{/each}
</div>
