<script lang="ts">
	import { choice } from '$lib/stores/choice.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import Dialog from './Dialog.svelte';

	let open = $state(false);

	$effect(() => {
		open = choice.request !== null;
	});
</script>

<Dialog bind:open title={choice.request?.title ?? ''} onclose={() => choice.answer(null)}>
	{#if choice.request}
		<p class="mb-4 text-sm">{choice.request.message}</p>
		<div class="flex flex-col gap-2">
			{#each choice.request.options as option (option.value)}
				<button
					type="button"
					class="btn justify-start {option.primary ? 'btn-primary' : ''} {option.danger
						? 'btn-danger'
						: ''}"
					onclick={() => choice.answer(option.value)}
				>
					{option.label}
				</button>
			{/each}
			<button type="button" class="btn btn-ghost" onclick={() => choice.answer(null)}>
				{t('choice.cancel')}
			</button>
		</div>
	{/if}
</Dialog>
